// Package fake provides in-memory Store and Sender implementations for tests.
package fake

import (
	"context"
	"errors"
	"fmt"
	"maps"
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
	Reminders  map[string]bool
	SentAt     map[string]time.Time
	Unresolved map[string]string
	Wamids     map[string]bool
	Now        func() time.Time // stamps subscriptions and attempts; see NewStore
	FailDue    int              // DueSubscribers fails this many times, like a database waking up
	Notices    map[string]bool
	nextID     int64
}

// NewStore's clock is stopped before every test's date, so whatever is subscribed before
// a test sets Now is old, whenever the test runs.
func NewStore() *Store {
	start := time.Date(2026, 10, 1, 12, 0, 0, 0, time.FixedZone("CST", -6*60*60))
	return &Store{Subs: map[string]store.Subscriber{}, SeenIDs: map[string]bool{}, Reminders: map[string]bool{},
		SentAt: map[string]time.Time{}, Unresolved: map[string]string{}, Wamids: map[string]bool{}, Notices: map[string]bool{},
		Now: func() time.Time { return start }}
}

func (s *Store) ProcessInbound(ctx context.Context, id string, process func(store.BotStore) error) error {
	if s.SeenIDs[id] {
		return nil
	}
	before := *s
	before.Subs, before.SeenIDs = maps.Clone(s.Subs), maps.Clone(s.SeenIDs)
	before.Reports = append([]Report(nil), s.Reports...)
	s.SeenIDs[id] = true
	if err := process(s); err != nil {
		*s = before
		return err
	}
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
	return sub, ok, nil
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
		sub = store.Subscriber{ID: s.nextID, Channel: channel, UserID: userID}
	}
	if phone != "" {
		sub.Phone = phone
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
			counts[sub.Zone]++
		}
	}
	return counts, nil
}

func (s *Store) Unsubscribe(_ context.Context, channel, userID, phone string) (bool, error) {
	removed := false
	for k, sub := range s.Subs {
		if (userID != "" && sub.Channel == channel && sub.UserID == userID) || (phone != "" && sub.Phone == phone) {
			delete(s.Subs, k)
			removed = true
		}
	}
	return removed, nil
}

func (s *Store) SaveReport(_ context.Context, id int64, zone int, d time.Time, answer string) error {
	s.Reports = append(s.Reports, Report{id, zone, d.Format("2006-01-02"), answer})
	return nil
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
		if sub.Channel == channel && slices.Contains(zones, sub.Zone) && !s.Reminders[key(sub.ID, d)] {
			out = append(out, sub)
		}
	}
	slices.SortFunc(out, func(a, b store.Subscriber) int { return int(a.ID - b.ID) })
	return out, nil
}

func (s *Store) SendReminder(ctx context.Context, sub store.Subscriber, d time.Time, zones []int, budget *store.Budget, send func(store.Subscriber) (string, error)) (bool, error) {
	current, ok := s.Subs[Key(sub.Channel, sub.UserID)]
	k := key(sub.ID, d)
	if !ok || current.ID != sub.ID || !slices.Contains(zones, current.Zone) || s.Reminders[k] {
		return false, nil
	}
	if s.overBudget(budget) {
		return false, store.ErrOverBudget
	}
	s.Reminders[k], s.SentAt[k] = true, s.Now()
	wamid, err := send(current)
	var rejected interface{ Rejected() bool }
	var gone interface{ Gone() bool }
	switch {
	case errors.As(err, &gone) && gone.Gone():
		delete(s.Subs, Key(current.Channel, current.UserID))
	case errors.As(err, &rejected) && rejected.Rejected():
		delete(s.Reminders, k)
		delete(s.SentAt, k)
		s.Unresolved[k] = d.Format("2006-01-02")
	case err != nil:
		s.Unresolved[k] = d.Format("2006-01-02")
	case current.Channel != store.WhatsApp:
		delete(s.Unresolved, k)
		delete(s.SentAt, k) // only WhatsApp sends count against the caps
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
		if sub.Channel == channel && sub.Zone == zone && !s.Notices[fmt.Sprintf("%d/%s", sub.ID, k)] {
			out = append(out, sub)
		}
	}
	slices.SortFunc(out, func(a, b store.Subscriber) int { return int(a.ID - b.ID) })
	return out, nil
}

func (s *Store) SendNotice(_ context.Context, sub store.Subscriber, k string, budget *store.Budget, send func(store.Subscriber) (string, error)) (bool, error) {
	nk := fmt.Sprintf("%d/%s", sub.ID, k)
	current, ok := s.Subs[Key(sub.Channel, sub.UserID)]
	if !ok || current.Zone != sub.Zone || s.Notices[nk] {
		return false, nil
	}
	if s.overBudget(budget) {
		return false, store.ErrOverBudget
	}
	s.Notices[nk], s.SentAt[fmt.Sprintf("%d/notice/%s", sub.ID, k)] = true, s.Now()
	_, err := send(current)
	var rejected interface{ Rejected() bool }
	var gone interface{ Gone() bool }
	if errors.As(err, &gone) && gone.Gone() {
		delete(s.Subs, Key(current.Channel, current.UserID))
	} else if errors.As(err, &rejected) && rejected.Rejected() {
		delete(s.Notices, nk)
		delete(s.SentAt, fmt.Sprintf("%d/notice/%s", sub.ID, k))
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

func (t *Telegram) Send(_ context.Context, m tg.Message) (int64, error) {
	if t.Err != nil {
		return 0, t.Err
	}
	t.Sent = append(t.Sent, m)
	return int64(len(t.Sent)), nil
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
