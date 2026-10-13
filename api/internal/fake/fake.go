// Package fake provides in-memory Store and Sender implementations for tests.
package fake

import (
	"context"
	"fmt"
	"slices"
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
	Subs      map[string]store.Subscriber
	SeenIDs   map[string]bool
	Reports   []Report
	Reminders map[string]bool
	SentCount int
	nextID    int64
}

func NewStore() *Store {
	return &Store{Subs: map[string]store.Subscriber{}, SeenIDs: map[string]bool{}, Reminders: map[string]bool{}}
}

func (s *Store) Seen(_ context.Context, id string) (bool, error) { return s.SeenIDs[id], nil }

func (s *Store) MarkSeen(_ context.Context, id string) error {
	s.SeenIDs[id] = true
	return nil
}

func (s *Store) PurgeSeen(context.Context, time.Time) error { return nil }

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

func (s *Store) UpdateStatus(context.Context, string, string) error { return nil }

func (s *Store) DueSubscribers(_ context.Context, zones []int, d time.Time) ([]store.Subscriber, error) {
	var out []store.Subscriber
	for _, sub := range s.Subs {
		if slices.Contains(zones, sub.Zone) && !s.Reminders[key(sub.ID, d)] {
			out = append(out, sub)
		}
	}
	slices.SortFunc(out, func(a, b store.Subscriber) int { return int(a.ID - b.ID) })
	return out, nil
}

func (s *Store) RecordReminder(_ context.Context, sub store.Subscriber, d time.Time, _ string) error {
	s.Reminders[key(sub.ID, d)] = true
	s.SentCount++
	return nil
}

func (s *Store) SentSince(context.Context, time.Time) (int, error) { return s.SentCount, nil }

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
