package bot

import (
	"context"
	"strings"
	"testing"
	"time"

	"aguagdl/api/internal/fake"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/tg"
)

type tgHarness struct {
	*harness
	tg *fake.Telegram
	n  int64
}

func newTGHarness(t *testing.T, now string) *tgHarness {
	h := &tgHarness{harness: newHarness(t, now), tg: &fake.Telegram{}}
	h.bot.Telegram, h.bot.TelegramOn = h.tg, true
	return h
}

func (h *tgHarness) update(t *testing.T, u tg.Update) tg.Message {
	t.Helper()
	h.n++
	u.UpdateID = h.n
	if err := h.bot.HandleTelegram(context.Background(), u); err != nil {
		t.Fatal(err)
	}
	if len(h.tg.Sent) == 0 {
		return tg.Message{}
	}
	return h.tg.Sent[len(h.tg.Sent)-1]
}

func (h *tgHarness) say(t *testing.T, text string) tg.Message {
	t.Helper()
	return h.update(t, tg.Update{Message: &tg.InboundMessage{Chat: tg.Chat{ID: 777, Type: "private"}, Text: text}})
}

func (h *tgHarness) press(t *testing.T, data string) tg.Message {
	t.Helper()
	return h.update(t, tg.Update{CallbackQuery: &tg.CallbackQuery{ID: "cb" + data, From: tg.User{ID: 777},
		Message: &tg.InboundMessage{Chat: tg.Chat{ID: 777, Type: "private"}}, Data: data}})
}

func (h *tgHarness) sub(t *testing.T) (store.Subscriber, bool) {
	t.Helper()
	s, ok := h.store.Subs[fake.Key(store.Telegram, "777")]
	return s, ok
}

func TestTelegramStartAsksForLocation(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	m := h.say(t, "/start")
	if m.ChatID != 777 || m.ParseMode != "HTML" || !strings.Contains(m.Text, "Te aviso por Telegram") || !strings.Contains(m.Text, "<b>Agua GDL</b>") {
		t.Errorf("welcome: %+v", m)
	}
	kb, ok := m.ReplyMarkup.(tg.ReplyKeyboard)
	if !ok || !kb.Keyboard[0][0].RequestLocation {
		t.Errorf("welcome must offer the location button: %+v", m.ReplyMarkup)
	}
	if len(h.sender.Sent) != 0 {
		t.Error("a Telegram message was answered on WhatsApp")
	}
}

func TestTelegramDeepLinkSubscribes(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	m := h.say(t, "/start z6")
	s, ok := h.sub(t)
	if !ok || s.Zone != 6 || s.Phone != "" {
		t.Fatalf("not subscribed: %+v", s)
	}
	if _, ok := m.ReplyMarkup.(tg.RemoveKeyboard); !ok || !strings.Contains(m.Text, "<b>Zona 6</b>") || !strings.Contains(m.Text, "tu ID de chat de Telegram") {
		t.Errorf("confirmation: %+v", m)
	}
	if got := h.say(t, "/start z9"); !strings.Contains(got.Text, "Estás suscrito a los avisos de la <b>Zona 6</b>") {
		t.Errorf("a bad deep link should greet, got:\n%s", got.Text)
	}
}

func TestTelegramColoniaButtonsAndLocation(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	m := h.say(t, "jardines del sauz")
	kb, ok := m.ReplyMarkup.(tg.InlineKeyboard)
	if !ok || len(kb.InlineKeyboard) < 2 {
		t.Fatalf("want colonia buttons: %+v", m)
	}
	var data string
	for _, row := range kb.InlineKeyboard {
		if strings.HasPrefix(row[0].Text, "JARDINES DEL SAUZ ·") {
			data = row[0].CallbackData
		}
	}
	if data == "" || len(data) > 64 {
		t.Fatalf("callback %q in %+v", data, kb)
	}
	h.press(t, data)
	if s, _ := h.sub(t); s.Zone != 6 {
		t.Errorf("zone %d, want 6", s.Zone)
	}
	if len(h.tg.Answered) != 1 {
		t.Errorf("button press not answered: %v", h.tg.Answered)
	}
	h.update(t, tg.Update{Message: &tg.InboundMessage{Chat: tg.Chat{ID: 777, Type: "private"}, Location: &tg.Location{Latitude: 20.6597, Longitude: -103.3496}}})
	if s, ok := h.sub(t); !ok || s.Zone == 0 {
		t.Errorf("location: %+v", s)
	}
}

func TestTelegramZonaCommand(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	if m := h.say(t, "/zona jardines del sauz"); strings.Contains(m.Text, "No encontré") {
		t.Errorf("/zona <colonia> must search the colonia:\n%s", m.Text)
	}
	h.say(t, "/zona 3")
	if s, _ := h.sub(t); s.Zone != 3 {
		t.Errorf("zone %d, want 3", s.Zone)
	}
}

func TestTelegramReportAndBaja(t *testing.T) {
	h := newTGHarness(t, "2026-10-16 09:00")
	h.say(t, "/start z6")
	m := h.say(t, "/reportar")
	kb, ok := m.ReplyMarkup.(tg.InlineKeyboard)
	if !ok || len(kb.InlineKeyboard) != 4 || kb.InlineKeyboard[1][0].CallbackData != "R:6:2026-10-16:baja" {
		t.Fatalf("report buttons: %+v", m)
	}
	h.press(t, "R:6:2026-10-16:baja")
	if len(h.store.Reports) != 1 || h.store.Reports[0].Answer != "baja" {
		t.Fatalf("reports: %+v", h.store.Reports)
	}
	h.press(t, "BAJA")
	if _, ok := h.sub(t); ok {
		t.Fatal("BAJA button must unsubscribe")
	}
	h.say(t, "zona 4")
	h.say(t, "/baja")
	if _, ok := h.sub(t); ok {
		t.Fatal("/baja must unsubscribe")
	}
}

// refusing answers the first sends with Telegram's 429.
type refusing struct {
	fake.Telegram
	refuse, attempts int
}

func (r *refusing) Send(ctx context.Context, m tg.Message) (int64, error) {
	r.attempts++
	if r.refuse > 0 {
		r.refuse--
		return 0, &tg.APIError{Status: 429, Description: "Too Many Requests"}
	}
	return r.Telegram.Send(ctx, m)
}

func TestRefusedReplyIsSentWhenTelegramRetries(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	tel := &refusing{refuse: 1}
	h.bot.Telegram = tel
	u := tg.Update{UpdateID: 1, Message: &tg.InboundMessage{Chat: tg.Chat{ID: 777, Type: "private"}, Text: "/start z6"}}
	if err := h.bot.HandleTelegram(context.Background(), u); err == nil {
		t.Fatal("a refused reply must make Telegram retry the update")
	}
	for range 2 {
		if err := h.bot.HandleTelegram(context.Background(), u); err != nil {
			t.Fatal(err)
		}
	}
	if tel.attempts != 2 || len(tel.Sent) != 1 || !strings.Contains(tel.Sent[0].Text, "Zona 6") {
		t.Fatalf("the retry sends the confirmation once: %d attempts, sent %+v", tel.attempts, tel.Sent)
	}
	if s, _ := h.sub(t); s.Zone != 6 || len(h.store.Subs) != 1 {
		t.Fatalf("the command runs once: %+v", h.store.Subs)
	}
}

func TestBajaCancelsARefusedConfirmation(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	tel := &refusing{refuse: 1}
	h.bot.Telegram = tel
	start := tg.Update{UpdateID: 100, Message: &tg.InboundMessage{Chat: tg.Chat{ID: 777, Type: "private"}, Text: "/start z6"}}
	if err := h.bot.HandleTelegram(context.Background(), start); err == nil {
		t.Fatal("a refused reply must make Telegram retry the update")
	}
	h.say(t, "/baja") // delivered before Telegram retries the start
	if err := h.bot.HandleTelegram(context.Background(), start); err != nil {
		t.Fatal(err)
	}
	if len(tel.Sent) != 1 || !strings.Contains(tel.Sent[0].Text, "ya no recibirás") {
		t.Fatalf("after BAJA only the goodbye is sent, never the old confirmation: %+v", tel.Sent)
	}
	if _, ok := h.sub(t); ok || len(h.store.Replies["tg:100"]) != 0 {
		t.Fatalf("BAJA drops the subscription and its queued replies: %+v", h.store.Replies)
	}
}

func TestRejoiningCantReportTheSameCutAgain(t *testing.T) {
	h := newTGHarness(t, "2026-10-16 09:00")
	h.say(t, "/start z6") // on the store's clock, before the cut
	h.press(t, "R:6:2026-10-16:turbia")
	h.store.Now = h.bot.Now
	for range 3 {
		h.say(t, "/baja")
		h.say(t, "/start z6")
		if m := h.say(t, "/reportar"); !strings.Contains(m.Text, "después de tu suscripción") {
			t.Fatalf("a subscription newer than the cut can't report it: %s", m.Text)
		}
		h.press(t, "R:6:2026-10-16:turbia")
	}
	if len(h.store.Reports) != 1 {
		t.Fatalf("BAJA and subscribing again must not add reports for the same cut: %+v", h.store.Reports)
	}
}

func TestNoSubscriptionsAfterTheRetentionDeadline(t *testing.T) {
	h := newTGHarness(t, "2027-04-29 23:59")
	h.say(t, "zona 4")
	loc, _ := time.LoadLocation("America/Mexico_City")
	h.bot.Now = func() time.Time { return time.Date(2027, 4, 30, 0, 0, 0, 0, loc) }
	if m := h.say(t, "zona 6"); !strings.Contains(m.Text, "ya terminó") {
		t.Fatalf("30 days after the end, no zone changes: %s", m.Text)
	}
	if s, _ := h.sub(t); s.Zone != 4 {
		t.Fatalf("zone %d, want 4", s.Zone)
	}
	h.say(t, "/baja")
	if _, ok := h.sub(t); ok {
		t.Fatal("BAJA still works")
	}
	if m := h.say(t, "zona 4"); !strings.Contains(m.Text, "ya terminó") {
		t.Fatalf("no new subscriptions after the purge: %s", m.Text)
	}
	if _, ok := h.sub(t); ok {
		t.Fatal("subscribed after the retention deadline")
	}
}

func TestReportKeepsTheZoneOfTheCut(t *testing.T) {
	h := newTGHarness(t, "2026-10-18 09:00")
	h.say(t, "zona 4")
	h.say(t, "/reportar")
	h.say(t, "zona 6")
	h.press(t, "R:4:2026-10-15:normal")
	if len(h.store.Reports) != 1 || h.store.Reports[0].Zone != 4 {
		t.Fatalf("a report after a zone change must count for the old zone: %+v", h.store.Reports)
	}
}

func TestTelegramBlockingTheBotUnsubscribes(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	h.say(t, "zona 2")
	sent := len(h.tg.Sent)
	blocked := &tg.ChatMemberUpdated{Chat: tg.Chat{ID: 777, Type: "private"}}
	blocked.NewChatMember.Status = "kicked"
	h.update(t, tg.Update{MyChatMember: blocked})
	if _, ok := h.sub(t); ok || len(h.tg.Sent) != sent {
		t.Fatal("blocking must delete the subscription without a reply")
	}
}

func TestTelegramIgnoresGroupsAndDuplicates(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	h.update(t, tg.Update{Message: &tg.InboundMessage{Chat: tg.Chat{ID: -100, Type: "group"}, Text: "zona 3"}})
	if len(h.tg.Sent) != 0 || len(h.store.Subs) != 0 {
		t.Fatal("group messages must be ignored")
	}
	u := tg.Update{UpdateID: 99, Message: &tg.InboundMessage{Chat: tg.Chat{ID: 777, Type: "private"}, Text: "zona 3"}}
	for range 2 {
		if err := h.bot.HandleTelegram(context.Background(), u); err != nil {
			t.Fatal(err)
		}
	}
	if len(h.tg.Sent) != 1 {
		t.Fatalf("a redelivered update must be ignored: %d replies", len(h.tg.Sent))
	}
}

func TestTelegramIsNotLimitedByTheWhatsAppCap(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	h.bot.NightCap = 1
	h.send(t, text("zona 6"))
	h.say(t, "zona 6")
	if _, ok := h.sub(t); !ok {
		t.Fatal("Meta's limit must not refuse Telegram subscriptions")
	}
}

func TestTelegramHTML(t *testing.T) {
	got := telegramHTML("<script> & *Zona 4*: _Las Juntas_ en https://aguagdl.com/privacidad")
	want := "&lt;script&gt; &amp; <b>Zona 4</b>: <i>Las Juntas</i> en https://aguagdl.com/privacidad"
	if got != want {
		t.Errorf("got  %s\nwant %s", got, want)
	}
}

func TestWriteToCongressIsTelegramOnly(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	if m := h.say(t, "/escribe"); !strings.Contains(m.Text, "https://aguagdl.test/escribe") {
		t.Errorf("/escribe: %s", m.Text)
	}
	if m := h.say(t, "congreso"); !strings.Contains(m.Text, "https://aguagdl.test/escribe") {
		t.Errorf("Telegram CONGRESO: %s", m.Text)
	}
	if got := h.send(t, text("congreso")); strings.Contains(got, "/escribe") {
		t.Errorf("WhatsApp must not link /escribe: %s", got)
	}
	if got := h.send(t, text("ayuda")); strings.Contains(got, "ESCRIBIR") {
		t.Errorf("WhatsApp help must not offer ESCRIBIR: %s", got)
	}
	if m := h.say(t, "ayuda"); !strings.Contains(m.Text, "ESCRIBIR") {
		t.Errorf("Telegram help: %s", m.Text)
	}
}
