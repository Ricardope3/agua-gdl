package fake

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"aguagdl/api/internal/store"
	"aguagdl/api/internal/tg"
)

// These hold the fake to what store.DB does, so tests built on it aren't misled.

func subscribe(t *testing.T, s *Store, channel, user string, zone int) store.Subscriber {
	t.Helper()
	if err := s.Subscribe(context.Background(), channel, user, "", zone); err != nil {
		t.Fatal(err)
	}
	sub, ok, err := s.Subscriber(context.Background(), channel, user)
	if err != nil || !ok {
		t.Fatalf("subscriber: %v %v", ok, err)
	}
	return sub
}

func outcome(err error) func(store.Subscriber) (string, error) {
	return func(store.Subscriber) (string, error) { return "", err }
}

func TestOnlyWhatsAppCountsTowardTheCaps(t *testing.T) {
	ctx := context.Background()
	s := NewStore()
	day := s.Now()
	since := day.Add(-time.Hour)
	for user, err := range map[string]error{"701": nil, "702": errors.New("timeout"), "703": &tg.APIError{Status: 403}} {
		sub := subscribe(t, s, store.Telegram, user, 4)
		if _, got := s.SendReminder(ctx, sub, day, []int{4}, nil, outcome(err)); !errors.Is(got, err) {
			t.Fatal(got)
		}
	}
	if _, err := s.SendNotice(ctx, subscribe(t, s, store.Telegram, "704", 4), "previo:2026-10-19", nil, outcome(nil)); err != nil {
		t.Fatal(err)
	}
	if n, _ := s.SentSince(ctx, since); n != 0 {
		t.Fatalf("Telegram's reminders and notices, sent, uncertain or blocked, must not count against the monthly cap: %d", n)
	}
	if n, _ := s.RecipientsSince(ctx, since); n != 0 {
		t.Fatalf("nor against Meta's limit: %d", n)
	}
	wa := subscribe(t, s, store.WhatsApp, "MX.a", 4)
	if _, err := s.SendReminder(ctx, wa, day, []int{4}, nil, outcome(errors.New("timeout"))); err == nil {
		t.Fatal("want the send error")
	}
	if n, _ := s.SentSince(ctx, since); n != 1 {
		t.Fatalf("an uncertain WhatsApp attempt counts, since it may have been sent: %d", n)
	}
}

func TestNoticeIsForTheSubscriptionItWasQueuedFor(t *testing.T) {
	ctx := context.Background()
	s := NewStore()
	old := subscribe(t, s, store.Telegram, "777", 4)
	if _, err := s.Unsubscribe(ctx, store.Telegram, "777", ""); err != nil {
		t.Fatal(err)
	}
	subscribe(t, s, store.Telegram, "777", 4)
	if attempted, err := s.SendNotice(ctx, old, "previo:2026-10-19", nil, func(store.Subscriber) (string, error) {
		t.Error("sent to the subscription made after BAJA")
		return "", nil
	}); attempted || err != nil {
		t.Fatalf("attempted %v, %v", attempted, err)
	}
}

func TestRefusedNoticeNeedsReviewUntilItGoesOut(t *testing.T) {
	ctx := context.Background()
	s := NewStore()
	const key = "previo:2026-10-19"
	sub := subscribe(t, s, store.Telegram, "777", 4)
	refused := &tg.APIError{Status: 429}
	if _, err := s.SendNotice(ctx, sub, key, nil, outcome(refused)); !errors.Is(err, refused) {
		t.Fatal(err)
	}
	if n, _ := s.UnresolvedNotices(ctx, store.Telegram, key); n != 1 {
		t.Fatalf("a refused notice needs review until it goes out: %d", n)
	}
	if due, _ := s.NoticeRecipients(ctx, store.Telegram, 4, key); len(due) != 1 {
		t.Fatalf("and it's due again: %+v", due)
	}
	if attempted, err := s.SendNotice(ctx, sub, key, nil, outcome(nil)); !attempted || err != nil {
		t.Fatalf("retry: %v %v", attempted, err)
	}
	if n, _ := s.UnresolvedNotices(ctx, store.Telegram, key); n != 0 {
		t.Fatalf("sent: %d need review", n)
	}
}

func TestBlockedAfterARefusalNeedsNoReview(t *testing.T) {
	ctx := context.Background()
	s := NewStore()
	day := s.Now()
	const key = "previo:2026-10-19"
	refused, blocked := &tg.APIError{Status: 429}, &tg.APIError{Status: 403}
	for _, err := range []error{refused, blocked} {
		if _, got := s.SendReminder(ctx, subscribe(t, s, store.Telegram, "777", 4), day, []int{4}, nil, outcome(err)); !errors.Is(got, err) {
			t.Fatal(got)
		}
		if _, got := s.SendNotice(ctx, subscribe(t, s, store.Telegram, "778", 4), key, nil, outcome(err)); !errors.Is(got, err) {
			t.Fatal(got)
		}
	}
	for _, channel := range []string{store.WhatsApp, store.Telegram} {
		reminders, _ := s.UnresolvedReminders(ctx, channel, day)
		notices, _ := s.UnresolvedNotices(ctx, channel, key)
		if reminders != 0 || notices != 0 {
			t.Errorf("%s: a blocked bot is an opt-out, not an attempt to review: %d reminders, %d notices", channel, reminders, notices)
		}
	}
}

func TestASecondReportOfACutReplacesTheFirst(t *testing.T) {
	ctx := context.Background()
	s := NewStore()
	sub := subscribe(t, s, store.Telegram, "777", 4)
	for _, r := range []Report{{sub.ID, 4, "", "normal"}, {sub.ID, 6, "", "turbia"}} {
		if err := s.SaveReport(ctx, r.SubscriberID, r.Zone, s.Now(), r.Answer); err != nil {
			t.Fatal(err)
		}
	}
	if len(s.Reports) != 1 || s.Reports[0].Answer != "turbia" || s.Reports[0].Zone != 6 {
		t.Fatalf("one report per subscription and cut, the latest: %+v", s.Reports)
	}
}

func TestTelegramRefusesWhatTheBotAPIRefuses(t *testing.T) {
	ctx := context.Background()
	tel := &Telegram{}
	long := tg.InlineKeyboard{InlineKeyboard: [][]tg.InlineButton{{{Text: "x", CallbackData: strings.Repeat("x", 65)}}}}
	for _, m := range []tg.Message{tg.NewHTML(1, "<b>a <i>b</b> c</i>"), tg.NewHTML(1, "<b>a"), {ChatID: 1, Text: "x", ReplyMarkup: long}} {
		_, err := tel.Send(ctx, m)
		var refused *tg.APIError
		if !errors.As(err, &refused) || !refused.Permanent() {
			t.Errorf("%q: want a permanent 400, got %v", m.Text, err)
		}
	}
	if _, err := tel.Send(ctx, tg.NewHTML(1, "<b>a <i>b</i></b> &lt;i&gt;")); err != nil || len(tel.Sent) != 1 {
		t.Fatalf("tags that nest are sent: %v", err)
	}
}
