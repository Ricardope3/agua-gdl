// Package reminders sends the evening-before WhatsApp reminder to every subscriber whose zone is cut tomorrow.
package reminders

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strconv"
	"time"

	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/wa"
)

type Store interface {
	DueSubscribers(ctx context.Context, zones []int, cutDate time.Time) ([]store.Subscriber, error)
	SendReminder(ctx context.Context, s store.Subscriber, cutDate time.Time, send func(store.Subscriber) (string, error)) (bool, error)
	UnresolvedReminders(ctx context.Context, cutDate time.Time) (int, error)
	SentSince(ctx context.Context, since time.Time) (int, error)
}

type Sender interface {
	Send(ctx context.Context, m wa.Message) (string, error)
}

type Runner struct {
	Store        Store
	Sender       Sender
	Schedule     *rotation.Schedule
	Template     string
	Language     string
	Hour         int // local hour to send, e.g. 20
	CatchUpUntil int // after a restart, still send until this hour
	DailyCap     int
	MonthlyCap   int
	Interval     time.Duration
	Heartbeat    func(ctx context.Context, ok bool, msg string) // optional dead-man's switch
	Now          func() time.Time
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

func (r *Runner) runOnce(ctx context.Context) {
	err := r.SendTonight(ctx)
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

func (r *Runner) SendTonight(ctx context.Context) (err error) {
	now := r.Now()
	tomorrow := r.Schedule.Day(now).AddDate(0, 0, 1)
	defer func() {
		n, checkErr := r.Store.UnresolvedReminders(ctx, tomorrow)
		err = errors.Join(err, checkErr)
		if n > 0 {
			err = errors.Join(err, fmt.Errorf("%d failed or uncertain reminder attempts require review", n))
		}
	}()
	zones := r.Schedule.ZonesOn(tomorrow)
	if len(zones) == 0 {
		return nil
	}
	subs, err := r.Store.DueSubscribers(ctx, zones, tomorrow)
	if err != nil || len(subs) == 0 {
		return err
	}
	y, m, _ := now.In(r.Schedule.Location()).Date()
	monthStart := time.Date(y, m, 1, 0, 0, 0, 0, r.Schedule.Location())
	date := rotation.DateES(tomorrow)
	sent, failures := 0, 0
	for i, s := range subs {
		if i > 0 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(r.Interval):
			}
		}
		capped, capErr := r.capReached(ctx, monthStart)
		if capErr != nil {
			return errors.Join(err, capErr)
		}
		if capped {
			r.Log.Error("send cap reached; the rest will not get tonight's reminder", "due", len(subs), "sent", sent)
			return errors.Join(err, ErrCapped)
		}
		attempted, sendErr := r.Store.SendReminder(ctx, s, tomorrow, func(current store.Subscriber) (string, error) {
			return r.Sender.Send(ctx, r.reminder(current, date))
		})
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
	r.Log.Info("reminders sent", "date", tomorrow.Format(rotation.DateLayout), "zones", zones, "sent", sent, "due", len(subs))
	return err
}

// capReached checks the caps before every send: Meta's limit is a moving 24-hour
// window, so last night's reminders expire while tonight's go out.
func (r *Runner) capReached(ctx context.Context, monthStart time.Time) (bool, error) {
	day, err := r.Store.SentSince(ctx, r.Now().Add(-24*time.Hour))
	if err != nil {
		return false, err
	}
	month, err := r.Store.SentSince(ctx, monthStart)
	if err != nil {
		return false, err
	}
	return day >= r.DailyCap || month >= r.MonthlyCap, nil
}

func (r *Runner) reminder(s store.Subscriber, date string) wa.Message {
	return wa.NewTemplate(wa.Recipient{UserID: s.UserID, Phone: s.Phone}, r.Template, r.Language,
		wa.BodyParams(date, strconv.Itoa(s.Zone)),
		wa.QuickReply(0, "BAJA"))
}
