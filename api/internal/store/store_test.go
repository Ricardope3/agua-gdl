package store

import (
	"context"
	"errors"
	"fmt"
	"os"
	"sync/atomic"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var schemaSequence atomic.Int64

func testDB(t *testing.T) *DB {
	t.Helper()
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("set TEST_DATABASE_URL to run PostgreSQL integration tests")
	}
	ctx := context.Background()
	admin, err := pgx.Connect(ctx, url)
	if err != nil {
		t.Fatal(err)
	}
	schema := fmt.Sprintf("test_%d_%d", time.Now().UnixNano(), schemaSequence.Add(1))
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
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		t.Fatal(err)
	}
	cfg.ConnConfig.RuntimeParams["search_path"] = schema
	cfg.ConnConfig.RuntimeParams["statement_timeout"] = "5000"
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	db := &DB{pool: pool, q: pool}
	t.Cleanup(db.Close)
	if err := db.Migrate(ctx); err != nil {
		t.Fatal(err)
	}
	return db
}

func testSubscriber(t *testing.T, db *DB) Subscriber {
	t.Helper()
	ctx := context.Background()
	if err := db.Subscribe(ctx, "MX.test", "521111", 4); err != nil {
		t.Fatal(err)
	}
	s, ok, err := db.Subscriber(ctx, "MX.test")
	if err != nil || !ok {
		t.Fatalf("subscriber: %+v %v", s, err)
	}
	return s
}

func TestInboundRollbackAndConcurrentDeduplication(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	failure := errors.New("abort command")
	err := db.ProcessInbound(ctx, "message", func(tx BotStore) error {
		if err := tx.Subscribe(ctx, "MX.test", "521111", 4); err != nil {
			return err
		}
		return failure
	})
	if !errors.Is(err, failure) {
		t.Fatal(err)
	}
	if _, ok, err := db.Subscriber(ctx, "MX.test"); err != nil || ok {
		t.Fatalf("rolled-back subscription exists: %v", err)
	}
	var calls atomic.Int32
	done := make(chan error, 2)
	for range 2 {
		go func() {
			done <- db.ProcessInbound(ctx, "message", func(tx BotStore) error {
				calls.Add(1)
				return tx.Subscribe(ctx, "MX.test", "521111", 4)
			})
		}()
	}
	for range 2 {
		if err := <-done; err != nil {
			t.Fatal(err)
		}
	}
	if calls.Load() != 1 {
		t.Fatalf("processed command %d times", calls.Load())
	}
	if _, err := db.Unsubscribe(ctx, "MX.test"); err != nil {
		t.Fatal(err)
	}
	if err := db.ProcessInbound(ctx, "message", func(tx BotStore) error {
		t.Error("duplicate command ran after BAJA")
		return tx.Subscribe(ctx, "MX.test", "521111", 4)
	}); err != nil {
		t.Fatal(err)
	}
}

func TestAcceptedReminderIsNotResentAfterRecordingFails(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx, date := context.Background(), time.Date(2026, 10, 19, 0, 0, 0, 0, time.UTC)
	_, err := db.pool.Exec(ctx, `create function reject_recording() returns trigger language plpgsql as $$
		begin raise exception 'simulated database failure after send'; end $$;
		create trigger reject_recording before update on reminder for each row execute function reject_recording()`)
	if err != nil {
		t.Fatal(err)
	}
	calls := 0
	send := func(Subscriber) (string, error) { calls++; return "accepted-wamid", nil }
	if attempted, err := db.SendReminder(ctx, s, date, send); !attempted || err == nil {
		t.Fatalf("expected accepted send followed by recording failure: %v %v", attempted, err)
	}
	if _, err := db.pool.Exec(ctx, `drop trigger reject_recording on reminder`); err != nil {
		t.Fatal(err)
	}
	if attempted, err := db.SendReminder(ctx, s, date, send); attempted || err != nil {
		t.Fatalf("retry: %v %v", attempted, err)
	}
	if calls != 1 {
		t.Fatalf("sent %d times", calls)
	}
	if n, err := db.UnresolvedReminders(ctx, date); err != nil || n != 1 {
		t.Fatalf("unresolved=%d %v", n, err)
	}
}

func TestQueuedReminderRechecksSubscriber(t *testing.T) {
	for _, change := range []string{"unsubscribe", "zone"} {
		t.Run(change, func(t *testing.T) {
			db := testDB(t)
			s := testSubscriber(t, db)
			ctx, date := context.Background(), time.Now()
			if change == "unsubscribe" {
				if _, err := db.Unsubscribe(ctx, s.UserID); err != nil {
					t.Fatal(err)
				}
			} else if err := db.Subscribe(ctx, s.UserID, "521111", 6); err != nil {
				t.Fatal(err)
			}
			attempted, err := db.SendReminder(ctx, s, date, func(Subscriber) (string, error) { t.Error("stale reminder sent"); return "id", nil })
			if err != nil || attempted {
				t.Fatalf("stale candidate: %v %v", attempted, err)
			}
		})
	}
}

func TestReminderSerializesWithUnsubscribeAndOtherSenders(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx, date := context.Background(), time.Now()
	entered, release := make(chan struct{}), make(chan struct{})
	defer func() {
		select {
		case <-release:
		default:
			close(release)
		}
	}()
	sent := make(chan error, 1)
	go func() {
		_, err := db.SendReminder(ctx, s, date, func(Subscriber) (string, error) { close(entered); <-release; return "accepted", nil })
		sent <- err
	}()
	select {
	case <-entered:
	case err := <-sent:
		t.Fatalf("send never started: %v", err)
	case <-time.After(3 * time.Second):
		t.Fatal("send timed out")
	}
	if attempted, err := db.SendReminder(ctx, s, date, func(Subscriber) (string, error) { t.Error("concurrent duplicate"); return "duplicate", nil }); attempted || err != nil {
		t.Fatalf("duplicate: %v %v", attempted, err)
	}
	conn, err := db.pool.Acquire(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Release()
	pid := conn.Conn().PgConn().PID()
	unsubscribed := make(chan error, 1)
	go func() { _, err := (&DB{q: conn}).Unsubscribe(ctx, s.UserID); unsubscribed <- err }()
	blocked := false
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if err := db.pool.QueryRow(ctx, `select cardinality(pg_blocking_pids($1)) > 0`, pid).Scan(&blocked); err != nil {
			t.Fatal(err)
		}
		if blocked {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	close(release)
	if err := <-sent; err != nil {
		t.Fatal(err)
	}
	if err := <-unsubscribed; err != nil {
		t.Fatal(err)
	}
	if !blocked {
		t.Fatal("BAJA did not serialize with the in-flight send")
	}
	if attempted, err := db.SendReminder(ctx, s, date, func(Subscriber) (string, error) { t.Error("send after BAJA"); return "late", nil }); attempted || err != nil {
		t.Fatalf("after BAJA: %v %v", attempted, err)
	}
}

func TestSendErrorPersistsUncertainty(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx, date := context.Background(), time.Now()
	failure := errors.New("HTTP response lost")
	if attempted, err := db.SendReminder(ctx, s, date, func(Subscriber) (string, error) { return "", failure }); !attempted || !errors.Is(err, failure) {
		t.Fatalf("send: %v %v", attempted, err)
	}
	if n, err := db.UnresolvedReminders(ctx, date); err != nil || n != 1 {
		t.Fatalf("unresolved=%d %v", n, err)
	}
	if n, err := db.SentSince(ctx, date.Add(-time.Hour)); err != nil || n != 1 {
		t.Fatalf("uncertain attempt must count against cap: %d %v", n, err)
	}
}
