// Package reminders sends the evening-before reminder, on WhatsApp and Telegram, to every
// subscriber whose zone is cut tomorrow.
package reminders

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strconv"
	"time"

	"aguagdl/api/internal/bot"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/tg"
	"aguagdl/api/internal/wa"
)

type Store interface {
	DueSubscribers(ctx context.Context, channel string, zones []int, cutDate time.Time) ([]store.Subscriber, error)
	SendReminder(ctx context.Context, s store.Subscriber, cutDate time.Time, zones []int, send func(store.Subscriber) (string, error)) (bool, error)
	UnresolvedReminders(ctx context.Context, channel string, cutDate time.Time) (int, error)
	SentSince(ctx context.Context, since time.Time) (int, error)
	RecipientsSince(ctx context.Context, since time.Time) (int, error)
}

type Sender interface {
	Send(ctx context.Context, m wa.Message) (string, error)
}

type TelegramSender interface {
	Send(ctx context.Context, m tg.Message) (int64, error)
}

// Runner sends each channel whose sender is set. The channels are independent: one
// failing doesn't stop the other, and Meta's caps only apply to WhatsApp.
type Runner struct {
	Store        Store
	Sender       Sender // WhatsApp; nil = off
	Telegram     TelegramSender
	Schedule     *rotation.Schedule
	Template     string
	Language     string
	Hour         int // local hour to send, e.g. 20
	CatchUpUntil int // after a restart, still send until this hour
	DailyCap     int // distinct recipients in a moving 24 hours, like Meta's messaging limit
	MonthlyCap   int
	Interval     time.Duration
	CapPoll      time.Duration                                  // how often to recheck a reached daily cap; default 1 minute
	Heartbeat    func(ctx context.Context, ok bool, msg string) // optional dead-man's switch
	Now          func() time.Time
	Sleep        func(ctx context.Context, d time.Duration) error // tests replace it
	Log          *slog.Logger
}

const maxConsecutiveFailures = 5

// Run sends tonight's reminders every day at Hour. Persisted attempts are never automatically resent.
func (r *Runner) Run(ctx context.Context) {
	if h := r.Now().In(r.Schedule.Location()).Hour(); h >= r.Hour && h < r.CatchUpUntil {
		r.runOnce(ctx)
	}
	for {
		select {
		case <-ctx.Done():
			return
		case <-time.After(time.Until(r.nextRun(r.Now()))):
			r.runOnce(ctx)
		}
	}
}

func (r *Runner) nextRun(now time.Time) time.Time {
	at := r.Schedule.Day(now).Add(time.Duration(r.Hour) * time.Hour)
	if !now.Before(at) {
		at = r.Schedule.Day(now).AddDate(0, 0, 1).Add(time.Duration(r.Hour) * time.Hour)
	}
	return at
}

// runOnce retries a run that failed before contacting WhatsApp, e.g. the database
// waking up, until the catch-up deadline; sends themselves are never retried here.
func (r *Runner) runOnce(ctx context.Context) {
	deadline := r.Schedule.Day(r.Now()).Add(time.Duration(r.CatchUpUntil) * time.Hour)
	err := r.SendTonight(ctx)
	for wait := time.Minute; errors.Is(err, errTransient) && r.Now().Add(wait).Before(deadline); wait = min(2*wait, 10*time.Minute) {
		r.Log.Warn("reminders failed before sending; retrying", "err", err, "in", wait)
		if r.sleep(ctx, wait) != nil {
			break
		}
		err = r.SendTonight(ctx)
	}
	if err != nil {
		r.Log.Error("reminders failed", "err", err)
	}
	if r.Heartbeat != nil {
		msg := "ok"
		if err != nil {
			msg = err.Error()
		}
		r.Heartbeat(ctx, err == nil, msg)
	}
}

// ErrCapped means some subscribers were skipped because a send cap was reached.
var ErrCapped = errors.New("send cap reached")

var errTransient = errors.New("failed before sending")

func transient(err error) error {
	if err == nil {
		return nil
	}
	return fmt.Errorf("%w: %w", errTransient, err)
}

func (r *Runner) SendTonight(ctx context.Context) error {
	var err error
	if r.Sender != nil {
		err = r.sendChannel(ctx, store.WhatsApp)
	}
	if r.Telegram != nil {
		err = errors.Join(err, r.sendChannel(ctx, store.Telegram))
	}
	return err
}

func (r *Runner) sendChannel(ctx context.Context, channel string) (err error) {
	now := r.Now()
	tomorrow := r.Schedule.Day(now).AddDate(0, 0, 1)
	defer func() {
		n, checkErr := r.Store.UnresolvedReminders(ctx, channel, tomorrow)
		err = errors.Join(err, transient(checkErr))
		if n > 0 {
			err = errors.Join(err, fmt.Errorf("%s: %d failed or uncertain reminder attempts require review", channel, n))
		}
	}()
	zones := r.Schedule.ZonesOn(tomorrow)
	if len(zones) == 0 {
		return nil
	}
	subs, err := r.Store.DueSubscribers(ctx, channel, zones, tomorrow)
	if err != nil || len(subs) == 0 {
		return transient(err)
	}
	y, m, _ := now.In(r.Schedule.Location()).Date()
	monthStart := time.Date(y, m, 1, 0, 0, 0, 0, r.Schedule.Location())
	deadline := r.Schedule.Day(now).Add(time.Duration(r.CatchUpUntil) * time.Hour)
	date := rotation.DateES(tomorrow)
	sent, failures := 0, 0
	for i, s := range subs {
		if i > 0 {
			if sleepErr := r.sleep(ctx, r.Interval); sleepErr != nil {
				return errors.Join(err, sleepErr)
			}
		}
		if channel == store.WhatsApp {
			if capErr := r.waitForCap(ctx, monthStart, deadline, len(subs), sent); capErr != nil {
				if !errors.Is(capErr, ErrCapped) {
					capErr = transient(capErr)
				}
				return errors.Join(err, capErr)
			}
		}
		attempted, sendErr := r.Store.SendReminder(ctx, s, tomorrow, zones, func(current store.Subscriber) (string, error) {
			if current.Channel == store.Telegram {
				return "", r.sendTelegram(ctx, current, date)
			}
			return r.Sender.Send(ctx, r.reminder(current, date))
		})
		var unreachable interface{ Gone() bool }
		if errors.As(sendErr, &unreachable) && unreachable.Gone() {
			r.Log.Info("subscriber blocked the bot; subscription deleted", "subscriber", s.ID)
			continue
		}
		if sendErr != nil && !attempted {
			// The reservation failed before any request to WhatsApp: retry the run later.
			return errors.Join(err, transient(fmt.Errorf("subscriber %d: %w", s.ID, sendErr)))
		}
		if sendErr != nil {
			err = errors.Join(err, fmt.Errorf("subscriber %d: %w", s.ID, sendErr))
			r.Log.Error("reminder attempt failed", "subscriber", s.ID, "err", sendErr)
			if failures++; failures >= maxConsecutiveFailures {
				return err
			}
			continue
		}
		if !attempted {
			continue
		}
		failures = 0
		sent++
	}
	r.Log.Info("reminders sent", "channel", channel, "date", tomorrow.Format(rotation.DateLayout), "zones", zones, "sent", sent, "due", len(subs))
	return err
}

// waitForCap checks the caps before every send. Meta's limit is a moving 24-hour
// window, so when last night's reminders still fill it, wait for them to expire
// instead of skipping the rest of tonight's batch. Only the monthly cap, or
// reaching the catch-up deadline, gives up.
func (r *Runner) waitForCap(ctx context.Context, monthStart, deadline time.Time, due, sent int) error {
	waiting := false
	for {
		month, err := r.Store.SentSince(ctx, monthStart)
		if err != nil {
			return err
		}
		if month >= r.MonthlyCap {
			r.Log.Error("monthly cap reached; the rest will not get tonight's reminder", "due", due, "sent", sent)
			return ErrCapped
		}
		day, err := r.Store.RecipientsSince(ctx, r.Now().Add(-24*time.Hour))
		if err != nil {
			return err
		}
		if day < r.DailyCap {
			return nil
		}
		if !r.Now().Before(deadline) {
			r.Log.Error("daily cap reached; the rest will not get tonight's reminder", "due", due, "sent", sent)
			return ErrCapped
		}
		if !waiting {
			r.Log.Warn("daily cap reached; waiting for the 24-hour window to free up", "due", due, "sent", sent)
			waiting = true
		}
		poll := r.CapPoll
		if poll <= 0 {
			poll = time.Minute
		}
		if err := r.sleep(ctx, poll); err != nil {
			return err
		}
	}
}

func (r *Runner) sleep(ctx context.Context, d time.Duration) error {
	if r.Sleep != nil {
		return r.Sleep(ctx, d)
	}
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(d):
		return nil
	}
}

// sendTelegram waits out Telegram's "too many requests" a few times: a 429 means
// the message wasn't sent, so trying again can't duplicate it.
func (r *Runner) sendTelegram(ctx context.Context, s store.Subscriber, date string) error {
	m, err := bot.TelegramReminder(s.UserID, date, s.Zone)
	if err != nil {
		return err
	}
	for attempt := 0; ; attempt++ {
		_, err = r.Telegram.Send(ctx, m)
		var apiErr *tg.APIError
		if attempt == 3 || !errors.As(err, &apiErr) || apiErr.Status != 429 {
			return err
		}
		if sleepErr := r.sleep(ctx, time.Duration(min(max(apiErr.RetryAfter, 1), 30))*time.Second); sleepErr != nil {
			return errors.Join(err, sleepErr)
		}
	}
}

func (r *Runner) reminder(s store.Subscriber, date string) wa.Message {
	return wa.NewTemplate(wa.Recipient{UserID: s.UserID, Phone: s.Phone}, r.Template, r.Language,
		wa.BodyParams(date, strconv.Itoa(s.Zone)),
		wa.QuickReply(0, "BAJA"))
}

// Manual is tomorrow's reminder sent by hand as a normal text, for nights the template
// can't be used. WhatsApp delivers non-template messages only within 24 hours of the
// person's last message, so it goes only to subscribers whose last change is after ActiveSince.
type Manual struct {
	Zone        int
	Text        string
	ActiveSince time.Time
}

// ManualRecipients returns the zone's subscribers still due for tomorrow's cut who are
// inside the window, and how many are due in all.
func (r *Runner) ManualRecipients(ctx context.Context, m Manual) (inWindow []store.Subscriber, due int, err error) {
	tomorrow := r.Schedule.Day(r.Now()).AddDate(0, 0, 1)
	if !r.Schedule.IsCut(m.Zone, tomorrow) {
		return nil, 0, fmt.Errorf("zone %d has no cut on %s", m.Zone, tomorrow.Format(rotation.DateLayout))
	}
	subs, err := r.Store.DueSubscribers(ctx, store.WhatsApp, []int{m.Zone}, tomorrow)
	if err != nil {
		return nil, 0, err
	}
	for _, s := range subs {
		if !s.UpdatedAt.Before(m.ActiveSince) {
			inWindow = append(inWindow, s)
		}
	}
	return inWindow, len(subs), nil
}

// SendManual sends m to ManualRecipients through the same reservation as the nightly run,
// so nobody gets it twice, nor again from the nightly run. A reached cap stops it instead
// of waiting.
func (r *Runner) SendManual(ctx context.Context, m Manual) (sent int, err error) {
	subs, _, err := r.ManualRecipients(ctx, m)
	if err != nil {
		return 0, err
	}
	tomorrow := r.Schedule.Day(r.Now()).AddDate(0, 0, 1)
	y, mo, _ := r.Now().In(r.Schedule.Location()).Date()
	monthStart := time.Date(y, mo, 1, 0, 0, 0, 0, r.Schedule.Location())
	failures := 0
	for i, s := range subs {
		if i > 0 {
			if sleepErr := r.sleep(ctx, r.Interval); sleepErr != nil {
				return sent, errors.Join(err, sleepErr)
			}
		}
		if capErr := r.waitForCap(ctx, monthStart, r.Now(), len(subs), sent); capErr != nil {
			return sent, errors.Join(err, capErr)
		}
		attempted, sendErr := r.Store.SendReminder(ctx, s, tomorrow, []int{m.Zone}, func(current store.Subscriber) (string, error) {
			return r.Sender.Send(ctx, wa.NewText(wa.Recipient{UserID: current.UserID, Phone: current.Phone}, m.Text))
		})
		if sendErr != nil {
			err = errors.Join(err, fmt.Errorf("subscriber %d: %w", s.ID, sendErr))
			r.Log.Error("manual reminder failed", "subscriber", s.ID, "err", sendErr)
			if failures++; failures >= maxConsecutiveFailures {
				return sent, err
			}
			continue
		}
		if attempted {
			failures = 0
			sent++
		}
	}
	return sent, err
}
