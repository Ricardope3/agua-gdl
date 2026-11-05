package main

import (
	"context"
	"crypto/hmac"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"math"
	"net"
	"net/http"
	"net/netip"
	"net/url"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"

	"aguagdl/api/internal/bot"
	"aguagdl/api/internal/colonias"
	"aguagdl/api/internal/geo"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/tg"
	"aguagdl/api/internal/wa"
	"aguagdl/api/internal/webreports"
)

type api struct {
	bot         *bot.Bot
	sched       *rotation.Schedule
	zones       *geo.Zones
	cols        *colonias.Index
	appSecret   []byte
	verifyToken string
	tgSecret    string            // empty = Telegram off
	reports     *webreports.Board // the map on /reportes; nil = off
	log         *slog.Logger
	now         func() time.Time // nil = time.Now

	mapOnce sync.Once
	mapCols map[string][]geo.Colonia // by mapKey
}

type zoneInfo struct {
	Zone     int      `json:"zone"`
	Days     []string `json:"days"`
	Weekdays []int    `json:"weekdays"`
	Next     []string `json:"next"`
	NextCuts []string `json:"next_cuts"` // the same dates as next, named for what they are
}

// meta tells readers, people and programs alike, what the numbers mean and how old they are.
type meta struct {
	Checked    string `json:"checked"`
	Source     string `json:"source"`
	ValidUntil string `json:"valid_until"`
	Unofficial bool   `json:"unofficial"`
	Meaning    string `json:"meaning"`
	MapSource  string `json:"map_source,omitempty"`
	MapFetched string `json:"map_fetched,omitempty"`
	Docs       string `json:"docs"`
	Version    string `json:"version"`
}

// Set at build time with -ldflags "-X main.version=… -X main.built=…".
var version, built = "dev", ""

const meaning = "Los días (days, weekdays, next, next_cuts) son días CON corte de agua según el calendario del SIAPA, no días con agua. El Gobierno de Jalisco dice que no son cortes totales; vecinos reportan que el agua se va antes y tarda en volver. Agua GDL es un proyecto cívico sin afiliación oficial: confirma en la fuente del SIAPA."

func (a *api) clock() time.Time {
	if a.now != nil {
		return a.now()
	}
	return time.Now()
}

func (a *api) meta() meta {
	m := meta{Unofficial: true, Meaning: meaning, Docs: "https://aguagdl.com/llms.txt", Version: version}
	if a.sched != nil {
		m.Checked, m.Source = a.sched.Provenance()
		if _, end := a.sched.Span(); !end.IsZero() {
			m.ValidUntil = end.Format(rotation.DateLayout)
		}
	}
	if a.zones != nil {
		m.MapSource, m.MapFetched = a.zones.Source()
	}
	return m
}

// Statuses say why a result is empty, so an empty list never reads as "no cuts".
const (
	statusZone      = "con_zona"
	statusOffMap    = "fuera_de_area"
	statusNoZone    = "sin_zona_en_siapa"
	statusListed    = "en_lista_siapa"
	statusOffList   = "fuera_de_lista"
	statusSuggested = "sin_coincidencia_exacta"
	statusNone      = "sin_resultados"
)

var statusNotes = map[string]string{
	statusOffMap:    "El punto queda fuera del mapa de la rotación del SIAPA. Eso no confirma que haya agua ni que no haya cortes: revisa la fuente oficial.",
	statusNoZone:    "El mapa del SIAPA no le da zona a esta colonia. Eso no confirma que tenga agua ni que esté fuera de la rotación: revisa la fuente oficial.",
	statusOffList:   "No está en la lista de colonias del SIAPA; las zonas en «others» son las que le da el mapa del SIAPA, y el mapa y la lista no siempre coinciden.",
	statusSuggested: "Ningún nombre coincide exactamente: «colonias» trae nombres parecidos, que pueden no ser la colonia buscada.",
	statusNone:      "No encontramos esa colonia. Eso no significa que no haya cortes: prueba otro nombre o busca por ubicación (POST /v1/zone).",
}

// mapOutline is one outline of a colonia on SIAPA's map (a name can have several, by postal code).
type mapOutline struct {
	CP          string      `json:"cp"`
	Zones       []int       `json:"zones"`
	Shares      map[int]int `json:"shares,omitempty"`     // percent of its area per zone
	ListZones   []int       `json:"list_zones,omitempty"` // what SIAPA's PDF list says, when it differs
	ListDiffers bool        `json:"list_differs,omitempty"`
}

type mapInfo struct {
	MapZones    []int        `json:"map_zones,omitempty"`
	ListDiffers bool         `json:"list_differs,omitempty"`
	Map         []mapOutline `json:"map,omitempty"`
}

type listColonia struct {
	colonias.Colonia
	mapInfo
}

type otherColonia struct {
	colonias.Other
	mapInfo
}

func mapKey(name, municipio string) string {
	m, _ := strings.CutPrefix(colonias.Normalize(municipio), "SAN PEDRO ")
	return colonias.Normalize(name) + "|" + m
}

func (a *api) mapInfo(name, municipio string) mapInfo {
	var info mapInfo
	if a.zones == nil {
		return info
	}
	a.mapOnce.Do(func() {
		a.mapCols = map[string][]geo.Colonia{}
		for _, c := range a.zones.Colonias() {
			for _, m := range strings.Split(c.Municipio, " y ") {
				k := mapKey(c.Name, m)
				a.mapCols[k] = append(a.mapCols[k], c)
			}
		}
	})
	for _, c := range a.mapCols[mapKey(name, municipio)] {
		o := mapOutline{CP: c.CP, Zones: c.Zones, Shares: c.Shares, ListZones: c.List, ListDiffers: c.List != nil}
		if o.Zones == nil {
			o.Zones = []int{}
		}
		info.Map = append(info.Map, o)
		info.ListDiffers = info.ListDiffers || o.ListDiffers
		for _, z := range c.Zones {
			if !slices.Contains(info.MapZones, z) {
				info.MapZones = append(info.MapZones, z)
			}
		}
	}
	return info
}

func (a *api) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) { io.WriteString(w, "ok") })
	mux.HandleFunc("GET /version", func(w http.ResponseWriter, _ *http.Request) {
		v := map[string]string{"sha": version}
		if built != "" {
			v["built"] = built
		}
		writeJSON(w, v, "no-store")
	})
	mux.HandleFunc("GET /v1/zones", a.zonesList)
	mux.HandleFunc("GET /v1/zone", a.zoneAt)
	mux.HandleFunc("POST /v1/zone", a.zoneAt)
	mux.HandleFunc("GET /v1/colonias", a.coloniaSearch)
	mux.HandleFunc("POST /v1/colonias", a.coloniaSearch)
	mux.HandleFunc("OPTIONS /v1/zone", a.privateOptions)
	mux.HandleFunc("OPTIONS /v1/colonias", a.privateOptions)
	if a.reports != nil {
		mux.HandleFunc("GET /v1/reportes", a.reportesGet)
		mux.HandleFunc("POST /v1/reportes", a.reportesPost)
		mux.HandleFunc("OPTIONS /v1/reportes", a.reportesOptions)
	}
	if len(a.appSecret) > 0 {
		mux.HandleFunc("GET /wa/webhook", a.verify)
		mux.HandleFunc("POST /wa/webhook", a.webhook)
	}
	if a.tgSecret != "" {
		mux.HandleFunc("POST /tg/webhook", a.telegram)
	}
	limit := &limiter{max: v1PerMinute, counts: map[string]int{}}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/v1/") {
			w.Header().Set("Access-Control-Allow-Origin", "*")
			// A refused preflight fails the browser's fetch with no status, so the page couldn't say
			// to wait a minute; preflights don't touch the database and don't count.
			if r.Method != http.MethodOptions && !limit.allow(clientIP(r), time.Now()) {
				w.Header().Set("Retry-After", "60")
				http.Error(w, "too many requests", http.StatusTooManyRequests)
				return
			}
		}
		mux.ServeHTTP(w, r)
	})
}

// v1PerMinute is generous because mobile carriers put many phones behind one IP.
const v1PerMinute = 120

// maxTracked bounds every key the limiter holds, including wider IPv6 networks.
const maxTracked = 10_000

// overflowPerMinute is what every address past maxTracked shares in one window.
const overflowPerMinute = 10 * v1PerMinute

// limiter allows max requests per client IP in each one-minute window. IPv6 clients
// also share wider /56 and /48 budgets, so rotating /64s doesn't multiply the limit.
// When the bounded key map fills, new clients share one bigger budget instead of each
// getting their own or passing unlimited.
type limiter struct {
	mu       sync.Mutex
	max      int
	start    time.Time
	counts   map[string]int
	overflow int
}

type rateLimit struct {
	key string
	max int
}

func (l *limiter) allow(ip string, now time.Time) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	if now.Sub(l.start) >= time.Minute {
		l.start, l.overflow = now, 0
		clear(l.counts)
	}
	limits := limitKeys(ip, l.max)
	unseen := 0
	for _, limit := range limits {
		n, seen := l.counts[limit.key]
		if n >= limit.max {
			return false
		}
		if !seen {
			unseen++
		}
	}
	if len(l.counts)+unseen > maxTracked {
		l.overflow++
		return l.overflow <= overflowPerMinute
	}
	for _, limit := range limits {
		l.counts[limit.key]++
	}
	return true
}

func limitKeys(ip string, maximum int) []rateLimit {
	limits := []rateLimit{{"ip:" + limitKey(ip), maximum}}
	addr, err := netip.ParseAddr(ip)
	if err != nil || !addr.Is6() || addr.Is4In6() {
		return limits
	}
	for _, network := range []struct {
		bits int
		max  int
	}{{56, 2 * maximum}, {48, 10 * maximum}} {
		if p, err := addr.Prefix(network.bits); err == nil {
			limits = append(limits, rateLimit{strconv.Itoa(network.bits) + ":" + p.String(), network.max})
		}
	}
	return limits
}

func limitKey(ip string) string {
	addr, err := netip.ParseAddr(ip)
	if err != nil || addr.Is4() || addr.Is4In6() {
		return ip
	}
	p, err := addr.Prefix(64)
	if err != nil {
		return ip
	}
	return p.String()
}

// clientIP is the address Fly's proxy saw. The header is trusted only when the
// connection itself came from a private or loopback address: Fly's proxy reaches the
// app over its private network, while a client connecting directly (any deployment
// that isn't behind Fly's edge) has a public RemoteAddr, so its spoofed header is
// ignored and every per-address limit falls back to the connection's address.
func clientIP(r *http.Request) string {
	if ip := r.Header.Get("Fly-Client-IP"); ip != "" {
		if a, err := netip.ParseAddr(ip); err == nil {
			if host, _, err := net.SplitHostPort(r.RemoteAddr); err == nil {
				if h, err := netip.ParseAddr(host); err == nil && (h.IsPrivate() || h.IsLoopback()) {
					return a.String()
				}
			}
		}
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

func (a *api) info(zone int) zoneInfo {
	z := zoneInfo{Zone: zone, Days: []string{}, Weekdays: []int{}, Next: []string{}, NextCuts: []string{}}
	for _, d := range a.sched.WeekdaysOn(zone, a.sched.Day(a.clock()).AddDate(0, 0, 1)) {
		z.Days = append(z.Days, rotation.WeekdayES(d))
		z.Weekdays = append(z.Weekdays, int(d))
	}
	for _, d := range a.sched.NextCuts(zone, a.clock(), 6) {
		z.Next = append(z.Next, d.Format(rotation.DateLayout))
	}
	z.NextCuts = z.Next
	return z
}

func (a *api) zonesList(w http.ResponseWriter, _ *http.Request) {
	out := []zoneInfo{}
	for _, z := range a.sched.Zones() {
		out = append(out, a.info(z))
	}
	checked, source := a.sched.Provenance()
	_, end := a.sched.Span()
	endAt := ""
	if !end.IsZero() {
		endAt = end.Format(rotation.DateLayout)
	}
	writeJSON(w, map[string]any{"zones": out, "checked": checked, "source": source, "end": endAt, "meta": a.meta()}, publicFiveMinutes)
}

func (a *api) zoneAt(w http.ResponseWriter, r *http.Request) {
	var lat, lon float64
	var err1, err2 error
	if r.Method == http.MethodPost {
		var in struct {
			Lat *float64 `json:"lat"`
			Lon *float64 `json:"lon"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 1024)).Decode(&in); err != nil || in.Lat == nil || in.Lon == nil {
			http.Error(w, "lat and lon required", http.StatusBadRequest)
			return
		}
		lat, lon = *in.Lat, *in.Lon
	} else {
		lat, err1 = strconv.ParseFloat(r.URL.Query().Get("lat"), 64)
		lon, err2 = strconv.ParseFloat(r.URL.Query().Get("lon"), 64)
	}
	if err1 != nil || err2 != nil || math.IsNaN(lat) || math.IsNaN(lon) || math.IsInf(lat, 0) || math.IsInf(lon, 0) || lat < -90 || lat > 90 || lon < -180 || lon > 180 {
		http.Error(w, "lat and lon required", http.StatusBadRequest)
		return
	}
	out := []zoneInfo{}
	ids, inColonia := a.zones.Where(lat, lon)
	for _, z := range ids {
		out = append(out, a.info(z))
	}
	status := statusZone
	switch {
	case len(out) > 0:
	case inColonia:
		status = statusNoZone
	default:
		status = statusOffMap
	}
	res := map[string]any{"zones": out, "status": status, "meta": a.meta()}
	if note, ok := statusNotes[status]; ok {
		res["status_note"] = note
	}
	// Coordinates and searches stay out of URLs, browser history, proxies and caches.
	writeJSON(w, res, "no-store")
}

func (a *api) coloniaSearch(w http.ResponseWriter, r *http.Request) {
	q := strings.TrimSpace(r.URL.Query().Get("q"))
	cache := publicFiveMinutes
	if r.Method == http.MethodPost {
		var in struct {
			Q string `json:"q"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 1024)).Decode(&in); err != nil {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		q, cache = strings.TrimSpace(in.Q), "no-store"
	}
	if n := len([]rune(q)); n < 1 || n > colonias.MaxQuery {
		http.Error(w, "q must have 1 to 80 characters", http.StatusBadRequest)
		return
	}
	matches, exact := a.cols.Search(q, 0)
	out := []listColonia{}
	for _, c := range matches {
		out = append(out, listColonia{c, a.mapInfo(c.Name, c.Municipio)})
	}
	res := map[string]any{"exact": exact, "colonias": out}
	status := statusListed
	if !exact {
		status = statusSuggested
		if len(out) == 0 {
			status = statusNone
		}
		if others := a.cols.Others(q); len(others) > 0 {
			var outOthers []otherColonia
			status = statusNoZone
			for _, o := range others {
				outOthers = append(outOthers, otherColonia{o, a.mapInfo(o.Name, o.Municipio)})
				if len(o.Zones) > 0 {
					status = statusOffList
				}
			}
			res["others"] = outOthers
		}
	}
	res["status"], res["meta"] = status, a.meta()
	if note, ok := statusNotes[status]; ok {
		res["status_note"] = note
	}
	writeJSON(w, res, cache)
}

func (a *api) privateOptions(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Access-Control-Max-Age", "86400")
	w.WriteHeader(http.StatusNoContent)
}

// reportesGet serves the map's numbers: the day's reports by colonia, the totals, the bot's
// answers by zone and the week. They come from memory, so traffic here doesn't wake Neon.
func (a *api) reportesGet(w http.ResponseWriter, r *http.Request) {
	raw, gz, err := a.reports.SummaryJSON()
	if err != nil {
		a.log.Error("reportes", "err", err)
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "public, max-age=30")
	w.Header().Set("Vary", "Accept-Encoding")
	if strings.Contains(r.Header.Get("Accept-Encoding"), "gzip") {
		w.Header().Set("Content-Encoding", "gzip")
		raw = gz
	}
	w.Write(raw)
}

type reportIn struct {
	Name      string `json:"n"`
	Municipio string `json:"m"`
	CP        string `json:"cp"`
	Status    string `json:"estado"`
	Turbia    bool   `json:"turbia"`
	Olor      bool   `json:"olor"`
	Sedimento bool   `json:"sedimento"`
}

// reportesPost takes a report from the map. Only the site's own pages may send one; the
// address only counts toward the hourly limits, in memory.
func (a *api) reportesPost(w http.ResponseWriter, r *http.Request) {
	if !reportOrigin(r.Header.Get("Origin")) {
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	var in reportIn
	if err := json.NewDecoder(io.LimitReader(r.Body, 2048)).Decode(&in); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	c, err := a.reports.Add(limitKey(clientIP(r)), in.Name, in.Municipio, in.CP, in.Status, in.Turbia, in.Olor, in.Sedimento)
	switch {
	case errors.Is(err, webreports.ErrTooMany):
		w.Header().Set("Retry-After", "3600")
		http.Error(w, "too many reports", http.StatusTooManyRequests)
		return
	case errors.Is(err, webreports.ErrBusy):
		w.Header().Set("Retry-After", "600")
		http.Error(w, "too many reports this hour", http.StatusServiceUnavailable)
		return
	case errors.Is(err, webreports.ErrColoniaFull):
		w.Header().Set("Retry-After", "900")
		http.Error(w, "colonia: too many reports this hour", http.StatusTooManyRequests)
		return
	case err != nil:
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	writeJSON(w, c, "no-store")
}

// reportesOptions answers the browser's preflight for the JSON POST.
func (a *api) reportesOptions(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	w.Header().Set("Access-Control-Max-Age", "86400")
	w.WriteHeader(http.StatusNoContent)
}

// reportOrigin accepts the site and local copies of it (pages served on localhost).
func reportOrigin(origin string) bool {
	if origin == "https://aguagdl.com" {
		return true
	}
	u, err := url.Parse(origin)
	return err == nil && u.Scheme == "http" && (u.Hostname() == "localhost" || u.Hostname() == "127.0.0.1")
}

func (a *api) verify(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	if q.Get("hub.mode") == "subscribe" && hmac.Equal([]byte(q.Get("hub.verify_token")), []byte(a.verifyToken)) {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		io.WriteString(w, q.Get("hub.challenge"))
		return
	}
	http.Error(w, "forbidden", http.StatusForbidden)
}

func (a *api) webhook(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	if !wa.ValidSignature(a.appSecret, body, r.Header.Get("X-Hub-Signature-256")) {
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	var p wa.Payload
	if err := json.Unmarshal(body, &p); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 20*time.Second)
	defer cancel()
	if err := a.bot.Handle(ctx, p); err != nil {
		a.log.Error("webhook", "err", err)
		http.Error(w, "retry", http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
}

// telegram receives the updates Telegram sends after setWebhook with our secret token.
func (a *api) telegram(w http.ResponseWriter, r *http.Request) {
	if !tg.ValidSecret(a.tgSecret, r.Header.Get("X-Telegram-Bot-Api-Secret-Token")) {
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	var u tg.Update
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&u); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 20*time.Second)
	defer cancel()
	if err := a.bot.HandleTelegram(ctx, u); err != nil {
		a.log.Error("telegram webhook", "err", err)
		http.Error(w, "retry", http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
}

const publicFiveMinutes = "public, max-age=300"

func writeJSON(w http.ResponseWriter, v any, cacheControl string) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", cacheControl)
	json.NewEncoder(w).Encode(v)
}
