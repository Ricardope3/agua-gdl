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
	"sync"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/store"
)

type fakeStore struct {
	saved            []store.WebReport
	failSave         int
	bot              []store.BotAnswer
	botCalls         int
	webDays, botDays []store.DayCount
}

func (f *fakeStore) WebReportsByDay(context.Context, time.Time) ([]store.DayCount, error) {
	return f.webDays, nil
}

func (f *fakeStore) BotAnswersByDay(context.Context, time.Time) ([]store.DayCount, error) {
	return f.botDays, nil
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

func TestIPv6NetworksShareTheirLimits(t *testing.T) {
	clock := start(t)
	b := board(t, &fakeStore{}, clock)
	var rows [][4]string
	if err := json.Unmarshal(data.ColoniasMapa, &rows); err != nil {
		t.Fatal(err)
	}
	// Four /56s of one /48, each with 256 /64s that try 20 reports apiece.
	accepted := map[int]int{}
	for net := range 4 {
		for sub := range 256 {
			addr := fmt.Sprintf("2001:db8:7:%x%02x::/64", net, sub)
			for i := range 20 {
				r := rows[(net*256*20+sub*20+i)%len(rows)]
				if _, err := b.Add(addr, r[0], r[1], r[2], "con_agua", false, false, false); err == nil {
					accepted[net]++
				}
			}
		}
	}
	if accepted[0] != perNet56PerHour || accepted[0]+accepted[1]+accepted[2]+accepted[3] != perNet48PerHour {
		t.Fatalf("a /56 gets %d an hour and a /48 %d, however many /64s: %v", perNet56PerHour, perNet48PerHour, accepted)
	}
}

func TestColoniaCapForEveryone(t *testing.T) {
	clock := start(t)
	b := board(t, &fakeStore{}, clock)
	add := func(addr, name, mun, cp string) error {
		_, err := b.Add(addr, name, mun, cp, "con_agua", false, false, false)
		return err
	}
	// Half the networks are IPv4 addresses, half IPv6 /48s.
	for i := range perColoniaAllPerHour {
		addr := fmt.Sprint("10.1.0.", i)
		if i%2 == 1 {
			addr = fmt.Sprintf("2001:db8:%x:1::/64", i)
		}
		if err := add(addr, "1 DE MAYO", "Guadalajara", "44940"); err != nil {
			t.Fatalf("network %d: %v", i+1, err)
		}
	}
	if err := add("10.1.1.1", "1 DE MAYO", "Guadalajara", "44940"); !errors.Is(err, ErrColoniaFull) {
		t.Fatalf("one network too many for the colonia: %v", err)
	}
	if err := add("2001:db8:1:2::/64", "1 DE MAYO", "Guadalajara", "44940"); err != nil {
		t.Fatalf("a network already counted, here from another /64 of its /48, can still report it: %v", err)
	}
	if err := add("10.1.1.1", "12 DE DICIEMBRE", "Zapopan", "45068"); err != nil {
		t.Fatalf("other colonias still take reports: %v", err)
	}
	*clock = clock.Add(time.Hour)
	if err := add("10.1.1.1", "1 DE MAYO", "Guadalajara", "44940"); err != nil {
		t.Fatalf("an hour later: %v", err)
	}
}

func TestOneNetworkCantFillAColonia(t *testing.T) {
	clock := start(t)
	b := board(t, &fakeStore{}, clock)
	accepted := map[string]int{}
	report := func(who, addr string) {
		t.Helper()
		if _, err := b.Add(addr, "1 DE MAYO", "Guadalajara", "44940", "con_agua", false, false, false); err == nil {
			accepted[who]++
		} else if !errors.Is(err, ErrTooMany) {
			t.Fatalf("%s: %v", addr, err)
		}
	}
	// A home's /56 from every one of its /64s, and three IPv4 addresses, send all they can.
	for sub := range 256 {
		for range perColoniaPerHour {
			report("/56", fmt.Sprintf("2001:db8:7:%02x::/64", sub))
		}
	}
	ips := []string{"198.51.100.1", "198.51.100.2", "198.51.100.3"}
	for _, ip := range ips {
		for range perIPv4ColoniaPerHour + 1 {
			report(ip, ip)
		}
	}
	if accepted["/56"] != perNet48ColoniaPerHour {
		t.Fatalf("a /56 put %d reports into one colonia", accepted["/56"])
	}
	for _, ip := range ips {
		if accepted[ip] != perIPv4ColoniaPerHour {
			t.Fatalf("%s put %d reports into one colonia", ip, accepted[ip])
		}
	}
	if _, err := b.Add("203.0.113.9", "1 DE MAYO", "Guadalajara", "44940", "sin_agua", false, false, false); err != nil {
		t.Fatalf("after %v, a neighbour on another network can still report the colonia: %v", accepted, err)
	}
}

func TestSlash48PutsNoMoreIntoAColoniaThanAnIPv4Address(t *testing.T) {
	clock := start(t)
	b := board(t, &fakeStore{}, clock)
	// Each report comes from a /64 in another /56 of the same /48, so only the /48's limits apply.
	n := 0
	for sub := range 256 {
		if _, err := b.Add(fmt.Sprintf("2001:db8:9:%02x00::/64", sub), "1 DE MAYO", "Guadalajara", "44940", "baja", false, false, false); err != nil {
			if !errors.Is(err, ErrTooMany) {
				t.Fatalf("after %d reports: %v", n, err)
			}
			break
		}
		n++
	}
	if n != perNet48ColoniaPerHour || perNet48ColoniaPerHour != perIPv4ColoniaPerHour {
		t.Fatalf("a /48 put %d reports into one colonia, an IPv4 address can put %d", n, perIPv4ColoniaPerHour)
	}
	if _, err := b.Add("2001:db8:9:ff01::/64", "12 DE DICIEMBRE", "Zapopan", "45068", "baja", false, false, false); err != nil {
		t.Fatalf("the /48 can still report another colonia: %v", err)
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
	if s.Reports[0].Name != "12 DE DICIEMBRE" || s.Reports[0].Turbia != 1 || s.Reports[0].Last != "2026-10-18T22:00:00-06:00" || s.Reports[0].LastStatus != "con_agua" {
		t.Fatalf("busiest colonia first, with its last report: %+v", s.Reports[0])
	}
	*clock = clock.Add(23 * time.Hour)
	if s := b.Summary(); s.Total != 4 || s.Colonias != 1 || s.AllTime != 5 || len(s.Stale) != 1 || s.Stale[0].LastStatus != "con_agua" {
		t.Fatalf("a day later the first report is stale, but stays in the total: %+v", s)
	}
}

func TestSummarySeparatesCurrentStaleAndExpiredReports(t *testing.T) {
	clock := start(t)
	now := *clock
	st := &fakeStore{saved: []store.WebReport{ // WebReportsSince returns oldest first
		{Colonia: "1 DE MAYO|Guadalajara|44940", Status: "sin_agua", At: now.Add(-StaleWindow)},      // exactly 72 hours: expired
		{Colonia: "OBLATOS|Guadalajara|44360", Status: "baja", At: now.Add(-StaleWindow)},            // exactly 72 hours: expired
		{Colonia: "12 DE DICIEMBRE|Zapopan|45068", Status: "sin_agua", At: now.Add(-30 * time.Hour)}, // hidden by newer current reports
		{Colonia: "1 DE MAYO|Guadalajara|44940", Status: "con_agua", At: now.Add(-Window)},           // exactly 24 hours: stale
		{Colonia: "12 DE DICIEMBRE|Zapopan|45068", Status: "sin_agua", At: now.Add(-2 * time.Hour)},
		{Colonia: "12 DE DICIEMBRE|Zapopan|45068", Status: "con_agua", At: now.Add(-time.Hour)},
	}}
	b := board(t, st, clock)
	if err := b.Load(context.Background()); err != nil {
		t.Fatal(err)
	}
	s := b.Summary()
	if s.Total != 2 || s.SinAgua != 1 || s.ConAgua != 1 || s.Colonias != 1 || s.AllTime != 6 || s.StaleHours != 72 {
		t.Fatalf("only the current 24 hours count in the summary: %+v", s)
	}
	if len(s.Reports) != 1 || s.Reports[0].LastStatus != "con_agua" {
		t.Fatalf("the latest answer comes from the latest report, not the majority: %+v", s.Reports)
	}
	if len(s.Stale) != 1 || s.Stale[0].Name != "1 DE MAYO" || s.Stale[0].ConAgua != 1 || s.Stale[0].LastStatus != "con_agua" {
		t.Fatalf("only a colonia without current reports is stale: %+v", s.Stale)
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

func TestWeekComparesReportsWithTheCalendar(t *testing.T) {
	clock := start(t) // Sunday 18 October
	day := func(d int) time.Time { return time.Date(2026, 10, d, 0, 0, 0, 0, time.UTC) }
	st := &fakeStore{
		webDays: []store.DayCount{
			{Colonia: "OBLATOS|Guadalajara|44360", Day: day(17), Answer: "sin_agua", Count: 8}, // 73 % zone 3, 27 % zone 2
			{Colonia: "OBLATOS|Guadalajara|44360", Day: day(16), Answer: "sin_agua", Count: 6},
			{Colonia: "20 DE NOVIEMBRE|Tonalá|45404", Day: day(18), Answer: "sin_agua", Count: 2}, // outside the rotation
			{Colonia: "OBLATOS|Guadalajara|44360", Day: day(10), Answer: "sin_agua", Count: 50},   // before the week
		},
		botDays: []store.DayCount{
			{Zone: 3, Day: day(16), Answer: "no", Count: 3}, {Zone: 3, Day: day(16), Answer: "si", Count: 1},
			{Zone: 3, Day: day(17), Answer: "no", Count: 3},
		},
	}
	b := board(t, st, clock)
	b.Cuts = func(zone int, d time.Time) bool { // zone 3 is cut on Wednesdays and Saturdays
		return zone == 3 && (d.Weekday() == time.Wednesday || d.Weekday() == time.Saturday)
	}
	if err := b.Load(context.Background()); err != nil {
		t.Fatal(err)
	}
	w := b.Summary().Week
	if w == nil || len(w.Days) != 7 || w.Days[0] != "2026-10-12" || w.Days[6] != "2026-10-18" || len(w.Zones) != 8 {
		t.Fatalf("seven days ending today, zones 1 to 7 and outside the rotation: %+v", w)
	}
	z3 := w.Zones[2]
	if z3.Zone != 3 || !z3.Cuts[2] || !z3.Cuts[5] || z3.Cuts[4] {
		t.Fatalf("zone 3's cut days: %+v", z3.Cuts)
	}
	if fri := z3.Days[4]; fri.Total != 10 || fri.Detail == nil || fri.Detail.SinAgua != 9 || fri.Detail.ConAgua != 1 {
		t.Fatalf("Friday, no cut: the map's reports and the bot's answers together: %+v", fri)
	}
	if w.Dry.OnCut != 8 || w.Dry.OffCut != 6 {
		t.Fatalf("the map's «sin agua» on cut days and on other days; the bot asks only on evenings that aren't cut days, so its answers stay out: %+v", w.Dry)
	}
	if out := w.Zones[7]; out.Zone != 0 || out.Days[6].Total != 2 || out.Days[6].Detail != nil {
		t.Fatalf("outside the rotation, below the minimum only the number shows: %+v", out)
	}
	if len(w.Reports) != 3 || w.Reports[0].Day != "2026-10-16" || w.Reports[0].SinAgua != 6 || w.Reports[2].Name != "20 DE NOVIEMBRE" {
		t.Fatalf("the timeline gets the map's daily history, but nothing before the week: %+v", w.Reports)
	}
}

func TestWeekHidesASplitWithFewBotAnswers(t *testing.T) {
	clock := start(t) // Sunday 18 October: the week starts on Monday 12
	day := func(d int) time.Time { return time.Date(2026, 10, d, 0, 0, 0, 0, time.UTC) }
	const oblatos = "OBLATOS|Guadalajara|44360" // zone 3
	st := &fakeStore{
		webDays: []store.DayCount{
			{Colonia: oblatos, Day: day(14), Answer: "con_agua", Count: 3},
			{Colonia: oblatos, Day: day(15), Answer: "con_agua", Count: 2},
			{Colonia: oblatos, Day: day(16), Answer: "con_agua", Count: 3},
		},
		botDays: []store.DayCount{
			{Zone: 3, Day: day(13), Answer: "no", Count: 3},
			{Zone: 3, Day: day(14), Answer: "no", Count: 3},
			{Zone: 3, Day: day(15), Answer: "no", Count: 1},
		},
	}
	b := board(t, st, clock) // the minimum is 3
	if err := b.Load(context.Background()); err != nil {
		t.Fatal(err)
	}
	w := b.Summary().Week
	days := w.Zones[2].Days
	if thu := days[3]; thu.Total != 3 || thu.Detail != nil {
		t.Fatalf("Thursday: two map reports and one answer reach the minimum, but the map's are public by colonia, so the split would give the answer away: %+v", thu)
	}
	for i, why := range map[int]string{1: "the bot's answers alone", 2: "both, each reaching the minimum", 4: "the map's reports alone"} {
		if days[i].Detail == nil {
			t.Errorf("%s, %s: the split shows", w.Days[i], why)
		}
	}
}

func TestBotSplitCantBeSubtractedFromTheWeek(t *testing.T) {
	clock := start(t)
	*clock = clock.Add(3 * time.Hour) // Sunday 18 October, 23:00: the window starts on Saturday at 23:00
	day := func(d int) time.Time { return time.Date(2026, 10, d, 0, 0, 0, 0, time.UTC) }
	st := &fakeStore{
		bot: []store.BotAnswer{
			{Zone: 1, Answer: "no", Count: 2}, {Zone: 1, Answer: "poca", Count: 2}, {Zone: 1, Answer: "si", Count: 1},
			{Zone: 2, Answer: "no", Count: 3}, {Zone: 2, Answer: "si", Count: 3},
			{Zone: 3, Answer: "no", Count: 5}, {Zone: 3, Answer: "si", Count: 1},
		},
		botDays: []store.DayCount{
			// zone 1: Saturday's two «no» came after 23:00, inside the window
			{Zone: 1, Day: day(17), Answer: "no", Count: 2}, {Zone: 1, Day: day(18), Answer: "poca", Count: 2}, {Zone: 1, Day: day(18), Answer: "si", Count: 1},
			{Zone: 2, Day: day(17), Answer: "no", Count: 3}, {Zone: 2, Day: day(18), Answer: "si", Count: 3},
			// zone 3: one answer today, and one of Saturday's before the window
			{Zone: 3, Day: day(17), Answer: "no", Count: 6}, {Zone: 3, Day: day(18), Answer: "si", Count: 1},
		},
	}
	b := board(t, st, clock) // the minimum is 3
	if err := b.Load(context.Background()); err != nil {
		t.Fatal(err)
	}
	s := b.Summary()
	if today := s.Week.Zones[0].Days[6]; today.Detail == nil {
		t.Fatalf("zone 1's Sunday shows its split: %+v", today)
	}
	z := s.Bot.Zones
	if len(z) != 3 || z[0].Answers != 5 || z[0].Detail != nil {
		t.Fatalf("zone 1: the window minus Sunday's split would show Saturday's two answers: %+v", z[0])
	}
	if z[1].Detail == nil {
		t.Fatalf("zone 2: Saturday's and Sunday's answers each reach the minimum: %+v", z[1])
	}
	if z[2].Detail != nil {
		t.Fatalf("zone 3: the window minus Saturday's split would show Sunday's answer: %+v", z[2])
	}
}

func TestAddressesAreForgottenAfterAnHour(t *testing.T) {
	loc, _ := time.LoadLocation("America/Mexico_City")
	var mu sync.Mutex
	clock := time.Date(2026, 10, 18, 20, 0, 0, 0, loc)
	now := func() time.Time { mu.Lock(); defer mu.Unlock(); return clock }
	advance := func(d time.Duration) { mu.Lock(); defer mu.Unlock(); clock = clock.Add(d) }
	b, err := New(&fakeStore{}, data.ColoniasMapa, 3, loc, now, slog.New(slog.NewTextHandler(io.Discard, nil)))
	if err != nil {
		t.Fatal(err)
	}
	b.forgetEvery = time.Millisecond
	add := func() {
		t.Helper()
		if _, err := b.Add("2001:db8:1:1::/64", "1 DE MAYO", "Guadalajara", "44940", "sin_agua", false, false, false); err != nil {
			t.Fatal(err)
		}
	}
	held := func() (keys, times, nets int) {
		b.mu.Lock()
		defer b.mu.Unlock()
		for _, ts := range b.hits {
			keys, times = keys+1, times+len(ts)
		}
		for _, ns := range b.nets {
			nets += max(len(ns), 1) // an emptied colonia must go too
		}
		return keys, times, nets
	}
	wait := func(keys, times, nets int, why string) {
		t.Helper()
		for deadline := time.Now().Add(5 * time.Second); ; time.Sleep(time.Millisecond) {
			k, n, c := held()
			if k == keys && n == times && c == nets {
				return
			}
			if time.Now().After(deadline) {
				t.Fatalf("%s: the limits hold %d times under %d keys and %d networks by colonia, want %d under %d and %d", why, n, k, c, times, keys, nets)
			}
		}
	}
	add()
	advance(30 * time.Minute)
	add()
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		b.Run(ctx, time.Hour)
		close(done)
	}()
	defer func() {
		cancel()
		<-done
	}()
	time.Sleep(20 * time.Millisecond)
	if k, n, c := held(); k != 5 || n != 10 || c != 1 {
		t.Fatalf("within the hour the /64, its /56 and its /48, and the /64 and the /48 for the colonia, hold both reports, and the colonia its /48: %d times under %d keys, %d networks", n, k, c)
	}
	advance(30 * time.Minute)
	wait(5, 5, 1, "the first report is an hour old")
	advance(30 * time.Minute)
	wait(0, 0, 0, "both reports are an hour old, and nobody sent another")
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
