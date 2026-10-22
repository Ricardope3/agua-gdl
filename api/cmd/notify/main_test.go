package main

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"

	"aguagdl/api/data"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
)

func TestDryRunsDontMigrate(t *testing.T) {
	base := os.Getenv("TEST_DATABASE_URL")
	if base == "" {
		t.Skip("set TEST_DATABASE_URL to run PostgreSQL integration tests")
	}
	ctx := context.Background()
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal(err)
	}
	schema := fmt.Sprintf("test_notify_%d", time.Now().UnixNano())
	quoted := pgx.Identifier{schema}.Sanitize()
	if _, err := admin.Exec(ctx, "create schema "+quoted); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	t.Cleanup(func() {
		defer admin.Close(ctx)
		if _, err := admin.Exec(ctx, "drop schema "+quoted+" cascade"); err != nil {
			t.Error(err)
		}
	})
	u, err := url.Parse(base)
	if err != nil {
		t.Fatal(err)
	}
	q := u.Query()
	q.Set("search_path", schema)
	u.RawQuery = q.Encode()
	t.Setenv("DATABASE_URL", u.String())
	db, err := store.Open(ctx, u.String())
	if err != nil {
		t.Fatal(err)
	}
	err = db.Migrate(ctx)
	db.Close()
	if err != nil {
		t.Fatal(err)
	}
	// The checkout has a migration the database lacks, as before a deploy.
	var newest string
	if err := admin.QueryRow(ctx, `delete from `+quoted+`.schema_migrations
		where version = (select max(version) from `+quoted+`.schema_migrations) returning version`).Scan(&newest); err != nil {
		t.Fatal(err)
	}
	dry := map[string]func() error{
		"cambio_rotacion": func() error { return run(store.WhatsApp, 4, "2026-11-02", false) },
		"telegram":        func() error { return run(store.Telegram, 4, "2026-11-02", false) },
		"avisos":          func() error { return runAvisos(false) },
	}
	loc, _ := time.LoadLocation("America/Mexico_City")
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		t.Fatal(err)
	}
	// A Sunday inside the rotation, so -tomorrow always has a zone cut on Monday to try.
	at := time.Date(2026, 10, 18, 12, 0, 0, 0, loc)
	now = func() time.Time { return at }
	t.Cleanup(func() { now = time.Now })
	zones := sched.ZonesOn(at.AddDate(0, 0, 1))
	if len(zones) == 0 {
		t.Fatalf("no zone is cut on %s", at.AddDate(0, 0, 1).Format(rotation.DateLayout))
	}
	dry["tomorrow"] = func() error { return runTomorrow(zones[0], false) }
	for name, f := range dry {
		if err := f(); err != nil {
			t.Errorf("%s: %v", name, err)
		}
		var applied bool
		if err := admin.QueryRow(ctx, `select exists(select 1 from `+quoted+`.schema_migrations where version = $1)`, newest).Scan(&applied); err != nil || applied {
			t.Fatalf("%s: a dry run applied %s under the running server: %v", name, newest, err)
		}
	}
}
