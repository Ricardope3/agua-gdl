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
	"aguagdl/api/internal/wa"
)

type Store = store.BotStore

type Sender interface {
	Send(ctx context.Context, m wa.Message) (string, error)
}

type Bot struct {
	Store         Store
	Sender        Sender
	Schedule      *rotation.Schedule
	Zones         *geo.Zones
	Colonias      *colonias.Index
	BaseURL       string
	PhoneNumberID string // ignore webhooks for other numbers on the same app, e.g. Meta's test number
	ReminderHour  int
	Alert         func(ctx context.Context, msg string) // optional, e.g. a failed heartbeat
	Now           func() time.Time
	Log           *slog.Logger
}

var (
	zoneRe      = regexp.MustCompile(`^(?:ZONA ?)?([1-7])$`)
	badZoneRe   = regexp.MustCompile(`^ZONA ?\d*$`)
	stopWords   = []string{"BAJA", "ALTO", "STOP", "CANCELAR", "DARME DE BAJA", "YA NO", "DEJAR DE RECIBIR AVISOS"}
	helpWords   = []string{"AYUDA", "MENU", "INFO", "OPCIONES"}
	reportWords = []string{"REPORTAR", "REPORTE", "REPORTAR CORTE"}
	pipaWords   = []string{"PIPA", "PIPAS", "PEDIR PIPA", "SIAPA", "SIAPATEL"}
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
				b.Log.Warn("delivery failed", "reminder", reminder, "errors", st.Errors)
				if reminder && b.Alert != nil {
					b.Alert(ctx, fmt.Sprintf("a reminder was not delivered: %v", st.Errors))
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
	r := wa.Recipient{UserID: m.FromUserID, Phone: m.From}
	for _, c := range contacts {
		if r.UserID == "" && c.WaID == m.From {
			r.UserID = c.UserID
		}
	}
	// Commit the command and its deduplication marker together before any HTTP call.
	// A failed reply must never cause Meta's retry to replay a completed command.
	replies := &replyBuffer{}
	err := b.Store.ProcessInbound(ctx, m.ID, func(tx Store) error {
		worker := *b
		worker.Store, worker.Sender = tx, replies
		return worker.route(ctx, r, m)
	})
	if err != nil {
		return err
	}
	for _, reply := range replies.messages {
		if err := b.send(ctx, reply); err != nil {
			return err
		}
	}
	return nil
}

type replyBuffer struct{ messages []wa.Message }

func (q *replyBuffer) Send(_ context.Context, m wa.Message) (string, error) {
	q.messages = append(q.messages, m)
	return "", nil
}

func (b *Bot) route(ctx context.Context, r wa.Recipient, m wa.Inbound) error {
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

func (b *Bot) onText(ctx context.Context, r wa.Recipient, body string) error {
	n := colonias.Normalize(body)
	switch {
	case n == "" || slices.Contains(helpWords, n):
		return b.text(ctx, r, msgHelp(b.BaseURL))
	case slices.Contains(stopWords, n):
		return b.unsubscribe(ctx, r)
	case slices.Contains(reportWords, n):
		return b.reportLastCut(ctx, r)
	case slices.Contains(pipaWords, n):
		return b.text(ctx, r, msgPipa)
	case zoneRe.MatchString(n):
		zone, _ := strconv.Atoi(zoneRe.FindStringSubmatch(n)[1])
		return b.subscribe(ctx, r, zone)
	case strings.HasPrefix(n, "HOLA ") || slices.Contains(greetWords, n):
		return b.greet(ctx, r)
	case municipios[n] != "":
		return b.text(ctx, r, msgMunicipio(municipios[n]))
	case badZoneRe.MatchString(n) || len([]rune(n)) < 3:
		return b.text(ctx, r, msgHelp(b.BaseURL))
	}
	matches, exact := b.Colonias.Search(body, 10)
	switch {
	case len(matches) == 0:
		return b.text(ctx, r, msgNotFound(strings.TrimSpace(body)))
	case exact && len(matches) == 1:
		return b.onColonia(ctx, r, matches[0])
	}
	rows := make([]wa.Row, len(matches))
	for i, c := range matches {
		rows[i] = wa.Row{ID: "C:" + c.Key(), Title: c.Name, Description: c.Municipio + " · " + zoneList(c.Zones)}
	}
	return b.send(ctx, wa.NewList(r, msgPickColonia, "Ver colonias", rows))
}

// onUserChanged follows a subscriber to a new number or business-scoped user ID,
// so reminders stop going to a number that may now belong to someone else.
func (b *Bot) onUserChanged(ctx context.Context, r wa.Recipient, sys *wa.System) error {
	if sys.Type != "user_changed_number" && sys.Type != "user_changed_user_id" {
		return nil
	}
	old := sys.PreviousUserID
	if old == "" {
		old = r.UserID
	}
	return b.Store.ChangeUser(ctx, old, r.Phone, sys.UserID, sys.WaID)
}

func (b *Bot) onLocation(ctx context.Context, r wa.Recipient, lat, lon float64) error {
	zones := b.Zones.Lookup(lat, lon)
	switch len(zones) {
	case 0:
		return b.text(ctx, r, msgOutside)
	case 1:
		return b.subscribe(ctx, r, zones[0])
	}
	return b.pickZone(ctx, r, msgPickZoneAtPoint, zones)
}

func (b *Bot) onPayload(ctx context.Context, r wa.Recipient, p string) error {
	kind, rest, _ := strings.Cut(p, ":")
	switch kind {
	case "BAJA":
		return b.unsubscribe(ctx, r)
	case "Z":
		zone, err := strconv.Atoi(rest)
		if err != nil || !b.Schedule.HasZone(zone) {
			return b.text(ctx, r, msgHelp(b.BaseURL))
		}
		return b.subscribe(ctx, r, zone)
	case "C":
		if c, ok := b.Colonias.ByKey(rest); ok {
			return b.onColonia(ctx, r, c)
		}
	case "REPORT":
		return b.askReport(ctx, r, rest)
	case "R":
		date, answer, _ := strings.Cut(rest, ":")
		return b.saveReport(ctx, r, date, answer)
	}
	return b.text(ctx, r, msgHelp(b.BaseURL))
}

func (b *Bot) onColonia(ctx context.Context, r wa.Recipient, c colonias.Colonia) error {
	if c.Multi || len(c.Zones) > 1 {
		return b.pickZone(ctx, r, msgPickZone(c.Name, zoneList(c.Zones)), c.Zones)
	}
	return b.subscribe(ctx, r, c.Zones[0])
}

func (b *Bot) pickZone(ctx context.Context, r wa.Recipient, body string, zones []int) error {
	rows := make([]wa.Row, len(zones))
	for i, z := range zones {
		rows[i] = wa.Row{ID: fmt.Sprintf("Z:%d", z), Title: fmt.Sprintf("Zona %d", z), Description: "Cortes: " + rotation.DaysES(b.Schedule.Weekdays(z))}
	}
	return b.send(ctx, wa.NewList(r, body, "Elegir zona", rows))
}

func (b *Bot) greet(ctx context.Context, r wa.Recipient) error {
	if r.UserID != "" {
		s, ok, err := b.Store.Subscriber(ctx, r.UserID)
		if err != nil {
			return err
		}
		if ok {
			return b.text(ctx, r, b.subscribedText(s.Zone, false))
		}
	}
	return b.text(ctx, r, msgWelcome(b.BaseURL))
}

func (b *Bot) subscribe(ctx context.Context, r wa.Recipient, zone int) error {
	if r.UserID == "" {
		b.Log.Warn("message without business-scoped user ID")
		return b.text(ctx, r, msgNoUserID)
	}
	if err := b.Store.Subscribe(ctx, r.UserID, r.Phone, zone); err != nil {
		return err
	}
	return b.text(ctx, r, b.subscribedText(zone, true))
}

func (b *Bot) subscribedText(zone int, fresh bool) string {
	now := b.Now()
	today := b.Schedule.Day(now)
	tomorrow := today.AddDate(0, 0, 1)
	info := subscribedInfo{
		zone: zone, fresh: fresh, base: b.BaseURL,
		days: rotation.DaysES(b.Schedule.Weekdays(zone)),
		hour: rotation.HourES(b.ReminderHour),
	}
	next := b.Schedule.NextCuts(zone, tomorrow, 2)
	if len(next) > 0 && next[0].Equal(tomorrow) && now.In(b.Schedule.Location()).Hour() >= b.ReminderHour {
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

func (b *Bot) unsubscribe(ctx context.Context, r wa.Recipient) error {
	if r.UserID == "" {
		return b.text(ctx, r, msgNotSubscribed)
	}
	removed, err := b.Store.Unsubscribe(ctx, r.UserID)
	if err != nil {
		return err
	}
	if !removed {
		return b.text(ctx, r, msgNotSubscribed)
	}
	return b.text(ctx, r, msgUnsubscribed)
}

// reportLastCut asks about the subscriber's most recent cut, today included.
func (b *Bot) reportLastCut(ctx context.Context, r wa.Recipient) error {
	if r.UserID == "" {
		return b.text(ctx, r, msgWelcome(b.BaseURL))
	}
	s, ok, err := b.Store.Subscriber(ctx, r.UserID)
	if err != nil {
		return err
	}
	if !ok {
		return b.text(ctx, r, msgWelcome(b.BaseURL))
	}
	tomorrow := b.Schedule.Day(b.Now()).AddDate(0, 0, 1)
	prev, ok := b.Schedule.PrevCut(s.Zone, tomorrow)
	if !ok {
		return b.text(ctx, r, msgNoReportYet)
	}
	return b.askReport(ctx, r, prev.Format(rotation.DateLayout))
}

func (b *Bot) askReport(ctx context.Context, r wa.Recipient, date string) error {
	d, err := b.Schedule.ParseDate(date)
	if err != nil {
		return b.text(ctx, r, msgNoReportYet)
	}
	rows := make([]wa.Row, len(reportAnswers))
	for i, a := range reportAnswers {
		rows[i] = wa.Row{ID: "R:" + date + ":" + a.key, Title: a.title}
	}
	return b.send(ctx, wa.NewList(r, msgAskReport(rotation.DateES(d)), "Elegir respuesta", rows))
}

func (b *Bot) saveReport(ctx context.Context, r wa.Recipient, date, answer string) error {
	if !slices.ContainsFunc(reportAnswers, func(a struct{ key, title string }) bool { return a.key == answer }) {
		return b.text(ctx, r, msgHelp(b.BaseURL))
	}
	if r.UserID == "" {
		return b.text(ctx, r, msgWelcome(b.BaseURL))
	}
	s, ok, err := b.Store.Subscriber(ctx, r.UserID)
	if err != nil {
		return err
	}
	if !ok {
		return b.text(ctx, r, msgWelcome(b.BaseURL))
	}
	d, err := b.Schedule.ParseDate(date)
	today := b.Schedule.Day(b.Now())
	if err != nil || !b.Schedule.IsCut(s.Zone, d) || d.After(today) || d.Before(today.AddDate(0, 0, -14)) {
		return b.text(ctx, r, msgReportClosed)
	}
	if err := b.Store.SaveReport(ctx, s.ID, s.Zone, d, answer); err != nil {
		return err
	}
	return b.text(ctx, r, msgThanks(b.BaseURL))
}

func (b *Bot) text(ctx context.Context, r wa.Recipient, body string) error {
	return b.send(ctx, wa.NewText(r, body))
}

// send drops permanent API errors so Meta doesn't retry a webhook we can never answer.
func (b *Bot) send(ctx context.Context, m wa.Message) error {
	_, err := b.Sender.Send(ctx, m)
	var apiErr *wa.APIError
	if errors.As(err, &apiErr) && apiErr.Permanent() {
		b.Log.Warn("reply not delivered", "err", err)
		return nil
	}
	return err
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
