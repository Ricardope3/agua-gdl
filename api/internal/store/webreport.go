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
