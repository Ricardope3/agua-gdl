package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/bot"
	"aguagdl/api/internal/fake"
	"aguagdl/api/internal/geo"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/webreports"
)

func TestV1ErrorsAllowAnyOrigin(t *testing.T) {
	h := (&api{}).routes()
	for _, path := range []string{"/v1/zone?lat=x", "/v1/colonias?q=", "/v1/nope"} {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
		if rec.Code < 400 || rec.Header().Get("Access-Control-Allow-Origin") != "*" {
			t.Errorf("%s: status %d, allow-origin %q", path, rec.Code, rec.Header().Get("Access-Control-Allow-Origin"))
		}
	}
}

func TestWebhookVerifyEchoesChallengeAsPlainText(t *testing.T) {
	h := (&api{verifyToken: "tok", appSecret: []byte("secret")}).routes()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/wa/webhook?hub.mode=subscribe&hub.verify_token=tok&hub.challenge=%3Cb%3E1%3C%2Fb%3E", nil))
	if rec.Code != http.StatusOK || rec.Body.String() != "<b>1</b>" || !strings.HasPrefix(rec.Header().Get("Content-Type"), "text/plain") {
		t.Fatalf("status %d, body %q, content type %q", rec.Code, rec.Body.String(), rec.Header().Get("Content-Type"))
	}
	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/wa/webhook?hub.mode=subscribe&hub.verify_token=tokx&hub.challenge=1", nil))
	if rec.Code != http.StatusForbidden {
		t.Fatalf("a wrong token must be refused: status %d", rec.Code)
	}
}

func TestHeartbeatCapsTheBody(t *testing.T) {
	var path string
	var body []byte
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path = r.URL.Path
		body, _ = io.ReadAll(r.Body)
	}))
	defer srv.Close()
	heartbeat(srv.URL+"/ping", slog.New(slog.NewTextHandler(io.Discard, nil)))(context.Background(), false, strings.Repeat("é", 5000))
	if path != "/ping/fail" || len([]rune(string(body))) != 1000 {
		t.Fatalf("path %q, %d characters", path, len([]rune(string(body))))
	}
}

func TestHeartbeatErrorsDontLogTheURL(t *testing.T) {
	var logs bytes.Buffer
	heartbeat("http://127.0.0.1:1/secret-check-id", slog.New(slog.NewTextHandler(&logs, nil)))(context.Background(), true, "ok")
	if !strings.Contains(logs.String(), "heartbeat") || strings.Contains(logs.String(), "secret-check-id") {
		t.Fatalf("the ping URL must stay out of the logs: %s", logs.String())
	}
}

func testSchedule(t *testing.T) *rotation.Schedule {
	t.Helper()
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		t.Fatal(err)
	}
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		t.Fatal(err)
	}
	return sched
}

func TestZoneLookupIsNotCached(t *testing.T) {
	zones, err := geo.Load(data.Zonas)
	if err != nil {
		t.Fatal(err)
	}
	h := (&api{zones: zones, sched: testSchedule(t)}).routes()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/v1/zone?lat=20.6767&lon=-103.3475", nil))
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), `"zone":6`) || rec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("status %d, cache %q, body %s", rec.Code, rec.Header().Get("Cache-Control"), rec.Body.String())
	}
}

type countingResults struct{ calls int }

func (c *countingResults) Results(context.Context, time.Time, int) ([]store.Result, error) {
	c.calls++
	return []store.Result{{Zone: 4, Date: "2026-10-19", Total: 12}}, nil
}

func TestResultsQueryTheDatabaseOncePerFiveMinutes(t *testing.T) {
	db := &countingResults{}
	a := &api{db: db, sched: testSchedule(t), minShown: 10, log: slog.New(slog.NewTextHandler(io.Discard, nil))}
	h := a.routes()
	get := func() {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/v1/results", nil))
		if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), `"total":12`) {
			t.Fatalf("status %d, body %s", rec.Code, rec.Body.String())
		}
	}
	for range 3 {
		get()
	}
	if db.calls != 1 {
		t.Fatalf("3 visits made %d queries, want 1", db.calls)
	}
	a.resultsAt = a.resultsAt.Add(-resultsTTL)
	get()
	if db.calls != 2 {
		t.Fatalf("after 5 minutes the next visit must query again: %d queries", db.calls)
	}
}

func TestV1IsRateLimitedPerClient(t *testing.T) {
	h := (&api{}).routes()
	get := func(path, ip string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		req.Header.Set("Fly-Client-IP", ip)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec
	}
	for range v1PerMinute {
		if get("/v1/nope", "1.1.1.1").Code == http.StatusTooManyRequests {
			t.Fatal("limited too early")
		}
	}
	rec := get("/v1/nope", "1.1.1.1")
	if rec.Code != http.StatusTooManyRequests || rec.Header().Get("Retry-After") != "60" || rec.Header().Get("Access-Control-Allow-Origin") != "*" {
		t.Fatalf("status %d, headers %v", rec.Code, rec.Header())
	}
	if get("/v1/nope", "2.2.2.2").Code == http.StatusTooManyRequests {
		t.Fatal("another client must not be limited")
	}
	if get("/healthz", "1.1.1.1").Code != http.StatusOK {
		t.Fatal("only /v1 is limited")
	}
}

func TestLimiterWindowAndMemoryCap(t *testing.T) {
	l := &limiter{max: 1, counts: map[string]int{}}
	now := time.Now()
	if !l.allow("a", now) || l.allow("a", now) {
		t.Fatal("one request per window")
	}
	if !l.allow("a", now.Add(time.Minute)) {
		t.Fatal("a new window starts over")
	}
	for i := range maxTracked {
		l.allow(strconv.Itoa(i), now.Add(time.Minute))
	}
	for i := 0; l.overflow < overflowPerMinute; i++ {
		if !l.allow("new"+strconv.Itoa(i), now.Add(time.Minute)) {
			t.Fatal("past maxTracked addresses, new ones share a budget instead of being locked out")
		}
	}
	if l.allow("new", now.Add(time.Minute)) || len(l.counts) != maxTracked {
		t.Fatal("the shared budget runs out, and memory stays bounded")
	}
	if !l.allow("new", now.Add(2*time.Minute)) {
		t.Fatal("the shared budget starts over with the window")
	}
}

func TestLimiterCountsIPv6PerSlash64(t *testing.T) {
	l := &limiter{max: 1, counts: map[string]int{}}
	now := time.Now()
	if !l.allow("2001:db8:1:2::1", now) || l.allow("2001:db8:1:2::ffff", now) {
		t.Fatal("two addresses in the same /64 share one budget")
	}
	if !l.allow("2001:db8:1:3::1", now) || !l.allow("203.0.113.7", now) {
		t.Fatal("other /64s and IPv4 addresses have their own")
	}
}

func TestTelegramWebhookChecksTheSecret(t *testing.T) {
	st, tel := fake.NewStore(), &fake.Telegram{}
	b := &bot.Bot{Store: st, Telegram: tel, Schedule: testSchedule(t), Now: time.Now, Log: slog.New(slog.NewTextHandler(io.Discard, nil))}
	update := `{"update_id":1,"message":{"message_id":1,"chat":{"id":777,"type":"private"},"text":"zona 4"}}`
	post := func(h http.Handler, secret string) int {
		req := httptest.NewRequest(http.MethodPost, "/tg/webhook", strings.NewReader(update))
		if secret != "" {
			req.Header.Set("X-Telegram-Bot-Api-Secret-Token", secret)
		}
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec.Code
	}
	if code := post((&api{bot: b}).routes(), "s3cret"); code != http.StatusMethodNotAllowed && code != http.StatusNotFound {
		t.Errorf("without TG_WEBHOOK_SECRET the route must not exist: %d", code)
	}
	h := (&api{bot: b, tgSecret: "s3cret", log: b.Log}).routes()
	for _, secret := range []string{"", "wrong"} {
		if code := post(h, secret); code != http.StatusForbidden {
			t.Errorf("secret %q: %d", secret, code)
		}
	}
	if len(st.Subs) != 0 {
		t.Fatal("a rejected update was processed")
	}
	if code := post(h, "s3cret"); code != http.StatusOK || len(st.Subs) != 1 || len(tel.Sent) != 1 {
		t.Fatalf("code %d, subs %d, replies %d", code, len(st.Subs), len(tel.Sent))
	}
}

func TestWhatsAppWebhookIsOffWithoutItsSecret(t *testing.T) {
	h := (&api{}).routes()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodPost, "/wa/webhook", strings.NewReader("{}")))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status %d, want 404 when WhatsApp isn't configured", rec.Code)
	}
}

func TestTelegramSecretWithoutTokenIsIgnored(t *testing.T) {
	t.Setenv("DATABASE_URL", "postgres://x")
	t.Setenv("PUBLIC_BASE_URL", "https://aguagdl.test")
	t.Setenv("TG_TOKEN", "")
	t.Setenv("TG_WEBHOOK_SECRET", "s3cret")
	c, err := loadConfig()
	if err != nil || c.TGWebhookSecret != "" {
		t.Fatalf("a secret without a token must not route the webhook: %q, %v", c.TGWebhookSecret, err)
	}
}

type memReports struct{ saved []store.WebReport }

func (m *memReports) SaveWebReports(_ context.Context, rs []store.WebReport) error {
	m.saved = append(m.saved, rs...)
	return nil
}
func (m *memReports) WebReportsSince(context.Context, time.Time) ([]store.WebReport, error) {
	return nil, nil
}
func (m *memReports) CountWebReports(context.Context) (int, error) { return 0, nil }
func (m *memReports) BotAnswersSince(context.Context, time.Time) ([]store.BotAnswer, error) {
	return nil, nil
}

func TestReportsFromTheMap(t *testing.T) {
	loc, _ := time.LoadLocation("America/Mexico_City")
	board, err := webreports.New(&memReports{}, data.ColoniasMapa, 10, loc, time.Now, slog.New(slog.NewTextHandler(io.Discard, nil)))
	if err != nil {
		t.Fatal(err)
	}
	h := (&api{reports: board}).routes()
	post := func(origin, body string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodPost, "/v1/reportes", strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Fly-Client-IP", "2001:db8::7")
		if origin != "" {
			req.Header.Set("Origin", origin)
		}
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec
	}
	ok := `{"n":"1 DE MAYO","m":"Guadalajara","cp":"44940","estado":"sin_agua"}`
	for _, origin := range []string{"", "https://evil.example", "http://aguagdl.com.evil.example"} {
		if rec := post(origin, ok); rec.Code != http.StatusForbidden {
			t.Errorf("origin %q: status %d", origin, rec.Code)
		}
	}
	if rec := post("https://aguagdl.com", `{"n":"NO EXISTE","m":"Guadalajara","cp":"1","estado":"sin_agua"}`); rec.Code != http.StatusBadRequest {
		t.Errorf("unknown colonia: %d", rec.Code)
	}
	for i := range 3 {
		rec := post("https://aguagdl.com", ok)
		var c webreports.Colonia
		if rec.Code != http.StatusOK || json.Unmarshal(rec.Body.Bytes(), &c) != nil || c.SinAgua != i+1 || rec.Header().Get("Access-Control-Allow-Origin") != "*" {
			t.Fatalf("report %d: %d %s", i+1, rec.Code, rec.Body)
		}
	}
	if rec := post("http://localhost:8771", ok); rec.Code != http.StatusTooManyRequests || rec.Header().Get("Retry-After") == "" {
		t.Errorf("a fourth report for the colonia from one address within the hour: %d", rec.Code)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodOptions, "/v1/reportes", nil))
	if rec.Code != http.StatusNoContent || !strings.Contains(rec.Header().Get("Access-Control-Allow-Methods"), "POST") || rec.Header().Get("Access-Control-Allow-Headers") != "Content-Type" {
		t.Errorf("preflight: %d %v", rec.Code, rec.Header())
	}
	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/v1/reportes", nil))
	var s webreports.Summary
	if rec.Code != http.StatusOK || json.Unmarshal(rec.Body.Bytes(), &s) != nil || s.Total != 3 || s.Colonias != 1 || rec.Header().Get("Cache-Control") != "public, max-age=30" {
		t.Errorf("summary: %d %s", rec.Code, rec.Body)
	}
}
