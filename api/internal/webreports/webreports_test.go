package webreports

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/store"
)

type fakeStore struct {
	saved    []store.WebReport
	failSave int
	bot      []store.BotAnswer
	botCalls int
}

func (f *fakeStore) SaveWebReports(_ context.Context, rs []store.WebReport) error {
	if f.failSave > 0 {
		f.failSave--
		return errors.New("connection refused")
	}
	f.saved = append(f.saved, rs...)
	return nil
}

func (f *fakeStore) WebReportsSince(_ context.Context, since time.Time) ([]store.WebReport, error) {
	var out []store.WebReport
	for _, r := range f.saved {
		if !r.At.Before(since) {
			out = append(out, r)
		}
	}
	return out, nil
}

func (f *fakeStore) CountWebReports(context.Context) (int, error) { return len(f.saved), nil }

func (f *fakeStore) BotAnswersSince(context.Context, time.Time) ([]store.BotAnswer, error) {
	f.botCalls++
	return f.bot, nil
}

func board(t *testing.T, st Store, clock *time.Time) *Board {
	t.Helper()
	loc, _ := time.LoadLocation("America/Mexico_City")
	b, err := New(st, data.ColoniasMapa, 3, loc, func() time.Time { return *clock }, slog.New(slog.NewTextHandler(io.Discard, nil)))
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func start(t *testing.T) *time.Time {
	t.Helper()
	loc, _ := time.LoadLocation("America/Mexico_City")
	clock := time.Date(2026, 10, 18, 20, 0, 0, 0, loc)
	return &clock
}

func TestAddChecksTheColoniaAndTheAnswer(t *testing.T) {
	clock := start(t)
	b := board(t, &fakeStore{}, clock)
	if _, err := b.Add("1.1.1.1", "NO EXISTE", "Guadalajara", "44100", "sin_agua", false, false, false); !errors.Is(err, ErrUnknownColonia) {
		t.Fatalf("unknown colonia: %v", err)
	}
	if _, err := b.Add("1.1.1.1", "1 DE MAYO", "Guadalajara", "44940", "seca", false, false, false); !errors.Is(err, ErrBadStatus) {
		t.Fatalf("unknown answer: %v", err)
	}
	c, err := b.Add("1.1.1.1", "1 DE MAYO", "Guadalajara", "44940", "sin_agua", true, true, true)
	if err != nil || c.SinAgua != 1 || c.Turbia+c.Olor+c.Sedimento != 0 || c.Name != "1 DE MAYO" {
		t.Fatalf("no water can't be muddy: %+v %v", c, err)
	}
	c, _ = b.Add("2.2.2.2", "1 DE MAYO", "Guadalajara", "44940", "baja", true, false, true)
	if c.SinAgua != 1 || c.Baja != 1 || c.Turbia != 1 || c.Sedimento != 1 || c.Olor != 0 {
		t.Fatalf("colonia counts: %+v", c)
	}
}

func TestLimitsPerAddress(t *testing.T) {
	var rows [][4]string
	if err := json.Unmarshal(data.ColoniasMapa, &rows); err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		addr, other, fresh string
		perColonia, hourly int
	}{
		{"2001:db8:1:1::/64", "2001:db8:1:9::/64", "2001:db8:1:5::/64", perColoniaPerHour, perAddressPerHour},
		{"1.1.1.1", "9.9.9.9", "5.5.5.5", perIPv4ColoniaPerHour, perIPv4PerHour}, // shared by many customers
	} {
		clock := start(t)
		b := board(t, &fakeStore{}, clock)
		add := func(addr, name, mun, cp string) error {
			_, err := b.Add(addr, name, mun, cp, "sin_agua", false, false, false)
			return err
		}
		for i := range tc.perColonia {
			if err := add(tc.addr, "1 DE MAYO", "Guadalajara", "44940"); err != nil {
				t.Fatalf("%s, report %d: %v", tc.addr, i+1, err)
			}
		}
		if err := add(tc.addr, "1 DE MAYO", "Guadalajara", "44940"); !errors.Is(err, ErrTooMany) {
			t.Fatalf("%s: one report too many for one colonia within the hour: %v", tc.addr, err)
		}
		if err := add(tc.other, "1 DE MAYO", "Guadalajara", "44940"); err != nil {
			t.Fatalf("another address can still report it: %v", err)
		}
		*clock = clock.Add(time.Hour)
		if err := add(tc.addr, "1 DE MAYO", "Guadalajara", "44940"); err != nil {
			t.Fatalf("%s: an hour later it can report again: %v", tc.addr, err)
		}
		n := 0
		for _, r := range rows[1:] {
			if err := add(tc.fresh, r[0], r[1], r[2]); err != nil {
				if !errors.Is(err, ErrTooMany) || n != tc.hourly {
					t.Fatalf("%s: after %d reports: %v", tc.fresh, n, err)
				}
				break
			}
			n++
		}
		if n != tc.hourly {
			t.Fatalf("%s must not report without limit: %d reports", tc.fresh, n)
		}
	}
}

func TestCapForEveryone(t *testing.T) {
	clock := start(t)
	b := board(t, &fakeStore{}, clock)
	var rows [][4]string
	if err := json.Unmarshal(data.ColoniasMapa, &rows); err != nil {
		t.Fatal(err)
	}
	add := func(i int) error {
		r := rows[i%len(rows)]
		_, err := b.Add(fmt.Sprint("10.0.", i/250, ".", i%250), r[0], r[1], r[2], "baja", false, false, false)
		return err
	}
	for i := range maxPerHour {
		if err := add(i); err != nil {
			t.Fatalf("report %d: %v", i+1, err)
		}
		if i == maxPerHour/2 {
			*clock = clock.Add(30 * time.Minute)
		}
	}
	if err := add(maxPerHour); !errors.Is(err, ErrBusy) {
		t.Fatalf("past the hourly cap: %v", err)
	}
	*clock = clock.Add(30 * time.Minute)
	if err := add(maxPerHour + 1); err != nil {
		t.Fatalf("the first half hour's reports no longer count: %v", err)
	}
	if s := b.Summary(); s.Total != maxPerHour+1 {
		t.Fatalf("refused reports aren't counted: %d", s.Total)
	}
}

func TestSummaryCountsTheLastDay(t *testing.T) {
	clock := start(t)
	st := &fakeStore{}
	b := board(t, st, clock)
	b.Add("1.1.1.1", "1 DE MAYO", "Guadalajara", "44940", "con_agua", false, false, false)
	*clock = clock.Add(2 * time.Hour)
	for _, addr := range []string{"2.2.2.2", "3.3.3.3", "4.4.4.4"} {
		b.Add(addr, "12 DE DICIEMBRE", "Zapopan", "45068", "sin_agua", false, false, false)
	}
	b.Add("5.5.5.5", "12 DE DICIEMBRE", "Zapopan", "45068", "con_agua", true, false, false)
	s := b.Summary()
	if s.Total != 5 || s.SinAgua != 3 || s.ConAgua != 2 || s.Colonias != 2 || s.MostlyDry != 1 || s.AllTime != 5 {
		t.Fatalf("summary: %+v", s)
	}
	if s.Reports[0].Name != "12 DE DICIEMBRE" || s.Reports[0].Turbia != 1 || s.Reports[0].Last != "2026-10-18T22:00:00-06:00" {
		t.Fatalf("busiest colonia first, with its last report: %+v", s.Reports[0])
	}
	*clock = clock.Add(23 * time.Hour)
	if s := b.Summary(); s.Total != 4 || s.Colonias != 1 || s.AllTime != 5 {
		t.Fatalf("a day later the first report no longer counts, but stays in the total: %+v", s)
	}
}

func TestFlushKeepsReportsUntilSaved(t *testing.T) {
	clock := start(t)
	st := &fakeStore{failSave: 1}
	b := board(t, st, clock)
	b.Add("1.1.1.1", "1 DE MAYO", "Guadalajara", "44940", "sin_agua", false, false, false)
	if err := b.Flush(context.Background()); err == nil {
		t.Fatal("want the database error")
	}
	b.Add("2.2.2.2", "1 DE MAYO", "Guadalajara", "44940", "baja", false, false, false)
	if err := b.Flush(context.Background()); err != nil || len(st.saved) != 2 || st.saved[0].Status != "sin_agua" {
		t.Fatalf("the failed batch is saved first on the next try: %v %+v", err, st.saved)
	}
	if err := b.Flush(context.Background()); err != nil || len(st.saved) != 2 {
		t.Fatalf("nothing is saved twice: %v %d", err, len(st.saved))
	}
	after := board(t, st, clock)
	if err := after.Load(context.Background()); err != nil {
		t.Fatal(err)
	}
	if s := after.Summary(); s.Total != 2 || s.AllTime != 2 {
		t.Fatalf("a restart reads the day's reports back: %+v", s)
	}
}

func TestBotAnswersByZone(t *testing.T) {
	clock := start(t)
	st := &fakeStore{bot: []store.BotAnswer{
		{Zone: 4, Answer: "no", Count: 2}, {Zone: 4, Answer: "no_regreso", Count: 1}, {Zone: 4, Answer: "turbia", Count: 1},
		{Zone: 6, Answer: "si", Count: 1},
	}}
	b := board(t, st, clock)
	if err := b.Load(context.Background()); err != nil {
		t.Fatal(err)
	}
	z := b.Summary().Bot.Zones
	if len(z) != 2 || z[0].Zone != 4 || z[0].Answers != 4 || z[0].Detail == nil || z[0].Detail.SinAgua != 3 || z[0].Detail.ConAgua != 1 || z[0].Detail.Turbia != 1 {
		t.Fatalf("zone 4: %+v", z)
	}
	if z[1].Answers != 1 || z[1].Detail != nil {
		t.Fatalf("below the minimum only the number of answers shows: %+v", z[1])
	}
	calls := st.botCalls
	b.refreshBot(context.Background())
	*clock = clock.Add(botTTL)
	b.refreshBot(context.Background())
	if st.botCalls != calls+1 {
		t.Fatalf("the bot's answers are reloaded once per %s while someone looks: %d calls", botTTL, st.botCalls-calls)
	}
	*clock = clock.Add(botTTL)
	b.refreshBot(context.Background())
	if st.botCalls != calls+1 {
		t.Fatal("nobody looked at the map since: no query")
	}
}

func TestColoniaListMatchesTheMap(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "..", "..", "web", "colonias_siapa.topo.json"))
	if err != nil {
		t.Fatal(err)
	}
	var topo struct {
		Objects struct {
			Colonias struct {
				Geometries []struct {
					Properties struct{ N, M, CP string }
				}
			}
		}
	}
	if err := json.Unmarshal(raw, &topo); err != nil {
		t.Fatal(err)
	}
	var want []string
	for _, g := range topo.Objects.Colonias.Geometries {
		want = append(want, Key(g.Properties.N, g.Properties.M, g.Properties.CP))
	}
	slices.Sort(want)
	want = slices.Compact(want)
	var rows [][4]string
	if err := json.Unmarshal(data.ColoniasMapa, &rows); err != nil {
		t.Fatal(err)
	}
	var got []string
	for _, r := range rows {
		got = append(got, Key(r[0], r[1], r[2]))
	}
	slices.Sort(got)
	if !slices.Equal(got, want) {
		t.Fatalf("api/data/colonias_mapa.json is out of date: run python3 pipelines/mapa_colonias.py (%d colonias, the map has %d)", len(got), len(want))
	}
}
