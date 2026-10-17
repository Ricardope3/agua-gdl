package notices

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"

	"aguagdl/api/internal/fake"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/tg"
)

func TestSendIsIdempotentAndCapped(t *testing.T) {
	ctx := context.Background()
	st, snd := fake.NewStore(), &fake.Sender{}
	for user, zone := range map[string]int{"a": 4, "b": 4, "c": 4, "d": 6} {
		st.Subscribe(ctx, store.WhatsApp, user, user, zone)
	}
	n := Notice{Zone: 4, Key: "cambio_rotacion/4/2026-11-02", Template: "cambio_rotacion", Language: "es_MX",
		Params: []string{"4", "lunes y jueves", "lunes 2 de noviembre"}}
	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	sent, err := Send(ctx, st, snd, n, 2, 100, 0, st.Now, log)
	if sent != 2 || !errors.Is(err, ErrCapped) {
		t.Fatalf("the cap must stop the run: sent %d, err %v", sent, err)
	}
	sent, err = Send(ctx, st, snd, n, 10, 100, 0, st.Now, log)
	if sent != 1 || err != nil || len(snd.Sent) != 3 {
		t.Fatalf("a re-run reaches only the rest of zone 4: sent %d, total %d, err %v", sent, len(snd.Sent), err)
	}
	tpl := snd.Sent[0].Template
	if tpl.Name != "cambio_rotacion" || len(tpl.Components) != 1 || tpl.Components[0].Parameters[2].Text != "lunes 2 de noviembre" {
		t.Errorf("unexpected template: %+v", tpl)
	}
}

func TestMonthlyCapStopsNotices(t *testing.T) {
	ctx := context.Background()
	st, snd := fake.NewStore(), &fake.Sender{}
	st.Subscribe(ctx, store.WhatsApp, "a", "a", 4)
	now := st.Now().AddDate(0, 0, 14)
	st.Now = func() time.Time { return now }
	st.SentAt["98/2026-09-20"] = now.AddDate(0, -1, 0) // last month's
	st.SentAt["99/2026-10-14"] = now.Add(-25 * time.Hour)
	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	sent, err := Send(ctx, st, snd, Notice{Zone: 4, Key: "k"}, 100, 1, 0, st.Now, log)
	if sent != 0 || !errors.Is(err, ErrCapped) || len(snd.Sent) != 0 {
		t.Fatalf("this month's message fills a monthly cap of 1: sent %d, err %v", sent, err)
	}
}

func TestSendTelegramReachesOnlyTelegramOnce(t *testing.T) {
	ctx := context.Background()
	st, tel := fake.NewStore(), &fake.Telegram{}
	st.Subscribe(ctx, store.WhatsApp, "MX.a", "5211", 4)
	st.Subscribe(ctx, store.Telegram, "777", "", 4)
	st.Subscribe(ctx, store.Telegram, "778", "", 6)
	n := Notice{Zone: 4, Key: "cambio_rotacion/4/2026-11-02"}
	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	for range 2 {
		if _, err := SendTelegram(ctx, st, tel, n, "⚠️ *Cambio*", 0, log); err != nil {
			t.Fatal(err)
		}
	}
	if len(tel.Sent) != 1 || tel.Sent[0].ChatID != 777 || tel.Sent[0].Text != "⚠️ <b>Cambio</b>" {
		t.Fatalf("sent %+v", tel.Sent)
	}
}

type blockedTelegram struct{ fake.Telegram }

func (blockedTelegram) Send(context.Context, tg.Message) (int64, error) {
	return 0, &tg.APIError{Status: 403, Description: "Forbidden: bot was blocked by the user"}
}

func TestBlockedTelegramChatIsNotAFailure(t *testing.T) {
	ctx := context.Background()
	st := fake.NewStore()
	st.Subscribe(ctx, store.Telegram, "777", "", 4)
	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	sent, err := SendTelegram(ctx, st, &blockedTelegram{}, Notice{Zone: 4, Key: "k"}, "hola", 0, log)
	if sent != 0 || err != nil || len(st.Subs) != 0 {
		t.Fatalf("a blocked bot is an opt-out: sent %d, err %v, subs %d", sent, err, len(st.Subs))
	}
}
