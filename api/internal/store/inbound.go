package store

import (
	"cmp"
	"context"
	"errors"
	"slices"
	"time"

	"github.com/jackc/pgx/v5"
)

// BotStore scopes command processing to the same transaction as deduplication.
type BotStore interface {
	ProcessInbound(context.Context, string, func(BotStore) error) error
	Subscriber(ctx context.Context, channel, userID string) (Subscriber, bool, error)
	Subscribe(ctx context.Context, channel, userID, phone string, zone int) error
	Unsubscribe(ctx context.Context, channel, userID, phone string) (bool, error)
	UnsubscribeZone(ctx context.Context, channel, userID string, zone int) (bool, bool, error)
	ChangeUser(ctx context.Context, oldUserID, oldPhone, newUserID, newPhone string) error
	ZoneCounts(context.Context) (map[int]int, error)
	NightLoad(context.Context, []int) (int, error)
	SaveReport(context.Context, int64, int, time.Time, string) error
	SaveWater(context.Context, int64, int, time.Time, string) (bool, error)
	NoWater(context.Context, time.Time) (map[int64]bool, error)
	UpdateStatus(context.Context, string, string) (bool, error)
	QueueReply(ctx context.Context, inboundID, channel, userID, phone string, body []byte) error
	SendReplies(ctx context.Context, inboundID string, send func(body []byte) error) error
}

func (db *DB) ProcessInbound(ctx context.Context, wamid string, process func(BotStore) error) error {
	if wamid == "" {
		return errors.New("missing inbound message ID")
	}
	return pgx.BeginFunc(ctx, db.pool, func(tx pgx.Tx) error {
		tag, err := tx.Exec(ctx, `insert into inbound_seen (wamid_hash) values ($1) on conflict do nothing`, hashID(wamid))
		if err != nil || tag.RowsAffected() == 0 {
			return err
		}
		return process(&DB{pool: db.pool, q: tx})
	})
}

// QueueReply stores a reply to the inbound message, in the same transaction as the
// command, so a retried delivery of the message can still send it. The recipient is
// stored apart from the body so BAJA can cancel the replies queued for them.
func (db *DB) QueueReply(ctx context.Context, inboundID, channel, userID, phone string, body []byte) error {
	_, err := db.q.Exec(ctx, `insert into pending_reply (inbound_hash, channel, user_id, phone, body) values ($1, $2, $3, nullif($4, ''), $5)`,
		hashID(inboundID), channel, userID, phone, body)
	return err
}

// SendReplies sends inboundID's queued replies in order. One statement claims them all
// and commits before the first request, and each is forgotten once send returns nil, so
// a reply the provider accepted is never sent again even if forgetting it fails or the
// process dies: its claim stays until the daily purge. When a send fails, or forgetting a
// sent reply does, it releases the replies not yet sent for the next delivery of the
// message. A concurrent delivery finds nothing to claim meanwhile.
func (db *DB) SendReplies(ctx context.Context, inboundID string, send func(body []byte) error) error {
	rows, err := db.pool.Query(ctx, `update pending_reply set claimed_at = now() where id in (
			select id from pending_reply where inbound_hash = $1 and claimed_at is null for update skip locked)
		returning id, body`, hashID(inboundID))
	if err != nil {
		return err
	}
	type pending struct {
		id   int64
		body []byte
	}
	replies, err := pgx.CollectRows(rows, func(r pgx.CollectableRow) (pending, error) {
		var p pending
		err := r.Scan(&p.id, &p.body)
		return p, err
	})
	if err != nil {
		return err
	}
	slices.SortFunc(replies, func(a, b pending) int { return cmp.Compare(a.id, b.id) })
	release := func(unsent []pending) error {
		if len(unsent) == 0 {
			return nil
		}
		ids := make([]int64, 0, len(unsent))
		for _, p := range unsent {
			ids = append(ids, p.id)
		}
		// The failure may be ctx's own deadline, the webhook's.
		ctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
		defer cancel()
		_, err := db.pool.Exec(ctx, `update pending_reply set claimed_at = null where id = any($1::bigint[])`, ids)
		return err
	}
	for i, p := range replies {
		if sendErr := send(p.body); sendErr != nil {
			return errors.Join(sendErr, release(replies[i:]))
		}
		if _, err := db.pool.Exec(ctx, `delete from pending_reply where id = $1`, p.id); err != nil {
			return errors.Join(err, release(replies[i+1:]))
		}
	}
	return nil
}
