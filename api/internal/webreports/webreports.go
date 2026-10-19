// Package webreports keeps the water reports people make on the map at aguagdl.com/reportes.
// A report is anonymous: a colonia, an answer and the time. Reports live in memory for the map
// and reach Postgres in batches, so a busy map doesn't keep Neon awake. Repeats are limited per
// client address, which is held in memory for an hour and never stored, and everyone's reports
// together are capped per hour, which bounds memory and the database however many addresses send.
package webreports

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"slices"
	"sort"
	"sync"
	"time"

	"aguagdl/api/internal/store"
)

type Store interface {
	SaveWebReports(ctx context.Context, rs []store.WebReport) error
	WebReportsSince(ctx context.Context, since time.Time) ([]store.WebReport, error)
	CountWebReports(ctx context.Context) (int, error)
	BotAnswersSince(ctx context.Context, since time.Time) ([]store.BotAnswer, error)
}

const (
	// Window is how far back the map counts reports.
	Window = 24 * time.Hour
	// A client address may send this many reports an hour, and this many for one colonia.
	perAddressPerHour = 20
	perColoniaPerHour = 3
	// maxPerHour caps everyone's reports together.
	maxPerHour = 5_000
	// maxTracked bounds the memory the limits use; past it, new addresses wait.
	maxTracked = 50_000
	// maxPending bounds the reports held while the database is unreachable.
	maxPending = 20_000
	summaryTTL = 30 * time.Second
	// botTTL is how long the bot's answers are reused: they change slowly and live in Postgres.
	botTTL = 30 * time.Minute
)

var (
	ErrUnknownColonia = errors.New("unknown colonia")
	ErrBadStatus      = errors.New("unknown status")
	ErrTooMany        = errors.New("too many reports from this address")
	ErrBusy           = errors.New("too many reports this hour")
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
// shown only from MinShown answers, as the privacy notice promises for reports.
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
}

type colonia struct {
	name, municipio, cp string
}

// Board holds the recent reports and the limits. Its methods are safe for concurrent use.
type Board struct {
	store    Store
	minShown int
	loc      *time.Location
	now      func() time.Time
	log      *slog.Logger
	colonias map[string]colonia

	mu        sync.Mutex
	recent    []store.WebReport // the window's reports, oldest first
	pending   []store.WebReport // not yet in Postgres
	allTime   int
	hits      map[string][]time.Time
	cached    *Summary
	cachedAt  time.Time
	bot       []store.BotAnswer
	botAt     time.Time
	botWanted bool
}

// New reads the colonias people may report on (api/data/colonias_mapa.json).
func New(st Store, coloniasJSON []byte, minShown int, loc *time.Location, now func() time.Time, log *slog.Logger) (*Board, error) {
	var rows [][4]string
	if err := json.Unmarshal(coloniasJSON, &rows); err != nil {
		return nil, fmt.Errorf("colonias_mapa.json: %w", err)
	}
	b := &Board{store: st, minShown: minShown, loc: loc, now: now, log: log, colonias: map[string]colonia{}, hits: map[string][]time.Time{}}
	for _, r := range rows {
		b.colonias[Key(r[0], r[1], r[2])] = colonia{r[0], r[1], r[2]}
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
	b.mu.Lock()
	defer b.mu.Unlock()
	b.recent, b.allTime, b.bot, b.botAt, b.cached = recent, all+len(b.pending), bot, now, nil
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
	now := b.now()
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lastHour(now) >= maxPerHour {
		return Colonia{}, ErrBusy
	}
	if !b.allow(addr, key, now) {
		return Colonia{}, ErrTooMany
	}
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
	recent := func(ts []time.Time) []time.Time {
		return slices.DeleteFunc(ts, func(t time.Time) bool { return now.Sub(t) >= time.Hour })
	}
	if len(b.hits) >= maxTracked {
		for k, ts := range b.hits {
			if ts = recent(ts); len(ts) == 0 {
				delete(b.hits, k)
			} else {
				b.hits[k] = ts
			}
		}
	}
	a, c := "a:"+addr, "c:"+addr+"|"+key
	as, cs := recent(b.hits[a]), recent(b.hits[c])
	_, known := b.hits[a]
	if (!known && len(b.hits) >= maxTracked) || len(as) >= perAddressPerHour || len(cs) >= perColoniaPerHour {
		return false
	}
	b.hits[a], b.hits[c] = append(as, now), append(cs, now)
	return true
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
	now := b.now()
	b.mu.Lock()
	defer b.mu.Unlock()
	b.botWanted = true
	if b.cached != nil && now.Sub(b.cachedAt) < summaryTTL {
		return *b.cached
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
	b.cached, b.cachedAt = &s, now
	return s
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
		if za.Answers >= b.minShown {
			za.Detail = c
		}
		out = append(out, za)
	}
	return out
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

// refreshBot reloads the bot's answers when someone looked at the map since the last load
// and botTTL has passed.
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
	b.mu.Lock()
	b.bot, b.botAt, b.botWanted, b.cached = rows, now, false, nil
	b.mu.Unlock()
	return nil
}

// Run writes the reports every interval until ctx ends. The server flushes once more after it
// stops taking requests.
func (b *Board) Run(ctx context.Context, every time.Duration) {
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
