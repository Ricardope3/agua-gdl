// Package reminders sends the evening-before WhatsApp reminder to every subscriber whose zone is cut tomorrow.
package reminders

import (
	"context"
	"errors"
	"log/slog"
	"strconv"
	"time"

	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/wa"
)

type Store interface {
	DueSubscribers(ctx context.Context, zones []int, cutDate time.Time) ([]store.Subscriber, error)
	RecordReminder(ctx context.Context, s store.Subscriber, cutDate time.Time, wamid string) error
	SentSince(ctx context.Context, since time.Time) (int, error)
	PurgeSeen(ctx context.Context, before time.Time) error
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
	Now          func() time.Time
	Log          *slog.Logger
}

const maxConsecutiveFailures = 5

// Run sends tonight's reminders every day at Hour. Sends are idempotent, so a restart is safe.
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
	if err := r.SendTonight(ctx); err != nil {
		r.Log.Error("reminders failed", "err", err)
	}
}

func (r *Runner) SendTonight(ctx context.Context) error {
	now := r.Now()
	if err := r.Store.PurgeSeen(ctx, now.Add(-7*24*time.Hour)); err != nil {
		r.Log.Warn("purge seen messages", "err", err)
	}
	tomorrow := r.Schedule.Day(now).AddDate(0, 0, 1)
	zones := r.Schedule.ZonesOn(tomorrow)
	if len(zones) == 0 {
		return nil
	}
	subs, err := r.Store.DueSubscribers(ctx, zones, tomorrow)
	if err != nil || len(subs) == 0 {
		return err
	}
	day, err := r.Store.SentSince(ctx, now.Add(-24*time.Hour))
	if err != nil {
		return err
	}
	y, m, _ := now.In(r.Schedule.Location()).Date()
	month, err := r.Store.SentSince(ctx, time.Date(y, m, 1, 0, 0, 0, 0, r.Schedule.Location()))
	if err != nil {
		return err
	}
	if allowed := min(r.DailyCap-day, r.MonthlyCap-month); allowed < len(subs) {
		r.Log.Error("send cap reached; some subscribers will not get tonight's reminder",
			"due", len(subs), "allowed", max(allowed, 0), "sent_24h", day, "sent_month", month)
		subs = subs[:max(allowed, 0)]
	}
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
		id, err := r.Sender.Send(ctx, r.reminder(s, date))
		var apiErr *wa.APIError
		if errors.As(err, &apiErr) && apiErr.Permanent() {
			r.Log.Warn("reminder rejected for this subscriber", "subscriber", s.ID, "err", err)
			continue
		}
		if err != nil {
			failures++
			r.Log.Error("reminder not sent", "subscriber", s.ID, "err", err)
			if failures >= maxConsecutiveFailures {
				return errors.New("too many consecutive send failures; stopping tonight's batch")
			}
			continue
		}
		failures = 0
		if err := r.Store.RecordReminder(ctx, s, tomorrow, id); err != nil {
			return err
		}
		sent++
	}
	r.Log.Info("reminders sent", "date", tomorrow.Format(rotation.DateLayout), "zones", zones, "sent", sent, "due", len(subs))
	return nil
}

func (r *Runner) reminder(s store.Subscriber, date string) wa.Message {
	return wa.NewTemplate(wa.Recipient{UserID: s.UserID, Phone: s.Phone}, r.Template, r.Language,
		wa.BodyParams(date, strconv.Itoa(s.Zone)),
		wa.QuickReply(0, "BAJA"))
}
