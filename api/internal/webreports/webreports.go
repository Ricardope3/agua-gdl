// Package webreports keeps the water reports people make on the map at aguagdl.com/reportes.
// A report is anonymous: a colonia, an answer and the time. Reports live in memory for the map
// and reach Postgres in batches, so a busy map doesn't keep Neon awake. Repeats are limited per
// client address, which is held in memory for an hour and never stored, and everyone's reports
// together are capped per hour, which bounds memory and the database however many addresses send.
package webreports

import (
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/netip"
	"slices"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"aguagdl/api/internal/store"
)

type Store interface {
	SaveWebReports(ctx context.Context, rs []store.WebReport) error
	WebReportsSince(ctx context.Context, since time.Time) ([]store.WebReport, error)
	CountWebReports(ctx context.Context) (int, error)
	BotAnswersSince(ctx context.Context, since time.Time) ([]store.BotAnswer, error)
	WebReportsByDay(ctx context.Context, since time.Time) ([]store.DayCount, error)
	BotAnswersByDay(ctx context.Context, since time.Time) ([]store.DayCount, error)
}

const (
	// Window is how far back the map counts reports.
	Window = 24 * time.Hour
	// A client address may send this many reports an hour, and this many for one colonia. An
	// IPv6 client comes as its /64; an IPv4 address gets more, since carriers and home providers
	// share one among many customers.
	perAddressPerHour     = 20
	perColoniaPerHour     = 3
	perIPv4PerHour        = 100
	perIPv4ColoniaPerHour = 10
	// The IPv6 networks a home or a provider gets (a /56, a /48) share these, so holding many
	// /64s doesn't multiply the limits, and a /48 puts no more into one colonia than an IPv4 address.
	perNet56PerHour        = 40
	perNet48PerHour        = 100
	perNet48ColoniaPerHour = perIPv4ColoniaPerHour
	// perColoniaAllPerHour is how many networks (an IPv4 address or an IPv6 /48) may report one
	// colonia in an hour: plenty to show how it is. Then a new one can't until one of them goes an
	// hour without reporting it, so no single network can fill a colonia and lock its neighbours out.
	perColoniaAllPerHour = 30
	// maxPerHour caps everyone's reports together. Each report adds at most five keys to the
	// limits and one network to its colonia, which Run forgets after the hour, so it also bounds
	// the memory they use.
	maxPerHour = 5_000
	// maxPending bounds the reports held while the database is unreachable.
	maxPending = 20_000
	summaryTTL = 30 * time.Second
	// botTTL is how long the bot's answers and the week are reused: they change slowly and
	// come from Postgres.
	botTTL = 30 * time.Minute
	// weekDays is how far back the week compares the reports with SIAPA's calendar.
	weekDays = 7
	// forgetEvery is how often Run drops what the limits hold from over an hour ago.
	forgetEvery = time.Minute
)

const dateLayout = "2006-01-02"

var (
	ErrUnknownColonia = errors.New("unknown colonia")
	ErrBadStatus      = errors.New("unknown status")
	ErrTooMany        = errors.New("too many reports from this address")
	ErrBusy           = errors.New("too many reports this hour")
	ErrColoniaFull    = errors.New("too many reports for this colonia this hour")
)

// Key is how a colonia is named in reports: "name|municipio|postal code".
func Key(name, municipio, cp string) string { return name + "|" + municipio + "|" + cp }

// Counts are reports by answer.
type Counts struct {
	SinAgua int `json:"sin_agua"`
	Baja    int `json:"baja"`
	ConAgua int `json:"con_agua"`
}

func (c Counts) total() int { return c.SinAgua + c.Baja + c.ConAgua }

func (c *Counts) add(status string) {
	switch status {
	case "sin_agua":
		c.SinAgua++
	case "baja":
		c.Baja++
	case "con_agua":
		c.ConAgua++
	}
}

// addN counts n of the map's reports or the bot's answers with one answer.
func (c *Counts) addN(answer string, n int) {
	switch answer {
	case "sin_agua", "no", "no_regreso":
		c.SinAgua += n
	case "baja", "poca":
		c.Baja += n
	case "con_agua", "si", "normal", "turbia":
		c.ConAgua += n
	}
}

// Colonia is one colonia's reports in the window.
type Colonia struct {
	Name      string `json:"n"`
	Municipio string `json:"m"`
	CP        string `json:"cp"`
	Counts
	Turbia    int    `json:"turbia"`
	Olor      int    `json:"olor"`
	Sedimento int    `json:"sedimento"`
	Last      string `json:"ultimo,omitempty"` // to the minute
}

// ZoneAnswers is what the bot's subscribers in a zone answered in the window. The detail is
// shown only from MinShown answers, as the privacy notice promises for reports, and only
// when the week's days can't be subtracted from it to show fewer (see windowSafe).
type ZoneAnswers struct {
	Zone    int       `json:"zone"`
	Answers int       `json:"respuestas"`
	Detail  *BotCount `json:"detalle,omitempty"`
}

// BotCount maps the bot's answers onto the map's: Sí/normal → con agua, Poca/baja → baja
// presión, No/no regresó → sin agua; «turbia» came back, but murky.
type BotCount struct {
	Counts
	Turbia int `json:"turbia"`
}

// Summary is what /v1/reportes serves.
type Summary struct {
	Updated string `json:"updated"`
	Hours   int    `json:"hours"`
	Counts
	Total     int       `json:"total"`
	Colonias  int       `json:"colonias_con_reportes"`
	MostlyDry int       `json:"mayormente_sin_agua"`
	AllTime   int       `json:"historico"`
	Reports   []Colonia `json:"colonias"`
	Bot       struct {
		Hours int           `json:"hours"`
		Min   int           `json:"min"`
		Zones []ZoneAnswers `json:"zonas"`
	} `json:"bot"`
	Week *Week `json:"semana,omitempty"`
}

// Week is the last seven days by zone: SIAPA's cut days beside what people reported on the map
// and answered in the bot, to see whether the water goes only on the days the calendar says.
// A map report counts for its colonia's main zone; zone 0 is colonias outside the rotation.
type Week struct {
	Days []string `json:"dias"` // oldest first
	// Min is how many reports a day needs before its split shows, and how many of the bot's
	// answers if it has any: the map's reports are public by colonia, so subtracting them
	// would give a few answers away.
	Min   int        `json:"min"`
	Zones []WeekZone `json:"zonas"`
	// The map's «sin agua» in zones 1 to 7, on their cut days and on other days. The bot's
	// answers stay out: it asks only on evenings that aren't its zone's cut days.
	Dry struct {
		OnCut  int `json:"en_corte"`
		OffCut int `json:"fuera_de_corte"`
	} `json:"sin_agua"`
	last map[int]lastDays // by zone, for the bot's 24-hour split
}

// lastDays is a zone's bot answers yesterday and today, and whether yesterday shows its split.
type lastDays struct {
	yesterday, today int
	yesterdayShown   bool
}

type WeekZone struct {
	Zone int       `json:"zone"`
	Cuts []bool    `json:"cortes"`
	Days []DayCell `json:"dias"`
}

type DayCell struct {
	Total  int     `json:"total"`
	Detail *Counts `json:"detalle,omitempty"`
}

type colonia struct {
	name, municipio, cp string
	zone                int // the one with most of its area; 0 = outside the rotation
}

// Board holds the recent reports and the limits. Its methods are safe for concurrent use.
type Board struct {
	store       Store
	minShown    int
	loc         *time.Location
	now         func() time.Time
	log         *slog.Logger
	colonias    map[string]colonia
	forgetEvery time.Duration

	mu        sync.Mutex
	recent    []store.WebReport // the window's reports, oldest first
	pending   []store.WebReport // not yet in Postgres
	allTime   int
	hits      map[string][]time.Time
	nets      map[string]map[string]time.Time // by colonia: the networks that reported it, and when they last did
	cached    *Summary
	cachedAt  time.Time
	raw, gz   []byte // cached encoded, plain and gzipped
	bot       []store.BotAnswer
	week      *Week
	botAt     time.Time
	botWanted bool

	// Cuts reports SIAPA's cut days, which the week marks; nil leaves them unmarked.
	Cuts func(zone int, day time.Time) bool
}

// New reads the colonias people may report on (api/data/colonias_mapa.json).
func New(st Store, coloniasJSON []byte, minShown int, loc *time.Location, now func() time.Time, log *slog.Logger) (*Board, error) {
	var rows [][4]string
	if err := json.Unmarshal(coloniasJSON, &rows); err != nil {
		return nil, fmt.Errorf("colonias_mapa.json: %w", err)
	}
	b := &Board{store: st, minShown: minShown, loc: loc, now: now, log: log, colonias: map[string]colonia{},
		forgetEvery: forgetEvery, hits: map[string][]time.Time{}, nets: map[string]map[string]time.Time{}}
	for _, r := range rows {
		zone, _ := strconv.Atoi(strings.Split(r[3], ",")[0])
		b.colonias[Key(r[0], r[1], r[2])] = colonia{r[0], r[1], r[2], zone}
	}
	return b, nil
}

// Load reads the window's reports, the all-time count and the bot's answers.
func (b *Board) Load(ctx context.Context) error {
	now := b.now()
	recent, err := b.store.WebReportsSince(ctx, now.Add(-Window))
	if err != nil {
		return err
	}
	all, err := b.store.CountWebReports(ctx)
	if err != nil {
		return err
	}
	bot, err := b.store.BotAnswersSince(ctx, now.Add(-Window))
	if err != nil {
		return err
	}
	week, err := b.loadWeek(ctx, now)
	if err != nil {
		return err
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	b.recent, b.allTime, b.bot, b.week, b.botAt, b.cached = recent, all+len(b.pending), bot, week, now, nil
	return nil
}

// Add records a report from addr (a client address, e.g. an IPv6 /64) and returns the
// colonia's counts with it. Muddy, smelly or sediment only count when there is water.
func (b *Board) Add(addr, name, municipio, cp, status string, turbia, olor, sedimento bool) (Colonia, error) {
	key := Key(name, municipio, cp)
	if _, ok := b.colonias[key]; !ok {
		return Colonia{}, ErrUnknownColonia
	}
	if status != "sin_agua" && status != "baja" && status != "con_agua" {
		return Colonia{}, ErrBadStatus
	}
	if status == "sin_agua" {
		turbia, olor, sedimento = false, false, false
	}
	now, net := b.now(), netOf(addr)
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lastHour(now) >= maxPerHour {
		return Colonia{}, ErrBusy
	}
	if b.coloniaFull(key, net, now) {
		return Colonia{}, ErrColoniaFull
	}
	if !b.allow(addr, key, now) {
		return Colonia{}, ErrTooMany
	}
	if b.nets[key] == nil {
		b.nets[key] = map[string]time.Time{}
	}
	b.nets[key][net] = now
	r := store.WebReport{Colonia: key, Status: status, Turbia: turbia, Olor: olor, Sedimento: sedimento, At: now}
	b.recent = append(b.recent, r)
	if len(b.pending) >= maxPending {
		b.log.Error("web reports: database unreachable for too long; dropping the oldest unsaved report")
		b.pending = b.pending[1:]
	}
	b.pending = append(b.pending, r)
	b.allTime++
	b.cached = nil
	b.trim(now)
	return b.coloniaCounts(key), nil
}

// lastHour counts everyone's reports in the last hour. Called with mu held.
func (b *Board) lastHour(now time.Time) int {
	return len(b.recent) - sort.Search(len(b.recent), func(i int) bool { return now.Sub(b.recent[i].At) < time.Hour })
}

// allow applies the hourly limits to addr. Called with mu held.
func (b *Board) allow(addr, key string, now time.Time) bool {
	type limit struct {
		key string
		max int
	}
	limits := []limit{{"a:" + addr, perAddressPerHour}, {"c:" + addr + "|" + key, perColoniaPerHour}}
	if ipv4(addr) {
		limits = []limit{{"a:" + addr, perIPv4PerHour}, {"c:" + addr + "|" + key, perIPv4ColoniaPerHour}}
	}
	for _, n := range []struct{ bits, max int }{{56, perNet56PerHour}, {48, perNet48PerHour}} {
		if wide, ok := network(addr, n.bits); ok {
			limits = append(limits, limit{"n:" + wide, n.max})
		}
	}
	if wide, ok := network(addr, 48); ok {
		limits = append(limits, limit{"c:" + wide + "|" + key, perNet48ColoniaPerHour})
	}
	kept := make([][]time.Time, len(limits))
	for i, l := range limits {
		if kept[i] = inLastHour(b.hits[l.key], now); len(kept[i]) >= l.max {
			return false
		}
	}
	for i, l := range limits {
		b.hits[l.key] = append(kept[i], now)
	}
	return true
}

// inLastHour keeps the times less than an hour old.
func inLastHour(ts []time.Time, now time.Time) []time.Time {
	return slices.DeleteFunc(ts, func(t time.Time) bool { return now.Sub(t) >= time.Hour })
}

// forget drops what the limits hold from over an hour ago, so no address, nor the colonias it
// reported, stays in memory much longer than that.
func (b *Board) forget() {
	b.mu.Lock()
	defer b.mu.Unlock()
	now := b.now()
	for k, ts := range b.hits {
		if ts = inLastHour(ts, now); len(ts) == 0 {
			delete(b.hits, k)
		} else {
			b.hits[k] = ts
		}
	}
	for key, nets := range b.nets {
		for net, last := range nets {
			if now.Sub(last) >= time.Hour {
				delete(nets, net)
			}
		}
		if len(nets) == 0 {
			delete(b.nets, key)
		}
	}
}

// coloniaFull reports whether perColoniaAllPerHour other networks reported the colonia in the
// last hour, so net, which didn't, can't. Called with mu held.
func (b *Board) coloniaFull(key, net string, now time.Time) bool {
	n := 0
	for other, last := range b.nets[key] {
		if now.Sub(last) < time.Hour {
			if other == net {
				return false
			}
			n++
		}
	}
	return n >= perColoniaAllPerHour
}

// netOf is the network a colonia's cap counts once: an IPv4 address, or an IPv6 /64's /48.
func netOf(addr string) string {
	if wide, ok := network(addr, 48); ok {
		return wide
	}
	return addr
}

// network returns the IPv6 network of the given size that a client's /64 belongs to.
func network(addr string, bits int) (string, bool) {
	p, err := netip.ParsePrefix(addr)
	if err != nil || !p.Addr().Is6() {
		return "", false
	}
	n, err := p.Addr().Prefix(bits)
	return n.String(), err == nil
}

// ipv4 reports whether addr is an IPv4 address rather than an IPv6 /64.
func ipv4(addr string) bool {
	a, err := netip.ParseAddr(addr)
	return err == nil && a.Unmap().Is4()
}

// trim drops reports older than the window. Called with mu held.
func (b *Board) trim(now time.Time) {
	i := 0
	for i < len(b.recent) && now.Sub(b.recent[i].At) >= Window {
		i++
	}
	b.recent = b.recent[i:]
}

// coloniaCounts sums one colonia's reports in the window. Called with mu held.
func (b *Board) coloniaCounts(key string) Colonia {
	c := b.colonias[key]
	out := Colonia{Name: c.name, Municipio: c.municipio, CP: c.cp}
	for _, r := range b.recent {
		if r.Colonia == key {
			out.tally(r, b.loc)
		}
	}
	return out
}

func (c *Colonia) tally(r store.WebReport, loc *time.Location) {
	c.add(r.Status)
	if r.Turbia {
		c.Turbia++
	}
	if r.Olor {
		c.Olor++
	}
	if r.Sedimento {
		c.Sedimento++
	}
	if last := r.At.In(loc).Truncate(time.Minute).Format(time.RFC3339); last > c.Last {
		c.Last = last
	}
}

// Summary is the map's numbers, reused for summaryTTL.
func (b *Board) Summary() Summary {
	b.mu.Lock()
	defer b.mu.Unlock()
	return *b.summary(b.now())
}

// SummaryJSON is the summary encoded, plain and gzipped, once per summary rather than once
// per request.
func (b *Board) SummaryJSON() (raw, gz []byte, err error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	s := b.summary(b.now())
	if b.raw == nil {
		raw, err := json.Marshal(s)
		if err != nil {
			return nil, nil, err
		}
		var buf bytes.Buffer
		w := gzip.NewWriter(&buf)
		w.Write(raw)
		if err := w.Close(); err != nil {
			return nil, nil, err
		}
		b.raw, b.gz = raw, buf.Bytes()
	}
	return b.raw, b.gz, nil
}

// summary returns the cached summary, or builds it. Called with mu held.
func (b *Board) summary(now time.Time) *Summary {
	b.botWanted = true
	if b.cached != nil && now.Sub(b.cachedAt) < summaryTTL {
		return b.cached
	}
	b.trim(now)
	s := Summary{Updated: now.In(b.loc).Truncate(time.Minute).Format(time.RFC3339), Hours: int(Window / time.Hour), AllTime: b.allTime, Reports: []Colonia{}}
	byKey := map[string]*Colonia{}
	for _, r := range b.recent {
		col, ok := b.colonias[r.Colonia]
		if !ok {
			continue // a colonia no longer on SIAPA's map
		}
		c := byKey[r.Colonia]
		if c == nil {
			c = &Colonia{Name: col.name, Municipio: col.municipio, CP: col.cp}
			byKey[r.Colonia] = c
		}
		c.tally(r, b.loc)
		s.add(r.Status)
	}
	for _, c := range byKey {
		s.Reports = append(s.Reports, *c)
		if 2*c.SinAgua > c.total() {
			s.MostlyDry++
		}
	}
	slices.SortFunc(s.Reports, func(x, y Colonia) int {
		if d := y.total() - x.total(); d != 0 {
			return d
		}
		return cmpStrings(Key(x.Name, x.Municipio, x.CP), Key(y.Name, y.Municipio, y.CP))
	})
	s.Total, s.Colonias = s.Counts.total(), len(s.Reports)
	s.Bot.Hours, s.Bot.Min, s.Bot.Zones = int(Window/time.Hour), b.minShown, b.botZones()
	s.Week = b.week
	b.cached, b.cachedAt, b.raw, b.gz = &s, now, nil, nil
	return &s
}

func cmpStrings(a, b string) int {
	switch {
	case a < b:
		return -1
	case a > b:
		return 1
	}
	return 0
}

// botZones groups the bot's answers by zone. Called with mu held.
func (b *Board) botZones() []ZoneAnswers {
	byZone := map[int]*BotCount{}
	var zones []int
	for _, a := range b.bot {
		c := byZone[a.Zone]
		if c == nil {
			c = &BotCount{}
			byZone[a.Zone] = c
			zones = append(zones, a.Zone)
		}
		switch a.Answer {
		case "si", "normal":
			c.ConAgua += a.Count
		case "turbia":
			c.ConAgua += a.Count
			c.Turbia += a.Count
		case "poca", "baja":
			c.Baja += a.Count
		case "no", "no_regreso":
			c.SinAgua += a.Count
		}
	}
	slices.Sort(zones)
	out := []ZoneAnswers{}
	for _, z := range zones {
		c := byZone[z]
		za := ZoneAnswers{Zone: z, Answers: c.total()}
		if za.Answers >= b.minShown && b.windowSafe(z, za.Answers) {
			za.Detail = c
		}
		out = append(out, za)
	}
	return out
}

// windowSafe reports whether a zone's split over the window can show beside the week's, which
// shows yesterday and today apart: the window holds today's answers and the end of yesterday's,
// so subtracting the days from it must not leave fewer than minShown answers. Called with mu held.
func (b *Board) windowSafe(zone, answers int) bool {
	if b.week == nil {
		return true
	}
	ok := func(n int) bool { return n <= 0 || n >= b.minShown }
	d := b.week.last[zone]
	late := answers - d.today // yesterday's answers inside the window
	return ok(d.today) && ok(late) && (!d.yesterdayShown || ok(d.yesterday-late))
}

// Flush writes the reports not yet in Postgres. On failure they stay for the next try.
func (b *Board) Flush(ctx context.Context) error {
	b.mu.Lock()
	batch := b.pending
	b.pending = nil
	b.mu.Unlock()
	if len(batch) == 0 {
		return nil
	}
	if err := b.store.SaveWebReports(ctx, batch); err != nil {
		b.mu.Lock()
		b.pending = append(batch, b.pending...)
		b.mu.Unlock()
		return err
	}
	return nil
}

// refreshBot reloads the bot's answers and the week when someone looked at the map since the
// last load and botTTL has passed.
func (b *Board) refreshBot(ctx context.Context) error {
	now := b.now()
	b.mu.Lock()
	due := b.botWanted && now.Sub(b.botAt) >= botTTL
	b.mu.Unlock()
	if !due {
		return nil
	}
	rows, err := b.store.BotAnswersSince(ctx, now.Add(-Window))
	if err != nil {
		return err
	}
	week, err := b.loadWeek(ctx, now)
	if err != nil {
		return err
	}
	b.mu.Lock()
	b.bot, b.week, b.botAt, b.botWanted, b.cached = rows, week, now, false, nil
	b.mu.Unlock()
	return nil
}

// loadWeek counts the last weekDays days by zone and day.
func (b *Board) loadWeek(ctx context.Context, now time.Time) (*Week, error) {
	local := now.In(b.loc)
	first := time.Date(local.Year(), local.Month(), local.Day()-(weekDays-1), 0, 0, 0, 0, b.loc)
	web, err := b.store.WebReportsByDay(ctx, first)
	if err != nil {
		return nil, err
	}
	bot, err := b.store.BotAnswersByDay(ctx, first)
	if err != nil {
		return nil, err
	}
	w := &Week{Min: b.minShown, last: map[int]lastDays{}}
	days := map[string]int{}
	for i := range weekDays {
		d := first.AddDate(0, 0, i).Format(dateLayout)
		days[d] = i
		w.Days = append(w.Days, d)
	}
	// A day keeps the map's reports apart from the bot's answers, which its split and the
	// share of «sin agua» treat differently.
	type cell struct{ web, bot Counts }
	cells := map[int]*[weekDays]cell{}
	at := func(zone int, day time.Time) *cell {
		i, ok := days[day.Format(dateLayout)]
		if !ok {
			return nil
		}
		if cells[zone] == nil {
			cells[zone] = &[weekDays]cell{}
		}
		return &cells[zone][i]
	}
	for _, r := range web {
		if col, ok := b.colonias[r.Colonia]; ok {
			if c := at(col.zone, r.Day); c != nil {
				c.web.addN(r.Answer, r.Count)
			}
		}
	}
	for _, r := range bot {
		if c := at(r.Zone, r.Day); c != nil {
			c.bot.addN(r.Answer, r.Count)
		}
	}
	for _, zone := range []int{1, 2, 3, 4, 5, 6, 7, 0} {
		wz := WeekZone{Zone: zone, Cuts: make([]bool, weekDays), Days: make([]DayCell, weekDays)}
		for i := range weekDays {
			var c cell
			if cells[zone] != nil {
				c = cells[zone][i]
			}
			all := Counts{c.web.SinAgua + c.bot.SinAgua, c.web.Baja + c.bot.Baja, c.web.ConAgua + c.bot.ConAgua}
			wz.Cuts[i] = zone > 0 && b.Cuts != nil && b.Cuts(zone, first.AddDate(0, 0, i))
			wz.Days[i].Total = all.total()
			if all.total() > 0 && all.total() >= b.minShown && (c.bot.total() == 0 || c.bot.total() >= b.minShown) {
				wz.Days[i].Detail = &all
			}
			switch {
			case zone == 0:
			case wz.Cuts[i]:
				w.Dry.OnCut += c.web.SinAgua
			default:
				w.Dry.OffCut += c.web.SinAgua
			}
		}
		if zc := cells[zone]; zc != nil {
			w.last[zone] = lastDays{zc[weekDays-2].bot.total(), zc[weekDays-1].bot.total(), wz.Days[weekDays-2].Detail != nil}
		}
		w.Zones = append(w.Zones, wz)
	}
	return w, nil
}

// Run works until ctx ends: every minute it forgets what the limits hold from over an hour
// ago, and every interval it saves the new reports and, while someone looks at the map,
// reloads the bot's answers and the week. The server flushes once more after it stops taking
// requests.
func (b *Board) Run(ctx context.Context, every time.Duration) {
	var forgetting sync.WaitGroup
	defer forgetting.Wait()
	forgetting.Go(func() {
		t := time.NewTicker(b.forgetEvery)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				b.forget()
			}
		}
	})
	t := time.NewTicker(every)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			if err := b.Flush(ctx); err != nil {
				b.log.Warn("web reports not saved yet; retrying later", "err", err)
			}
			if err := b.refreshBot(ctx); err != nil {
				b.log.Warn("bot answers not refreshed", "err", err)
			}
		}
	}
}
