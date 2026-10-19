package store

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5"
)

// WebReport is one report from the map on /reportes. Colonia is "name|municipio|postal code".
type WebReport struct {
	Colonia                 string
	Status                  string // sin_agua, baja or con_agua
	Turbia, Olor, Sedimento bool
	At                      time.Time
}

// SaveWebReports stores a batch of reports in one statement.
func (db *DB) SaveWebReports(ctx context.Context, rs []WebReport) error {
	if len(rs) == 0 {
		return nil
	}
	rows := make([][]any, len(rs))
	for i, r := range rs {
		rows[i] = []any{r.Colonia, r.Status, r.Turbia, r.Olor, r.Sedimento, r.At}
	}
	_, err := db.pool.CopyFrom(ctx, pgx.Identifier{"web_report"},
		[]string{"colonia", "status", "turbia", "olor", "sedimento", "created_at"}, pgx.CopyFromRows(rows))
	return err
}

// WebReportsSince returns the reports made since the given time, oldest first.
func (db *DB) WebReportsSince(ctx context.Context, since time.Time) ([]WebReport, error) {
	rows, err := db.q.Query(ctx, `select colonia, status, turbia, olor, sedimento, created_at
		from web_report where created_at >= $1 order by created_at, id`, since)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (WebReport, error) {
		var w WebReport
		err := r.Scan(&w.Colonia, &w.Status, &w.Turbia, &w.Olor, &w.Sedimento, &w.At)
		return w, err
	})
}

// CountWebReports counts every report since the map opened.
func (db *DB) CountWebReports(ctx context.Context) (int, error) {
	var n int
	err := db.q.QueryRow(ctx, `select count(*) from web_report`).Scan(&n)
	return n, err
}

// BotAnswer is how many subscribers in a zone gave an answer since a time: to the reminder's
// «¿Ahorita tienes agua?» (si, poca, no) or to REPORTAR (normal, baja, no_regreso, turbia).
type BotAnswer struct {
	Zone   int
	Answer string
	Count  int
}

// BotAnswersSince counts the bot's answers by zone since the given time.
func (db *DB) BotAnswersSince(ctx context.Context, since time.Time) ([]BotAnswer, error) {
	rows, err := db.q.Query(ctx, `select zone, answer, count(*)::int from water_report where created_at >= $1 group by zone, answer
		union all
		select zone, answer, count(*)::int from cut_report where created_at >= $1 group by zone, answer
		order by 1, 2`, since)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (BotAnswer, error) {
		var a BotAnswer
		err := r.Scan(&a.Zone, &a.Answer, &a.Count)
		return a, err
	})
}

// DayCount is how many reports or answers with one answer a colonia (the map's) or a zone
// (the bot's) got on one day in Guadalajara.
type DayCount struct {
	Colonia string
	Zone    int
	Day     time.Time // the date, at midnight UTC
	Answer  string
	Count   int
}

// WebReportsByDay counts the map's reports by colonia, local day and answer since a time.
func (db *DB) WebReportsByDay(ctx context.Context, since time.Time) ([]DayCount, error) {
	rows, err := db.q.Query(ctx, `select colonia, (created_at at time zone 'America/Mexico_City')::date, status, count(*)::int
		from web_report where created_at >= $1 group by 1, 2, 3 order by 2, 1, 3`, since)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (DayCount, error) {
		var c DayCount
		err := r.Scan(&c.Colonia, &c.Day, &c.Answer, &c.Count)
		return c, err
	})
}

// BotAnswersByDay counts the bot's answers by zone, local day and answer since a time.
func (db *DB) BotAnswersByDay(ctx context.Context, since time.Time) ([]DayCount, error) {
	rows, err := db.q.Query(ctx, `select zone, (created_at at time zone 'America/Mexico_City')::date as day, answer, count(*)::int
		from water_report where created_at >= $1 group by 1, 2, 3
		union all
		select zone, (created_at at time zone 'America/Mexico_City')::date, answer, count(*)::int
		from cut_report where created_at >= $1 group by 1, 2, 3
		order by 2, 1, 3`, since)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (DayCount, error) {
		var c DayCount
		err := r.Scan(&c.Zone, &c.Day, &c.Answer, &c.Count)
		return c, err
	})
}
