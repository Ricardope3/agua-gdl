package store

import (
	"context"
	"errors"
	"slices"
	"time"

	"github.com/jackc/pgx/v5"

	"aguagdl/api/internal/wa"
)

// SendReminder durably reserves a single attempt before contacting WhatsApp.
// A crash or an ambiguous HTTP failure leaves a visible unresolved attempt;
// it must not be retried automatically, since WhatsApp may have accepted it.
// Only attempts Meta explicitly rejected are retried by a later run.
// zones are the zones cut on cutDate: a subscriber who moved between two of them
// mid-batch still gets the reminder, for the zone they're in now.
func (db *DB) SendReminder(ctx context.Context, s Subscriber, cutDate time.Time, zones []int, send func(Subscriber) (string, error)) (attempted bool, err error) {
	var reminderID int64
	err = db.pool.QueryRow(ctx, `insert into reminder (subscriber_id, zone, cut_date, status)
		select id, zone, $3::date, 'sending' from subscriber where id = $1 and zone = any($2::int[])
		on conflict (subscriber_id, cut_date) do update set status = 'sending', zone = excluded.zone, sent_at = now()
			where reminder.status = 'rejected'
		returning id`, s.ID, zones, cutDate.Format(dateLayout)).Scan(&reminderID)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	var sendErr error
	err = pgx.BeginFunc(ctx, db.pool, func(tx pgx.Tx) error {
		// Serialize the actual send with BAJA and zone changes. Once BAJA commits,
		// no queued reminder can start sending to that subscription.
		var current Subscriber
		err := tx.QueryRow(ctx, `select id, wa_user_id, coalesce(phone, ''), zone
			from subscriber where id = $1 for update`, s.ID).
			Scan(&current.ID, &current.UserID, &current.Phone, &current.Zone)
		if errors.Is(err, pgx.ErrNoRows) || (err == nil && !slices.Contains(zones, current.Zone)) {
			// No HTTP request was made, so removing this reservation is safe.
			_, err = tx.Exec(ctx, `delete from reminder where id = $1`, reminderID)
			return err
		}
		if err != nil {
			return err
		}
		attempted = true
		var wamid string
		wamid, sendErr = send(current)
		status := "sent"
		var apiErr *wa.APIError
		switch {
		case errors.As(sendErr, &apiErr) && apiErr.Rejected():
			status = "rejected"
		case sendErr != nil:
			status = "uncertain"
		}
		_, err = tx.Exec(ctx, `update reminder set wamid_hash = nullif($2, ''), status = $3, zone = $4 where id = $1`, reminderID, hashID(wamid), status, current.Zone)
		return err
	})
	return attempted, errors.Join(err, sendErr)
}

// UnresolvedReminders also catches interrupted attempts on a subsequent startup.
func (db *DB) UnresolvedReminders(ctx context.Context, cutDate time.Time) (int, error) {
	var n int
	err := db.pool.QueryRow(ctx, `select count(*) from reminder where cut_date = $1::date
		and status in ('sending', 'uncertain', 'rejected', 'failed')`, cutDate.Format(dateLayout)).Scan(&n)
	return n, err
}
