package bot

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"strings"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/colonias"
	"aguagdl/api/internal/fake"
	"aguagdl/api/internal/geo"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/wa"
)

type harness struct {
	bot    *Bot
	store  *fake.Store
	sender *fake.Sender
	n      int
}

func newHarness(t *testing.T, now string) *harness {
	t.Helper()
	loc, _ := time.LoadLocation("America/Mexico_City")
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		t.Fatal(err)
	}
	zones, _ := geo.Load(data.Zonas)
	cols, _ := colonias.Load(data.Colonias)
	if err := cols.LoadOthers(data.OtrasColonias); err != nil {
		t.Fatal(err)
	}
	at, _ := time.ParseInLocation("2006-01-02 15:04", now, loc)
	h := &harness{store: fake.NewStore(), sender: &fake.Sender{}}
	h.bot = &Bot{Store: h.store, Sender: h.sender, Schedule: sched, Zones: zones, Colonias: cols,
		BaseURL: "https://aguagdl.test", ReminderHour: 20, RemindersOn: true, Now: func() time.Time { return at },
		Log: slog.New(slog.NewTextHandler(io.Discard, nil))}
	return h
}

func (h *harness) send(t *testing.T, m wa.Inbound) string {
	t.Helper()
	return h.sendFrom(t, m, "MX.42", "5213300000000")
}

func (h *harness) sendFrom(t *testing.T, m wa.Inbound, userID, phone string) string {
	t.Helper()
	h.n++
	m.ID = "wamid.in." + string(rune('a'+h.n))
	m.From, m.FromUserID = phone, userID
	p := wa.Payload{Entry: []wa.Entry{{Changes: []wa.Change{{Field: "messages", Value: wa.Value{Messages: []wa.Inbound{m}}}}}}}
	if err := h.bot.Handle(context.Background(), p); err != nil {
		t.Fatal(err)
	}
	return h.sender.Last()
}

func text(s string) wa.Inbound { return wa.Inbound{Type: "text", Text: &wa.InboundText{Body: s}} }

func TestSubscribeByZone(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	got := h.send(t, text("zona 4"))
	if h.store.Subs["MX.42"].Zone != 4 {
		t.Fatal("not subscribed")
	}
	for _, want := range []string{"*Zona 4*", "lunes y jueves", "Próximo aviso: *hoy, 8 p. m.* (corte del jueves 15 de octubre)"} {
		if !strings.Contains(got, want) {
			t.Errorf("missing %q in:\n%s", want, got)
		}
	}
}

func TestLateSubscriberIsWarnedAboutTomorrow(t *testing.T) {
	h := newHarness(t, "2026-10-14 21:30")
	got := h.send(t, text("ZONA 2"))
	if !strings.Contains(got, "¡Ojo! *Mañana jueves 15 de octubre* hay corte") || !strings.Contains(got, "(cortes del domingo 18, martes 20 y jueves 22 de octubre)") {
		t.Errorf("unexpected:\n%s", got)
	}
}

func TestColoniaFlows(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	if got := h.send(t, text("Americana")); !strings.Contains(got, "varios acueductos") {
		t.Errorf("multi-zone colonia should ask for location:\n%s", got)
	}
	if got := h.send(t, text("chapalitta")); got != msgPickColonia {
		t.Errorf("fuzzy match should offer a list, got:\n%s", got)
	}
	if got := h.send(t, text("Colonia que no existe xyz")); !strings.Contains(got, "No encontré") {
		t.Errorf("unexpected:\n%s", got)
	}
	h.send(t, wa.Inbound{Type: "interactive", Interactive: &wa.InboundInteract{ListReply: &wa.Reply{ID: "Z:5"}}})
	if h.store.Subs["MX.42"].Zone != 5 {
		t.Error("list reply did not subscribe")
	}
}

func TestLocation(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.send(t, wa.Inbound{Type: "location", Location: &wa.Location{Latitude: 20.6767, Longitude: -103.3475}})
	if h.store.Subs["MX.42"].Zone != 6 {
		t.Errorf("Catedral should subscribe to zone 6, got %+v", h.store.Subs)
	}
	if got := h.send(t, wa.Inbound{Type: "location", Location: &wa.Location{Latitude: 20.295, Longitude: -103.256}}); got != msgOutside {
		t.Errorf("unexpected:\n%s", got)
	}
}

func TestReportAndUnsubscribe(t *testing.T) {
	h := newHarness(t, "2026-10-18 20:30")
	h.send(t, text("zona 4"))
	if h.store.Subs["MX.42"].Phone != "5213300000000" {
		t.Error("phone not stored")
	}
	if got := h.send(t, text("reportar")); !strings.Contains(got, "jueves 15 de octubre") {
		t.Errorf("REPORTAR should ask about the last cut:\n%s", got)
	}
	h.send(t, wa.Inbound{Type: "interactive", Interactive: &wa.InboundInteract{ListReply: &wa.Reply{ID: "R:2026-10-15:no_regreso"}}})
	if len(h.store.Reports) != 1 || h.store.Reports[0].Answer != "no_regreso" || h.store.Reports[0].Zone != 4 {
		t.Errorf("report not saved: %+v", h.store.Reports)
	}
	if got := h.send(t, wa.Inbound{Type: "interactive", Interactive: &wa.InboundInteract{ListReply: &wa.Reply{ID: "R:2026-10-16:normal"}}}); got != msgReportClosed {
		t.Error("a day that wasn't a cut for zone 4 must be rejected")
	}
	if got := h.send(t, wa.Inbound{Type: "button", Button: &wa.Button{Payload: "BAJA"}}); got != msgUnsubscribed || len(h.store.Subs) != 0 {
		t.Error("BAJA did not unsubscribe")
	}
}

func TestDuplicateDeliveryIsIgnored(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	m := text("hola")
	m.ID, m.FromUserID = "wamid.dup", "MX.42"
	p := wa.Payload{Entry: []wa.Entry{{Changes: []wa.Change{{Field: "messages", Value: wa.Value{Messages: []wa.Inbound{m}}}}}}}
	for range 2 {
		if err := h.bot.Handle(context.Background(), p); err != nil {
			t.Fatal(err)
		}
	}
	if len(h.sender.Sent) != 1 {
		t.Errorf("sent %d replies, want 1", len(h.sender.Sent))
	}
}

func TestEdgeTexts(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	if got := h.send(t, text("zona 8")); !strings.Contains(got, "ZONA 1* a *ZONA 7") {
		t.Errorf("zona 8 should get help, got:\n%s", got)
	}
	if got := h.send(t, text("Hola, quiero recibir avisos de agua")); got != msgWelcome(h.bot.BaseURL, store.WhatsApp) {
		t.Errorf("prefilled wa.me text should get the welcome, got:\n%s", got)
	}
	if got := h.send(t, text("Tlaquepaque")); got != msgMunicipio("Tlaquepaque") || len(h.store.Subs) != 0 {
		t.Errorf("a municipio spans zones and must not subscribe, got:\n%s", got)
	}
	if got := h.send(t, text("zapopan")); got != msgMunicipio("Zapopan") {
		t.Errorf("unexpected:\n%s", got)
	}
	if got := h.send(t, text("Pipa")); got != msgPipa("https://aguagdl.test") {
		t.Errorf("unexpected:\n%s", got)
	}
	if got := h.send(t, text(strings.Repeat("agua ", 20))); got != msgHelp(h.bot.BaseURL, store.WhatsApp) {
		t.Errorf("a long text must get help, not be echoed:\n%s", got)
	}
}

type failingSender struct{ err error }

func (f failingSender) Send(context.Context, wa.Message) (string, error) { return "", f.err }

func TestPermanentSendErrorIsNotRetried(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.bot.Sender = failingSender{&wa.APIError{Status: 400, Code: 131026, Message: "undeliverable"}}
	p := wa.Payload{Entry: []wa.Entry{{Changes: []wa.Change{{Field: "messages", Value: wa.Value{Messages: []wa.Inbound{{ID: "w1", FromUserID: "MX.1", Type: "text", Text: &wa.InboundText{Body: "hola"}}}}}}}}}
	if err := h.bot.Handle(context.Background(), p); err != nil {
		t.Errorf("permanent error should be swallowed, got %v", err)
	}
	h.bot.Sender = failingSender{&wa.APIError{Status: 500}}
	p.Entry[0].Changes[0].Value.Messages[0].ID = "w2"
	if err := h.bot.Handle(context.Background(), p); err != nil || len(h.store.Replies) != 0 {
		t.Errorf("a server error may have delivered the reply, so it isn't kept for a retry: %v %d", err, len(h.store.Replies))
	}
}

func TestTemplateButtonByText(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.send(t, text("zona 2"))
	h.send(t, wa.Inbound{Type: "button", Button: &wa.Button{Payload: "Dejar de recibir avisos", Text: "Dejar de recibir avisos"}})
	if len(h.store.Subs) != 0 {
		t.Error("button text should unsubscribe too")
	}
}

func TestResubscribeAfterBaja(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.send(t, text("zona 3"))
	h.send(t, text("baja"))
	if got := h.send(t, text("hola")); got != msgWelcome(h.bot.BaseURL, store.WhatsApp) {
		t.Errorf("after BAJA, HOLA should start over:\n%s", got)
	}
	h.send(t, text("zona 5"))
	if h.store.Subs["MX.42"].Zone != 5 {
		t.Error("could not resubscribe")
	}
}

func TestReplyFailureCannotReplaySubscriptionAfterBaja(t *testing.T) {
	h := newHarness(t, "2026-10-18 20:00")
	m := text("ZONA 4")
	m.ID, m.From, m.FromUserID = "original-zone-message", "5213300000000", "MX.42"
	p := wa.Payload{Entry: []wa.Entry{{Changes: []wa.Change{{Field: "messages", Value: wa.Value{Messages: []wa.Inbound{m}}}}}}}
	h.bot.Sender = failingSender{errors.New("reply timeout")}
	if err := h.bot.Handle(context.Background(), p); err != nil {
		t.Fatalf("a reply that may have been delivered is dropped, not retried: %v", err)
	}
	if len(h.store.Subs) != 1 || !h.store.SeenIDs[m.ID] {
		t.Fatal("command and processed marker must be committed before replying")
	}
	h.bot.Sender = h.sender
	h.send(t, text("BAJA"))
	before := len(h.sender.Sent)
	if err := h.bot.Handle(context.Background(), p); err != nil {
		t.Fatal(err)
	}
	if len(h.store.Subs) != 0 || len(h.sender.Sent) != before {
		t.Fatal("retried command must not reactivate subscription or send a stale confirmation")
	}
}

func TestTwinColoniaListPicksTheRightZone(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	if got := h.send(t, text("Jardines del Sauz")); got != msgPickColonia {
		t.Fatalf("two colonias share the name, got:\n%s", got)
	}
	var id string
	for _, row := range h.sender.Sent[len(h.sender.Sent)-1].Interactive.Action.Sections[0].Rows {
		if row.Title == "JARDINES DEL SAUZ" {
			id = row.ID
		}
	}
	h.send(t, wa.Inbound{Type: "interactive", Interactive: &wa.InboundInteract{ListReply: &wa.Reply{ID: id}}})
	if h.store.Subs["MX.42"].Zone != 6 {
		t.Errorf("Jardines del Sauz is zone 6, got %+v", h.store.Subs["MX.42"])
	}
}

func TestReminderDeliveryFailureAlerts(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	var alerts []string
	h.bot.Alert = func(_ context.Context, msg string) { alerts = append(alerts, msg) }
	h.store.Wamids["wamid.reminder"] = true
	statuses := []wa.Status{{ID: "wamid.reminder", Status: "failed"}, {ID: "wamid.reply", Status: "failed"}, {ID: "wamid.reminder", Status: "read"}}
	p := wa.Payload{Entry: []wa.Entry{{Changes: []wa.Change{{Field: "messages", Value: wa.Value{Statuses: statuses}}}}}}
	if err := h.bot.Handle(context.Background(), p); err != nil {
		t.Fatal(err)
	}
	if len(alerts) != 1 {
		t.Errorf("only the failed reminder should alert, got %v", alerts)
	}
}

func TestReactionGetsNoReply(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.send(t, wa.Inbound{Type: "reaction"})
	if len(h.sender.Sent) != 0 {
		t.Fatalf("a reaction to a reminder must not get a reply: %+v", h.sender.Sent)
	}
}

func TestIgnoresOtherPhoneNumbers(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.bot.PhoneNumberID = "1318161744724814"
	m := text("zona 4")
	m.ID, m.From, m.FromUserID = "wamid.test", "5213300000000", "MX.42"
	p := wa.Payload{Entry: []wa.Entry{{Changes: []wa.Change{{Field: "messages", Value: wa.Value{
		Metadata: wa.Metadata{PhoneNumberID: "1451624204690902"}, Messages: []wa.Inbound{m}}}}}}}
	if err := h.bot.Handle(context.Background(), p); err != nil {
		t.Fatal(err)
	}
	if len(h.sender.Sent) != 0 || len(h.store.Subs) != 0 {
		t.Fatal("a message to Meta's test number must not be answered from the production number")
	}
}

func TestFollowsANumberChange(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.send(t, text("zona 4"))
	sent := len(h.sender.Sent)
	system := func(id string, sys wa.System) {
		m := wa.Inbound{ID: id, From: "5213300000000", Type: "system", System: &sys}
		p := wa.Payload{Entry: []wa.Entry{{Changes: []wa.Change{{Field: "messages", Value: wa.Value{Messages: []wa.Inbound{m}}}}}}}
		if err := h.bot.Handle(context.Background(), p); err != nil {
			t.Fatal(err)
		}
	}
	system("wamid.sys1", wa.System{Type: "user_changed_number", WaID: "5213311111111", UserID: "MX.99", PreviousUserID: "MX.42"})
	s, ok := h.store.Subs["MX.99"]
	if _, old := h.store.Subs["MX.42"]; old || !ok || s.Zone != 4 || s.Phone != "5213311111111" {
		t.Fatalf("the subscription must follow the new number: %+v", h.store.Subs)
	}
	system("wamid.sys2", wa.System{Type: "user_changed_user_id", UserID: "MX.100", PreviousUserID: "MX.99"})
	if s := h.store.Subs["MX.100"]; s.Zone != 4 || s.Phone != "" || len(h.store.Subs) != 1 {
		t.Fatalf("without a shareable number the old one must not be kept: %+v", h.store.Subs)
	}
	if len(h.sender.Sent) != sent {
		t.Error("system messages get no reply")
	}
}

func TestNoReminderPromisedWhileTheyAreOff(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.bot.RemindersOn = false
	got := h.send(t, text("zona 4"))
	if strings.Contains(got, "Próximo aviso") || !strings.Contains(got, "empiezan en unos días") || !strings.Contains(got, "Mañana jueves 15 de octubre") {
		t.Errorf("with reminders off, warn about tomorrow's cut and promise no reminder:\n%s", got)
	}
}

func TestRefusesSubscriptionsPastTheNightlyCap(t *testing.T) {
	ctx := context.Background()
	h := newHarness(t, "2026-10-14 10:00")
	h.bot.NightCap = 2
	h.store.Subscribe(ctx, store.WhatsApp, "MX.1", "1", 4)
	h.store.Subscribe(ctx, store.WhatsApp, "MX.2", "2", 4)
	if got := h.send(t, text("zona 6")); got != msgFull(h.bot.BaseURL) || len(h.store.Subs) != 2 {
		t.Fatalf("Monday night already reminds 2 people in zone 4; zone 6 is cut Monday too:\n%s", got)
	}
	if got := h.send(t, text("zona 3")); !strings.Contains(got, "¡Listo!") {
		t.Fatalf("zone 3 (Wednesday, Saturday) still has room:\n%s", got)
	}
	h.store.Unsubscribe(ctx, store.WhatsApp, "MX.42", "")
	h.store.Unsubscribe(ctx, store.WhatsApp, "MX.2", "")
	h.store.Subscribe(ctx, store.WhatsApp, "MX.42", "5213300000000", 4)
	if got := h.send(t, text("zona 6")); !strings.Contains(got, "¡Listo!") {
		t.Fatalf("moving from zone 4 to 6 doesn't add anyone to Monday:\n%s", got)
	}
}

func TestZoneLabels(t *testing.T) {
	if got := msgPickZone("MEDRANO", []int{3}); !strings.Contains(got, "solo la lista en la zona 3") {
		t.Errorf("one zone:\n%s", got)
	}
	if got := msgPickZone("AMERICANA", []int{1, 5, 6}); !strings.Contains(got, "(zonas 1, 5 y 6)") {
		t.Errorf("several zones:\n%s", got)
	}
	h := newHarness(t, "2026-10-14 10:00")
	h.send(t, text("chapalit"))
	m := h.sender.Sent[len(h.sender.Sent)-1]
	if m.Interactive == nil || !strings.Contains(m.Interactive.Action.Sections[0].Rows[0].Description, " · Zona") {
		t.Fatalf("list rows should read like «Guadalajara · Zona 5»: %+v", m.Interactive)
	}
}

func TestANumberBelongsToItsLatestSubscriber(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.sendFrom(t, text("zona 4"), "MX.1", "5213300000000")
	h.sendFrom(t, text("zona 6"), "MX.2", "5213300000000")
	if len(h.store.Subs) != 1 || h.store.Subs["MX.2"].Zone != 6 {
		t.Fatalf("a recycled number moves to its new owner: %+v", h.store.Subs)
	}
	if got := h.sendFrom(t, text("baja"), "MX.2", "5213300000000"); got != msgUnsubscribed || len(h.store.Subs) != 0 {
		t.Fatalf("BAJA must leave nothing sending to the number: %q %+v", got, h.store.Subs)
	}
}

func TestBajaWithoutUserIDUsesThePhone(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.send(t, text("zona 4"))
	if got := h.sendFrom(t, text("baja"), "", "5213300000000"); got != msgUnsubscribed || len(h.store.Subs) != 0 {
		t.Fatalf("got %q, subs %+v", got, h.store.Subs)
	}
}

func TestNumberChangeIntoAHeldNumberLeavesOneRow(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	h.sendFrom(t, text("zona 4"), "MX.1", "5213311111111")
	h.sendFrom(t, text("zona 6"), "MX.2", "5213322222222")
	m := wa.Inbound{ID: "wamid.sys", From: "5213311111111", FromUserID: "MX.1", Type: "system",
		System: &wa.System{Type: "user_changed_user_id", UserID: "MX.3", WaID: "5213322222222"}}
	p := wa.Payload{Entry: []wa.Entry{{Changes: []wa.Change{{Field: "messages", Value: wa.Value{Messages: []wa.Inbound{m}}}}}}}
	if err := h.bot.Handle(context.Background(), p); err != nil {
		t.Fatal(err)
	}
	if s, ok := h.store.Subs["MX.3"]; len(h.store.Subs) != 1 || !ok || s.Zone != 4 || s.Phone != "5213322222222" {
		t.Fatalf("MX.1's subscription moves to the number and MX.2's stale row goes: %+v", h.store.Subs)
	}
}

func TestManualReminderMatchesTheTemplate(t *testing.T) {
	got := ManualReminder("viernes 16 de octubre", 6)
	for _, want := range []string{"*Mañana viernes 16 de octubre*", "*Zona 6*", "puede bajar la presión o faltar el agua hasta por un día", MapURL, "*BAJA*"} {
		if !strings.Contains(got, want) {
			t.Errorf("missing %q in:\n%s", want, got)
		}
	}
}

func TestWordingAgreesInNumber(t *testing.T) {
	if got := msgOtherColonia("HERNANDEZ ROMO", "Guadalajara", []int{2, 3}); !strings.Contains(got, "dentro del mapa de las zonas 2 y 3") {
		t.Errorf("two zones:\n%s", got)
	}
	if got := msgOtherColonia("VALLARTA NORTE", "Guadalajara", []int{6}); !strings.Contains(got, "dentro del mapa de la zona 6") {
		t.Errorf("one zone:\n%s", got)
	}
	tue := time.Date(2026, 10, 20, 0, 0, 0, 0, time.UTC)
	if got := msgNotice([]time.Time{tue}, 4); !strings.Contains(got, "Se acerca el corte en la Zona 4") {
		t.Errorf("one cut:\n%s", got)
	}
	if got := msgNotice([]time.Time{tue, tue.AddDate(0, 0, 1)}, 5); !strings.Contains(got, "Se acercan los cortes en la Zona 5") {
		t.Errorf("a block:\n%s", got)
	}
}

func TestColoniaOffTheList(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	if got := h.send(t, text("Jardín Real")); !strings.Contains(got, "*JARDIN REAL* (Zapopan) no está en la lista") || !strings.Contains(got, "no le toca racionamiento") {
		t.Errorf("a colonia outside the rotation should say so, got:\n%s", got)
	}
	if len(h.store.Subs) != 0 {
		t.Error("must not subscribe")
	}
}

func TestNeverSubscribesToAZoneWithoutDays(t *testing.T) {
	h := newHarness(t, "2026-10-14 10:00")
	loc, _ := time.LoadLocation("America/Mexico_City")
	sched, err := rotation.Load([]byte(`{"start": "2026-10-15", "end": "2027-03-31", "zones": {"3": ["wed", "sat"], "4": ["mon", "thu"]}}`), loc)
	if err != nil {
		t.Fatal(err)
	}
	cols, err := colonias.Load([]byte(`[{"name": "PRUEBA SIN ZONA", "municipio": "GUADALAJARA", "zones": [], "multi": false},
		{"name": "PRUEBA SEIS", "municipio": "GUADALAJARA", "zones": [6], "multi": false},
		{"name": "PRUEBA TRES", "municipio": "GUADALAJARA", "zones": [3, 4, 6], "multi": true},
		{"name": "PRUEBA ASTERISCO", "municipio": "GUADALAJARA", "zones": [4], "multi": true},
		{"name": "PRUEBA PARTIDA", "municipio": "GUADALAJARA", "zones": [4, 6], "multi": true}]`))
	if err != nil {
		t.Fatal(err)
	}
	h.bot.Schedule, h.bot.Colonias = sched, cols
	for _, name := range []string{"prueba sin zona", "prueba seis"} {
		if got := h.send(t, text(name)); !strings.HasPrefix(got, "No tengo días de corte para *PRUEBA") {
			t.Errorf("%s: a colonia without a zone that has days is outside the rotation, got:\n%s", name, got)
		}
	}
	// Two zones with days are left to pick from; SIAPA's * on a colonia it lists in one zone,
	// all with days, still asks, as before.
	for name, want := range map[string]string{"prueba tres": "Z:3 Z:4", "prueba asterisco": "Z:4"} {
		h.send(t, text(name))
		var ids []string
		if m := h.sender.Sent[len(h.sender.Sent)-1]; m.Interactive != nil {
			for _, row := range m.Interactive.Action.Sections[0].Rows {
				ids = append(ids, row.ID)
			}
		}
		if got := strings.Join(ids, " "); got != want {
			t.Errorf("%s: choices %q, want %q", name, got, want)
		}
	}
	// Catedral is in zone 6, which this rotation doesn't have.
	if got := h.send(t, wa.Inbound{Type: "location", Location: &wa.Location{Latitude: 20.6767, Longitude: -103.3475}}); got != msgOutside {
		t.Errorf("unexpected:\n%s", got)
	}
	if got := h.send(t, text("zona 6")); got != msgHelp(h.bot.BaseURL, store.WhatsApp) {
		t.Errorf("unexpected:\n%s", got)
	}
	if len(h.store.Subs) != 0 {
		t.Fatalf("subscribed to a zone without days: %+v", h.store.Subs)
	}
	// With one zone with days left, there's nothing to pick.
	h.send(t, text("prueba partida"))
	if s, ok := h.store.Subs["MX.42"]; !ok || s.Zone != 4 {
		t.Errorf("a split colonia with one zone with days subscribes to it: %+v", h.store.Subs)
	}
	h.send(t, wa.Inbound{Type: "location", Location: &wa.Location{Latitude: 20.6597, Longitude: -103.3496}})
	if s, ok := h.store.Subs["MX.42"]; !ok || s.Zone != 3 {
		t.Errorf("a location in zone 3 still subscribes: %+v", h.store.Subs)
	}
}

func TestColoniaButtonsFitTelegram(t *testing.T) {
	var list []struct{ Name string }
	if err := json.Unmarshal(data.Colonias, &list); err != nil {
		t.Fatal(err)
	}
	cols, err := colonias.Load(data.Colonias)
	if err != nil {
		t.Fatal(err)
	}
	// Only SIAPA's list becomes buttons; the other colonias are answered in text.
	ids := map[string]bool{}
	for _, c := range list {
		matches, exact := cols.Search(c.Name, 0)
		if !exact {
			t.Fatalf("%s doesn't find itself", c.Name)
		}
		for _, choice := range coloniaChoices(matches) {
			if n := len(choice.ID); n > 64 {
				t.Errorf("%q is %d bytes; Telegram's callback data takes 64", choice.ID, n)
			}
			ids[choice.ID] = true
		}
	}
	if len(ids) != len(list) {
		t.Errorf("checked %d buttons for %d colonias", len(ids), len(list))
	}
}

func TestNextMessageCoversTheWholeBlock(t *testing.T) {
	cases := []struct{ now, want, notWant string }{
		{"2026-10-19 10:00", "Próximo aviso: *hoy, 8 p. m.* (cortes del martes 20 y miércoles 21 de octubre)", "¡Ojo!"},
		{"2026-10-19 21:00", "¡Ojo! *Mañana martes 20 de octubre* hay corte, y también el miércoles 21 de octubre.", "cortes del martes"},
		{"2026-10-20 10:00", "¡Ojo! *Mañana miércoles 21 de octubre* hay corte.", "Próximo aviso: *hoy"},
	}
	for _, c := range cases {
		h := newHarness(t, c.now)
		got := h.send(t, text("zona 5"))
		if !strings.Contains(got, c.want) || strings.Contains(got, c.notWant) {
			t.Errorf("%s: want %q and not %q in:\n%s", c.now, c.want, c.notWant, got)
		}
		if c.now != "2026-10-19 10:00" && !strings.Contains(got, "Próximo aviso: *viernes 23 de octubre, 8 p. m.* (corte del sábado 24 de octubre)") {
			t.Errorf("%s: no reminder comes in the middle of a block, so the next one is Friday's:\n%s", c.now, got)
		}
	}
}

func TestTelegramPromisesTheNoticeTwoDaysBefore(t *testing.T) {
	h := newTGHarness(t, "2026-10-19 21:00")
	m := h.say(t, "/start z5")
	for _, want := range []string{"dos días antes y otra vez la noche antes", "Próximo aviso: <b>jueves 22 de octubre, 8 p. m.</b> (corte del sábado 24 de octubre)"} {
		if !strings.Contains(m.Text, want) {
			t.Errorf("missing %q in:\n%s", want, m.Text)
		}
	}
}
