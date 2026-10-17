// Package store keeps subscribers, sent reminders and cut reports in Postgres.
package store

import (
	"context"
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"errors"
	"fmt"
	"io/fs"
	"sort"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

const dateLayout = "2006-01-02"

// hashID keeps WhatsApp message IDs out of the database: a wamid embeds the phone number.
func hashID(wamid string) string {
	if wamid == "" {
		return ""
	}
	sum := sha256.Sum256([]byte(wamid))
	return hex.EncodeToString(sum[:])
}

//go:embed migrations/*.sql
var migrations embed.FS

// Channels a subscriber can receive reminders on.
const (
	WhatsApp = "wa"
	Telegram = "tg"
)

type Subscriber struct {
	ID        int64
	Channel   string
	UserID    string // WhatsApp's business-scoped user ID, or the Telegram chat ID
	Phone     string
	Zone      int
	UpdatedAt time.Time // last subscription or zone change; set by DueSubscribers only
}

type Result struct {
	Zone      int    `json:"zone"`
	Date      string `json:"date"`
	Total     int    `json:"total"`
	Normal    int    `json:"normal"`
	Baja      int    `json:"baja"`
	NoRegreso int    `json:"no_regreso"`
	Turbia    int    `json:"turbia"`
	LastAt    string `json:"last_report_at"`
}

type querier interface {
	Exec(context.Context, string, ...any) (pgconn.CommandTag, error)
	Query(context.Context, string, ...any) (pgx.Rows, error)
	QueryRow(context.Context, string, ...any) pgx.Row
}

type DB struct {
	pool *pgxpool.Pool
	q    querier
}

func Open(ctx context.Context, url string) (*DB, error) {
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		return nil, err
	}
	// Neon suspends compute after 5 idle minutes; drop idle connections before that.
	cfg.MaxConnIdleTime = 4 * time.Minute
	cfg.MaxConnLifetime = 30 * time.Minute
	cfg.MaxConns = 5
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return &DB{pool: pool, q: pool}, nil
}

func (db *DB) Close() { db.pool.Close() }

// migrateLock is the advisory lock key that serializes migrations across machines.
const migrateLock = 7_103_115_241_817

func (db *DB) Migrate(ctx context.Context) error {
	// A session-level lock, so it needs a direct connection, not a transaction pooler.
	conn, err := db.pool.Acquire(ctx)
	if err != nil {
		return err
	}
	defer conn.Release()
	if _, err := conn.Exec(ctx, `select pg_advisory_lock($1)`, migrateLock); err != nil {
		return err
	}
	defer conn.Exec(context.WithoutCancel(ctx), `select pg_advisory_unlock($1)`, migrateLock)
	if _, err := conn.Exec(ctx, `create table if not exists schema_migrations (
		version text primary key, applied_at timestamptz not null default now())`); err != nil {
		return err
	}
	names, err := fs.Glob(migrations, "migrations/*.sql")
	if err != nil {
		return err
	}
	sort.Strings(names)
	for _, name := range names {
		var done bool
		if err := conn.QueryRow(ctx, `select exists(select 1 from schema_migrations where version = $1)`, name).Scan(&done); err != nil {
			return err
		}
		if done {
			continue
		}
		sql, err := migrations.ReadFile(name)
		if err != nil {
			return err
		}
		err = pgx.BeginFunc(ctx, conn, func(tx pgx.Tx) error {
			if _, err := tx.Exec(ctx, string(sql)); err != nil {
				return err
			}
			_, err := tx.Exec(ctx, `insert into schema_migrations (version) values ($1)`, name)
			return err
		})
		if err != nil {
			return fmt.Errorf("migration %s: %w", name, err)
		}
	}
	return nil
}

// DeleteSubscribers removes every subscription; reports and reminders stay, unlinked.
func (db *DB) DeleteSubscribers(ctx context.Context) (int64, error) {
	tag, err := db.q.Exec(ctx, `delete from subscriber`)
	return tag.RowsAffected(), err
}

func (db *DB) PurgeSeen(ctx context.Context, before time.Time) error {
	_, err := db.q.Exec(ctx, `delete from inbound_seen where seen_at < $1`, before)
	return err
}

func (db *DB) Subscriber(ctx context.Context, channel, userID string) (Subscriber, bool, error) {
	s := Subscriber{Channel: channel, UserID: userID}
	err := db.q.QueryRow(ctx, `select id, zone from subscriber where channel = $1 and user_id = $2`, channel, userID).Scan(&s.ID, &s.Zone)
	if errors.Is(err, pgx.ErrNoRows) {
		return Subscriber{}, false, nil
	}
	return s, err == nil, err
}

// Subscribe stores userID's zone. WhatsApp reminders go to the phone, so whoever writes
// from a number now owns it: any other subscription holding that number is dropped.
func (db *DB) Subscribe(ctx context.Context, channel, userID, phone string, zone int) error {
	if _, err := db.q.Exec(ctx, `delete from subscriber where phone = nullif($3, '')
		and not (channel = $1 and user_id = $2)`, channel, userID, phone); err != nil {
		return err
	}
	_, err := db.q.Exec(ctx, `insert into subscriber (channel, user_id, phone, zone) values ($1, $2, nullif($3, ''), $4)
		on conflict (channel, user_id) do update set zone = excluded.zone,
			phone = coalesce(excluded.phone, subscriber.phone), updated_at = now()`, channel, userID, phone, zone)
	return err
}

// ChangeUser moves a WhatsApp subscription to the user's new WhatsApp ID and number. The old
// number is never kept: it may be reassigned to someone else. Without a new ID the
// subscription is dropped. One row survives: an existing subscription for newUserID,
// else the one for oldUserID, else the newest holding oldPhone. Every other row with
// the old ID or phone, the new ID or the new phone is deleted, even when none survives.
// The survivor keeps its updated_at: no confirmation is sent, so the nightly run must
// still remind it.
func (db *DB) ChangeUser(ctx context.Context, oldUserID, oldPhone, newUserID, newPhone string) error {
	const old = `((channel = 'wa' and user_id = $1) or phone = nullif($2, ''))`
	if newUserID == "" {
		_, err := db.q.Exec(ctx, `delete from subscriber where `+old, oldUserID, oldPhone)
		return err
	}
	var keep int64
	err := db.q.QueryRow(ctx, `select id from subscriber where (channel = 'wa' and user_id = $3) or `+old+`
		order by user_id = $3 desc, user_id = $1 desc, id desc limit 1`, oldUserID, oldPhone, newUserID).Scan(&keep)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	if _, err := db.q.Exec(ctx, `delete from subscriber where id <> $5
		and ((channel = 'wa' and user_id = $3) or `+old+` or phone = nullif($4, ''))`, oldUserID, oldPhone, newUserID, newPhone, keep); err != nil {
		return err
	}
	if keep == 0 {
		return nil
	}
	_, err = db.q.Exec(ctx, `update subscriber set user_id = $2, phone = nullif($3, '') where id = $1`,
		keep, newUserID, newPhone)
	return err
}

// admissionLock serializes the capacity check with the subscription that follows it.
const admissionLock = 7_103_115_241_818

// ZoneCounts returns the number of WhatsApp subscribers in each zone, the ones Meta's
// messaging limit applies to. Inside ProcessInbound it holds a lock until the transaction
// ends, so two people can't both take a night's last slot.
func (db *DB) ZoneCounts(ctx context.Context) (map[int]int, error) {
	if _, err := db.q.Exec(ctx, `select pg_advisory_xact_lock($1)`, admissionLock); err != nil {
		return nil, err
	}
	rows, err := db.q.Query(ctx, `select zone, count(*) from subscriber where channel = 'wa' group by zone`)
	if err != nil {
		return nil, err
	}
	counts := map[int]int{}
	var zone, n int
	_, err = pgx.ForEachRow(rows, []any{&zone, &n}, func() error {
		counts[zone] = n
		return nil
	})
	return counts, err
}

// Unsubscribe deletes userID's subscription and any holding phone, so BAJA stops
// every reminder to that number.
func (db *DB) Unsubscribe(ctx context.Context, channel, userID, phone string) (bool, error) {
	tag, err := db.q.Exec(ctx, `delete from subscriber where (channel = $1 and user_id = $2) or phone = nullif($3, '')`, channel, userID, phone)
	return tag.RowsAffected() > 0, err
}

func (db *DB) SaveReport(ctx context.Context, subscriberID int64, zone int, cutDate time.Time, answer string) error {
	_, err := db.q.Exec(ctx, `insert into cut_report (subscriber_id, zone, cut_date, answer) values ($1, $2, $3::date, $4)
		on conflict (subscriber_id, cut_date) do update set answer = excluded.answer, zone = excluded.zone, created_at = now()`,
		subscriberID, zone, cutDate.Format(dateLayout), answer)
	return err
}

// UpdateStatus records a delivery status and reports whether it changed a reminder.
func (db *DB) UpdateStatus(ctx context.Context, wamid, status string) (bool, error) {
	const progress = `array_position(array['sent','delivered','read','failed'], status) < array_position(array['sent','delivered','read','failed'], $2)`
	if _, err := db.q.Exec(ctx, `update notice set status = $2 where wamid_hash = $1 and `+progress, hashID(wamid), status); err != nil {
		return false, err
	}
	tag, err := db.q.Exec(ctx, `update reminder set status = $2 where wamid_hash = $1 and `+progress, hashID(wamid), status)
	return tag.RowsAffected() > 0, err
}

// DueSubscribers lists a channel's subscribers in zones that haven't been reminded about
// cutDate yet, including those whose earlier attempt was rejected.
func (db *DB) DueSubscribers(ctx context.Context, channel string, zones []int, cutDate time.Time) ([]Subscriber, error) {
	rows, err := db.q.Query(ctx, `select s.id, s.channel, s.user_id, coalesce(s.phone, ''), s.zone, s.updated_at from subscriber s
		where s.channel = $3 and s.zone = any($1::int[]) and not exists (
			select 1 from reminder r where r.subscriber_id = s.id and r.cut_date = $2::date and r.status <> 'rejected')
		order by s.id`, zones, cutDate.Format(dateLayout), channel)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (Subscriber, error) {
		var s Subscriber
		err := r.Scan(&s.ID, &s.Channel, &s.UserID, &s.Phone, &s.Zone, &s.UpdatedAt)
		return s, err
	})
}

// RecipientsSince counts the distinct people sent a WhatsApp template since the given
// time, which is what Meta's messaging limit counts.
func (db *DB) RecipientsSince(ctx context.Context, since time.Time) (int, error) {
	var n int
	err := db.q.QueryRow(ctx, `select count(distinct coalesce(subscriber_id::text, t || id)) from (
			select subscriber_id, id, 'r' t from reminder where channel = 'wa' and sent_at >= $1 and status <> 'rejected'
			union all
			select subscriber_id, id, 'n' from notice where channel = 'wa' and sent_at >= $1 and status <> 'rejected') m`, since).Scan(&n)
	return n, err
}

// SentSince counts the WhatsApp messages sent since the given time, which is what costs money.
func (db *DB) SentSince(ctx context.Context, since time.Time) (int, error) {
	var n int
	err := db.q.QueryRow(ctx, `select (select count(*) from reminder where channel = 'wa' and sent_at >= $1 and status <> 'rejected')
		+ (select count(*) from notice where channel = 'wa' and sent_at >= $1 and status <> 'rejected')`, since).Scan(&n)
	return n, err
}

// Results counts reports per zone and cut day, hiding any day with fewer than minReports.
// The last report time is truncated to the hour so it can't single out a reporter.
func (db *DB) Results(ctx context.Context, since time.Time, minReports int) ([]Result, error) {
	rows, err := db.q.Query(ctx, `select zone, cut_date::text, count(*),
			count(*) filter (where answer = 'normal'), count(*) filter (where answer = 'baja'),
			count(*) filter (where answer = 'no_regreso'), count(*) filter (where answer = 'turbia'),
			to_char(date_trunc('hour', max(created_at) at time zone 'America/Mexico_City'), 'YYYY-MM-DD"T"HH24:MI')
		from cut_report where cut_date >= $1::date
		group by zone, cut_date having count(*) >= $2
		order by cut_date desc, zone`, since.Format(dateLayout), minReports)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (Result, error) {
		var x Result
		err := r.Scan(&x.Zone, &x.Date, &x.Total, &x.Normal, &x.Baja, &x.NoRegreso, &x.Turbia, &x.LastAt)
		return x, err
	})
}
