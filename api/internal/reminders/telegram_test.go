package reminders

import (
	"context"
	"errors"
	"fmt"
	"net"
	"slices"
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

func TestNetworkBlipIsRetried(t *testing.T) {
	st := fake.NewStore()
	ctx := context.Background()
	for i := range 10 {
		st.Subscribe(ctx, store.Telegram, fmt.Sprint(700+i), "", 4)
	}
	r := runner(t, "2026-10-18 20:00", st, nil)
	down := fmt.Errorf("tg: sendMessage: %w", &tg.NotSentError{Err: &net.OpError{Op: "dial", Net: "tcp", Err: errors.New("connect: network is unreachable")}})
	tel := &flakyTelegram{errs: slices.Repeat([]error{down}, 25)} // the first five subscribers' four tries each, and more
	r.Sender, r.Telegram = nil, tel
	now := r.Now()
	r.Now = func() time.Time { return now }
	r.Sleep = func(_ context.Context, d time.Duration) error { now = now.Add(d); return nil }
	r.runOnce(ctx)
	got := map[int64]int{}
	for _, m := range tel.Sent {
		got[m.ChatID]++
	}
	if len(got) != 10 || len(tel.Sent) != 10 {
		t.Fatalf("nothing reached Telegram, so the run tries again until everyone has it once: %d sent to %d chats", len(tel.Sent), len(got))
	}
	if now.Hour() >= 22 {
		t.Fatalf("delivered within the catch-up window, not at %s", now.Format("15:04"))
	}
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

func tgRunner(t *testing.T, now string, st *fake.Store, tel *fake.Telegram) *Runner {
	t.Helper()
	r := runner(t, now, st, nil)
	r.Sender, r.Telegram = nil, tel
	return r
}

func TestOneRoundOfMessagesPerBlock(t *testing.T) {
	ctx := context.Background()
	st, tel := fake.NewStore(), &fake.Telegram{}
	st.Subscribe(ctx, store.Telegram, "501", "", 5) // Tuesday and Wednesday in a row, then Saturday
	st.Subscribe(ctx, store.Telegram, "301", "", 3) // Wednesday and Saturday
	if err := tgRunner(t, "2026-10-19 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 2 {
		t.Fatalf("Monday: err %v, sent %d", err, len(tel.Sent))
	}
	if m := tel.Sent[0]; m.ChatID != 501 || !strings.Contains(m.Text, "<b>mañana martes 20 de octubre</b>, y también el miércoles 21 de octubre") {
		t.Errorf("zone 5's reminder must cover its block: %s", m.Text)
	}
	if m := tel.Sent[1]; m.ChatID != 301 || !strings.Contains(m.Text, "Se acerca el corte en la Zona 3") || !strings.Contains(m.Text, "<b>miércoles 21 de octubre</b>") {
		t.Errorf("zone 3 gets its notice two days before Wednesday: %s", m.Text)
	}
	if kb := tel.Sent[1].ReplyMarkup.(tg.InlineKeyboard); kb.InlineKeyboard[0][2].CallbackData != "A:3:2026-10-21:no" {
		t.Errorf("the notice asks «¿Ahorita tienes agua?» about the block: %+v", kb)
	}
	if err := tgRunner(t, "2026-10-19 20:30", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 2 {
		t.Fatalf("a second run must not resend: err %v, sent %d", err, len(tel.Sent))
	}
	if err := tgRunner(t, "2026-10-20 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 3 || tel.Sent[2].ChatID != 301 {
		t.Fatalf("Tuesday, in the middle of zone 5's block, only zone 3 is reminded: err %v, sent %+v", err, tel.Sent)
	}
}

func TestNoticeNotRepeatedAfterSubscribingAgain(t *testing.T) {
	ctx := context.Background()
	st, tel := fake.NewStore(), &fake.Telegram{}
	st.Subscribe(ctx, store.Telegram, "301", "", 3)
	if err := tgRunner(t, "2026-10-19 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 1 {
		t.Fatalf("Monday's notice: err %v, sent %d", err, len(tel.Sent))
	}
	st.Now = func() time.Time { return day(t, "2026-10-19").Add(20*time.Hour + 30*time.Minute) }
	st.Unsubscribe(ctx, store.Telegram, "301", "")
	st.Subscribe(ctx, store.Telegram, "301", "", 3)
	if err := tgRunner(t, "2026-10-19 20:45", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 1 {
		t.Fatalf("BAJA and subscribing again must not repeat tonight's notice: err %v, sent %d", err, len(tel.Sent))
	}
}

func TestNoReminderForWhoeverHasNoWater(t *testing.T) {
	ctx := context.Background()
	st, tel := fake.NewStore(), &fake.Telegram{}
	st.Subscribe(ctx, store.Telegram, "301", "", 3)
	st.Subscribe(ctx, store.Telegram, "302", "", 3)
	if err := tgRunner(t, "2026-10-19 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 2 {
		t.Fatalf("Monday's notices: err %v, sent %d", err, len(tel.Sent))
	}
	dry := st.Subs[fake.Key(store.Telegram, "301")]
	if kept, _ := st.SaveWater(ctx, dry.ID, 3, day(t, "2026-10-21"), "no"); !kept {
		t.Fatal("the notice's answer must be kept")
	}
	if err := tgRunner(t, "2026-10-20 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 3 || tel.Sent[2].ChatID != 302 {
		t.Fatalf("Tuesday: only whoever still has water gets «llena tu tinaco»: err %v, sent %+v", err, tel.Sent)
	}
}

func TestAskWhetherTheWaterCameBack(t *testing.T) {
	ctx := context.Background()
	st, tel := fake.NewStore(), &fake.Telegram{}
	st.Subscribe(ctx, store.Telegram, "601", "", 6) // Monday's block, then Friday's
	st.Subscribe(ctx, store.Telegram, "602", "", 6)
	st.Subscribe(ctx, store.Telegram, "603", "", 6)
	if err := tgRunner(t, "2026-10-17 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 3 {
		t.Fatalf("Saturday's notices for Monday: err %v, sent %d", err, len(tel.Sent))
	}
	monday := day(t, "2026-10-19")
	for user, answer := range map[string]string{"601": "no", "602": "poca", "603": "si"} {
		if kept, _ := st.SaveWater(ctx, st.Subs[fake.Key(store.Telegram, user)].ID, 6, monday, answer); !kept {
			t.Fatalf("%s's answer must be kept", user)
		}
	}
	st.SaveReport(ctx, st.Subs[fake.Key(store.Telegram, "602")].ID, 6, monday, "normal") // already said how it came back
	tel.Sent = nil
	if err := tgRunner(t, "2026-10-18 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 2 {
		t.Fatalf("Sunday: the reminder skips whoever has no water: err %v, sent %d", err, len(tel.Sent))
	}
	tel.Sent = nil
	if err := tgRunner(t, "2026-10-20 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 1 {
		t.Fatalf("Tuesday: one «¿Ya regresó?», to 601 only: err %v, sent %+v", err, tel.Sent)
	}
	m := tel.Sent[0]
	kb, ok := m.ReplyMarkup.(tg.InlineKeyboard)
	if m.ChatID != 601 || !strings.Contains(m.Text, "¿Ya regresó el agua?") || !ok || kb.InlineKeyboard[0][0].CallbackData != "R:6:2026-10-19:normal" {
		t.Errorf("follow-up: %+v", m)
	}
	if err := tgRunner(t, "2026-10-20 20:30", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 1 {
		t.Fatalf("asked once: err %v, sent %d", err, len(tel.Sent))
	}
}

func TestNoticeNightsDontAlsoAskWhetherTheWaterCameBack(t *testing.T) {
	ctx := context.Background()
	st, tel := fake.NewStore(), &fake.Telegram{}
	st.Subscribe(ctx, store.Telegram, "401", "", 4) // Monday, then Thursday: Tuesday is the Thursday notice's night
	if err := tgRunner(t, "2026-10-17 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 1 {
		t.Fatalf("Saturday's notice: err %v, sent %d", err, len(tel.Sent))
	}
	st.SaveWater(ctx, st.Subs[fake.Key(store.Telegram, "401")].ID, 4, day(t, "2026-10-19"), "no")
	tel.Sent = nil
	if err := tgRunner(t, "2026-10-20 20:00", st, tel).SendTonight(ctx); err != nil || len(tel.Sent) != 1 || !strings.Contains(tel.Sent[0].Text, "Se acerca el corte") {
		t.Fatalf("Tuesday: only Thursday's notice, whose question covers Monday's: err %v, sent %+v", err, tel.Sent)
	}
}

func day(t *testing.T, v string) time.Time {
	t.Helper()
	loc, _ := time.LoadLocation("America/Mexico_City")
	d, err := time.ParseInLocation("2006-01-02", v, loc)
	if err != nil {
		t.Fatal(err)
	}
	return d
}
