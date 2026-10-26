// Package fake provides in-memory Store and Sender implementations for tests.
package fake

import (
	"context"
	"errors"
	"fmt"
	"maps"
	"net/http"
	"regexp"
	"slices"
	"strings"
	"time"

	"aguagdl/api/internal/store"
	"aguagdl/api/internal/tg"
	"aguagdl/api/internal/wa"
)

type Report struct {
	SubscriberID int64
	Zone         int
	Date         string
	Answer       string
}

type Store struct {
	Subs       map[string]store.Subscriber // keyed by Key(channel, user ID)
	SeenIDs    map[string]bool
	Reports    []Report
	Water      []Report // answers to «¿Ahorita tienes agua?»
	Reminders  map[string]bool
	SentAt     map[string]time.Time
	Unresolved map[string]string
	Wamids     map[string]bool
	Now        func() time.Time // stamps subscriptions and attempts; see NewStore
	FailDue    int              // DueSubscribers fails this many times, like a database waking up
	Notices    map[string]bool
	NoticeErrs map[string]bool      // notice attempts that need review, uncertain or refused, keyed like Notices
	Replies    map[string][]Pending // queued replies by inbound message ID
	nextID     int64
}

// Pending is a queued reply and its recipient.
type Pending struct {
	Channel, UserID, Phone string
	Body                   []byte
}

// NewStore's clock is stopped before every test's date, so whatever is subscribed before
// a test sets Now is old, whenever the test runs.
func NewStore() *Store {
	start := time.Date(2026, 10, 1, 12, 0, 0, 0, time.FixedZone("CST", -6*60*60))
	return &Store{Subs: map[string]store.Subscriber{}, SeenIDs: map[string]bool{}, Reminders: map[string]bool{},
		SentAt: map[string]time.Time{}, Unresolved: map[string]string{}, Wamids: map[string]bool{}, Notices: map[string]bool{}, NoticeErrs: map[string]bool{},
		Replies: map[string][]Pending{}, Now: func() time.Time { return start }}
}

func (s *Store) ProcessInbound(ctx context.Context, id string, process func(store.BotStore) error) error {
	if s.SeenIDs[id] {
		return nil
	}
	before := *s
	before.Subs, before.SeenIDs, before.Replies = maps.Clone(s.Subs), maps.Clone(s.SeenIDs), maps.Clone(s.Replies)
	before.Reports = append([]Report(nil), s.Reports...)
	before.Water = append([]Report(nil), s.Water...)
	s.SeenIDs[id] = true
	if err := process(s); err != nil {
		*s = before
		return err
	}
	return nil
}

func (s *Store) QueueReply(_ context.Context, id, channel, userID, phone string, body []byte) error {
	s.Replies[id] = append(s.Replies[id], Pending{channel, userID, phone, body})
	return nil
}

func (s *Store) SendReplies(_ context.Context, id string, send func([]byte) error) error {
	for len(s.Replies[id]) > 0 {
		if err := send(s.Replies[id][0].Body); err != nil {
			return err
		}
		s.Replies[id] = s.Replies[id][1:]
	}
	delete(s.Replies, id)
	return nil
}

// Key is a WhatsApp user ID as is, and "tg:<chat ID>" for Telegram.
func Key(channel, userID string) string {
	if channel == store.WhatsApp {
		return userID
	}
	return channel + ":" + userID
}

func (s *Store) Subscriber(_ context.Context, channel, userID string) (store.Subscriber, bool, error) {
	sub, ok := s.Subs[Key(channel, userID)]
	sub.Zones = slices.Clone(sub.Zones)
	return sub, ok, nil
}

func matchingZone(sub store.Subscriber, zones []int) (int, bool) {
	for _, candidate := range sub.Memberships() {
		if slices.Contains(zones, candidate) {
			return candidate, true
		}
	}
	return 0, false
}

func (s *Store) Subscribe(_ context.Context, channel, userID, phone string, zone int) error {
	id := Key(channel, userID)
	for k, other := range s.Subs {
		if phone != "" && other.Phone == phone && k != id {
			delete(s.Subs, k)
		}
	}
	sub, ok := s.Subs[id]
	if !ok {
		s.nextID++
		sub = store.Subscriber{ID: s.nextID, Channel: channel, UserID: userID, CreatedAt: s.Now()}
	}
	if phone != "" {
		sub.Phone = phone
	}
	if len(sub.Zones) == 0 {
		sub.Zones = []int{zone}
	} else if !sub.HasZone(zone) {
		sub.Zones = append(slices.Clone(sub.Zones), zone)
		slices.Sort(sub.Zones)
	}
	sub.Zone, sub.UpdatedAt = zone, s.Now()
	s.Subs[id] = sub
	return nil
}

// ChangeUser mirrors store.DB.ChangeUser: one row survives (the new ID's, else the
// old ID's, else the newest with the old phone) and every other match is deleted.
func (s *Store) ChangeUser(_ context.Context, oldUserID, oldPhone, newUserID, newPhone string) error {
	old := func(sub store.Subscriber) bool {
		return (sub.Channel == store.WhatsApp && sub.UserID == oldUserID) || (oldPhone != "" && sub.Phone == oldPhone)
	}
	keep, found := s.Subs[newUserID]
	found = found && newUserID != ""
	if newUserID != "" && !found {
		for _, sub := range s.Subs {
			if !old(sub) {
				continue
			}
			byID, keepByID := sub.UserID == oldUserID, keep.UserID == oldUserID
			if !found || (byID && !keepByID) || (byID == keepByID && sub.ID > keep.ID) {
				keep, found = sub, true
			}
		}
	}
	for k, sub := range s.Subs {
		if found && sub.ID == keep.ID {
			continue
		}
		if old(sub) || (newUserID != "" && ((sub.Channel == store.WhatsApp && sub.UserID == newUserID) || (newPhone != "" && sub.Phone == newPhone))) {
			delete(s.Subs, k)
		}
	}
	if found {
		delete(s.Subs, keep.UserID)
		keep.UserID, keep.Phone = newUserID, newPhone
		s.Subs[newUserID] = keep
	}
	return nil
}

func (s *Store) ZoneCounts(context.Context) (map[int]int, error) {
	counts := map[int]int{}
	for _, sub := range s.Subs {
		if sub.Channel == store.WhatsApp {
			for _, zone := range sub.Memberships() {
				counts[zone]++
			}
		}
	}
	return counts, nil
}

func (s *Store) NightLoad(_ context.Context, zones []int) (int, error) {
	n := 0
	for _, sub := range s.Subs {
		if sub.Channel == store.WhatsApp {
			if _, ok := matchingZone(sub, zones); ok {
				n++
			}
		}
	}
	return n, nil
}

func (s *Store) UnsubscribeZone(_ context.Context, channel, userID string, zone int) (bool, bool, error) {
	id := Key(channel, userID)
	sub, ok := s.Subs[id]
	if !ok || !sub.HasZone(zone) {
		return false, ok, nil
	}
	if len(sub.Zones) == 0 {
		sub.Zones = []int{sub.Zone}
	}
	sub.Zones = slices.DeleteFunc(sub.Zones, func(z int) bool { return z == zone })
	if len(sub.Zones) == 0 {
		delete(s.Subs, id)
		return true, false, nil
	}
	if sub.Zone == zone {
		sub.Zone = sub.Zones[0]
	}
	sub.UpdatedAt = s.Now()
	s.Subs[id] = sub
	return true, true, nil
}

func (s *Store) Unsubscribe(_ context.Context, channel, userID, phone string) (bool, error) {
	removed := false
	for k, sub := range s.Subs {
		if (userID != "" && sub.Channel == channel && sub.UserID == userID) || (phone != "" && sub.Phone == phone) {
			delete(s.Subs, k)
			removed = true
		}
	}
	for id, replies := range s.Replies {
		s.Replies[id] = slices.DeleteFunc(replies, func(p Pending) bool {
			return (userID != "" && p.Channel == channel && p.UserID == userID) || (phone != "" && p.Phone == phone)
		})
	}
	return removed, nil
}

// SaveReport keeps one report per subscription and cut, the latest, like store.DB.SaveReport.
func (s *Store) SaveReport(_ context.Context, id int64, zone int, d time.Time, answer string) error {
	r := Report{id, zone, d.Format("2006-01-02"), answer}
	for i, old := range s.Reports {
		if old.SubscriberID == id && old.Date == r.Date {
			s.Reports[i] = r
			return nil
		}
	}
	s.Reports = append(s.Reports, r)
	return nil
}

// SaveWater keeps one answer per subscription and block, and only from a subscription that
// was sent that block's notice or reminder, like store.DB.SaveWater.
func (s *Store) SaveWater(_ context.Context, id int64, zone int, d time.Time, answer string) (bool, error) {
	if !s.Reminders[key(id, d)] && !s.Notices[fmt.Sprintf("%d/%s", id, store.AheadKey(d))] {
		return false, nil
	}
	w := Report{id, zone, d.Format("2006-01-02"), answer}
	for i, old := range s.Water {
		if old.SubscriberID == id && old.Date == w.Date {
			s.Water[i] = w
			return true, nil
		}
	}
	s.Water = append(s.Water, w)
	return true, nil
}

func (s *Store) NoWater(_ context.Context, start time.Time) (map[int64]bool, error) {
	ids := map[int64]bool{}
	for _, w := range s.Water {
		if w.Date == start.Format("2006-01-02") && w.Answer == "no" {
			ids[w.SubscriberID] = true
		}
	}
	return ids, nil
}

// ReturnRecipients mirrors store.DB.ReturnRecipients.
func (s *Store) ReturnRecipients(_ context.Context, channel string, zone int, start, last time.Time) ([]store.Subscriber, error) {
	var out []store.Subscriber
	for _, sub := range s.Subs {
		if sub.Channel != channel || !sub.HasZone(zone) || s.Notices[fmt.Sprintf("%d/%s", sub.ID, store.ReturnKey(start))] {
			continue
		}
		dry := slices.ContainsFunc(s.Water, func(w Report) bool {
			return w.SubscriberID == sub.ID && w.Date == start.Format("2006-01-02") && (w.Answer == "no" || w.Answer == "poca")
		})
		reported := slices.ContainsFunc(s.Reports, func(r Report) bool {
			return r.SubscriberID == sub.ID && r.Date >= start.Format("2006-01-02") && r.Date <= last.Format("2006-01-02")
		})
		if dry && !reported {
			sub.Zone = zone
			out = append(out, sub)
		}
	}
	slices.SortFunc(out, func(a, b store.Subscriber) int { return int(a.ID - b.ID) })
	return out, nil
}

func (s *Store) UnresolvedNotices(_ context.Context, channel, k string) (int, error) {
	n := 0
	for nk := range s.NoticeErrs {
		if strings.HasSuffix(nk, "/"+k) && s.channelOf(nk) == channel {
			n++
		}
	}
	return n, nil
}

func (s *Store) UpdateStatus(_ context.Context, wamid, _ string) (bool, error) {
	return s.Wamids[wamid], nil
}

func (s *Store) DueSubscribers(_ context.Context, channel string, zones []int, d time.Time) ([]store.Subscriber, error) {
	if s.FailDue > 0 {
		s.FailDue--
		return nil, errors.New("connection refused")
	}
	var out []store.Subscriber
	for _, sub := range s.Subs {
		zone, match := matchingZone(sub, zones)
		if sub.Channel == channel && match && !s.Reminders[key(sub.ID, d)] {
			sub.Zone = zone
			out = append(out, sub)
		}
	}
	slices.SortFunc(out, func(a, b store.Subscriber) int { return int(a.ID - b.ID) })
	return out, nil
}

func (s *Store) SendReminder(ctx context.Context, sub store.Subscriber, d time.Time, zones []int, budget *store.Budget, send func(store.Subscriber) (string, error)) (bool, error) {
	current, ok := s.Subs[Key(sub.Channel, sub.UserID)]
	k := key(sub.ID, d)
	zone, match := matchingZone(current, zones)
	if !ok || current.ID != sub.ID || !match || s.Reminders[k] {
		return false, nil
	}
	current.Zone = zone
	if s.overBudget(budget) {
		return false, store.ErrOverBudget
	}
	s.Reminders[k] = true
	if current.Channel == store.WhatsApp {
		s.SentAt[k] = s.Now() // only WhatsApp's attempts count against the caps
	}
	wamid, err := send(current)
	var rejected interface{ Rejected() bool }
	var gone interface{ Gone() bool }
	switch {
	case errors.As(err, &gone) && gone.Gone():
		delete(s.Subs, Key(current.Channel, current.UserID))
		delete(s.Unresolved, k)
	case errors.As(err, &rejected) && rejected.Rejected():
		delete(s.Reminders, k)
		delete(s.SentAt, k)
		s.Unresolved[k] = d.Format("2006-01-02")
	case err != nil:
		s.Unresolved[k] = d.Format("2006-01-02")
	case current.Channel != store.WhatsApp:
		delete(s.Unresolved, k)
	default:
		delete(s.Unresolved, k)
		s.Wamids[wamid] = true
	}
	return true, err
}

func (s *Store) UnresolvedReminders(_ context.Context, channel string, d time.Time) (int, error) {
	n := 0
	for k, date := range s.Unresolved {
		if date == d.Format("2006-01-02") && s.channelOf(k) == channel {
			n++
		}
	}
	return n, nil
}

func (s *Store) SentSince(_ context.Context, since time.Time) (int, error) {
	n := 0
	for _, at := range s.SentAt {
		if !at.Before(since) {
			n++
		}
	}
	return n, nil
}

func (s *Store) RecipientsSince(_ context.Context, since time.Time) (int, error) {
	ids := map[string]bool{}
	for k, at := range s.SentAt {
		if !at.Before(since) {
			id, _, _ := strings.Cut(k, "/")
			ids[id] = true
		}
	}
	return len(ids), nil
}

func (s *Store) NoticeRecipients(_ context.Context, channel string, zone int, k string) ([]store.Subscriber, error) {
	var out []store.Subscriber
	for _, sub := range s.Subs {
		if sub.Channel == channel && sub.HasZone(zone) && !s.Notices[fmt.Sprintf("%d/%s", sub.ID, k)] {
			sub.Zone = zone
			out = append(out, sub)
		}
	}
	slices.SortFunc(out, func(a, b store.Subscriber) int { return int(a.ID - b.ID) })
	return out, nil
}

// SendNotice mirrors store.DB.SendNotice: the attempt's latest outcome decides whether it
// needs review, as the notice row's status does.
func (s *Store) SendNotice(_ context.Context, sub store.Subscriber, k string, budget *store.Budget, send func(store.Subscriber) (string, error)) (bool, error) {
	nk := fmt.Sprintf("%d/%s", sub.ID, k)
	current, ok := s.Subs[Key(sub.Channel, sub.UserID)]
	if !ok || current.ID != sub.ID || !current.HasZone(sub.Zone) || s.Notices[nk] {
		return false, nil
	}
	current.Zone = sub.Zone
	if s.overBudget(budget) {
		return false, store.ErrOverBudget
	}
	s.Notices[nk] = true
	sent := fmt.Sprintf("%d/notice/%s", sub.ID, k)
	if current.Channel == store.WhatsApp {
		s.SentAt[sent] = s.Now()
	}
	_, err := send(current)
	var rejected interface{ Rejected() bool }
	var gone interface{ Gone() bool }
	switch {
	case errors.As(err, &gone) && gone.Gone():
		delete(s.Subs, Key(current.Channel, current.UserID))
		delete(s.NoticeErrs, nk)
	case errors.As(err, &rejected) && rejected.Rejected():
		delete(s.Notices, nk)
		delete(s.SentAt, sent)
		s.NoticeErrs[nk] = true
	case err != nil:
		s.NoticeErrs[nk] = true
	default:
		delete(s.NoticeErrs, nk)
	}
	return true, err
}

func (s *Store) overBudget(b *store.Budget) bool {
	if b == nil {
		return false
	}
	month, _ := s.SentSince(context.Background(), b.MonthStart)
	day, _ := s.RecipientsSince(context.Background(), b.DayStart)
	return month >= b.Monthly || day >= b.Daily
}

// channelOf finds the channel of the subscriber in a reminder key; a deleted subscriber's
// attempts count as WhatsApp's.
func (s *Store) channelOf(k string) string {
	id, _, _ := strings.Cut(k, "/")
	for _, sub := range s.Subs {
		if fmt.Sprint(sub.ID) == id {
			return sub.Channel
		}
	}
	return store.WhatsApp
}

func key(id int64, d time.Time) string { return fmt.Sprintf("%d/%s", id, d.Format("2006-01-02")) }

type Sender struct{ Sent []wa.Message }

func (s *Sender) Send(_ context.Context, m wa.Message) (string, error) {
	s.Sent = append(s.Sent, m)
	return fmt.Sprintf("wamid.%d", len(s.Sent)), nil
}

// Last returns the text or interactive body of the last message sent.
func (s *Sender) Last() string {
	if len(s.Sent) == 0 {
		return ""
	}
	m := s.Sent[len(s.Sent)-1]
	switch {
	case m.Text != nil:
		return m.Text.Body
	case m.Interactive != nil:
		return m.Interactive.Body.Text
	}
	return m.Type
}

type Telegram struct {
	Sent     []tg.Message
	Answered []string
	Err      error // returned by every Send
}

// Send refuses what Telegram refuses with a 400: HTML whose tags don't nest, and callback
// data over 64 bytes.
func (t *Telegram) Send(_ context.Context, m tg.Message) (int64, error) {
	if t.Err != nil {
		return 0, t.Err
	}
	if why := refusal(m); why != "" {
		return 0, &tg.APIError{Status: http.StatusBadRequest, Description: "Bad Request: " + why}
	}
	t.Sent = append(t.Sent, m)
	return int64(len(t.Sent)), nil
}

var htmlTag = regexp.MustCompile(`<(/?)([a-z-]+)[^>]*>`)

func refusal(m tg.Message) string {
	if m.ParseMode == "HTML" {
		var open []string
		for _, tag := range htmlTag.FindAllStringSubmatch(m.Text, -1) {
			switch {
			case tag[1] == "":
				open = append(open, tag[2])
			case len(open) == 0 || open[len(open)-1] != tag[2]:
				return "can't parse entities: unmatched end tag </" + tag[2] + ">"
			default:
				open = open[:len(open)-1]
			}
		}
		if len(open) > 0 {
			return "can't parse entities: can't find end tag corresponding to start tag <" + open[len(open)-1] + ">"
		}
	}
	if kb, ok := m.ReplyMarkup.(tg.InlineKeyboard); ok {
		for _, row := range kb.InlineKeyboard {
			for _, b := range row {
				if len(b.CallbackData) > 64 {
					return "BUTTON_DATA_INVALID"
				}
			}
		}
	}
	return ""
}

func (t *Telegram) AnswerCallback(_ context.Context, id string) error {
	t.Answered = append(t.Answered, id)
	return nil
}

// Last returns the text of the last Telegram message sent.
func (t *Telegram) Last() string {
	if len(t.Sent) == 0 {
		return ""
	}
	return t.Sent[len(t.Sent)-1].Text
}
