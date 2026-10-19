package reminders

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/fake"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/wa"
)

func runner(t *testing.T, now string, st *fake.Store, snd *fake.Sender) *Runner {
	t.Helper()
	loc, _ := time.LoadLocation("America/Mexico_City")
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		t.Fatal(err)
	}
	at, _ := time.ParseInLocation("2006-01-02 15:04", now, loc)
	st.Now = func() time.Time { return at }
	return &Runner{Store: st, Sender: snd, Schedule: sched, Template: "aviso_corte", Language: "es_MX",
		Hour: 20, CatchUpUntil: 22, DailyCap: 250, MonthlyCap: 10000,
		Now: st.Now, Log: slog.New(slog.NewTextHandler(io.Discard, nil))}
}

func TestSendsToZonesCutTomorrow(t *testing.T) {
	st, snd := fake.NewStore(), &fake.Sender{}
	for i, z := range []int{2, 4, 6, 2} {
		st.Subscribe(context.Background(), store.WhatsApp, string(rune('a'+i)), "52133000000"+string(rune('0'+i)), z)
	}
	r := runner(t, "2026-10-18 20:00", st, snd)
	if err := r.SendTonight(context.Background()); err != nil {
		t.Fatal(err)
	}
	if len(snd.Sent) != 2 {
		t.Fatalf("Monday 19 cuts zones 4 and 6: sent %d, want 2", len(snd.Sent))
	}
	tpl := snd.Sent[0].Template
	if tpl.Name != "aviso_corte" || tpl.Components[0].Parameters[0].Text != "lunes 19 de octubre" || tpl.Components[0].Parameters[1].Text != "4" {
		t.Errorf("unexpected template: %+v", tpl)
	}
	if p := tpl.Components[1].Parameters[0].Payload; p != "BAJA" || snd.Sent[0].To == "" {
		t.Errorf("payload %s, to %q", p, snd.Sent[0].To)
	}
	if err := r.SendTonight(context.Background()); err != nil || len(snd.Sent) != 2 {
		t.Error("a second run must not resend")
	}
}

// tick makes the runner's clock advance only when it sleeps or sends.
func tick(r *Runner, st *fake.Store, start time.Time) *time.Time {
	clock := start
	r.Now, st.Now = func() time.Time { return clock }, func() time.Time { return clock }
	r.Sleep = func(_ context.Context, d time.Duration) error { clock = clock.Add(d); return nil }
	return &clock
}

func TestDailyCap(t *testing.T) {
	st, snd := fake.NewStore(), &fake.Sender{}
	for i := range 5 {
		st.Subscribe(context.Background(), store.WhatsApp, string(rune('a'+i)), "", 4)
	}
	r := runner(t, "2026-10-18 20:00", st, snd)
	clock := tick(r, st, r.Now())
	r.DailyCap = 3
	var beat []bool
	r.Heartbeat = func(_ context.Context, ok bool, _ string) { beat = append(beat, ok) }
	r.runOnce(context.Background())
	if len(snd.Sent) != 3 {
		t.Errorf("sent %d, want cap of 3", len(snd.Sent))
	}
	if len(beat) != 1 || beat[0] {
		t.Errorf("hitting the cap must report a failed heartbeat, got %v", beat)
	}
	if clock.Hour() != 22 {
		t.Errorf("should wait for the window until the catch-up deadline, stopped at %v", clock)
	}
}

func TestDailyCapWaitsForLastNightToExpire(t *testing.T) {
	ctx := context.Background()
	loc, _ := time.LoadLocation("America/Mexico_City")
	st, snd := fake.NewStore(), &fake.Sender{}
	// Friday night reminds Saturday's zones 3, 5 and 7; Saturday night reminds Sunday's zone 2
	// (zone 1's Sunday continues Friday's block and zone 7's Saturday's).
	for user, zone := range map[string]int{"a": 3, "b": 5, "c": 7, "d": 1, "e": 2, "f": 2, "g": 2} {
		st.Subscribe(ctx, store.WhatsApp, user, user, zone)
	}
	r := runner(t, "2026-10-16 20:00", st, snd)
	clock := tick(r, st, time.Date(2026, 10, 16, 20, 0, 5, 0, loc))
	r.Sender = senderFunc(func(ctx context.Context, m wa.Message) (string, error) {
		*clock = clock.Add(time.Second)
		return snd.Send(ctx, m)
	})
	r.DailyCap = 3
	if err := r.SendTonight(ctx); err != nil || len(snd.Sent) != 3 {
		t.Fatalf("Friday: sent %d, err %v", len(snd.Sent), err)
	}
	*clock = time.Date(2026, 10, 17, 20, 0, 0, 0, loc)
	if err := r.SendTonight(ctx); err != nil || len(snd.Sent) != 6 {
		t.Fatalf("Saturday started before Friday's sends left the window and must wait, not skip: sent %d in total, err %v", len(snd.Sent), err)
	}
}

func TestNextRun(t *testing.T) {
	loc, _ := time.LoadLocation("America/Mexico_City")
	r := runner(t, "2026-10-18 20:00", fake.NewStore(), &fake.Sender{})
	at := func(s string) time.Time { t, _ := time.ParseInLocation("2006-01-02 15:04", s, loc); return t }
	if got := r.nextRun(at("2026-10-18 19:59")); !got.Equal(at("2026-10-18 20:00")) {
		t.Error(got)
	}
	if got := r.nextRun(at("2026-10-18 20:00")); !got.Equal(at("2026-10-19 20:00")) {
		t.Error(got)
	}
}

type senderFunc func(context.Context, wa.Message) (string, error)

func (f senderFunc) Send(ctx context.Context, m wa.Message) (string, error) { return f(ctx, m) }

func TestAnyFailedSendFailsHeartbeatIncludingAfterRestart(t *testing.T) {
	for sendErr, wantCalls := range map[error]int{
		errors.New("network timeout"): 1, // WhatsApp may have accepted it: never resend
		// Meta rejected it: nothing was sent, so each run retries with backoff until the 22:00 deadline.
		&wa.APIError{Status: 400, Code: 131026}: 18,
	} {
		t.Run(sendErr.Error(), func(t *testing.T) {
			st, snd := fake.NewStore(), &fake.Sender{}
			st.Subscribe(context.Background(), store.WhatsApp, "a", "521111", 4)
			r := runner(t, "2026-10-18 20:00", st, snd)
			tick(r, st, r.Now())
			calls := 0
			r.Sender = senderFunc(func(context.Context, wa.Message) (string, error) { calls++; return "", sendErr })
			var beats []bool
			r.Heartbeat = func(_ context.Context, ok bool, _ string) { beats = append(beats, ok) }
			r.runOnce(context.Background())
			r.runOnce(context.Background())
			if calls != wantCalls || len(beats) != 2 || beats[0] || beats[1] {
				t.Fatalf("calls=%d heartbeats=%v: failed attempts must stay visible", calls, beats)
			}
		})
	}
}

func TestUnsubscribeDuringBatchSkipsQueuedRecipient(t *testing.T) {
	ctx := context.Background()
	st, snd := fake.NewStore(), &fake.Sender{}
	for _, user := range []string{"a", "b", "c"} {
		st.Subscribe(ctx, store.WhatsApp, user, user, 4)
	}
	r := runner(t, "2026-10-18 20:00", st, snd)
	r.Sender = senderFunc(func(ctx context.Context, m wa.Message) (string, error) {
		if m.To == "a" {
			st.Unsubscribe(ctx, store.WhatsApp, "b", "")
		}
		return snd.Send(ctx, m)
	})
	if err := r.SendTonight(ctx); err != nil {
		t.Fatal(err)
	}
	if len(snd.Sent) != 2 || snd.Sent[0].To != "a" || snd.Sent[1].To != "c" {
		t.Fatalf("BAJA must skip b and allow the remaining batch: %+v", snd.Sent)
	}
}

func TestPartialFailureStillFailsHeartbeat(t *testing.T) {
	ctx := context.Background()
	st, snd := fake.NewStore(), &fake.Sender{}
	for _, user := range []string{"a", "b"} {
		st.Subscribe(ctx, store.WhatsApp, user, user, 4)
	}
	r := runner(t, "2026-10-18 20:00", st, snd)
	r.Sender = senderFunc(func(ctx context.Context, m wa.Message) (string, error) {
		if m.To == "a" {
			return "", errors.New("timeout")
		}
		return snd.Send(ctx, m)
	})
	if err := r.SendTonight(ctx); err == nil {
		t.Fatal("a later success must not erase an earlier failure")
	}
	if len(snd.Sent) != 1 || snd.Sent[0].To != "b" {
		t.Fatal("remaining recipients should still be attempted")
	}
}

func TestSystemicRejectionAbortsAndRetries(t *testing.T) {
	ctx := context.Background()
	st, snd := fake.NewStore(), &fake.Sender{}
	for i := range 10 {
		st.Subscribe(ctx, store.WhatsApp, string(rune('a'+i)), string(rune('a'+i)), 4)
	}
	r := runner(t, "2026-10-18 20:00", st, snd)
	calls := 0
	r.Sender = senderFunc(func(context.Context, wa.Message) (string, error) {
		calls++
		return "", &wa.APIError{Status: 400, Code: 132015, Message: "Template is paused"}
	})
	if err := r.SendTonight(ctx); err == nil || calls != maxConsecutiveFailures {
		t.Fatalf("a paused template must abort after %d attempts, got %d (err %v)", maxConsecutiveFailures, calls, err)
	}
	r.Sender = snd
	if err := r.SendTonight(ctx); err != nil || len(snd.Sent) != 10 {
		t.Fatalf("after the fix a re-run must reach everyone: sent %d, err %v", len(snd.Sent), err)
	}
}

func TestDailyCapIsAMovingWindow(t *testing.T) {
	ctx := context.Background()
	loc, _ := time.LoadLocation("America/Mexico_City")
	st, snd := fake.NewStore(), &fake.Sender{}
	// Zone 2's Tuesday continues Sunday's block, so Monday night reminds zone 5 only.
	for user, zone := range map[string]int{"a": 4, "b": 6, "c": 5, "d": 5, "e": 5} {
		st.Subscribe(ctx, store.WhatsApp, user, user, zone)
	}
	r := runner(t, "2026-10-18 20:00", st, snd)
	clock := time.Date(2026, 10, 18, 20, 0, 0, 0, loc)
	r.Now, st.Now = func() time.Time { return clock }, func() time.Time { return clock }
	r.Sender = senderFunc(func(ctx context.Context, m wa.Message) (string, error) {
		clock = clock.Add(time.Second)
		return snd.Send(ctx, m)
	})
	r.DailyCap = 3
	if err := r.SendTonight(ctx); err != nil || len(snd.Sent) != 2 {
		t.Fatalf("Sunday: sent %d, err %v", len(snd.Sent), err)
	}
	clock = time.Date(2026, 10, 19, 20, 0, 0, 0, loc)
	if err := r.SendTonight(ctx); err != nil || len(snd.Sent) != 5 {
		t.Fatalf("Monday: last night's reminders expire as tonight's go out; sent %d in total, err %v", len(snd.Sent), err)
	}
}

func TestTransientDatabaseErrorIsRetriedUntilDeadline(t *testing.T) {
	st, snd := fake.NewStore(), &fake.Sender{}
	st.Subscribe(context.Background(), store.WhatsApp, "a", "a", 4)
	r := runner(t, "2026-10-18 20:00", st, snd)
	tick(r, st, r.Now())
	st.FailDue = 2
	var beats []bool
	r.Heartbeat = func(_ context.Context, ok bool, _ string) { beats = append(beats, ok) }
	r.runOnce(context.Background())
	if len(snd.Sent) != 1 || len(beats) != 1 || !beats[0] {
		t.Fatalf("a database hiccup must not lose the night: sent %d, heartbeats %v", len(snd.Sent), beats)
	}

	st, snd = fake.NewStore(), &fake.Sender{}
	st.Subscribe(context.Background(), store.WhatsApp, "a", "a", 4)
	r = runner(t, "2026-10-18 20:00", st, snd)
	clock := tick(r, st, r.Now())
	st.FailDue = 1000
	beats = nil
	r.Heartbeat = func(_ context.Context, ok bool, _ string) { beats = append(beats, ok) }
	r.runOnce(context.Background())
	if len(snd.Sent) != 0 || len(beats) != 1 || beats[0] || clock.Hour() >= 22 {
		t.Fatalf("an outage must give up before the deadline and fail the heartbeat: %v at %v", beats, clock)
	}
}

func TestZoneChangeMidBatchToAnotherZoneCutTomorrow(t *testing.T) {
	ctx := context.Background()
	st, snd := fake.NewStore(), &fake.Sender{}
	st.Subscribe(ctx, store.WhatsApp, "a", "a", 4)
	st.Subscribe(ctx, store.WhatsApp, "b", "b", 4)
	r := runner(t, "2026-10-18 20:00", st, snd)
	r.Sender = senderFunc(func(ctx context.Context, m wa.Message) (string, error) {
		if m.To == "a" {
			st.Subscribe(ctx, store.WhatsApp, "b", "b", 6)
		}
		return snd.Send(ctx, m)
	})
	if err := r.SendTonight(ctx); err != nil {
		t.Fatal(err)
	}
	if len(snd.Sent) != 2 || snd.Sent[1].Template.Components[0].Parameters[1].Text != "6" {
		t.Fatalf("b moved from zone 4 to zone 6, both cut Monday, and must get the zone 6 reminder: %+v", snd.Sent)
	}
}

func TestOnePhoneGetsOneReminder(t *testing.T) {
	ctx := context.Background()
	st, snd := fake.NewStore(), &fake.Sender{}
	st.Subscribe(ctx, store.WhatsApp, "old-owner", "5213300000000", 4)
	st.Subscribe(ctx, store.WhatsApp, "new-owner", "5213300000000", 6)
	r := runner(t, "2026-10-18 20:00", st, snd)
	if err := r.SendTonight(ctx); err != nil {
		t.Fatal(err)
	}
	if len(snd.Sent) != 1 || snd.Sent[0].Template.Components[0].Parameters[1].Text != "6" {
		t.Fatalf("Monday cuts zones 4 and 6; the number's current owner is in zone 6: %+v", snd.Sent)
	}
}

func TestManualReminderReachesTheWindowOnceAndTheNightlyRunSkipsIt(t *testing.T) {
	ctx := context.Background()
	st, snd := fake.NewStore(), &fake.Sender{}
	r := runner(t, "2026-10-15 19:00", st, snd)
	st.Subscribe(ctx, store.WhatsApp, "a", "521", 6)
	st.Subscribe(ctx, store.WhatsApp, "b", "522", 6)
	st.Subscribe(ctx, store.WhatsApp, "c", "523", 4)
	old := st.Subs["b"]
	old.UpdatedAt = old.UpdatedAt.Add(-30 * time.Hour)
	st.Subs["b"] = old
	m := Manual{Zone: 6, Text: "aviso", ActiveSince: r.Now().Add(-23 * time.Hour)}
	if in, due, err := r.ManualRecipients(ctx, m); err != nil || len(in) != 1 || due != 2 {
		t.Fatalf("Friday cuts zone 6: want a inside the window of 2 due, got %d of %d, err %v", len(in), due, err)
	}
	if sent, err := r.SendManual(ctx, m); err != nil || sent != 1 || snd.Sent[0].Type != "text" || snd.Sent[0].To != "521" {
		t.Fatalf("sent %d, err %v, messages %+v", sent, err, snd.Sent)
	}
	if sent, err := r.SendManual(ctx, m); err != nil || sent != 0 {
		t.Fatalf("a re-run must not resend: sent %d, err %v", sent, err)
	}
	if err := r.SendTonight(ctx); err != nil || len(snd.Sent) != 2 || snd.Sent[1].To != "522" || snd.Sent[1].Template == nil {
		t.Fatalf("the nightly run must skip a and remind b with the template: %+v, err %v", snd.Sent, err)
	}
}

func TestManualReminderNeedsACutTomorrow(t *testing.T) {
	r := runner(t, "2026-10-15 19:00", fake.NewStore(), &fake.Sender{})
	if _, err := r.SendManual(context.Background(), Manual{Zone: 4, Text: "aviso"}); err == nil {
		t.Fatal("zone 4 has no cut on Friday 16")
	}
}

func TestResubscribingAfterTheRunIsNotRemindedTwice(t *testing.T) {
	ctx := context.Background()
	st, snd := fake.NewStore(), &fake.Sender{}
	r := runner(t, "2026-10-18 19:00", st, snd)
	st.Subscribe(ctx, store.WhatsApp, "a", "a", 4)
	clock := tick(r, st, r.Now().Add(time.Hour))
	if err := r.SendTonight(ctx); err != nil || len(snd.Sent) != 1 {
		t.Fatalf("sent %d, err %v", len(snd.Sent), err)
	}
	*clock = clock.Add(30 * time.Minute)
	st.Unsubscribe(ctx, store.WhatsApp, "a", "a")
	st.Subscribe(ctx, store.WhatsApp, "a", "a", 4)
	if err := r.SendTonight(ctx); err != nil || len(snd.Sent) != 1 {
		t.Fatalf("the confirmation already announced tomorrow's cut: sent %d, err %v", len(snd.Sent), err)
	}
}

func TestShutdownMidSendStillRecordsTheReminder(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	st, snd := fake.NewStore(), &fake.Sender{}
	st.Subscribe(ctx, store.WhatsApp, "a", "a", 4)
	r := runner(t, "2026-10-18 20:00", st, snd)
	r.Sender = senderFunc(func(sendCtx context.Context, m wa.Message) (string, error) {
		cancel()
		if err := sendCtx.Err(); err != nil {
			return "", err
		}
		return snd.Send(sendCtx, m)
	})
	if err := r.SendTonight(ctx); err != nil || len(snd.Sent) != 1 || len(st.Unresolved) != 0 {
		t.Fatalf("a send in flight at shutdown must complete and be recorded: sent %d, unresolved %v, err %v", len(snd.Sent), st.Unresolved, err)
	}
}

// slotTaken refuses the first reservation, as if another sender took the last slot
// between the runner's cap check and its reservation.
type slotTaken struct {
	*fake.Store
	refused bool
}

func (s *slotTaken) SendReminder(ctx context.Context, sub store.Subscriber, d time.Time, zones []int, b *store.Budget, send func(store.Subscriber) (string, error)) (bool, error) {
	if !s.refused && b != nil {
		s.refused = true
		return false, store.ErrOverBudget
	}
	return s.Store.SendReminder(ctx, sub, d, zones, b, send)
}

func TestSlotTakenByAnotherSenderIsRetriedNotSkipped(t *testing.T) {
	st, snd := fake.NewStore(), &fake.Sender{}
	st.Subscribe(context.Background(), store.WhatsApp, "a", "a", 4)
	r := runner(t, "2026-10-18 20:00", st, snd)
	r.Store = &slotTaken{Store: st}
	if err := r.SendTonight(context.Background()); err != nil || len(snd.Sent) != 1 {
		t.Fatalf("sent %d, err %v", len(snd.Sent), err)
	}
}
