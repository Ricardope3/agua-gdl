// Package reminders sends the evening-before reminder, on WhatsApp and Telegram, to every
// subscriber whose zone's block of cuts starts tomorrow; on Telegram also a notice two days
// before each block, and afterwards a question to whoever said they had no water.
package reminders

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"slices"
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
	SendReminder(ctx context.Context, s store.Subscriber, cutDate time.Time, zones []int, budget *store.Budget, send func(store.Subscriber) (string, error)) (bool, error)
	UnresolvedReminders(ctx context.Context, channel string, cutDate time.Time) (int, error)
	NoWater(ctx context.Context, start time.Time) (map[int64]bool, error)
	NoticeRecipients(ctx context.Context, channel string, zone int, key string) ([]store.Subscriber, error)
	ReturnRecipients(ctx context.Context, channel string, zone int, start, last time.Time) ([]store.Subscriber, error)
	SendNotice(ctx context.Context, s store.Subscriber, key string, budget *store.Budget, send func(store.Subscriber) (string, error)) (bool, error)
	UnresolvedNotices(ctx context.Context, channel, key string) (int, error)
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
// waking up, or had sends refused, until the catch-up deadline; only refused sends are
// sent again, since nothing was delivered.
func (r *Runner) runOnce(ctx context.Context) {
	deadline := r.Schedule.Day(r.Now()).Add(time.Duration(r.CatchUpUntil) * time.Hour)
	err := r.SendTonight(ctx)
	for wait := time.Minute; (errors.Is(err, errTransient) || errors.Is(err, errRejected)) && r.Now().Add(wait).Before(deadline); wait = min(2*wait, 10*time.Minute) {
		r.Log.Warn("reminders incomplete; retrying", "err", err, "in", wait)
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

var errRejected = errors.New("some sends were refused; they are retried")

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
		err = errors.Join(err, r.sendChannel(ctx, store.Telegram), r.sendAhead(ctx), r.askReturn(ctx))
	}
	return err
}

func (r *Runner) sendChannel(ctx context.Context, channel string) (err error) {
	now := r.Now()
	tomorrow := r.Schedule.Day(now).AddDate(0, 0, 1)
	rejected := false
	defer func() {
		n, checkErr := r.Store.UnresolvedReminders(ctx, channel, tomorrow)
		err = errors.Join(err, transient(checkErr))
		if n > 0 {
			err = errors.Join(err, fmt.Errorf("%s: %d failed or uncertain reminder attempts require review", channel, n))
		}
		if rejected {
			err = errors.Join(err, errRejected)
		}
	}()
	// A block of cuts gets one reminder, the evening before its first day.
	zones := slices.DeleteFunc(r.Schedule.ZonesOn(tomorrow), func(z int) bool { return !r.Schedule.StartsBlock(z, tomorrow) })
	if len(zones) == 0 {
		return nil
	}
	subs, err := r.Store.DueSubscribers(ctx, channel, zones, tomorrow)
	if err != nil {
		return transient(err)
	}
	// Whoever subscribed or changed zone after the reminder hour was told about tomorrow's
	// cut in the confirmation; skipping them also keeps BAJA + re-subscribe from repeating it.
	remindAt := r.Schedule.Day(now).Add(time.Duration(r.Hour) * time.Hour)
	subs = slices.DeleteFunc(subs, func(s store.Subscriber) bool { return !s.UpdatedAt.Before(remindAt) })
	// Whoever already said they have no water learns nothing from «llena tu tinaco».
	dry, err := r.Store.NoWater(ctx, tomorrow)
	if err != nil {
		return transient(err)
	}
	subs = slices.DeleteFunc(subs, func(s store.Subscriber) bool { return dry[s.ID] })
	if len(subs) == 0 {
		return nil
	}
	deadline := r.Schedule.Day(now).Add(time.Duration(r.CatchUpUntil) * time.Hour)
	date := rotation.DateES(tomorrow)
	sent, failures := 0, 0
	for i, s := range subs {
		if i > 0 {
			if sleepErr := r.sleep(ctx, r.Interval); sleepErr != nil {
				return errors.Join(err, sleepErr)
			}
		}
		// A send that has started finishes and is recorded even during shutdown;
		// the HTTP clients have their own timeouts.
		sendCtx := context.WithoutCancel(ctx)
		var attempted bool
		var sendErr error
		for {
			var budget *store.Budget
			if channel == store.WhatsApp {
				if capErr := r.waitForCap(ctx, deadline, len(subs), sent); capErr != nil {
					if !errors.Is(capErr, ErrCapped) {
						capErr = transient(capErr)
					}
					return errors.Join(err, capErr)
				}
				budget = r.budget()
			}
			attempted, sendErr = r.Store.SendReminder(sendCtx, s, tomorrow, zones, budget, func(current store.Subscriber) (string, error) {
				if current.Channel == store.Telegram {
					m, err := bot.TelegramReminder(current.UserID, current.Zone, r.Schedule.Block(current.Zone, tomorrow))
					if err != nil {
						return "", err
					}
					return "", r.sendTelegram(ctx, sendCtx, m)
				}
				return r.Sender.Send(sendCtx, r.reminder(current, date))
			})
			// Another sender may have taken the last slot since waitForCap looked.
			if !errors.Is(sendErr, store.ErrOverBudget) {
				break
			}
		}
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
			var refused interface{ Rejected() bool }
			rejected = rejected || errors.As(sendErr, &refused) && refused.Rejected()
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
func (r *Runner) waitForCap(ctx context.Context, deadline time.Time, due, sent int) error {
	waiting := false
	for {
		b := r.budget()
		month, err := r.Store.SentSince(ctx, b.MonthStart)
		if err != nil {
			return err
		}
		if month >= r.MonthlyCap {
			r.Log.Error("monthly cap reached; the rest will not get tonight's reminder", "due", due, "sent", sent)
			return ErrCapped
		}
		day, err := r.Store.RecipientsSince(ctx, b.DayStart)
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

// budget is WhatsApp's caps as of now.
func (r *Runner) budget() *store.Budget {
	b := store.NewBudget(r.DailyCap, r.MonthlyCap, r.Now().In(r.Schedule.Location()))
	return &b
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

// sendTelegram waits out Telegram's "too many requests" a few times, and a network blip
// that kept the request from going out: neither sent the message, so trying again can't
// duplicate it. Waits stop at shutdown (ctx); requests use sendCtx, which doesn't.
func (r *Runner) sendTelegram(ctx, sendCtx context.Context, m tg.Message) error {
	for attempt := 0; ; attempt++ {
		_, err := r.Telegram.Send(sendCtx, m)
		var apiErr *tg.APIError
		var notSent *tg.NotSentError
		var wait time.Duration
		switch {
		case err == nil || attempt == 3:
			return err
		case errors.As(err, &apiErr) && apiErr.Status == 429:
			wait = time.Duration(min(max(apiErr.RetryAfter, 1), 30)) * time.Second
		case errors.As(err, &notSent):
			wait = time.Duration(5<<attempt) * time.Second
		default:
			return err
		}
		if sleepErr := r.sleep(ctx, wait); sleepErr != nil {
			return errors.Join(err, sleepErr)
		}
	}
}

// sendAhead sends Telegram's notice two days before each block of cuts: neighbours report
// the water goes a day early, so the evening before can be too late.
func (r *Runner) sendAhead(ctx context.Context) error {
	start := r.Schedule.Day(r.Now()).AddDate(0, 0, 2)
	var err error
	for _, zone := range r.Schedule.ZonesOn(start) {
		if !r.Schedule.StartsBlock(zone, start) {
			continue
		}
		subs, qErr := r.Store.NoticeRecipients(ctx, store.Telegram, zone, store.AheadKey(start))
		if qErr != nil {
			err = errors.Join(err, transient(qErr))
			continue
		}
		err = errors.Join(err, r.sendNotices(ctx, subs, store.AheadKey(start), func(s store.Subscriber) (tg.Message, error) {
			return bot.TelegramNotice(s.UserID, s.Zone, r.Schedule.Block(s.Zone, start))
		}))
	}
	return err
}

// askReturn asks, the evening after a block of cuts, whoever said they had no water or little
// whether it came back; not on a night their zone gets a notice, whose question covers it.
func (r *Runner) askReturn(ctx context.Context) error {
	today := r.Schedule.Day(r.Now())
	last := today.AddDate(0, 0, -1)
	var err error
	for _, zone := range r.Schedule.ZonesOn(last) {
		if !r.Schedule.EndsBlock(zone, last) || r.Schedule.StartsBlock(zone, today.AddDate(0, 0, 2)) {
			continue
		}
		start, _ := r.Schedule.BlockStart(zone, last)
		subs, qErr := r.Store.ReturnRecipients(ctx, store.Telegram, zone, start, last)
		if qErr != nil {
			err = errors.Join(err, transient(qErr))
			continue
		}
		days := r.Schedule.Block(zone, start)
		err = errors.Join(err, r.sendNotices(ctx, subs, store.ReturnKey(start), func(s store.Subscriber) (tg.Message, error) {
			return bot.TelegramFollowUp(s.UserID, s.Zone, days)
		}))
	}
	return err
}

// sendNotices sends a Telegram notice to each subscriber through the notice table's
// reservation, so nobody gets it twice, and reports the attempts that need review.
func (r *Runner) sendNotices(ctx context.Context, subs []store.Subscriber, key string, render func(store.Subscriber) (tg.Message, error)) (err error) {
	defer func() {
		n, checkErr := r.Store.UnresolvedNotices(ctx, store.Telegram, key)
		err = errors.Join(err, transient(checkErr))
		if n > 0 {
			err = errors.Join(err, fmt.Errorf("%s: %d failed or uncertain notice attempts require review", key, n))
		}
	}()
	sent, failures := 0, 0
	for i, s := range subs {
		if i > 0 {
			if sleepErr := r.sleep(ctx, r.Interval); sleepErr != nil {
				return errors.Join(err, sleepErr)
			}
		}
		sendCtx := context.WithoutCancel(ctx)
		attempted, sendErr := r.Store.SendNotice(sendCtx, s, key, nil, func(current store.Subscriber) (string, error) {
			m, err := render(current)
			if err != nil {
				return "", err
			}
			return "", r.sendTelegram(ctx, sendCtx, m)
		})
		var unreachable interface{ Gone() bool }
		if errors.As(sendErr, &unreachable) && unreachable.Gone() {
			r.Log.Info("subscriber blocked the bot; subscription deleted", "subscriber", s.ID)
			continue
		}
		if sendErr != nil && !attempted {
			return errors.Join(err, transient(fmt.Errorf("subscriber %d: %w", s.ID, sendErr)))
		}
		if sendErr != nil {
			var refused interface{ Rejected() bool }
			if errors.As(sendErr, &refused) && refused.Rejected() {
				err = errors.Join(err, errRejected)
			}
			err = errors.Join(err, fmt.Errorf("subscriber %d: %w", s.ID, sendErr))
			r.Log.Error("notice attempt failed", "key", key, "subscriber", s.ID, "err", sendErr)
			if failures++; failures >= maxConsecutiveFailures {
				return err
			}
			continue
		}
		if attempted {
			failures = 0
			sent++
		}
	}
	r.Log.Info("notices sent", "key", key, "sent", sent, "due", len(subs))
	return err
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
	failures := 0
	for i, s := range subs {
		if i > 0 {
			if sleepErr := r.sleep(ctx, r.Interval); sleepErr != nil {
				return sent, errors.Join(err, sleepErr)
			}
		}
		if capErr := r.waitForCap(ctx, r.Now(), len(subs), sent); capErr != nil {
			return sent, errors.Join(err, capErr)
		}
		attempted, sendErr := r.Store.SendReminder(ctx, s, tomorrow, []int{m.Zone}, r.budget(), func(current store.Subscriber) (string, error) {
			return r.Sender.Send(ctx, wa.NewText(wa.Recipient{UserID: current.UserID, Phone: current.Phone}, m.Text))
		})
		if errors.Is(sendErr, store.ErrOverBudget) {
			return sent, errors.Join(err, ErrCapped)
		}
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
