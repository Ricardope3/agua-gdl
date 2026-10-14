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
	Subscriber(context.Context, string) (Subscriber, bool, error)
	Subscribe(context.Context, string, string, int) error
	Unsubscribe(context.Context, string) (bool, error)
	SaveReport(context.Context, int64, int, time.Time, string) error
	UpdateStatus(context.Context, string, string) error
}

func (db *DB) ProcessInbound(ctx context.Context, wamid string, process func(BotStore) error) error {
	if wamid == "" {
		return errors.New("missing inbound message ID")
	}
	return pgx.BeginFunc(ctx, db.pool, func(tx pgx.Tx) error {
		tag, err := tx.Exec(ctx, `insert into inbound_seen (wamid) values ($1) on conflict do nothing`, wamid)
		if err != nil || tag.RowsAffected() == 0 {
			return err
		}
		return process(&DB{pool: db.pool, q: tx})
	})
}
