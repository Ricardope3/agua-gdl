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

// emptyDB returns a store on a fresh, unmigrated schema.
func emptyDB(t *testing.T) *DB {
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
	return db
}

func testDB(t *testing.T) *DB {
	t.Helper()
	db := emptyDB(t)
	if err := db.Migrate(context.Background()); err != nil {
		t.Fatal(err)
	}
	return db
}

func TestConcurrentMigrations(t *testing.T) {
	db := emptyDB(t)
	errs := make(chan error, 3)
	for range 3 {
		go func() { errs <- db.Migrate(context.Background()) }()
	}
	for range 3 {
		if err := <-errs; err != nil {
			t.Fatalf("two machines starting at once must not fail: %v", err)
		}
	}
}

func testSubscriber(t *testing.T, db *DB) Subscriber {
	t.Helper()
	ctx := context.Background()
	if err := db.Subscribe(ctx, WhatsApp, "MX.test", "521111", 4); err != nil {
		t.Fatal(err)
	}
	s, ok, err := db.Subscriber(ctx, WhatsApp, "MX.test")
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
		if err := tx.Subscribe(ctx, WhatsApp, "MX.test", "521111", 4); err != nil {
			return err
		}
		return failure
	})
	if !errors.Is(err, failure) {
		t.Fatal(err)
	}
	if _, ok, err := db.Subscriber(ctx, WhatsApp, "MX.test"); err != nil || ok {
		t.Fatalf("rolled-back subscription exists: %v", err)
	}
	var calls atomic.Int32
	done := make(chan error, 2)
	for range 2 {
		go func() {
			done <- db.ProcessInbound(ctx, "message", func(tx BotStore) error {
				calls.Add(1)
				return tx.Subscribe(ctx, WhatsApp, "MX.test", "521111", 4)
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
	if _, err := db.Unsubscribe(ctx, WhatsApp, "MX.test", ""); err != nil {
		t.Fatal(err)
	}
	if err := db.ProcessInbound(ctx, "message", func(tx BotStore) error {
		t.Error("duplicate command ran after BAJA")
		return tx.Subscribe(ctx, WhatsApp, "MX.test", "521111", 4)
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
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, send); !attempted || err == nil {
		t.Fatalf("expected accepted send followed by recording failure: %v %v", attempted, err)
	}
	if _, err := db.pool.Exec(ctx, `drop trigger reject_recording on reminder`); err != nil {
		t.Fatal(err)
	}
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, send); attempted || err != nil {
		t.Fatalf("retry: %v %v", attempted, err)
	}
	if calls != 1 {
		t.Fatalf("sent %d times", calls)
	}
	if n, err := db.UnresolvedReminders(ctx, WhatsApp, date); err != nil || n != 1 {
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
				if _, err := db.Unsubscribe(ctx, WhatsApp, s.UserID, ""); err != nil {
					t.Fatal(err)
				}
			} else if err := db.Subscribe(ctx, WhatsApp, s.UserID, "521111", 6); err != nil {
				t.Fatal(err)
			}
			attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { t.Error("stale reminder sent"); return "id", nil })
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
	if err := db.Subscribe(ctx, WhatsApp, s.UserID, "521111", 6); err != nil {
		t.Fatal(err)
	}
	var got Subscriber
	attempted, err := db.SendReminder(ctx, s, date, []int{4, 6}, nil, func(current Subscriber) (string, error) { got = current; return "wamid.z6", nil })
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
		_, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { close(entered); <-release; return "accepted", nil })
		sent <- err
	}()
	select {
	case <-entered:
	case err := <-sent:
		t.Fatalf("send never started: %v", err)
	case <-time.After(3 * time.Second):
		t.Fatal("send timed out")
	}
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { t.Error("concurrent duplicate"); return "duplicate", nil }); attempted || err != nil {
		t.Fatalf("duplicate: %v %v", attempted, err)
	}
	conn, err := db.pool.Acquire(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Release()
	pid := conn.Conn().PgConn().PID()
	unsubscribed := make(chan error, 1)
	go func() { _, err := (&DB{q: conn}).Unsubscribe(ctx, WhatsApp, s.UserID, ""); unsubscribed <- err }()
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
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { t.Error("send after BAJA"); return "late", nil }); attempted || err != nil {
		t.Fatalf("after BAJA: %v %v", attempted, err)
	}
}

func TestSendErrorPersistsUncertainty(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx, date := context.Background(), time.Now()
	failure := errors.New("HTTP response lost")
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { return "", failure }); !attempted || !errors.Is(err, failure) {
		t.Fatalf("send: %v %v", attempted, err)
	}
	if n, err := db.UnresolvedReminders(ctx, WhatsApp, date); err != nil || n != 1 {
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
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { return "", rejected }); !attempted || !errors.Is(err, rejected) {
		t.Fatalf("send: %v %v", attempted, err)
	}
	if n, err := db.UnresolvedReminders(ctx, WhatsApp, date); err != nil || n != 1 {
		t.Fatalf("a rejection must fail the heartbeat: unresolved=%d %v", n, err)
	}
	if n, err := db.SentSince(ctx, date.Add(-time.Hour)); err != nil || n != 0 {
		t.Fatalf("a rejected message was never sent, so it must not count against the cap: %d %v", n, err)
	}
	if due, err := db.DueSubscribers(ctx, WhatsApp, []int{4}, date); err != nil || len(due) != 1 {
		t.Fatalf("due=%v %v", due, err)
	}
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { return "wamid.ok", nil }); !attempted || err != nil {
		t.Fatalf("retry: %v %v", attempted, err)
	}
	if n, err := db.UnresolvedReminders(ctx, WhatsApp, date); err != nil || n != 0 {
		t.Fatalf("unresolved=%d %v", n, err)
	}
	if n, err := db.SentSince(ctx, date.Add(-time.Hour)); err != nil || n != 1 {
		t.Fatalf("sent=%d %v", n, err)
	}
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { t.Error("resent after success"); return "", nil }); attempted || err != nil {
		t.Fatalf("after success: %v %v", attempted, err)
	}
}

func TestUpdateStatusReportsReminders(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx := context.Background()
	if _, err := db.SendReminder(ctx, s, time.Now(), []int{4}, nil, func(Subscriber) (string, error) { return "wamid.ok", nil }); err != nil {
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
	if _, err := db.SendReminder(ctx, s, time.Now(), []int{4}, nil, func(Subscriber) (string, error) { return reminderID, nil }); err != nil {
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
		if attempted, err := db.SendReminder(ctx, s, d, []int{4}, nil, ok); !attempted || err != nil {
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
	if _, err := db.Unsubscribe(ctx, WhatsApp, s.UserID, ""); err != nil {
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
	if err := db.pool.QueryRow(ctx, `select phone, zone from subscriber where user_id = 'MX.new'`).Scan(&phone, &zone); err != nil || phone != nil || zone != 4 {
		t.Fatalf("phone=%v zone=%d %v", phone, zone, err)
	}
	if err := db.Subscribe(ctx, WhatsApp, "MX.other", "522222", 2); err != nil {
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
		if err := db.Subscribe(ctx, WhatsApp, user, "", zone); err != nil {
			t.Fatal(err)
		}
	}
	counts, err := db.ZoneCounts(ctx)
	if err != nil || len(counts) != 2 || counts[4] != 2 || counts[6] != 1 {
		t.Fatalf("%v %v", counts, err)
	}
}

func TestNoticeIsSentOnceAndCountsTowardTheLimit(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx := context.Background()
	key := "cambio_rotacion/4/2026-11-02"
	if due, err := db.NoticeRecipients(ctx, WhatsApp, 4, key); err != nil || len(due) != 1 {
		t.Fatalf("due=%v %v", due, err)
	}
	if attempted, err := db.SendNotice(ctx, s, key, nil, func(Subscriber) (string, error) { return "wamid.n1", nil }); !attempted || err != nil {
		t.Fatalf("send: %v %v", attempted, err)
	}
	if attempted, err := db.SendNotice(ctx, s, key, nil, func(Subscriber) (string, error) { t.Error("resent"); return "", nil }); attempted || err != nil {
		t.Fatalf("resend: %v %v", attempted, err)
	}
	if due, err := db.NoticeRecipients(ctx, WhatsApp, 4, key); err != nil || len(due) != 0 {
		t.Fatalf("due after send=%v %v", due, err)
	}
	if _, err := db.SendReminder(ctx, s, time.Now(), []int{4}, nil, func(Subscriber) (string, error) { return "wamid.r1", nil }); err != nil {
		t.Fatal(err)
	}
	since := time.Now().Add(-time.Hour)
	if n, err := db.RecipientsSince(ctx, since); err != nil || n != 1 {
		t.Fatalf("one person got a notice and a reminder: recipients=%d %v", n, err)
	}
	if n, err := db.SentSince(ctx, since); err != nil || n != 2 {
		t.Fatalf("sent=%d %v", n, err)
	}
	if _, err := db.UpdateStatus(ctx, "wamid.n1", "delivered"); err != nil {
		t.Fatal(err)
	}
	var status string
	if err := db.pool.QueryRow(ctx, `select status from notice`).Scan(&status); err != nil || status != "delivered" {
		t.Fatalf("status=%s %v", status, err)
	}
}

func TestDeleteSubscribers(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx := context.Background()
	if _, err := db.SendReminder(ctx, s, time.Now(), []int{4}, nil, func(Subscriber) (string, error) { return "wamid.d", nil }); err != nil {
		t.Fatal(err)
	}
	if n, err := db.DeleteSubscribers(ctx); err != nil || n != 1 {
		t.Fatalf("deleted %d %v", n, err)
	}
	if n, err := db.SentSince(ctx, time.Now().Add(-time.Hour)); err != nil || n != 1 {
		t.Fatalf("reminders stay for the statistics: %d %v", n, err)
	}
}

func TestResultsHideSmallDaysAndTruncateLastReport(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	if _, err := db.pool.Exec(ctx, `insert into cut_report (zone, cut_date, answer, created_at) values
		(6, '2026-10-16', 'normal', '2026-10-17 09:47:12-06'), (6, '2026-10-16', 'baja', '2026-10-17 08:05:00-06'),
		(4, '2026-10-19', 'turbia', '2026-10-20 10:00:00-06')`); err != nil {
		t.Fatal(err)
	}
	got, err := db.Results(ctx, time.Date(2026, 10, 1, 0, 0, 0, 0, time.UTC), 2)
	want := Result{Zone: 6, Date: "2026-10-16", Total: 2, Normal: 1, Baja: 1, LastAt: "2026-10-17T09:00"}
	if err != nil || len(got) != 1 || got[0] != want {
		t.Errorf("Results = %+v %v, want [%+v]", got, err, want)
	}
}

func phoneHolders(t *testing.T, db *DB, phone string) []Subscriber {
	t.Helper()
	rows, err := db.pool.Query(context.Background(), `select id, user_id, coalesce(phone, ''), zone from subscriber where phone = $1`, phone)
	if err != nil {
		t.Fatal(err)
	}
	subs, err := pgx.CollectRows(rows, func(r pgx.CollectableRow) (Subscriber, error) {
		var s Subscriber
		err := r.Scan(&s.ID, &s.UserID, &s.Phone, &s.Zone)
		return s, err
	})
	if err != nil {
		t.Fatal(err)
	}
	return subs
}

func TestSecondIDClaimingAPhoneReplacesTheFirst(t *testing.T) {
	db := testDB(t)
	ctx, date := context.Background(), time.Now()
	for _, sub := range []struct {
		user string
		zone int
	}{{"MX.a", 4}, {"MX.b", 6}} {
		if err := db.Subscribe(ctx, WhatsApp, sub.user, "521111", sub.zone); err != nil {
			t.Fatal(err)
		}
	}
	if subs := phoneHolders(t, db, "521111"); len(subs) != 1 || subs[0].UserID != "MX.b" || subs[0].Zone != 6 {
		t.Fatalf("the number belongs to its latest subscriber only: %+v", subs)
	}
	due, err := db.DueSubscribers(ctx, WhatsApp, []int{4, 6}, date)
	if err != nil {
		t.Fatal(err)
	}
	sends := 0
	for _, s := range due {
		if _, err := db.SendReminder(ctx, s, date, []int{4, 6}, nil, func(Subscriber) (string, error) { sends++; return fmt.Sprint("wamid.", sends), nil }); err != nil {
			t.Fatal(err)
		}
	}
	if sends != 1 {
		t.Fatalf("tonight's batch sent %d reminders to one number", sends)
	}
}

func TestChangeUserIntoAPhoneAnotherRowHolds(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	if err := db.Subscribe(ctx, WhatsApp, "MX.a", "521111", 4); err != nil {
		t.Fatal(err)
	}
	if err := db.Subscribe(ctx, WhatsApp, "MX.b", "522222", 6); err != nil {
		t.Fatal(err)
	}
	if err := db.ChangeUser(ctx, "MX.a", "521111", "MX.c", "522222"); err != nil {
		t.Fatal(err)
	}
	var n int
	if err := db.pool.QueryRow(ctx, `select count(*) from subscriber`).Scan(&n); err != nil || n != 1 {
		t.Fatalf("rows=%d %v", n, err)
	}
	if subs := phoneHolders(t, db, "522222"); len(subs) != 1 || subs[0].UserID != "MX.c" || subs[0].Zone != 4 {
		t.Fatalf("the moved subscription must own the number: %+v", subs)
	}
}

func TestChangeUserMatchingTwoRows(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	if err := db.Subscribe(ctx, WhatsApp, "MX.a", "521111", 4); err != nil {
		t.Fatal(err)
	}
	if err := db.Subscribe(ctx, WhatsApp, "MX.b", "523333", 6); err != nil {
		t.Fatal(err)
	}
	// The old ID matches MX.a and the old phone matches MX.b.
	if err := db.ChangeUser(ctx, "MX.a", "523333", "MX.c", "524444"); err != nil {
		t.Fatalf("used to fail with a duplicate wa_user_id: %v", err)
	}
	var n int
	if err := db.pool.QueryRow(ctx, `select count(*) from subscriber`).Scan(&n); err != nil || n != 1 {
		t.Fatalf("rows=%d %v", n, err)
	}
	if subs := phoneHolders(t, db, "524444"); len(subs) != 1 || subs[0].UserID != "MX.c" || subs[0].Zone != 4 {
		t.Fatalf("the row with the old ID moves: %+v", subs)
	}
}

func TestChangeUserToAnUnsubscribedUserFreesTheNumber(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	if err := db.Subscribe(ctx, WhatsApp, "MX.b", "522222", 6); err != nil {
		t.Fatal(err)
	}
	if err := db.ChangeUser(ctx, "MX.x", "529999", "MX.y", "522222"); err != nil {
		t.Fatal(err)
	}
	if subs := phoneHolders(t, db, "522222"); len(subs) != 0 {
		t.Fatalf("the number now belongs to someone who never subscribed: %+v", subs)
	}
}

func TestPhoneMigrationKeepsTheNewestRow(t *testing.T) {
	db := emptyDB(t)
	ctx := context.Background()
	// A database deployed before 005, holding one number twice.
	if _, err := db.pool.Exec(ctx, `create table schema_migrations (
		version text primary key, applied_at timestamptz not null default now())`); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"001_init.sql", "002_phone.sql", "003_hash_wamids.sql", "004_notice.sql"} {
		sql, err := migrations.ReadFile("migrations/" + name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := db.pool.Exec(ctx, string(sql)); err != nil {
			t.Fatal(err)
		}
		if _, err := db.pool.Exec(ctx, `insert into schema_migrations (version) values ($1)`, "migrations/"+name); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := db.pool.Exec(ctx, `insert into subscriber (wa_user_id, phone, zone) values
		('MX.old', '521111', 4), ('MX.new', '521111', 6), ('MX.solo', '522222', 2), ('MX.none1', null, 3), ('MX.none2', null, 3)`); err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(ctx); err != nil {
		t.Fatal(err)
	}
	rows, err := db.pool.Query(ctx, `select user_id from subscriber order by id`)
	if err != nil {
		t.Fatal(err)
	}
	users, err := pgx.CollectRows(rows, pgx.RowTo[string])
	if err != nil || fmt.Sprint(users) != "[MX.new MX.solo MX.none1 MX.none2]" {
		t.Fatalf("users=%v %v", users, err)
	}
	var other int
	if err := db.pool.QueryRow(ctx, `select count(*) from subscriber where channel <> 'wa'`).Scan(&other); err != nil || other != 0 {
		t.Fatalf("existing subscribers must stay on WhatsApp: %d %v", other, err)
	}
	if _, err := db.pool.Exec(ctx, `insert into subscriber (user_id, phone, zone) values ('MX.dup', '522222', 1)`); err == nil {
		t.Fatal("a second row with the same phone must be refused")
	}
}

func TestBajaByPhoneRemovesEveryRowWithIt(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	if err := db.Subscribe(ctx, WhatsApp, "MX.a", "521111", 4); err != nil {
		t.Fatal(err)
	}
	if removed, err := db.Unsubscribe(ctx, WhatsApp, "MX.other", "521111"); err != nil || !removed {
		t.Fatalf("BAJA from the number must remove its subscription: %v %v", removed, err)
	}
	if err := db.Subscribe(ctx, WhatsApp, "MX.a", "521111", 4); err != nil {
		t.Fatal(err)
	}
	if removed, err := db.Unsubscribe(ctx, WhatsApp, "", "521111"); err != nil || !removed {
		t.Fatalf("BAJA without a WhatsApp ID works by phone: %v %v", removed, err)
	}
	if subs := phoneHolders(t, db, "521111"); len(subs) != 0 {
		t.Fatalf("rows left: %+v", subs)
	}
}

func TestDueSubscribersCarryTheLastChange(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx := context.Background()
	if _, err := db.pool.Exec(ctx, `update subscriber set updated_at = now() - interval '30 hours' where id = $1`, s.ID); err != nil {
		t.Fatal(err)
	}
	due, err := db.DueSubscribers(ctx, WhatsApp, []int{4}, time.Now())
	if err != nil || len(due) != 1 {
		t.Fatalf("due=%v %v", due, err)
	}
	if age := time.Since(due[0].UpdatedAt); age < 29*time.Hour || age > 31*time.Hour {
		t.Fatalf("updated_at is %v old, want about 30h", age)
	}
}

type blockedErr struct{}

func (blockedErr) Error() string  { return "tg: 403 Forbidden: bot was blocked by the user" }
func (blockedErr) Rejected() bool { return true }
func (blockedErr) Gone() bool     { return true }

func TestTelegramSubscribersAreSeparateAndUncapped(t *testing.T) {
	db := testDB(t)
	ctx, date := context.Background(), time.Now()
	if err := db.Subscribe(ctx, WhatsApp, "MX.a", "521111", 4); err != nil {
		t.Fatal(err)
	}
	// A Telegram chat ID equal to a WhatsApp user ID is a different person.
	for _, id := range []string{"MX.a", "777"} {
		if err := db.Subscribe(ctx, Telegram, id, "", 4); err != nil {
			t.Fatal(err)
		}
	}
	if s, ok, err := db.Subscriber(ctx, WhatsApp, "MX.a"); err != nil || !ok || s.Zone != 4 {
		t.Fatalf("whatsapp subscriber lost: %v %v %v", s, ok, err)
	}
	if counts, err := db.ZoneCounts(ctx); err != nil || counts[4] != 1 {
		t.Fatalf("ZoneCounts must count WhatsApp only: %v %v", counts, err)
	}
	tg, err := db.DueSubscribers(ctx, Telegram, []int{4}, date)
	if err != nil || len(tg) != 2 || tg[0].Channel != Telegram || tg[0].Phone != "" {
		t.Fatalf("telegram due=%+v %v", tg, err)
	}
	if wa, err := db.DueSubscribers(ctx, WhatsApp, []int{4}, date); err != nil || len(wa) != 1 || wa[0].Phone != "521111" {
		t.Fatalf("whatsapp due=%+v %v", wa, err)
	}
	for _, s := range tg {
		if _, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(current Subscriber) (string, error) {
			if current.Channel != Telegram {
				t.Errorf("sent on %q", current.Channel)
			}
			return "", nil
		}); err != nil {
			t.Fatal(err)
		}
	}
	if n, err := db.RecipientsSince(ctx, date.Add(-time.Hour)); err != nil || n != 0 {
		t.Fatalf("Telegram sends must not count against Meta's limit: %d %v", n, err)
	}
	if n, err := db.SentSince(ctx, date.Add(-time.Hour)); err != nil || n != 0 {
		t.Fatalf("Telegram sends must not count against the monthly cap: %d %v", n, err)
	}
	if removed, err := db.Unsubscribe(ctx, Telegram, "MX.a", ""); err != nil || !removed {
		t.Fatalf("unsubscribe: %v %v", removed, err)
	}
	if _, ok, _ := db.Subscriber(ctx, WhatsApp, "MX.a"); !ok {
		t.Fatal("a Telegram BAJA removed the WhatsApp subscription")
	}
}

func TestBlockedBotDeletesTheSubscriber(t *testing.T) {
	db := testDB(t)
	ctx, date := context.Background(), time.Now()
	if err := db.Subscribe(ctx, Telegram, "777", "", 4); err != nil {
		t.Fatal(err)
	}
	s, _, _ := db.Subscriber(ctx, Telegram, "777")
	if attempted, err := db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { return "", blockedErr{} }); !attempted || err == nil {
		t.Fatalf("send: %v %v", attempted, err)
	}
	if _, ok, err := db.Subscriber(ctx, Telegram, "777"); err != nil || ok {
		t.Fatalf("blocking the bot must delete the subscription: %v %v", ok, err)
	}
	if n, err := db.UnresolvedReminders(ctx, Telegram, date); err != nil || n != 0 {
		t.Fatalf("a blocked bot needs no review: unresolved=%d %v", n, err)
	}
	var status string
	if err := db.pool.QueryRow(ctx, `select status from reminder where channel = 'tg'`).Scan(&status); err != nil || status != "blocked" {
		t.Fatalf("status=%q %v", status, err)
	}
}

func TestUnresolvedRemindersArePerChannel(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx, date := context.Background(), time.Now()
	db.SendReminder(ctx, s, date, []int{4}, nil, func(Subscriber) (string, error) { return "", errors.New("lost") })
	if n, err := db.UnresolvedReminders(ctx, Telegram, date); err != nil || n != 0 {
		t.Fatalf("a WhatsApp failure must not fail the Telegram run: %d %v", n, err)
	}
}

func TestUpdatedReportTakesTheNewZone(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	s := testSubscriber(t, db)
	date := time.Date(2026, 10, 15, 0, 0, 0, 0, time.UTC)
	for _, zone := range []int{6, 4} {
		if err := db.SaveReport(ctx, s.ID, zone, date, "normal"); err != nil {
			t.Fatal(err)
		}
	}
	var zone int
	if err := db.pool.QueryRow(ctx, `select zone from cut_report where subscriber_id = $1`, s.ID).Scan(&zone); err != nil || zone != 4 {
		t.Fatalf("zone %d, err %v", zone, err)
	}
}

func TestChangeUserKeepsTheLastChange(t *testing.T) {
	db := testDB(t)
	s := testSubscriber(t, db)
	ctx := context.Background()
	if _, err := db.pool.Exec(ctx, `update subscriber set updated_at = now() - interval '30 hours' where id = $1`, s.ID); err != nil {
		t.Fatal(err)
	}
	if err := db.ChangeUser(ctx, s.UserID, "", "MX.new", "522222"); err != nil {
		t.Fatal(err)
	}
	due, err := db.DueSubscribers(ctx, WhatsApp, []int{4}, time.Now())
	if err != nil || len(due) != 1 || time.Since(due[0].UpdatedAt) < 29*time.Hour {
		t.Fatalf("a number change sends no confirmation, so the nightly run must still remind it: %+v %v", due, err)
	}
}

func TestAdmissionChecksWaitForEachOther(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	counted, release, first := make(chan struct{}), make(chan struct{}), make(chan error, 1)
	go func() {
		first <- db.ProcessInbound(ctx, "in.a", func(tx BotStore) error {
			if _, err := tx.ZoneCounts(ctx); err != nil {
				return err
			}
			close(counted)
			<-release
			return tx.Subscribe(ctx, WhatsApp, "MX.a", "", 4)
		})
	}()
	select {
	case <-counted:
	case err := <-first:
		t.Fatal(err)
	}
	time.AfterFunc(200*time.Millisecond, func() { close(release) })
	var counts map[int]int
	err := db.ProcessInbound(ctx, "in.b", func(tx BotStore) error {
		var err error
		counts, err = tx.ZoneCounts(ctx)
		return err
	})
	if err != nil || <-first != nil {
		t.Fatal(err)
	}
	if counts[4] != 1 {
		t.Fatalf("the second check must see the first subscription, or both take the last slot: %v", counts)
	}
}

func TestBudgetHoldsAcrossConcurrentSenders(t *testing.T) {
	db := testDB(t)
	ctx, date := context.Background(), time.Now()
	var subs []Subscriber
	for _, user := range []string{"MX.a", "MX.b"} {
		if err := db.Subscribe(ctx, WhatsApp, user, "", 4); err != nil {
			t.Fatal(err)
		}
		s, _, err := db.Subscriber(ctx, WhatsApp, user)
		if err != nil {
			t.Fatal(err)
		}
		subs = append(subs, s)
	}
	// Another sender holds the lock and takes the last slot of a daily cap of 1.
	other, err := db.pool.Begin(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer other.Rollback(ctx)
	if _, err := other.Exec(ctx, `select pg_advisory_xact_lock($1)`, budgetLock); err != nil {
		t.Fatal(err)
	}
	if _, err := other.Exec(ctx, `insert into reminder (subscriber_id, zone, cut_date, status, channel)
		values ($1, 4, $2::date, 'sending', 'wa')`, subs[0].ID, date.Format(dateLayout)); err != nil {
		t.Fatal(err)
	}
	budget := NewBudget(1, 100, time.Now())
	done := make(chan error, 1)
	go func() {
		_, err := db.SendReminder(ctx, subs[1], date, []int{4}, &budget, func(Subscriber) (string, error) {
			t.Error("sent over the daily cap")
			return "", nil
		})
		done <- err
	}()
	select {
	case err := <-done:
		t.Fatalf("reserved without waiting for the other sender: %v", err)
	case <-time.After(300 * time.Millisecond):
	}
	if err := other.Commit(ctx); err != nil {
		t.Fatal(err)
	}
	if err := <-done; !errors.Is(err, ErrOverBudget) {
		t.Fatalf("the other sender's reservation fills the cap: %v", err)
	}
	month := Budget{Daily: 100, Monthly: 1, DayStart: date.Add(-time.Hour), MonthStart: date.Add(-time.Hour)}
	if attempted, err := db.SendNotice(ctx, subs[1], "k", &month, func(Subscriber) (string, error) { t.Error("sent over the monthly cap"); return "", nil }); attempted || !errors.Is(err, ErrOverBudget) {
		t.Fatalf("notices share the monthly cap: %v %v", attempted, err)
	}
}

func TestCreatedAtSurvivesAZoneChangeButNotBAJA(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	created := func() time.Time {
		t.Helper()
		s, ok, err := db.Subscriber(ctx, Telegram, "777")
		if err != nil || !ok {
			t.Fatalf("subscriber: %v %v", ok, err)
		}
		return s.CreatedAt
	}
	if err := db.Subscribe(ctx, Telegram, "777", "", 4); err != nil {
		t.Fatal(err)
	}
	first := created()
	if err := db.Subscribe(ctx, Telegram, "777", "", 6); err != nil {
		t.Fatal(err)
	}
	if !created().Equal(first) {
		t.Fatal("a zone change is the same subscription")
	}
	if _, err := db.Unsubscribe(ctx, Telegram, "777", ""); err != nil {
		t.Fatal(err)
	}
	if err := db.Subscribe(ctx, Telegram, "777", "", 6); err != nil {
		t.Fatal(err)
	}
	if !created().After(first) {
		t.Fatal("subscribing again after BAJA is a new subscription")
	}
}

func TestQueuedRepliesSurviveARefusal(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	if err := db.ProcessInbound(ctx, "tg:1", func(tx BotStore) error {
		for _, body := range []string{`"one"`, `"two"`, `"three"`} {
			if err := tx.QueueReply(ctx, "tg:1", Telegram, "1", "", []byte(body)); err != nil {
				return err
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	refused := errors.New("429")
	var sent []string
	refuse := true
	send := func(body []byte) error {
		if string(body) == `"two"` && refuse {
			refuse = false
			return refused
		}
		sent = append(sent, string(body))
		return nil
	}
	if err := db.SendReplies(ctx, "tg:1", send); !errors.Is(err, refused) {
		t.Fatal(err)
	}
	if err := db.SendReplies(ctx, "tg:1", send); err != nil {
		t.Fatal(err)
	}
	if err := db.SendReplies(ctx, "tg:1", send); err != nil || fmt.Sprint(sent) != `["one" "two" "three"]` {
		t.Fatalf("each reply once, in order: %v %v", sent, err)
	}
	failed := errors.New("command failed")
	if err := db.ProcessInbound(ctx, "tg:2", func(tx BotStore) error {
		if err := tx.QueueReply(ctx, "tg:2", Telegram, "2", "", []byte(`"stale"`)); err != nil {
			return err
		}
		return failed
	}); !errors.Is(err, failed) {
		t.Fatal(err)
	}
	if err := db.ProcessInbound(ctx, "tg:3", func(tx BotStore) error { return tx.QueueReply(ctx, "tg:3", Telegram, "3", "", []byte(`"old"`)) }); err != nil {
		t.Fatal(err)
	}
	if _, err := db.pool.Exec(ctx, `update pending_reply set created_at = now() - interval '25 hours'`); err != nil {
		t.Fatal(err)
	}
	if err := db.PurgeSeen(ctx, time.Now().Add(-7*24*time.Hour)); err != nil {
		t.Fatal(err)
	}
	var n int
	if err := db.pool.QueryRow(ctx, `select count(*) from pending_reply`).Scan(&n); err != nil || n != 0 {
		t.Fatalf("a rolled-back command queues nothing, and a day-old reply is purged: %d %v", n, err)
	}
}

func TestAcceptedReplyIsNeverResent(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	if err := db.ProcessInbound(ctx, "tg:1", func(tx BotStore) error {
		return tx.QueueReply(ctx, "tg:1", Telegram, "1", "", []byte(`"hi"`))
	}); err != nil {
		t.Fatal(err)
	}
	// Forgetting the reply fails right after the provider accepted it.
	if _, err := db.pool.Exec(ctx, `create function block_delete() returns trigger language plpgsql as $$
		begin raise exception 'database gone'; end $$;
		create trigger block_delete before delete on pending_reply execute function block_delete()`); err != nil {
		t.Fatal(err)
	}
	sent := 0
	send := func([]byte) error { sent++; return nil }
	if err := db.SendReplies(ctx, "tg:1", send); err == nil {
		t.Fatal("the failed delete must be reported")
	}
	if _, err := db.pool.Exec(ctx, `drop trigger block_delete on pending_reply`); err != nil {
		t.Fatal(err)
	}
	if err := db.SendReplies(ctx, "tg:1", send); err != nil || sent != 1 {
		t.Fatalf("the accepted reply stays claimed, never resent: sent %d, %v", sent, err)
	}
	var n int
	if err := db.pool.QueryRow(ctx, `select count(*) from pending_reply where claimed_at is not null`).Scan(&n); err != nil || n != 1 {
		t.Fatalf("the claim stays until the purge: %d %v", n, err)
	}
}

func TestUnsubscribeCancelsQueuedReplies(t *testing.T) {
	db := testDB(t)
	ctx := context.Background()
	if err := db.ProcessInbound(ctx, "tg:1", func(tx BotStore) error {
		if err := tx.Subscribe(ctx, Telegram, "777", "", 4); err != nil {
			return err
		}
		return tx.QueueReply(ctx, "tg:1", Telegram, "777", "", []byte(`"subscribed"`))
	}); err != nil {
		t.Fatal(err)
	}
	if err := db.ProcessInbound(ctx, "tg:2", func(tx BotStore) error {
		return tx.QueueReply(ctx, "tg:2", Telegram, "888", "", []byte(`"other"`))
	}); err != nil {
		t.Fatal(err)
	}
	if removed, err := db.Unsubscribe(ctx, Telegram, "777", ""); err != nil || !removed {
		t.Fatal(removed, err)
	}
	var n int
	if err := db.pool.QueryRow(ctx, `select count(*) from pending_reply where user_id = '777'`).Scan(&n); err != nil || n != 0 {
		t.Fatalf("BAJA drops the replies queued for the person: %d %v", n, err)
	}
	sent := 0
	if err := db.SendReplies(ctx, "tg:1", func([]byte) error { sent++; return nil }); err != nil || sent != 0 {
		t.Fatalf("nothing left to send: %d %v", sent, err)
	}
	if err := db.SendReplies(ctx, "tg:2", func([]byte) error { sent++; return nil }); err != nil || sent != 1 {
		t.Fatalf("other people's replies stay: %d %v", sent, err)
	}
}
