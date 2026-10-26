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
}

type zoneInfo struct {
	Zone int      `json:"zone"`
	Days []string `json:"days"`
	Next []string `json:"next"`
}

func (a *api) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) { io.WriteString(w, "ok") })
	mux.HandleFunc("GET /v1/zones", a.zonesList)
	mux.HandleFunc("GET /v1/zone", a.zoneAt)
	mux.HandleFunc("GET /v1/colonias", a.coloniaSearch)
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

// clientIP is the address Fly's proxy saw; without the proxy (local runs) it's the connection's.
func clientIP(r *http.Request) string {
	if ip := r.Header.Get("Fly-Client-IP"); ip != "" {
		return ip
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

func (a *api) info(zone int) zoneInfo {
	z := zoneInfo{Zone: zone, Days: []string{}, Next: []string{}}
	for _, d := range a.sched.Weekdays(zone) {
		z.Days = append(z.Days, rotation.WeekdayES(d))
	}
	for _, d := range a.sched.NextCuts(zone, time.Now(), 6) {
		z.Next = append(z.Next, d.Format(rotation.DateLayout))
	}
	return z
}

func (a *api) zonesList(w http.ResponseWriter, _ *http.Request) {
	var out []zoneInfo
	for _, z := range a.sched.Zones() {
		out = append(out, a.info(z))
	}
	writeJSON(w, out, publicFiveMinutes)
}

func (a *api) zoneAt(w http.ResponseWriter, r *http.Request) {
	lat, err1 := strconv.ParseFloat(r.URL.Query().Get("lat"), 64)
	lon, err2 := strconv.ParseFloat(r.URL.Query().Get("lon"), 64)
	if err1 != nil || err2 != nil || math.IsNaN(lat) || math.IsNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180 {
		http.Error(w, "lat and lon required", http.StatusBadRequest)
		return
	}
	out := []zoneInfo{}
	for _, z := range a.zones.Lookup(lat, lon) {
		out = append(out, a.info(z))
	}
	// The request carries the visitor's coordinates: keep it out of every cache.
	writeJSON(w, map[string]any{"zones": out}, "no-store")
}

func (a *api) coloniaSearch(w http.ResponseWriter, r *http.Request) {
	q := strings.TrimSpace(r.URL.Query().Get("q"))
	if n := len([]rune(q)); n < 1 || n > colonias.MaxQuery {
		http.Error(w, "q must have 1 to 80 characters", http.StatusBadRequest)
		return
	}
	matches, exact := a.cols.Search(q, 0)
	if matches == nil {
		matches = []colonias.Colonia{}
	}
	res := map[string]any{"exact": exact, "colonias": matches}
	if !exact {
		if others := a.cols.Others(q); len(others) > 0 {
			res["others"] = others
		}
	}
	writeJSON(w, res, publicFiveMinutes)
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
