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

	"aguagdl/api/internal/wa"
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
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, send); !attempted || err == nil {
		t.Fatalf("expected accepted send followed by recording failure: %v %v", attempted, err)
	}
	if _, err := db.pool.Exec(ctx, `drop trigger reject_recording on reminder`); err != nil {
		t.Fatal(err)
	}
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, send); attempted || err != nil {
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
			attempted, err := db.SendReminder(ctx, s, date, []int{4}, func(Subscriber) (string, error) { t.Error("stale reminder sent"); return "id", nil })
			if err != nil || attempted {
				t.Fatalf("stale candidate: %v %v", attempted, err)
			}
		})
	}
}

func TestZoneChangeBetweenZonesCutTheSameDay(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx, date := context.Background(), time.Now()
	// Listed for zone 4, then moved to zone 6 before the send; both are cut tomorrow.
	if err := db.Subscribe(ctx, s.UserID, "521111", 6); err != nil {
		t.Fatal(err)
	}
	var got Subscriber
	attempted, err := db.SendReminder(ctx, s, date, []int{4, 6}, func(current Subscriber) (string, error) { got = current; return "wamid.z6", nil })
	if err != nil || !attempted || got.Zone != 6 {
		t.Fatalf("the reminder must go out for the new zone: %v %v %+v", attempted, err, got)
	}
	var zone int
	if err := db.pool.QueryRow(ctx, `select zone from reminder where subscriber_id = $1`, s.ID).Scan(&zone); err != nil || zone != 6 {
		t.Fatalf("recorded zone %d %v", zone, err)
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
		_, err := db.SendReminder(ctx, s, date, []int{4}, func(Subscriber) (string, error) { close(entered); <-release; return "accepted", nil })
		sent <- err
	}()
	select {
	case <-entered:
	case err := <-sent:
		t.Fatalf("send never started: %v", err)
	case <-time.After(3 * time.Second):
		t.Fatal("send timed out")
	}
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, func(Subscriber) (string, error) { t.Error("concurrent duplicate"); return "duplicate", nil }); attempted || err != nil {
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
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, func(Subscriber) (string, error) { t.Error("send after BAJA"); return "late", nil }); attempted || err != nil {
		t.Fatalf("after BAJA: %v %v", attempted, err)
	}
}

func TestSendErrorPersistsUncertainty(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx, date := context.Background(), time.Now()
	failure := errors.New("HTTP response lost")
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, func(Subscriber) (string, error) { return "", failure }); !attempted || !errors.Is(err, failure) {
		t.Fatalf("send: %v %v", attempted, err)
	}
	if n, err := db.UnresolvedReminders(ctx, date); err != nil || n != 1 {
		t.Fatalf("unresolved=%d %v", n, err)
	}
	if n, err := db.SentSince(ctx, date.Add(-time.Hour)); err != nil || n != 1 {
		t.Fatalf("uncertain attempt must count against cap: %d %v", n, err)
	}
}

func TestRejectedReminderIsRetried(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx, date := context.Background(), time.Now()
	rejected := &wa.APIError{Status: 400, Code: 132015, Message: "Template is paused"}
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, func(Subscriber) (string, error) { return "", rejected }); !attempted || !errors.Is(err, rejected) {
		t.Fatalf("send: %v %v", attempted, err)
	}
	if n, err := db.UnresolvedReminders(ctx, date); err != nil || n != 1 {
		t.Fatalf("a rejection must fail the heartbeat: unresolved=%d %v", n, err)
	}
	if n, err := db.SentSince(ctx, date.Add(-time.Hour)); err != nil || n != 0 {
		t.Fatalf("a rejected message was never sent, so it must not count against the cap: %d %v", n, err)
	}
	if due, err := db.DueSubscribers(ctx, []int{4}, date); err != nil || len(due) != 1 {
		t.Fatalf("due=%v %v", due, err)
	}
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, func(Subscriber) (string, error) { return "wamid.ok", nil }); !attempted || err != nil {
		t.Fatalf("retry: %v %v", attempted, err)
	}
	if n, err := db.UnresolvedReminders(ctx, date); err != nil || n != 0 {
		t.Fatalf("unresolved=%d %v", n, err)
	}
	if n, err := db.SentSince(ctx, date.Add(-time.Hour)); err != nil || n != 1 {
		t.Fatalf("sent=%d %v", n, err)
	}
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, func(Subscriber) (string, error) { t.Error("resent after success"); return "", nil }); attempted || err != nil {
		t.Fatalf("after success: %v %v", attempted, err)
	}
}

func TestUpdateStatusReportsReminders(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx := context.Background()
	if _, err := db.SendReminder(ctx, s, time.Now(), []int{4}, func(Subscriber) (string, error) { return "wamid.ok", nil }); err != nil {
		t.Fatal(err)
	}
	for _, c := range []struct {
		wamid, status string
		want          bool
	}{{"wamid.ok", "failed", true}, {"wamid.ok", "failed", false}, {"wamid.reply", "failed", false}} {
		if got, err := db.UpdateStatus(ctx, c.wamid, c.status); err != nil || got != c.want {
			t.Errorf("UpdateStatus(%s, %s) = %v %v, want %v", c.wamid, c.status, got, err, c.want)
		}
	}
}

func TestStoresOnlyHashesOfMessageIDs(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx := context.Background()
	const reminderID, inboundID = "wamid.HBgLMTY1MDM4Nzk0MzkVAgARGBI", "wamid.HBgLMTY1MDM4Nzk0MzkVAgASGBQ"
	if _, err := db.SendReminder(ctx, s, time.Now(), []int{4}, func(Subscriber) (string, error) { return reminderID, nil }); err != nil {
		t.Fatal(err)
	}
	if err := db.ProcessInbound(ctx, inboundID, func(BotStore) error { return nil }); err != nil {
		t.Fatal(err)
	}
	var raw int
	if err := db.pool.QueryRow(ctx, `select (select count(*) from reminder where wamid_hash like 'wamid%') +
		(select count(*) from inbound_seen where wamid_hash like 'wamid%')`).Scan(&raw); err != nil || raw != 0 {
		t.Fatalf("message IDs embed the phone number and must not be stored: %d %v", raw, err)
	}
	if ok, err := db.UpdateStatus(ctx, reminderID, "delivered"); err != nil || !ok {
		t.Fatalf("status by message ID: %v %v", ok, err)
	}
}

func TestRecipientsSinceCountsPeopleNotMessages(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx, today := context.Background(), time.Now()
	ok := func(Subscriber) (string, error) { return "wamid." + fmt.Sprint(time.Now().UnixNano()), nil }
	for _, d := range []time.Time{today, today.AddDate(0, 0, 1)} {
		if attempted, err := db.SendReminder(ctx, s, d, []int{4}, ok); !attempted || err != nil {
			t.Fatalf("send: %v %v", attempted, err)
		}
	}
	since := today.Add(-time.Hour)
	if n, err := db.SentSince(ctx, since); err != nil || n != 2 {
		t.Fatalf("sent=%d %v", n, err)
	}
	if n, err := db.RecipientsSince(ctx, since); err != nil || n != 1 {
		t.Fatalf("Meta's limit counts one person once: recipients=%d %v", n, err)
	}
	if _, err := db.Unsubscribe(ctx, s.UserID); err != nil {
		t.Fatal(err)
	}
	if n, err := db.RecipientsSince(ctx, since); err != nil || n != 2 {
		t.Fatalf("after BAJA the rows can't be linked, so count each: %d %v", n, err)
	}
}

func TestChangeUserNeverKeepsTheOldNumber(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx := context.Background()
	if err := db.ChangeUser(ctx, s.UserID, "", "MX.new", ""); err != nil {
		t.Fatal(err)
	}
	var phone *string
	var zone int
	if err := db.pool.QueryRow(ctx, `select phone, zone from subscriber where wa_user_id = 'MX.new'`).Scan(&phone, &zone); err != nil || phone != nil || zone != 4 {
		t.Fatalf("phone=%v zone=%d %v", phone, zone, err)
	}
	if err := db.Subscribe(ctx, "MX.other", "522222", 2); err != nil {
		t.Fatal(err)
	}
	if err := db.ChangeUser(ctx, "MX.new", "", "MX.other", "522222"); err != nil {
		t.Fatal(err)
	}
	var n int
	if err := db.pool.QueryRow(ctx, `select count(*) from subscriber`).Scan(&n); err != nil || n != 1 {
		t.Fatalf("an existing subscription for the new ID wins: %d %v", n, err)
	}
}

func TestZoneCounts(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	for user, zone := range map[string]int{"MX.a": 4, "MX.b": 4, "MX.c": 6} {
		if err := db.Subscribe(ctx, user, "", zone); err != nil {
			t.Fatal(err)
		}
	}
	counts, err := db.ZoneCounts(ctx)
	if err != nil || len(counts) != 2 || counts[4] != 2 || counts[6] != 1 {
		t.Fatalf("%v %v", counts, err)
	}
}
