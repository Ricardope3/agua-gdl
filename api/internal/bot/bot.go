// Package bot answers WhatsApp messages: subscriptions, zone lookups, unsubscribes and cut reports.
package bot

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"time"

	"aguagdl/api/internal/colonias"
	"aguagdl/api/internal/geo"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/tg"
	"aguagdl/api/internal/wa"
)

type Store = store.BotStore

type Sender interface {
	Send(ctx context.Context, m wa.Message) (string, error)
}

type TelegramSender interface {
	Send(ctx context.Context, m tg.Message) (int64, error)
	AnswerCallback(ctx context.Context, id string) error
}

// User is who a message came from: a WhatsApp user (business-scoped ID and phone)
// or a Telegram chat.
type User struct {
	Channel string
	ID      string
	Phone   string
}

// Reply is one outgoing message; each channel renders it its own way.
type Reply struct {
	Text          string
	Choices       []Choice // a list on WhatsApp, buttons on Telegram
	Button        string   // the WhatsApp list's button label
	AskLocation   bool     // Telegram: show a button that shares the location
	CloseKeyboard bool     // Telegram: hide that button again
}

type Choice struct{ ID, Title, Description string }

type Bot struct {
	Store         Store
	Sender        Sender
	Schedule      *rotation.Schedule
	Zones         *geo.Zones
	Colonias      *colonias.Index
	BaseURL       string
	PhoneNumberID string // ignore webhooks for other numbers on the same app, e.g. Meta's test number
	ReminderHour  int
	RemindersOn   bool // WhatsApp reminders
	Telegram      TelegramSender
	TelegramOn    bool                                  // Telegram reminders
	NightCap      int                                   // refuse subscriptions that would push a night's reminders past this; 0 = no limit
	Alert         func(ctx context.Context, msg string) // optional, e.g. a failed heartbeat
	Now           func() time.Time
	Log           *slog.Logger

	queue *[]queued // replies held until the inbound message's transaction commits
}

type queued struct {
	to    User
	reply Reply
}

var (
	zoneRe      = regexp.MustCompile(`^(?:ZONA ?)?([1-7])$`)
	badZoneRe   = regexp.MustCompile(`^ZONA ?\d*$`)
	stopWords   = []string{"BAJA", "ALTO", "STOP", "CANCELAR", "DARME DE BAJA", "YA NO", "DEJAR DE RECIBIR AVISOS"}
	helpWords   = []string{"AYUDA", "MENU", "INFO", "OPCIONES"}
	reportWords = []string{"REPORTAR", "REPORTE", "REPORTAR CORTE"}
	pipaWords   = []string{"PIPA", "PIPAS", "PEDIR PIPA", "SIAPA", "SIAPATEL"}
	writeWords  = []string{"ESCRIBIR", "ESCRIBE", "CONGRESO", "DIPUTADOS"}
	greetWords  = []string{"HOLA", "BUENAS", "BUENOS DIAS", "BUENAS TARDES", "BUENAS NOCHES", "AVISOS", "INICIO", "EMPEZAR"}
	// Municipios span several zones; "TLAQUEPAQUE" is also a colonia in Guadalajara's zone 7.
	municipios = map[string]string{"GUADALAJARA": "Guadalajara", "ZAPOPAN": "Zapopan", "TLAQUEPAQUE": "Tlaquepaque", "SAN PEDRO TLAQUEPAQUE": "San Pedro Tlaquepaque", "TONALA": "Tonalá"}
)

// Handle processes one webhook payload. Returning an error makes Meta retry it later.
func (b *Bot) Handle(ctx context.Context, p wa.Payload) error {
	for _, e := range p.Entry {
		for _, c := range e.Changes {
			if c.Field != "messages" || (b.PhoneNumberID != "" && c.Value.Metadata.PhoneNumberID != "" && c.Value.Metadata.PhoneNumberID != b.PhoneNumberID) {
				continue
			}
			for _, st := range c.Value.Statuses {
				reminder, err := b.Store.UpdateStatus(ctx, st.ID, st.Status)
				if err != nil {
					return err
				}
				if st.Status != "failed" {
					continue
				}
				errs := fmt.Sprintf("%.200s", fmt.Sprint(st.Errors))
				b.Log.Warn("delivery failed", "reminder", reminder, "errors", errs)
				if reminder && b.Alert != nil {
					b.Alert(ctx, "a reminder was not delivered: "+errs)
				}
			}
			for _, m := range c.Value.Messages {
				if err := b.handleMessage(ctx, m, c.Value.Contacts); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

func (b *Bot) handleMessage(ctx context.Context, m wa.Inbound, contacts []wa.Contact) error {
	r := User{Channel: store.WhatsApp, ID: m.FromUserID, Phone: m.From}
	for _, c := range contacts {
		if r.ID == "" && c.WaID == m.From {
			r.ID = c.UserID
		}
	}
	return b.process(ctx, m.ID, func(w *Bot) error { return w.route(ctx, r, m) })
}

// process runs one inbound message. The command and its deduplication marker commit
// together before any HTTP call: a failed reply must never let a retried delivery
// replay a completed command.
func (b *Bot) process(ctx context.Context, id string, handle func(*Bot) error) error {
	var replies []queued
	err := b.Store.ProcessInbound(ctx, id, func(tx Store) error {
		worker := *b
		worker.Store, worker.queue = tx, &replies
		return handle(&worker)
	})
	if err != nil {
		return err
	}
	for _, q := range replies {
		if err := b.deliver(ctx, q.to, q.reply); err != nil {
			return err
		}
	}
	return nil
}

func (b *Bot) route(ctx context.Context, r User, m wa.Inbound) error {
	switch {
	case m.Type == "reaction":
		// A 👍 on a reminder needs no answer.
		return nil
	case m.Type == "system" && m.System != nil:
		return b.onUserChanged(ctx, r, m.System)
	case m.Type == "text" && m.Text != nil:
		return b.onText(ctx, r, m.Text.Body)
	case m.Type == "location" && m.Location != nil:
		return b.onLocation(ctx, r, m.Location.Latitude, m.Location.Longitude)
	case m.Type == "button" && m.Button != nil && m.Button.Payload == "BAJA":
		return b.unsubscribe(ctx, r)
	case m.Type == "button" && m.Button != nil:
		return b.onText(ctx, r, m.Button.Text)
	case m.Type == "interactive" && m.Interactive != nil && m.Interactive.ListReply != nil:
		return b.onPayload(ctx, r, m.Interactive.ListReply.ID)
	case m.Type == "interactive" && m.Interactive != nil && m.Interactive.ButtonReply != nil:
		return b.onPayload(ctx, r, m.Interactive.ButtonReply.ID)
	}
	return b.text(ctx, r, msgUnsupported)
}

func (b *Bot) onText(ctx context.Context, r User, body string) error {
	n := colonias.Normalize(body)
	switch {
	case n == "" || slices.Contains(helpWords, n):
		return b.text(ctx, r, msgHelp(b.BaseURL, r.Channel))
	case slices.Contains(stopWords, n):
		return b.unsubscribe(ctx, r)
	case slices.Contains(reportWords, n):
		return b.reportLastCut(ctx, r)
	case slices.Contains(pipaWords, n):
		return b.text(ctx, r, msgPipa)
	case slices.Contains(writeWords, n) && r.Channel == store.Telegram:
		return b.text(ctx, r, msgWrite(b.BaseURL))
	case zoneRe.MatchString(n):
		zone, _ := strconv.Atoi(zoneRe.FindStringSubmatch(n)[1])
		return b.subscribe(ctx, r, zone)
	case strings.HasPrefix(n, "HOLA ") || slices.Contains(greetWords, n):
		return b.greet(ctx, r)
	case municipios[n] != "":
		return b.text(ctx, r, msgMunicipio(municipios[n]))
	case badZoneRe.MatchString(n) || len([]rune(n)) < 3 || len([]rune(body)) > colonias.MaxQuery:
		return b.text(ctx, r, msgHelp(b.BaseURL, r.Channel))
	}
	matches, exact := b.Colonias.Search(body, 10)
	switch {
	case len(matches) == 0:
		return b.text(ctx, r, msgNotFound(strings.TrimSpace(body)))
	case exact && len(matches) == 1:
		return b.onColonia(ctx, r, matches[0])
	}
	choices := make([]Choice, len(matches))
	for i, c := range matches {
		label := zoneLabel(c.Zones)
		choices[i] = Choice{ID: "C:" + c.Key(), Title: c.Name, Description: municipioName(c.Municipio) + " · " + strings.ToUpper(label[:1]) + label[1:]}
	}
	return b.reply(ctx, r, Reply{Text: msgPickColonia, Button: "Ver colonias", Choices: choices})
}

// onUserChanged follows a subscriber to a new number or business-scoped user ID,
// so reminders stop going to a number that may now belong to someone else.
func (b *Bot) onUserChanged(ctx context.Context, r User, sys *wa.System) error {
	if sys.Type != "user_changed_number" && sys.Type != "user_changed_user_id" {
		return nil
	}
	old := sys.PreviousUserID
	if old == "" {
		old = r.ID
	}
	return b.Store.ChangeUser(ctx, old, r.Phone, sys.UserID, sys.WaID)
}

func (b *Bot) onLocation(ctx context.Context, r User, lat, lon float64) error {
	zones := b.Zones.Lookup(lat, lon)
	switch len(zones) {
	case 0:
		return b.text(ctx, r, msgOutside)
	case 1:
		return b.subscribe(ctx, r, zones[0])
	}
	return b.pickZone(ctx, r, msgPickZoneAtPoint, zones)
}

func (b *Bot) onPayload(ctx context.Context, r User, p string) error {
	kind, rest, _ := strings.Cut(p, ":")
	switch kind {
	case "BAJA":
		return b.unsubscribe(ctx, r)
	case "Z":
		zone, err := strconv.Atoi(rest)
		if err != nil || !b.Schedule.HasZone(zone) {
			return b.text(ctx, r, msgHelp(b.BaseURL, r.Channel))
		}
		return b.subscribe(ctx, r, zone)
	case "C":
		if c, ok := b.Colonias.ByKey(rest); ok {
			return b.onColonia(ctx, r, c)
		}
	case "REPORT":
		return b.askReport(ctx, r, 0, rest)
	case "R":
		// R:zone:date:answer; buttons sent before the zone was added are R:date:answer.
		parts, zone := strings.Split(rest, ":"), 0
		if len(parts) == 3 {
			var err error
			if zone, err = strconv.Atoi(parts[0]); err != nil {
				break
			}
			parts = parts[1:]
		}
		if len(parts) == 2 {
			return b.saveReport(ctx, r, zone, parts[0], parts[1])
		}
	}
	return b.text(ctx, r, msgHelp(b.BaseURL, r.Channel))
}

func (b *Bot) onColonia(ctx context.Context, r User, c colonias.Colonia) error {
	if c.Multi || len(c.Zones) > 1 {
		return b.pickZone(ctx, r, msgPickZone(c.Name, c.Zones), c.Zones)
	}
	return b.subscribe(ctx, r, c.Zones[0])
}

func (b *Bot) pickZone(ctx context.Context, r User, body string, zones []int) error {
	choices := make([]Choice, len(zones))
	for i, z := range zones {
		choices[i] = Choice{ID: fmt.Sprintf("Z:%d", z), Title: fmt.Sprintf("Zona %d", z), Description: "Cortes: " + rotation.DaysES(b.Schedule.Weekdays(z))}
	}
	return b.reply(ctx, r, Reply{Text: body, Button: "Elegir zona", Choices: choices})
}

func (b *Bot) greet(ctx context.Context, r User) error {
	if r.ID != "" {
		s, ok, err := b.Store.Subscriber(ctx, r.Channel, r.ID)
		if err != nil {
			return err
		}
		if ok {
			return b.reply(ctx, r, Reply{Text: b.subscribedText(r.Channel, s.Zone, false), CloseKeyboard: true})
		}
	}
	return b.welcome(ctx, r)
}

func (b *Bot) subscribe(ctx context.Context, r User, zone int) error {
	if r.ID == "" {
		b.Log.Warn("message without business-scoped user ID")
		return b.text(ctx, r, msgNoUserID)
	}
	full, err := b.nightFull(ctx, r, zone)
	if err != nil {
		return err
	}
	if full {
		b.Log.Warn("subscription refused: a night would exceed the send cap", "zone", zone, "cap", b.NightCap)
		return b.text(ctx, r, msgFull(b.BaseURL))
	}
	if err := b.Store.Subscribe(ctx, r.Channel, r.ID, r.Phone, zone); err != nil {
		return err
	}
	return b.reply(ctx, r, Reply{Text: b.subscribedText(r.Channel, zone, true), CloseKeyboard: true})
}

// nightFull reports whether putting r in zone would make some night's reminders
// exceed what WhatsApp lets us send in 24 hours. Past that, the newest subscribers
// would silently miss reminders, so it's better to say so up front.
func (b *Bot) nightFull(ctx context.Context, r User, zone int) (bool, error) {
	if b.NightCap <= 0 || r.Channel != store.WhatsApp {
		return false, nil
	}
	current, subscribed, err := b.Store.Subscriber(ctx, r.Channel, r.ID)
	if err != nil || (subscribed && current.Zone == zone) {
		return false, err
	}
	counts, err := b.Store.ZoneCounts(ctx)
	if err != nil {
		return false, err
	}
	for _, day := range b.Schedule.Weekdays(zone) {
		load := 1
		for z, n := range counts {
			if slices.Contains(b.Schedule.Weekdays(z), day) {
				load += n
			}
		}
		if subscribed && slices.Contains(b.Schedule.Weekdays(current.Zone), day) {
			load-- // already counted on that night
		}
		if load > b.NightCap {
			return true, nil
		}
	}
	return false, nil
}

func (b *Bot) welcome(ctx context.Context, r User) error {
	return b.reply(ctx, r, Reply{Text: msgWelcome(b.BaseURL, r.Channel), AskLocation: true})
}

func (b *Bot) remindersOn(channel string) bool {
	if channel == store.Telegram {
		return b.TelegramOn
	}
	return b.RemindersOn
}

func (b *Bot) subscribedText(channel string, zone int, fresh bool) string {
	now := b.Now()
	today := b.Schedule.Day(now)
	tomorrow := today.AddDate(0, 0, 1)
	info := subscribedInfo{
		zone: zone, fresh: fresh, base: b.BaseURL, off: !b.remindersOn(channel), channel: channel,
		days: rotation.DaysES(b.Schedule.Weekdays(zone)),
		hour: rotation.HourES(b.ReminderHour),
	}
	next := b.Schedule.NextCuts(zone, tomorrow, 2)
	if len(next) > 0 && next[0].Equal(tomorrow) && (!b.remindersOn(channel) || now.In(b.Schedule.Location()).Hour() >= b.ReminderHour) {
		info.cutTomorrow = rotation.DateES(tomorrow)
		next = next[1:]
	}
	if len(next) > 0 {
		remind := next[0].AddDate(0, 0, -1)
		info.nextReminder = rotation.DateES(remind)
		if remind.Equal(today) {
			info.nextReminder = "hoy"
		}
		info.nextCut = rotation.DateES(next[0])
	}
	return msgSubscribed(info)
}

func (b *Bot) unsubscribe(ctx context.Context, r User) error {
	if r.ID == "" && r.Phone == "" {
		return b.text(ctx, r, msgNotSubscribed)
	}
	removed, err := b.Store.Unsubscribe(ctx, r.Channel, r.ID, r.Phone)
	if err != nil {
		return err
	}
	if !removed {
		return b.text(ctx, r, msgNotSubscribed)
	}
	return b.text(ctx, r, msgUnsubscribed)
}

// reportLastCut asks about the subscriber's most recent cut, today included.
func (b *Bot) reportLastCut(ctx context.Context, r User) error {
	if r.ID == "" {
		return b.welcome(ctx, r)
	}
	s, ok, err := b.Store.Subscriber(ctx, r.Channel, r.ID)
	if err != nil {
		return err
	}
	if !ok {
		return b.welcome(ctx, r)
	}
	tomorrow := b.Schedule.Day(b.Now()).AddDate(0, 0, 1)
	prev, ok := b.Schedule.PrevCut(s.Zone, tomorrow)
	if !ok {
		return b.text(ctx, r, msgNoReportYet)
	}
	return b.askReport(ctx, r, s.Zone, prev.Format(rotation.DateLayout))
}

// askReport offers the answers for zone's cut on date; zone 0 means the subscriber's zone when they answer.
func (b *Bot) askReport(ctx context.Context, r User, zone int, date string) error {
	d, err := b.Schedule.ParseDate(date)
	if err != nil {
		return b.text(ctx, r, msgNoReportYet)
	}
	prefix := "R:" + date + ":"
	if zone > 0 {
		prefix = fmt.Sprintf("R:%d:%s:", zone, date)
	}
	choices := make([]Choice, len(reportAnswers))
	for i, a := range reportAnswers {
		choices[i] = Choice{ID: prefix + a.key, Title: a.title}
	}
	return b.reply(ctx, r, Reply{Text: msgAskReport(rotation.DateES(d)), Button: "Elegir respuesta", Choices: choices})
}

func (b *Bot) saveReport(ctx context.Context, r User, zone int, date, answer string) error {
	if !slices.ContainsFunc(reportAnswers, func(a struct{ key, title string }) bool { return a.key == answer }) {
		return b.text(ctx, r, msgHelp(b.BaseURL, r.Channel))
	}
	if r.ID == "" {
		return b.welcome(ctx, r)
	}
	s, ok, err := b.Store.Subscriber(ctx, r.Channel, r.ID)
	if err != nil {
		return err
	}
	if !ok {
		return b.welcome(ctx, r)
	}
	if zone == 0 {
		zone = s.Zone
	}
	d, err := b.Schedule.ParseDate(date)
	today := b.Schedule.Day(b.Now())
	if err != nil || !b.Schedule.IsCut(zone, d) || d.After(today) || d.Before(today.AddDate(0, 0, -14)) {
		return b.text(ctx, r, msgReportClosed)
	}
	if err := b.Store.SaveReport(ctx, s.ID, zone, d, answer); err != nil {
		return err
	}
	return b.text(ctx, r, msgThanks(b.BaseURL))
}

func (b *Bot) text(ctx context.Context, r User, body string) error {
	return b.reply(ctx, r, Reply{Text: body})
}

// reply queues a reply while an inbound message is processed, else sends it.
func (b *Bot) reply(ctx context.Context, to User, r Reply) error {
	if b.queue != nil {
		*b.queue = append(*b.queue, queued{to, r})
		return nil
	}
	return b.deliver(ctx, to, r)
}

// deliver drops permanent API errors so the webhook isn't retried for a reply we can never send.
func (b *Bot) deliver(ctx context.Context, to User, r Reply) error {
	var err error
	if to.Channel == store.Telegram {
		var m tg.Message
		if m, err = TelegramMessage(to.ID, r); err == nil {
			_, err = b.Telegram.Send(ctx, m)
		}
	} else {
		_, err = b.Sender.Send(ctx, whatsAppMessage(to, r))
	}
	var permanent interface{ Permanent() bool }
	if errors.As(err, &permanent) && permanent.Permanent() {
		b.Log.Warn("reply not delivered", "err", err)
		return nil
	}
	return err
}

func whatsAppMessage(to User, r Reply) wa.Message {
	rec := wa.Recipient{UserID: to.ID, Phone: to.Phone}
	if len(r.Choices) == 0 {
		return wa.NewText(rec, r.Text)
	}
	rows := make([]wa.Row, len(r.Choices))
	for i, c := range r.Choices {
		rows[i] = wa.Row(c)
	}
	return wa.NewList(rec, r.Text, r.Button, rows)
}

// zoneLabel is "zona 3" or "zonas 1, 5 y 6".
func zoneLabel(zones []int) string {
	if len(zones) == 1 {
		return "zona " + zoneList(zones)
	}
	return "zonas " + zoneList(zones)
}

func municipioName(m string) string {
	if name := municipios[colonias.Normalize(m)]; name != "" {
		return name
	}
	return m
}

func zoneList(zones []int) string {
	s := make([]string, len(zones))
	for i, z := range zones {
		s[i] = strconv.Itoa(z)
	}
	if len(s) < 2 {
		return strings.Join(s, "")
	}
	return strings.Join(s[:len(s)-1], ", ") + " y " + s[len(s)-1]
}
