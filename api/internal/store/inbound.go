package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
)

// BotStore scopes command processing to the same transaction as deduplication.
type BotStore interface {
	ProcessInbound(context.Context, string, func(BotStore) error) error
	Subscriber(ctx context.Context, channel, userID string) (Subscriber, bool, error)
	Subscribe(ctx context.Context, channel, userID, phone string, zone int) error
	Unsubscribe(ctx context.Context, channel, userID, phone string) (bool, error)
	ChangeUser(ctx context.Context, oldUserID, oldPhone, newUserID, newPhone string) error
	ZoneCounts(context.Context) (map[int]int, error)
	SaveReport(context.Context, int64, int, time.Time, string) error
	UpdateStatus(context.Context, string, string) (bool, error)
	QueueReply(ctx context.Context, inboundID string, body []byte) error
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
// command, so a retried delivery of the message can still send it.
func (db *DB) QueueReply(ctx context.Context, inboundID string, body []byte) error {
	_, err := db.q.Exec(ctx, `insert into pending_reply (inbound_hash, body) values ($1, $2)`, hashID(inboundID), body)
	return err
}

// SendReplies sends inboundID's queued replies in order, forgetting each one send
// returns nil for. At the first error it stops and keeps that reply and the rest for the
// next delivery of the message. The rows stay locked meanwhile, so a concurrent delivery
// skips them instead of sending them twice.
func (db *DB) SendReplies(ctx context.Context, inboundID string, send func(body []byte) error) error {
	var sendErr error
	err := pgx.BeginFunc(ctx, db.pool, func(tx pgx.Tx) error {
		rows, err := tx.Query(ctx, `select id, body from pending_reply where inbound_hash = $1
			order by id for update skip locked`, hashID(inboundID))
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
		for _, p := range replies {
			if sendErr = send(p.body); sendErr != nil {
				return nil // commit what was sent
			}
			if _, err := tx.Exec(ctx, `delete from pending_reply where id = $1`, p.id); err != nil {
				return err
			}
		}
		return nil
	})
	return errors.Join(err, sendErr)
}
