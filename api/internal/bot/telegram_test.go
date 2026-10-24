package bot

import (
	"context"
	"fmt"
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
	SignButtons("test")
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
	if m.ChatID != 777 || m.ParseMode != "HTML" || !strings.Contains(m.Text, "te aviso por Telegram") || !strings.Contains(m.Text, "<b>Agua GDL</b>") || !strings.Contains(m.Text, "https://aguagdl.test/reportes") {
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
	if _, ok := m.ReplyMarkup.(tg.RemoveKeyboard); !ok || !strings.Contains(m.Text, "<b>Zona 6</b>") || !strings.Contains(m.Text, "tu ID de usuario de Telegram") {
		t.Errorf("confirmation: %+v", m)
	}
	if got := h.say(t, "/start z9"); !strings.Contains(got.Text, "Estás suscrito a los avisos de la <b>Zona 6</b>") {
		t.Errorf("a bad deep link should greet, got:\n%s", got.Text)
	}
}

func TestTypedAnswersPointToTheButtons(t *testing.T) {
	h := newTGHarness(t, "2026-10-19 21:00")
	h.say(t, "/start z5")
	for _, text := range []string{"Ya no", "ya no.", "Sí", "No hay agua", "Poca", "Baja presión", "Ya regresó"} {
		m := h.say(t, text)
		if s, ok := h.sub(t); !ok || s.Zone != 5 {
			t.Fatalf("%q changed the subscription: %+v %v", text, s, ok)
		}
		// The bot can't tell a «no» to a reminder from a «no» to «¿Es la tuya?» about a colonia.
		if !strings.Contains(m.Text, "toca uno de los botones") || !strings.Contains(m.Text, "<b>BAJA</b>") || !strings.Contains(m.Text, "Si es sobre tu colonia") {
			t.Errorf("%q: %s", text, m.Text)
		}
	}
	h.say(t, "baja")
	if _, ok := h.sub(t); ok {
		t.Fatal("BAJA still unsubscribes")
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
	if s, ok := h.sub(t); !ok || s.Zone != 3 {
		t.Errorf("a location in zone 3 moves the subscription there: %+v", s)
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
	if !ok || len(kb.InlineKeyboard) != 4 || !strings.HasPrefix(kb.InlineKeyboard[1][0].CallbackData, "R:6:2026-10-16:baja:") || len(kb.InlineKeyboard[1][0].CallbackData) > 64 {
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

func TestNoSubscriptionsOnceTheRotationIsOver(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	_, end := h.bot.Schedule.Span()
	h.bot.Now = func() time.Time { return end.Add(24*time.Hour - time.Minute) }
	m := h.say(t, "zona 4")
	if s, ok := h.sub(t); !ok || s.Zone != 4 || !strings.Contains(m.Text, "<b>ZONA 1</b> a <b>ZONA 7</b> para cambiar de zona") {
		t.Fatalf("the rotation's last day still takes subscriptions and zone changes: %+v %v\n%s", s, ok, m.Text)
	}
	h.bot.Now = func() time.Time { return end.AddDate(0, 0, 1) }
	if m := h.say(t, "zona 6"); !strings.Contains(m.Text, "ya terminó") {
		t.Fatalf("from the day after the end, no zone changes: %s", m.Text)
	}
	if s, _ := h.sub(t); s.Zone != 4 {
		t.Fatalf("zone %d, want 4", s.Zone)
	}
	if m := h.say(t, "hola"); !strings.Contains(m.Text, "Escribe <b>BAJA</b> para borrar tu suscripción.") || strings.Contains(m.Text, "ZONA 1") {
		t.Fatalf("once the rotation is over, the greeting offers BAJA, not zone changes: %s", m.Text)
	}
	h.say(t, "/baja")
	if _, ok := h.sub(t); ok {
		t.Fatal("BAJA still works")
	}
	if m := h.say(t, "zona 4"); !strings.Contains(m.Text, "ya terminó") {
		t.Fatalf("no new subscriptions once the rotation is over: %s", m.Text)
	}
	if _, ok := h.sub(t); ok {
		t.Fatal("subscribed after the rotation's end")
	}
	m = h.say(t, "/start")
	if _, asks := m.ReplyMarkup.(tg.ReplyKeyboard); asks || !strings.Contains(m.Text, "ya terminó") {
		t.Fatalf("/start says the rotation is over instead of asking for a location: %+v", m)
	}
}

func TestReportKeepsTheZoneOfTheCut(t *testing.T) {
	h := newTGHarness(t, "2026-10-18 09:00")
	h.say(t, "zona 4")
	kb, _ := h.say(t, "/reportar").ReplyMarkup.(tg.InlineKeyboard)
	h.say(t, "zona 6")
	h.press(t, kb.InlineKeyboard[0][0].CallbackData) // «Regresó normal», signed for zone 4's cut
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

func TestTypedMarkupIsShownBackPlain(t *testing.T) {
	h := newTGHarness(t, "2026-10-14 10:00")
	// As bold and italics, these would close out of order and Telegram would refuse the reply.
	if m := h.say(t, "*a _b* c_"); !strings.HasPrefix(m.Text, "No encontré «a b c»") {
		t.Fatalf("got %q", m.Text)
	}
}

func TestEveryMessageIsHTMLTelegramTakes(t *testing.T) {
	SignButtons("test")
	loc, _ := time.LoadLocation("America/Mexico_City")
	one := []time.Time{time.Date(2026, 10, 24, 0, 0, 0, 0, loc)}
	block := []time.Time{time.Date(2026, 10, 21, 0, 0, 0, 0, loc), time.Date(2026, 10, 23, 0, 0, 0, 0, loc), time.Date(2026, 10, 25, 0, 0, 0, 0, loc)}
	const base = "https://aguagdl.test"
	texts := []string{
		msgWelcome(base, store.Telegram), msgWelcome(base, store.WhatsApp), msgHelp(base, store.Telegram), msgHelp(base, store.WhatsApp),
		msgUseButtons, msgNotFound("*a _b* c_"), msgOutside, msgColoniaOutside("AMERICANA"), msgMunicipio("Tonalá"),
		msgPickColonia, msgPickOneColonia, msgOtherColonia("EL MIRADOR", "Tonalá", nil), msgOtherColonia("EL MIRADOR", "Tonalá", []int{5, 6}),
		msgOrOneOfThese, msgOrThisOne, msgPickZone("AMERICANA", []int{6}), msgPickZone("AMERICANA", []int{5, 6}), msgPickZoneAtPoint,
		msgPipa(base), msgWrite(base), msgFull(base), msgUnsubscribed, msgNotSubscribed, msgNoUserID, msgUnsupported,
		msgNoReportYet, msgReportClosed, msgReportBeforeJoin, msgRotationOver(base), msgAskReport("jueves 15 de octubre"), msgThanks,
		msgAskPlace, ScheduleChange(4, "lunes y jueves", "lunes 2 de noviembre"), ManualReminder("lunes 19 de octubre", 4),
		reminderBody("lunes 19 de octubre", 4), msgNotice(one, 3), msgNotice(block, 1), msgFollowUp(block, 1), msgReportMap(base),
		AvisosChange(base, 1, block), AvisosChange(base, 1, nil), msgTelegramReminder(one, 3), msgTelegramReminder(block, 1),
	}
	for _, a := range waterAnswers {
		texts = append(texts, a.thanks)
	}
	info := subscribedInfo{zone: 1, days: "miércoles, viernes y domingo", hour: "8 p. m.", base: base, channel: store.Telegram}
	fresh, under, off, over := info, info, info, info
	fresh.fresh, fresh.cutTomorrow, fresh.nextReminder, fresh.nextCut = true, block, "hoy", one
	under.cutsLeft, under.nextReminder, under.nextCut = block[1:], "lunes 26 de octubre", block
	off.off, off.channel = true, store.WhatsApp
	over.over, over.off = true, true
	for _, i := range []subscribedInfo{info, fresh, under, off, over} {
		texts = append(texts, msgSubscribed(i))
	}
	var msgs []tg.Message
	for _, text := range texts {
		m, err := TelegramMessage("777", Reply{Text: text})
		if err != nil {
			t.Fatal(err)
		}
		msgs = append(msgs, m)
	}
	for _, build := range []func(string, int, []time.Time) (tg.Message, error){TelegramReminder, TelegramNotice, TelegramFollowUp} {
		m, err := build("777", 7, block)
		if err != nil {
			t.Fatal(err)
		}
		msgs = append(msgs, m)
	}
	tel := &fake.Telegram{}
	for _, m := range msgs {
		if _, err := tel.Send(context.Background(), m); err != nil {
			t.Errorf("%v:\n%s", err, m.Text)
		}
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

func TestJoinInTheMiddleOfABlock(t *testing.T) {
	for _, c := range []struct{ now, zone, later string }{
		{"2026-10-23 10:00", "1", "domingo 25"}, // zone 1: Friday and Sunday are one block
		{"2026-10-18 10:00", "2", "martes 20"}, // zone 2: Sunday, Tuesday and Thursday
		{"2026-10-20 10:00", "2", "jueves 22"},
	} {
		h := newTGHarness(t, c.now)
		m := h.say(t, "/start z"+c.zone)
		if !strings.Contains(m.Text, "Hoy hay corte") || !strings.Contains(m.Text, c.later) || !strings.Contains(m.Text, "Próximo aviso") {
			t.Errorf("%s, zone %s: no message comes for the rest of the block (%s), so the confirmation names it:\n%s", c.now, c.zone, c.later, m.Text)
		}
	}
	h := newTGHarness(t, "2026-10-25 10:00")
	if m := h.say(t, "/start z1"); strings.Contains(m.Text, "Hoy hay corte") {
		t.Errorf("Sunday ends zone 1's block, so nothing is left to warn about: %s", m.Text)
	}
}

func TestMadeUpButtonsCantAnswerForAnotherZone(t *testing.T) {
	h := newTGHarness(t, "2026-10-19 21:00")
	h.say(t, "/start z2")
	s, _ := h.sub(t)
	h.store.Reminders[fmt.Sprintf("%d/2026-10-20", s.ID)] = true
	for _, data := range []string{"A:5:2026-10-20:no", "A:5:2026-10-20:no:AAAAAAAA"} { // zone 5 is cut that Tuesday too
		if m := h.press(t, data); !strings.Contains(m.Text, "ya cerró") {
			t.Errorf("%s: %s", data, m.Text)
		}
	}
	if len(h.store.Water) != 0 {
		t.Fatalf("a zone 2 subscriber answered for zone 5: %+v", h.store.Water)
	}
	m, err := TelegramReminder(s.UserID, 2, h.bot.Schedule.Block(2, h.bot.Schedule.Day(h.bot.Now()).AddDate(0, 0, 1)))
	if err != nil {
		t.Fatal(err)
	}
	h.press(t, m.ReplyMarkup.(tg.InlineKeyboard).InlineKeyboard[0][2].CallbackData) // ❌ No, as the reminder sends it
	if len(h.store.Water) != 1 || h.store.Water[0].Zone != 2 || h.store.Water[0].Answer != "no" {
		t.Fatalf("the reminder's own button: %+v", h.store.Water)
	}
	h = newTGHarness(t, "2026-10-16 09:00")
	h.say(t, "/start z6")
	h.press(t, "R:1:2026-10-16:baja") // zone 1 is cut that Friday too
	if len(h.store.Reports) != 0 {
		t.Fatalf("a zone 6 subscriber reported zone 1's cut: %+v", h.store.Reports)
	}
}

func TestWaterAnswersToTheReminder(t *testing.T) {
	h := newTGHarness(t, "2026-10-19 21:00")
	h.say(t, "/start z5")
	s, _ := h.sub(t)
	h.store.Reminders[fmt.Sprintf("%d/2026-10-20", s.ID)] = true // Monday's reminder for Tuesday and Wednesday
	if m := h.press(t, "A:5:2026-10-20:no"); !strings.Contains(m.Text, "33 3668 2482") || !strings.Contains(m.Text, "https://aguagdl.test/pipas") || !strings.Contains(m.Text, "https://aguagdl.test/reportes") {
		t.Errorf("«No» must say how to get a pipa and link the map of reports: %s", m.Text)
	}
	if m := h.press(t, "A:5:2026-10-20:poca"); !strings.Contains(m.Text, "https://aguagdl.test/reportes") {
		t.Errorf("«Poca» links the map of reports: %s", m.Text)
	}
	if len(h.store.Water) != 1 || h.store.Water[0].Answer != "poca" || h.store.Water[0].Zone != 5 {
		t.Fatalf("one answer per cut, the latest: %+v", h.store.Water)
	}
	loc, _ := time.LoadLocation("America/Mexico_City")
	h.bot.Now = func() time.Time { return time.Date(2026, 10, 21, 18, 0, 0, 0, loc) }
	if m := h.press(t, "A:5:2026-10-20:si"); !strings.Contains(m.Text, "Gracias") || strings.Contains(m.Text, "/reportes") || h.store.Water[0].Answer != "si" {
		t.Errorf("answers stay open until the run's last day: %s %+v", m.Text, h.store.Water)
	}
	h.bot.Now = func() time.Time { return time.Date(2026, 10, 22, 8, 0, 0, 0, loc) }
	if m := h.press(t, "A:5:2026-10-20:no"); !strings.Contains(m.Text, "ya cerró") || h.store.Water[0].Answer != "si" {
		t.Errorf("closed after the run: %s %+v", m.Text, h.store.Water)
	}
}

func TestOnlyTheRemindedSubscriptionCanAnswer(t *testing.T) {
	h := newTGHarness(t, "2026-10-19 21:00")
	h.say(t, "/start z5")
	s, _ := h.sub(t)
	h.store.Reminders[fmt.Sprintf("%d/2026-10-20", s.ID)] = true
	h.press(t, "A:5:2026-10-20:no")
	h.store.Now = h.bot.Now
	for range 3 {
		h.say(t, "/baja")
		h.say(t, "/start z5")
		if m := h.press(t, "A:5:2026-10-20:no"); !strings.Contains(m.Text, "ya cerró") {
			t.Fatalf("a subscription that wasn't sent the reminder can't answer it: %s", m.Text)
		}
	}
	if len(h.store.Water) != 1 {
		t.Fatalf("BAJA and subscribing again must not add answers: %+v", h.store.Water)
	}
}

func TestNoReminderPromisedToWhoeverHasNoWater(t *testing.T) {
	h := newTGHarness(t, "2026-10-18 21:00") // Sunday: the notice for zone 5's Tuesday block went out at 8 p.m.
	h.say(t, "/start z5")
	s, _ := h.sub(t)
	h.store.Notices[fmt.Sprintf("%d/previo:2026-10-20", s.ID)] = true
	h.press(t, "A:5:2026-10-20:no")
	loc, _ := time.LoadLocation("America/Mexico_City")
	h.bot.Now = func() time.Time { return time.Date(2026, 10, 19, 10, 0, 0, 0, loc) }
	m := h.say(t, "hola")
	for _, want := range []string{"<b>Mañana martes 20 de octubre</b> hay corte", "Próximo aviso: <b>jueves 22 de octubre, 8 p. m.</b> (corte del sábado 24 de octubre)"} {
		if !strings.Contains(m.Text, want) {
			t.Errorf("tonight's reminder skips whoever answered «No»: missing %q in:\n%s", want, m.Text)
		}
	}
	h.press(t, "A:5:2026-10-20:si")
	if m := h.say(t, "hola"); !strings.Contains(m.Text, "Próximo aviso: <b>hoy, 8 p. m.</b>") || strings.Contains(m.Text, "¡Ojo!") {
		t.Errorf("after «Sí» tonight's reminder comes:\n%s", m.Text)
	}

	// A zone change keeps the answer: zone 7's block starts on Saturday, as zone 3's cut does.
	h = newTGHarness(t, "2026-10-22 21:00")
	h.say(t, "/start z3")
	s, _ = h.sub(t)
	h.store.Notices[fmt.Sprintf("%d/previo:2026-10-24", s.ID)] = true
	h.press(t, "A:3:2026-10-24:no")
	h.bot.Now = func() time.Time { return time.Date(2026, 10, 23, 10, 0, 0, 0, loc) }
	m = h.say(t, "zona 7")
	if s, _ := h.sub(t); s.Zone != 7 || strings.Contains(m.Text, "Próximo aviso: <b>hoy") || !strings.Contains(m.Text, "<b>Mañana sábado 24 de octubre</b> hay corte") {
		t.Errorf("no reminder is promised after a zone change either:\n%s", m.Text)
	}
}

func TestAnswersOpenWithTheNotice(t *testing.T) {
	h := newTGHarness(t, "2026-10-18 21:00") // Sunday: the notice for Tuesday's block went out at 8 p.m.
	h.say(t, "/start z5")
	s, _ := h.sub(t)
	h.store.Notices[fmt.Sprintf("%d/previo:2026-10-20", s.ID)] = true
	if m := h.press(t, "A:5:2026-10-20:no"); !strings.Contains(m.Text, "33 3668 2482") || len(h.store.Water) != 1 {
		t.Fatalf("an answer to the notice counts: %s %+v", m.Text, h.store.Water)
	}
	loc, _ := time.LoadLocation("America/Mexico_City")
	h.bot.Now = func() time.Time { return time.Date(2026, 10, 17, 21, 0, 0, 0, loc) }
	if m := h.press(t, "A:5:2026-10-20:si"); !strings.Contains(m.Text, "ya cerró") || h.store.Water[0].Answer != "no" {
		t.Errorf("not before the notice's evening: %s %+v", m.Text, h.store.Water)
	}
}
