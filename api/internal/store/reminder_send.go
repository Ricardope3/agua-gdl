package store

import (
	"context"
	"errors"
	"slices"
	"time"

	"github.com/jackc/pgx/v5"
)

// A send error that says the message was refused, so it was never delivered and can be
// retried; Gone means the recipient can never be reached again, e.g. they blocked the bot.
type rejection interface{ Rejected() bool }
type gone interface{ Gone() bool }

// SendReminder durably reserves a single attempt before contacting WhatsApp or Telegram.
// A crash or an ambiguous HTTP failure leaves a visible unresolved attempt;
// it must not be retried automatically, since it may have been accepted.
// Only attempts explicitly rejected are retried by a later run.
// zones are the zones cut on cutDate: a subscriber who moved between two of them
// mid-batch still gets the reminder, for the zone they're in now.
func (db *DB) SendReminder(ctx context.Context, s Subscriber, cutDate time.Time, zones []int, send func(Subscriber) (string, error)) (attempted bool, err error) {
	var reminderID int64
	err = db.pool.QueryRow(ctx, `insert into reminder (subscriber_id, zone, cut_date, status, channel)
		select id, zone, $3::date, 'sending', channel from subscriber where id = $1 and zone = any($2::int[])
		on conflict (subscriber_id, cut_date) do update set status = 'sending', zone = excluded.zone, sent_at = now()
			where reminder.status = 'rejected'
		returning id`, s.ID, zones, cutDate.Format(dateLayout)).Scan(&reminderID)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return db.sendReserved(ctx, "reminder", reminderID, s.ID, zones, send)
}

// sendReserved makes the request for a reservation in table (reminder or notice)
// and records the outcome.
func (db *DB) sendReserved(ctx context.Context, table string, id, subscriberID int64, zones []int, send func(Subscriber) (string, error)) (attempted bool, err error) {
	var sendErr error
	err = pgx.BeginFunc(ctx, db.pool, func(tx pgx.Tx) error {
		// Serialize the actual send with BAJA and zone changes. Once BAJA commits,
		// no queued message can start sending to that subscription.
		var current Subscriber
		err := tx.QueryRow(ctx, `select id, channel, user_id, coalesce(phone, ''), zone
			from subscriber where id = $1 for update`, subscriberID).
			Scan(&current.ID, &current.Channel, &current.UserID, &current.Phone, &current.Zone)
		if errors.Is(err, pgx.ErrNoRows) || (err == nil && !slices.Contains(zones, current.Zone)) {
			// No HTTP request was made, so removing this reservation is safe.
			_, err = tx.Exec(ctx, `delete from `+table+` where id = $1`, id)
			return err
		}
		if err != nil {
			return err
		}
		attempted = true
		var wamid string
		wamid, sendErr = send(current)
		status := "sent"
		var rejected rejection
		var unreachable gone
		switch {
		case errors.As(sendErr, &unreachable) && unreachable.Gone():
			// Blocking the bot is an opt-out: forget the subscription, as BAJA does.
			status = "blocked"
			if _, err := tx.Exec(ctx, `delete from subscriber where id = $1`, subscriberID); err != nil {
				return err
			}
		case errors.As(sendErr, &rejected) && rejected.Rejected():
			status = "rejected"
		case sendErr != nil:
			status = "uncertain"
		}
		_, err = tx.Exec(ctx, `update `+table+` set wamid_hash = nullif($2, ''), status = $3, zone = $4 where id = $1`, id, hashID(wamid), status, current.Zone)
		return err
	})
	return attempted, errors.Join(err, sendErr)
}

// NoticeRecipients lists a channel's subscribers in zone who haven't received the notice
// key, including those whose earlier attempt was rejected.
func (db *DB) NoticeRecipients(ctx context.Context, channel string, zone int, key string) ([]Subscriber, error) {
	rows, err := db.q.Query(ctx, `select s.id, s.channel, s.user_id, coalesce(s.phone, ''), s.zone from subscriber s
		where s.channel = $3 and s.zone = $1 and not exists (
			select 1 from notice n where n.subscriber_id = s.id and n.key = $2 and n.status <> 'rejected')
		order by s.id`, zone, key, channel)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (Subscriber, error) {
		var s Subscriber
		err := r.Scan(&s.ID, &s.Channel, &s.UserID, &s.Phone, &s.Zone)
		return s, err
	})
}

// SendNotice sends a one-off notice, such as a schedule change, at most once per
// subscriber and key, with the same guarantees as SendReminder.
func (db *DB) SendNotice(ctx context.Context, s Subscriber, key string, send func(Subscriber) (string, error)) (attempted bool, err error) {
	var id int64
	err = db.pool.QueryRow(ctx, `insert into notice (subscriber_id, key, zone, status, channel)
		select id, $2, zone, 'sending', channel from subscriber where id = $1 and zone = $3
		on conflict (subscriber_id, key) do update set status = 'sending', sent_at = now()
			where notice.status = 'rejected'
		returning id`, s.ID, key, s.Zone).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return db.sendReserved(ctx, "notice", id, s.ID, []int{s.Zone}, send)
}

// UnresolvedReminders also catches interrupted attempts on a subsequent startup.
func (db *DB) UnresolvedReminders(ctx context.Context, channel string, cutDate time.Time) (int, error) {
	var n int
	err := db.pool.QueryRow(ctx, `select count(*) from reminder where channel = $2 and cut_date = $1::date
		and status in ('sending', 'uncertain', 'rejected', 'failed')`, cutDate.Format(dateLayout), channel).Scan(&n)
	return n, err
}
