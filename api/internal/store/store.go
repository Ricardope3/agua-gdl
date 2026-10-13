// Package store keeps subscribers, sent reminders and cut reports in Postgres.
package store

import (
	"context"
	"embed"
	"errors"
	"fmt"
	"io/fs"
	"sort"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const dateLayout = "2006-01-02"

//go:embed migrations/*.sql
var migrations embed.FS

type Subscriber struct {
	ID     int64
	UserID string
	Zone   int
}

type Result struct {
	Zone      int    `json:"zone"`
	Date      string `json:"date"`
	Total     int    `json:"total"`
	Normal    int    `json:"normal"`
	Baja      int    `json:"baja"`
	NoRegreso int    `json:"no_regreso"`
	Turbia    int    `json:"turbia"`
}

type DB struct{ pool *pgxpool.Pool }

func Open(ctx context.Context, url string) (*DB, error) {
	pool, err := pgxpool.New(ctx, url)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return &DB{pool: pool}, nil
}

func (db *DB) Close() { db.pool.Close() }

func (db *DB) Migrate(ctx context.Context) error {
	if _, err := db.pool.Exec(ctx, `create table if not exists schema_migrations (
		version text primary key, applied_at timestamptz not null default now())`); err != nil {
		return err
	}
	names, err := fs.Glob(migrations, "migrations/*.sql")
	if err != nil {
		return err
	}
	sort.Strings(names)
	for _, name := range names {
		var done bool
		if err := db.pool.QueryRow(ctx, `select exists(select 1 from schema_migrations where version = $1)`, name).Scan(&done); err != nil {
			return err
		}
		if done {
			continue
		}
		sql, err := migrations.ReadFile(name)
		if err != nil {
			return err
		}
		err = pgx.BeginFunc(ctx, db.pool, func(tx pgx.Tx) error {
			if _, err := tx.Exec(ctx, string(sql)); err != nil {
				return err
			}
			_, err := tx.Exec(ctx, `insert into schema_migrations (version) values ($1)`, name)
			return err
		})
		if err != nil {
			return fmt.Errorf("migration %s: %w", name, err)
		}
	}
	return nil
}

func (db *DB) Seen(ctx context.Context, wamid string) (bool, error) {
	var seen bool
	err := db.pool.QueryRow(ctx, `select exists(select 1 from inbound_seen where wamid = $1)`, wamid).Scan(&seen)
	return seen, err
}

func (db *DB) MarkSeen(ctx context.Context, wamid string) error {
	_, err := db.pool.Exec(ctx, `insert into inbound_seen (wamid) values ($1) on conflict do nothing`, wamid)
	return err
}

func (db *DB) PurgeSeen(ctx context.Context, before time.Time) error {
	_, err := db.pool.Exec(ctx, `delete from inbound_seen where seen_at < $1`, before)
	return err
}

func (db *DB) Subscriber(ctx context.Context, userID string) (Subscriber, bool, error) {
	s := Subscriber{UserID: userID}
	err := db.pool.QueryRow(ctx, `select id, zone from subscriber where wa_user_id = $1`, userID).Scan(&s.ID, &s.Zone)
	if errors.Is(err, pgx.ErrNoRows) {
		return Subscriber{}, false, nil
	}
	return s, err == nil, err
}

func (db *DB) Subscribe(ctx context.Context, userID string, zone int) error {
	_, err := db.pool.Exec(ctx, `insert into subscriber (wa_user_id, zone) values ($1, $2)
		on conflict (wa_user_id) do update set zone = excluded.zone, updated_at = now()`, userID, zone)
	return err
}

func (db *DB) Unsubscribe(ctx context.Context, userID string) (bool, error) {
	tag, err := db.pool.Exec(ctx, `delete from subscriber where wa_user_id = $1`, userID)
	return tag.RowsAffected() > 0, err
}

func (db *DB) SaveReport(ctx context.Context, subscriberID int64, zone int, cutDate time.Time, answer string) error {
	_, err := db.pool.Exec(ctx, `insert into cut_report (subscriber_id, zone, cut_date, answer) values ($1, $2, $3::date, $4)
		on conflict (subscriber_id, cut_date) do update set answer = excluded.answer, created_at = now()`,
		subscriberID, zone, cutDate.Format(dateLayout), answer)
	return err
}

func (db *DB) UpdateStatus(ctx context.Context, wamid, status string) error {
	_, err := db.pool.Exec(ctx, `update reminder set status = $2 where wamid = $1
		and array_position(array['sent','delivered','read','failed'], status) < array_position(array['sent','delivered','read','failed'], $2)`, wamid, status)
	return err
}

// DueSubscribers lists subscribers in zones that haven't been reminded about cutDate yet.
func (db *DB) DueSubscribers(ctx context.Context, zones []int, cutDate time.Time) ([]Subscriber, error) {
	rows, err := db.pool.Query(ctx, `select s.id, s.wa_user_id, s.zone from subscriber s
		where s.zone = any($1::int[]) and not exists (
			select 1 from reminder r where r.subscriber_id = s.id and r.cut_date = $2::date)
		order by s.id`, zones, cutDate.Format(dateLayout))
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (Subscriber, error) {
		var s Subscriber
		err := r.Scan(&s.ID, &s.UserID, &s.Zone)
		return s, err
	})
}

func (db *DB) RecordReminder(ctx context.Context, s Subscriber, cutDate time.Time, wamid string) error {
	_, err := db.pool.Exec(ctx, `insert into reminder (subscriber_id, zone, cut_date, wamid) values ($1, $2, $3::date, $4)
		on conflict (subscriber_id, cut_date) do nothing`, s.ID, s.Zone, cutDate.Format(dateLayout), wamid)
	return err
}

func (db *DB) SentSince(ctx context.Context, since time.Time) (int, error) {
	var n int
	err := db.pool.QueryRow(ctx, `select count(*) from reminder where sent_at >= $1`, since).Scan(&n)
	return n, err
}

// Results counts reports per zone and cut day, hiding any day with fewer than minReports.
func (db *DB) Results(ctx context.Context, since time.Time, minReports int) ([]Result, error) {
	rows, err := db.pool.Query(ctx, `select zone, cut_date::text, count(*),
			count(*) filter (where answer = 'normal'), count(*) filter (where answer = 'baja'),
			count(*) filter (where answer = 'no_regreso'), count(*) filter (where answer = 'turbia')
		from cut_report where cut_date >= $1::date
		group by zone, cut_date having count(*) >= $2
		order by cut_date desc, zone`, since.Format(dateLayout), minReports)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (Result, error) {
		var x Result
		err := r.Scan(&x.Zone, &x.Date, &x.Total, &x.Normal, &x.Baja, &x.NoRegreso, &x.Turbia)
		return x, err
	})
}
