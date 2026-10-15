package main

import (
	"context"
	"crypto/hmac"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"aguagdl/api/internal/bot"
	"aguagdl/api/internal/colonias"
	"aguagdl/api/internal/geo"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/wa"
)

type api struct {
	bot         *bot.Bot
	db          resultsStore
	sched       *rotation.Schedule
	zones       *geo.Zones
	cols        *colonias.Index
	appSecret   []byte
	verifyToken string
	minShown    int
	log         *slog.Logger

	resultsMu   sync.Mutex
	resultsAt   time.Time
	resultsRows []store.Result
}

type resultsStore interface {
	Results(ctx context.Context, since time.Time, minReports int) ([]store.Result, error)
}

// resultsTTL is how long /v1/results reuses one query, so traffic to /resultados
// can't keep Neon awake and use up its compute hours.
const resultsTTL = 5 * time.Minute

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
	mux.HandleFunc("GET /v1/results", a.results)
	mux.HandleFunc("GET /wa/webhook", a.verify)
	mux.HandleFunc("POST /wa/webhook", a.webhook)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/v1/") {
			w.Header().Set("Access-Control-Allow-Origin", "*")
		}
		mux.ServeHTTP(w, r)
	})
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
	if err1 != nil || err2 != nil || lat < -90 || lat > 90 || lon < -180 || lon > 180 {
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
	if len([]rune(q)) < 3 {
		http.Error(w, "q must have at least 3 characters", http.StatusBadRequest)
		return
	}
	matches, exact := a.cols.Search(q, 10)
	if matches == nil {
		matches = []colonias.Colonia{}
	}
	writeJSON(w, map[string]any{"exact": exact, "colonias": matches}, publicFiveMinutes)
}

func (a *api) results(w http.ResponseWriter, r *http.Request) {
	rows, err := a.cachedResults(r.Context())
	if err != nil {
		a.log.Error("results", "err", err)
		http.Error(w, "error", http.StatusInternalServerError)
		return
	}
	writeJSON(w, rows, publicFiveMinutes)
}

// cachedResults queries Postgres at most once per resultsTTL; concurrent requests
// wait for that one query.
func (a *api) cachedResults(ctx context.Context) ([]store.Result, error) {
	a.resultsMu.Lock()
	defer a.resultsMu.Unlock()
	if a.resultsRows != nil && time.Since(a.resultsAt) < resultsTTL {
		return a.resultsRows, nil
	}
	rows, err := a.db.Results(ctx, a.sched.Day(time.Now()).AddDate(0, 0, -60), a.minShown)
	if err != nil {
		return nil, err
	}
	if rows == nil {
		rows = []store.Result{}
	}
	a.resultsRows, a.resultsAt = rows, time.Now()
	return rows, nil
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

const publicFiveMinutes = "public, max-age=300"

func writeJSON(w http.ResponseWriter, v any, cacheControl string) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", cacheControl)
	json.NewEncoder(w).Encode(v)
}
