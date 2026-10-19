package reminders

import (
	"context"
	"strings"
	"testing"
	"time"

	"aguagdl/api/internal/fake"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/tg"
	"aguagdl/api/internal/wa"
)

type flakyTelegram struct {
	fake.Telegram
	errs []error // returned by the first sends, in order
}

func (f *flakyTelegram) Send(ctx context.Context, m tg.Message) (int64, error) {
	if len(f.errs) > 0 {
		err := f.errs[0]
		f.errs = f.errs[1:]
		return 0, err
	}
	return f.Telegram.Send(ctx, m)
}

func TestTelegramRemindersSkipMetaCaps(t *testing.T) {
	st, snd, tel := fake.NewStore(), &fake.Sender{}, &fake.Telegram{}
	ctx := context.Background()
	st.Subscribe(ctx, store.WhatsApp, "MX.a", "5213300000001", 4)
	st.Subscribe(ctx, store.Telegram, "777", "", 4)
	st.Subscribe(ctx, store.Telegram, "778", "", 6)
	st.Subscribe(ctx, store.Telegram, "779", "", 2)
	r := runner(t, "2026-10-18 20:00", st, snd)
	r.Telegram, r.DailyCap = tel, 1
	if err := r.SendTonight(ctx); err != nil {
		t.Fatal(err)
	}
	if len(snd.Sent) != 1 || len(tel.Sent) != 2 {
		t.Fatalf("Monday 19 cuts zones 4 and 6: whatsapp %d, telegram %d", len(snd.Sent), len(tel.Sent))
	}
	m := tel.Sent[0]
	kb, ok := m.ReplyMarkup.(tg.InlineKeyboard)
	if m.ChatID != 777 || !strings.Contains(m.Text, "<b>mañana lunes 19 de octubre</b>") || !strings.Contains(m.Text, "<b>Zona 4</b>") ||
		!ok || len(kb.InlineKeyboard) != 3 || kb.InlineKeyboard[0][2].CallbackData != "A:4:2026-10-19:no" ||
		kb.InlineKeyboard[1][0].URL == "" || kb.InlineKeyboard[2][0].CallbackData != "BAJA" {
		t.Errorf("telegram reminder: %+v", m)
	}
	if strings.Contains(m.Text, "hasta por un día") {
		t.Error("the Telegram reminder must not state SIAPA's account as fact")
	}
	if err := r.SendTonight(ctx); err != nil || len(tel.Sent) != 2 {
		t.Error("a second run must not resend")
	}
}

func TestBlockedTelegramChatIsDroppedQuietly(t *testing.T) {
	st := fake.NewStore()
	ctx := context.Background()
	st.Subscribe(ctx, store.Telegram, "777", "", 4)
	tel := &flakyTelegram{errs: []error{&tg.APIError{Status: 403, Description: "Forbidden: bot was blocked by the user"}}}
	r := runner(t, "2026-10-18 20:00", st, nil)
	r.Sender, r.Telegram = nil, tel
	if err := r.SendTonight(ctx); err != nil {
		t.Fatalf("a blocked bot is an opt-out, not a failure: %v", err)
	}
	if len(st.Subs) != 0 {
		t.Fatal("the subscription must be deleted")
	}
}

func TestTelegramWaitsOutTooManyRequests(t *testing.T) {
	st := fake.NewStore()
	ctx := context.Background()
	st.Subscribe(ctx, store.Telegram, "777", "", 4)
	tel := &flakyTelegram{errs: []error{&tg.APIError{Status: 429, RetryAfter: 3}}}
	r := runner(t, "2026-10-18 20:00", st, nil)
	r.Sender, r.Telegram = nil, tel
	var slept time.Duration
	r.Sleep = func(_ context.Context, d time.Duration) error { slept += d; return nil }
	if err := r.SendTonight(ctx); err != nil || len(tel.Sent) != 1 || slept != 3*time.Second {
		t.Fatalf("err=%v sent=%d slept=%s", err, len(tel.Sent), slept)
	}
}

func TestWhatsAppFailuresDontStopTelegram(t *testing.T) {
	st, tel := fake.NewStore(), &fake.Telegram{}
	ctx := context.Background()
	for i := range 6 {
		st.Subscribe(ctx, store.WhatsApp, "MX."+string(rune('a'+i)), "52133000000"+string(rune('0'+i)), 4)
	}
	st.Subscribe(ctx, store.Telegram, "777", "", 4)
	r := runner(t, "2026-10-18 20:00", st, nil)
	r.Sender = failingSender{&wa.APIError{Status: 400, Code: 131031, Message: "Account has been locked"}}
	r.Telegram = tel
	if err := r.SendTonight(ctx); err == nil {
		t.Fatal("the WhatsApp failures must still fail the heartbeat")
	}
	if len(tel.Sent) != 1 {
		t.Fatal("Telegram must still be sent")
	}
}

type failingSender struct{ err error }

func (f failingSender) Send(context.Context, wa.Message) (string, error) { return "", f.err }

func TestRefusedTelegramSendIsRetriedTheSameNight(t *testing.T) {
	ctx := context.Background()
	st := fake.NewStore()
	st.Subscribe(ctx, store.Telegram, "777", "", 4)
	tel := &flakyTelegram{errs: []error{&tg.APIError{Status: 400, Description: "Bad Request"}}}
	r := runner(t, "2026-10-18 20:00", st, nil)
	r.Sender, r.Telegram = nil, tel
	tick(r, st, r.Now())
	r.runOnce(ctx)
	if len(tel.Sent) != 1 || len(st.Unresolved) != 0 {
		t.Fatalf("a refused send must be retried before the deadline: sent %d, unresolved %v", len(tel.Sent), st.Unresolved)
	}
}

func TestOneReminderPerRunOfCutDays(t *testing.T) {
	ctx := context.Background()
	st, tel := fake.NewStore(), &fake.Telegram{}
	st.Subscribe(ctx, store.Telegram, "501", "", 5) // Tuesday and Wednesday in a row, then Saturday
	st.Subscribe(ctx, store.Telegram, "301", "", 3) // Wednesday and Saturday
	r := runner(t, "2026-10-19 20:00", st, nil)
	r.Sender, r.Telegram = nil, tel
	if err := r.SendTonight(ctx); err != nil || len(tel.Sent) != 1 {
		t.Fatalf("Monday: err %v, sent %d", err, len(tel.Sent))
	}
	if m := tel.Sent[0]; m.ChatID != 501 || !strings.Contains(m.Text, "<b>mañana martes 20 y miércoles 21 de octubre</b>") {
		t.Errorf("zone 5's reminder must cover both days: %s", m.Text)
	}
	r = runner(t, "2026-10-20 20:00", st, nil)
	r.Sender, r.Telegram = nil, tel
	if err := r.SendTonight(ctx); err != nil || len(tel.Sent) != 2 || tel.Sent[1].ChatID != 301 {
		t.Fatalf("Tuesday, in the middle of zone 5's cut, only zone 3 is reminded: err %v, sent %+v", err, tel.Sent)
	}
}
