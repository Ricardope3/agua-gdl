package bot

import (
	"context"
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
	at, _ := time.ParseInLocation("2006-01-02 15:04", now, loc)
	h := &harness{store: fake.NewStore(), sender: &fake.Sender{}}
	h.bot = &Bot{Store: h.store, Sender: h.sender, Schedule: sched, Zones: zones, Colonias: cols,
		BaseURL: "https://aguagdl.test", ReminderHour: 20, Now: func() time.Time { return at },
		Log: slog.New(slog.NewTextHandler(io.Discard, nil))}
	return h
}

func (h *harness) send(t *testing.T, m wa.Inbound) string {
	t.Helper()
	h.n++
	m.ID = "wamid.in." + string(rune('a'+h.n))
	m.From, m.FromUserID = "5213300000000", "MX.42"
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
	if !strings.Contains(got, "¡Ojo! *Mañana jueves 15 de octubre* hay corte") || !strings.Contains(got, "corte del domingo 18 de octubre") {
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
	if got := h.send(t, text("Hola, quiero recibir avisos de agua")); got != msgWelcome(h.bot.BaseURL) {
		t.Errorf("prefilled wa.me text should get the welcome, got:\n%s", got)
	}
	if got := h.send(t, text("Tlaquepaque")); got != msgMunicipio("Tlaquepaque") || len(h.store.Subs) != 0 {
		t.Errorf("a municipio spans zones and must not subscribe, got:\n%s", got)
	}
	if got := h.send(t, text("zapopan")); got != msgMunicipio("Zapopan") {
		t.Errorf("unexpected:\n%s", got)
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
	if err := h.bot.Handle(context.Background(), p); err == nil {
		t.Error("server error should make Meta retry")
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
	if got := h.send(t, text("hola")); got != msgWelcome(h.bot.BaseURL) {
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
	if err := h.bot.Handle(context.Background(), p); err == nil {
		t.Fatal("expected reply failure")
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
