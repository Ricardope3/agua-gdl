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
	"aguagdl/api/internal/wa"
)

type Report struct {
	SubscriberID int64
	Zone         int
	Date         string
	Answer       string
}

type Store struct {
	Subs       map[string]store.Subscriber
	SeenIDs    map[string]bool
	Reports    []Report
	Reminders  map[string]bool
	SentAt     map[string]time.Time
	Unresolved map[string]string
	Wamids     map[string]bool
	Now        func() time.Time // stamps reminder attempts
	FailDue    int              // DueSubscribers fails this many times, like a database waking up
	nextID     int64
}

func NewStore() *Store {
	return &Store{Subs: map[string]store.Subscriber{}, SeenIDs: map[string]bool{}, Reminders: map[string]bool{},
		SentAt: map[string]time.Time{}, Unresolved: map[string]string{}, Wamids: map[string]bool{}, Now: time.Now}
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

func (s *Store) Subscriber(_ context.Context, userID string) (store.Subscriber, bool, error) {
	sub, ok := s.Subs[userID]
	return sub, ok, nil
}

func (s *Store) Subscribe(_ context.Context, userID, phone string, zone int) error {
	sub, ok := s.Subs[userID]
	if !ok {
		s.nextID++
		sub = store.Subscriber{ID: s.nextID, UserID: userID}
	}
	if phone != "" {
		sub.Phone = phone
	}
	sub.Zone = zone
	s.Subs[userID] = sub
	return nil
}

func (s *Store) Unsubscribe(_ context.Context, userID string) (bool, error) {
	_, ok := s.Subs[userID]
	delete(s.Subs, userID)
	return ok, nil
}

func (s *Store) SaveReport(_ context.Context, id int64, zone int, d time.Time, answer string) error {
	s.Reports = append(s.Reports, Report{id, zone, d.Format("2006-01-02"), answer})
	return nil
}

func (s *Store) UpdateStatus(_ context.Context, wamid, _ string) (bool, error) {
	return s.Wamids[wamid], nil
}

func (s *Store) DueSubscribers(_ context.Context, zones []int, d time.Time) ([]store.Subscriber, error) {
	if s.FailDue > 0 {
		s.FailDue--
		return nil, errors.New("connection refused")
	}
	var out []store.Subscriber
	for _, sub := range s.Subs {
		if slices.Contains(zones, sub.Zone) && !s.Reminders[key(sub.ID, d)] {
			out = append(out, sub)
		}
	}
	slices.SortFunc(out, func(a, b store.Subscriber) int { return int(a.ID - b.ID) })
	return out, nil
}

func (s *Store) SendReminder(ctx context.Context, sub store.Subscriber, d time.Time, zones []int, send func(store.Subscriber) (string, error)) (bool, error) {
	current, ok := s.Subs[sub.UserID]
	k := key(sub.ID, d)
	if !ok || current.ID != sub.ID || !slices.Contains(zones, current.Zone) || s.Reminders[k] {
		return false, nil
	}
	s.Reminders[k], s.SentAt[k] = true, s.Now()
	wamid, err := send(current)
	var apiErr *wa.APIError
	switch {
	case errors.As(err, &apiErr) && apiErr.Rejected():
		delete(s.Reminders, k)
		delete(s.SentAt, k)
		s.Unresolved[k] = d.Format("2006-01-02")
	case err != nil:
		s.Unresolved[k] = d.Format("2006-01-02")
	default:
		delete(s.Unresolved, k)
		s.Wamids[wamid] = true
	}
	return true, err
}

func (s *Store) UnresolvedReminders(_ context.Context, d time.Time) (int, error) {
	n := 0
	for _, date := range s.Unresolved {
		if date == d.Format("2006-01-02") {
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
