package reminders

import (
	"context"
	"io"
	"log/slog"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/fake"
	"aguagdl/api/internal/rotation"
)

func runner(t *testing.T, now string, st *fake.Store, snd *fake.Sender) *Runner {
	t.Helper()
	loc, _ := time.LoadLocation("America/Mexico_City")
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		t.Fatal(err)
	}
	at, _ := time.ParseInLocation("2006-01-02 15:04", now, loc)
	return &Runner{Store: st, Sender: snd, Schedule: sched, Template: "aviso_corte", Language: "es_MX",
		Hour: 20, CatchUpUntil: 22, DailyCap: 250, MonthlyCap: 10000,
		Now: func() time.Time { return at }, Log: slog.New(slog.NewTextHandler(io.Discard, nil))}
}

func TestSendsToZonesCutTomorrow(t *testing.T) {
	st, snd := fake.NewStore(), &fake.Sender{}
	for i, z := range []int{2, 4, 6, 2} {
		st.Subscribe(context.Background(), string(rune('a'+i)), z)
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
	if p := tpl.Components[1].Parameters[0].Payload; p != "REPORT:2026-10-15" {
		t.Errorf("report payload = %s", p)
	}
	if err := r.SendTonight(context.Background()); err != nil || len(snd.Sent) != 2 {
		t.Error("a second run must not resend")
	}
}

func TestDailyCap(t *testing.T) {
	st, snd := fake.NewStore(), &fake.Sender{}
	for i := range 5 {
		st.Subscribe(context.Background(), string(rune('a'+i)), 4)
	}
	r := runner(t, "2026-10-18 20:00", st, snd)
	r.DailyCap = 3
	r.SendTonight(context.Background())
	if len(snd.Sent) != 3 {
		t.Errorf("sent %d, want cap of 3", len(snd.Sent))
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
