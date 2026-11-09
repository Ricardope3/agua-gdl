package main

import (
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"slices"
	"strconv"
	"strings"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/bot"
	"aguagdl/api/internal/colonias"
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
	var logs bytes.Buffer
	heartbeat(srv.URL+"/ping", slog.New(slog.NewTextHandler(&logs, nil)))(context.Background(), false, strings.Repeat("é", 5000))
	if path != "/ping/fail" || len([]rune(string(body))) != 1000 || logs.Len() != 0 {
		t.Fatalf("path %q, %d characters, logs %q", path, len([]rune(string(body))), logs.String())
	}
}

func TestHeartbeatErrorsDontLogTheURL(t *testing.T) {
	var logs bytes.Buffer
	heartbeat("http://127.0.0.1:1/secret-check-id", slog.New(slog.NewTextHandler(&logs, nil)))(context.Background(), true, "ok")
	if !strings.Contains(logs.String(), "heartbeat") || strings.Contains(logs.String(), "secret-check-id") {
		t.Fatalf("the ping URL must stay out of the logs: %s", logs.String())
	}
}

func TestHeartbeatRefusedPingIsAnError(t *testing.T) {
	srv := httptest.NewServer(http.NotFoundHandler()) // a deleted check
	defer srv.Close()
	var logs bytes.Buffer
	heartbeat(srv.URL+"/secret-check-id", slog.New(slog.NewTextHandler(&logs, nil)))(context.Background(), true, "ok")
	if !strings.Contains(logs.String(), "level=ERROR") || !strings.Contains(logs.String(), "status 404") || strings.Contains(logs.String(), "secret-check-id") {
		t.Fatalf("a refused ping must be logged by its status alone: %s", logs.String())
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

func TestPrivateLookupsAcceptJSONPosts(t *testing.T) {
	zones, err := geo.Load(data.Zonas)
	if err != nil {
		t.Fatal(err)
	}
	cols, err := colonias.Load(data.Colonias)
	if err != nil {
		t.Fatal(err)
	}
	h := (&api{zones: zones, sched: testSchedule(t), cols: cols}).routes()
	for _, tc := range []struct {
		path, body, want string
	}{
		{"/v1/zone", `{"lat":20.6767,"lon":-103.3475}`, `"zone":6`},
		{"/v1/colonias", `{"q":"Americana"}`, `"colonias"`},
	} {
		req := httptest.NewRequest(http.MethodPost, tc.path, strings.NewReader(tc.body))
		req.Header.Set("Content-Type", "application/json")
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK || rec.Header().Get("Cache-Control") != "no-store" || !strings.Contains(rec.Body.String(), tc.want) {
			t.Errorf("POST %s: status %d, cache %q, body %s", tc.path, rec.Code, rec.Header().Get("Cache-Control"), rec.Body.String())
		}
	}
	for _, path := range []string{"/v1/zone", "/v1/colonias"} {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodOptions, path, nil))
		if rec.Code != http.StatusNoContent || rec.Header().Get("Cache-Control") != "no-store" {
			t.Errorf("OPTIONS %s: status %d, headers %v", path, rec.Code, rec.Header())
		}
	}
}

func TestZoneLookupNeedsRealCoordinates(t *testing.T) {
	zones, err := geo.Load(data.Zonas)
	if err != nil {
		t.Fatal(err)
	}
	h := (&api{zones: zones, sched: testSchedule(t)}).routes()
	for _, q := range []string{"lat=NaN&lon=NaN", "lat=20.6767&lon=nan", "lat=Inf&lon=-103.3475", "lat=20.6767&lon=-Infinity"} {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/v1/zone?"+q, nil))
		if rec.Code != http.StatusBadRequest {
			t.Errorf("%s: status %d, body %s", q, rec.Code, rec.Body.String())
		}
	}
}

func TestV1IsRateLimitedPerClient(t *testing.T) {
	h := (&api{}).routes()
	do := func(method, path, ip string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(method, path, nil)
		req.RemoteAddr = "10.0.0.1:1234" // Fly's proxy connects over the private network
		req.Header.Set("Fly-Client-IP", ip)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec
	}
	get := func(path, ip string) *httptest.ResponseRecorder { return do(http.MethodGet, path, ip) }
	for range v1PerMinute + 1 {
		do(http.MethodOptions, "/v1/reportes", "3.3.3.3")
	}
	if get("/v1/nope", "3.3.3.3").Code == http.StatusTooManyRequests {
		t.Fatal("preflights don't count")
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
	if do(http.MethodOptions, "/v1/reportes", "1.1.1.1").Code == http.StatusTooManyRequests {
		t.Fatal("a limited client's preflight still passes, so the browser shows the POST's 429")
	}
	if get("/healthz", "1.1.1.1").Code != http.StatusOK {
		t.Fatal("only /v1 is limited")
	}
}

func TestFlyClientIPOnlyCountsFromTheProxy(t *testing.T) {
	// Fly's edge connects over the private network, so its header is the client address.
	r := httptest.NewRequest(http.MethodGet, "/v1/nope", nil)
	r.RemoteAddr = "[fdaa:0:1:a7b:102:2d78:0:1]:1234"
	r.Header.Set("Fly-Client-IP", "2001:db8::7")
	if got := clientIP(r); got != "2001:db8::7" {
		t.Fatalf("the proxy's header is trusted: %q", got)
	}
	// A direct client (any deployment not behind Fly) has a public RemoteAddr: its
	// spoofed header must not defeat the per-address limits.
	r = httptest.NewRequest(http.MethodGet, "/v1/nope", nil)
	r.Header.Set("Fly-Client-IP", "2001:db8::7")
	if got := clientIP(r); got == "2001:db8::7" {
		t.Fatalf("a spoofed header from a public address was trusted: %q", got)
	}
	// Loopback (local runs) still trusts the header, so tests and dev keep working.
	r = httptest.NewRequest(http.MethodGet, "/v1/nope", nil)
	r.RemoteAddr = "127.0.0.1:54321"
	r.Header.Set("Fly-Client-IP", "2001:db8::7")
	if got := clientIP(r); got != "2001:db8::7" {
		t.Fatalf("loopback should trust the header: %q", got)
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

func TestLimiterCountsIPv6PerSlash56And48(t *testing.T) {
	now := time.Now()
	l56 := &limiter{max: 1, counts: map[string]int{}}
	if !l56.allow("2001:db8:1:1::1", now) || !l56.allow("2001:db8:1:2::1", now) || l56.allow("2001:db8:1:3::1", now) {
		t.Fatal("different /64s in one /56 share its wider budget")
	}

	l48 := &limiter{max: 1, counts: map[string]int{}}
	for i := 0; i <= 10; i++ {
		// The fourth hextet's high byte selects a new /56 inside the same /48.
		ip := "2001:db8:1:" + strconv.FormatInt(int64(i<<8), 16) + "::1"
		if got := l48.allow(ip, now); got != (i < 10) {
			t.Fatalf("request %d from a new /56 in one /48: allowed=%v", i, got)
		}
	}
}

func TestLimiterSlash48RotationCannotExhaustTracker(t *testing.T) {
	l := &limiter{max: v1PerMinute, counts: map[string]int{}}
	now := time.Now()
	allowed := 0
	for i := 0; i <= 10*v1PerMinute; i++ {
		// Every address is a different /64 in 2001:db8:1::/48, spread across its /56s.
		fourth := (i%256)<<8 | i/256
		ip := "2001:db8:1:" + strconv.FormatInt(int64(fourth), 16) + "::1"
		if l.allow(ip, now) {
			allowed++
		}
	}
	if allowed != 10*v1PerMinute || len(l.counts) != allowed+256+1 || l.overflow != 0 {
		t.Fatalf("one /48 got %d requests and %d tracked keys, overflow %d", allowed, len(l.counts), l.overflow)
	}
	if !l.allow("2001:db8:2:1::1", now) {
		t.Fatal("the exhausted /48 must not deny a visitor outside it")
	}
}

func TestTelegramWebhookChecksTheSecret(t *testing.T) {
	st, tel, sched := fake.NewStore(), &fake.Telegram{}, testSchedule(t)
	// Inside the rotation: once it's over, the bot takes no subscriptions.
	now := func() time.Time { return time.Date(2026, 10, 20, 10, 0, 0, 0, sched.Location()) }
	b := &bot.Bot{Store: st, Telegram: tel, Schedule: sched, Now: now, Log: slog.New(slog.NewTextHandler(io.Discard, nil))}
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

func TestConfigChecksTheNumbers(t *testing.T) {
	t.Setenv("DATABASE_URL", "postgres://x")
	t.Setenv("PUBLIC_BASE_URL", "https://aguagdl.test")
	for _, name := range []string{"WA_TOKEN", "TG_TOKEN", "REMINDER_HOUR", "CATCH_UP_UNTIL_HOUR", "DAILY_CAP", "MONTHLY_CAP", "MIN_REPORTS_SHOWN"} {
		t.Setenv(name, "")
	}
	if c, err := loadConfig(); err != nil || c.ReminderHour != 20 || c.CatchUpUntil != 22 || c.MinShown != 10 {
		t.Fatalf("the defaults: %+v %v", c, err)
	}
	t.Run("in range", func(t *testing.T) {
		for name, v := range map[string]string{"REMINDER_HOUR": "0", "CATCH_UP_UNTIL_HOUR": "23", "DAILY_CAP": "0", "MONTHLY_CAP": "0", "MIN_REPORTS_SHOWN": "1"} {
			t.Setenv(name, v)
		}
		if _, err := loadConfig(); err != nil {
			t.Fatal(err)
		}
	})
	for _, c := range []struct{ name, value string }{
		{"REMINDER_HOUR", "-1"}, {"REMINDER_HOUR", "22"}, {"REMINDER_HOUR", "24"},
		{"CATCH_UP_UNTIL_HOUR", "20"}, {"CATCH_UP_UNTIL_HOUR", "24"},
		{"DAILY_CAP", "-1"}, {"MONTHLY_CAP", "-1"}, {"MIN_REPORTS_SHOWN", "0"},
	} {
		t.Run(c.name+"="+c.value, func(t *testing.T) {
			t.Setenv(c.name, c.value)
			if _, err := loadConfig(); err == nil || !strings.Contains(err.Error(), c.name) {
				t.Errorf("want an error that names %s: %v", c.name, err)
			}
		})
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
func (m *memReports) WebReportsByDay(context.Context, time.Time) ([]store.DayCount, error) {
	return nil, nil
}
func (m *memReports) BotAnswersByDay(context.Context, time.Time) ([]store.DayCount, error) {
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
		req.RemoteAddr = "10.0.0.1:1234"
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
	req := httptest.NewRequest(http.MethodGet, "/v1/reportes", nil)
	req.Header.Set("Accept-Encoding", "gzip")
	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	zr, err := gzip.NewReader(rec.Body)
	var zipped webreports.Summary
	if err != nil || rec.Header().Get("Content-Encoding") != "gzip" || json.NewDecoder(zr).Decode(&zipped) != nil || zipped.Total != 3 {
		t.Errorf("gzipped summary: %v %v %+v", err, rec.Header(), zipped)
	}
	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/v1/reportes", nil))
	var s webreports.Summary
	if rec.Code != http.StatusOK || json.Unmarshal(rec.Body.Bytes(), &s) != nil || s.Total != 3 || s.Colonias != 1 || rec.Header().Get("Cache-Control") != "public, max-age=30" {
		t.Errorf("summary: %d %s", rec.Code, rec.Body)
	}
}

func TestReportFailureKeepsStorageErrorsOutOfTheReply(t *testing.T) {
	disk := fmt.Errorf("durable report acknowledgement: %w", errors.New("write /data/web-reports.wal: no space left on device"))
	if code, body, retry := reportFailure(disk); code != http.StatusInternalServerError || body != "internal error" || retry != "" {
		t.Errorf("a failed log write: %d %q %q", code, body, retry)
	}
	for _, c := range []struct {
		err   error
		code  int
		body  string
		retry string
	}{
		{webreports.ErrUnknownColonia, http.StatusBadRequest, "unknown colonia", ""},
		{webreports.ErrBadStatus, http.StatusBadRequest, "unknown status", ""},
		{webreports.ErrTooMany, http.StatusTooManyRequests, "too many reports", "3600"},
		{webreports.ErrBusy, http.StatusServiceUnavailable, "too many reports this hour", "600"},
		{webreports.ErrColoniaFull, http.StatusTooManyRequests, "colonia: too many reports this hour", "900"},
	} {
		if code, body, retry := reportFailure(c.err); code != c.code || body != c.body || retry != c.retry {
			t.Errorf("%v: %d %q %q", c.err, code, body, retry)
		}
	}
}

func agentAPI(t *testing.T) *api {
	t.Helper()
	zones, err := geo.Load(data.Zonas)
	if err != nil {
		t.Fatal(err)
	}
	cols, err := colonias.Load(data.Colonias)
	if err != nil {
		t.Fatal(err)
	}
	if err := cols.LoadOthers(data.OtrasColonias); err != nil {
		t.Fatal(err)
	}
	sched := testSchedule(t)
	now := func() time.Time { return time.Date(2026, 10, 20, 10, 0, 0, 0, sched.Location()) }
	return &api{zones: zones, sched: sched, cols: cols, now: now}
}

func getJSON(t *testing.T, h http.Handler, method, path, body string, v any) {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("%s %s: status %d, body %s", method, path, rec.Code, rec.Body.String())
	}
	if err := json.Unmarshal(rec.Body.Bytes(), v); err != nil {
		t.Fatal(err)
	}
}

type metaOut struct {
	Checked, Source, ValidUntil, Meaning string
	Unofficial                           bool
}

func (m metaOut) check(t *testing.T, where string) {
	t.Helper()
	checked, source := testSchedule(t).Provenance()
	if m.Checked == "" || m.Checked != checked || m.Source != source || m.ValidUntil != "2027-03-31" || !m.Unofficial || !strings.Contains(m.Meaning, "CON corte") {
		t.Errorf("%s: meta %+v", where, m)
	}
}

func TestZonesSayTheDaysAreCuts(t *testing.T) {
	h := agentAPI(t).routes()
	var out struct {
		Meta struct {
			metaOut
			ValidUntil string `json:"valid_until"`
		}
		Zones []struct {
			Zone     int
			Next     []string
			NextCuts []string `json:"next_cuts"`
		}
	}
	getJSON(t, h, http.MethodGet, "/v1/zones", "", &out)
	out.Meta.metaOut.ValidUntil = out.Meta.ValidUntil
	out.Meta.check(t, "/v1/zones")
	if len(out.Zones) != 7 || out.Zones[0].Zone != 1 || len(out.Zones[0].NextCuts) != 6 || out.Zones[0].NextCuts[0] != "2026-10-23" || !slices.Equal(out.Zones[0].Next, out.Zones[0].NextCuts) {
		t.Errorf("zones %+v", out.Zones)
	}
}

func TestEmptyLookupsSayWhy(t *testing.T) {
	h := agentAPI(t).routes()
	type res struct {
		Zones      []json.RawMessage
		Status     string
		StatusNote string `json:"status_note"`
		Meta       struct {
			metaOut
			ValidUntil string `json:"valid_until"`
		}
	}
	for _, tc := range []struct {
		where, body, status string
		zones               int
	}{
		{"Catedral", `{"lat":20.6767,"lon":-103.3475}`, "con_zona", 1},
		{"Chapala", `{"lat":20.2950,"lon":-103.2560}`, "fuera_de_area", 0},
		{"Basílica de Zapopan", `{"lat":20.7206,"lon":-103.3916}`, "sin_zona_en_siapa", 0},
	} {
		var out res
		getJSON(t, h, http.MethodPost, "/v1/zone", tc.body, &out)
		out.Meta.metaOut.ValidUntil = out.Meta.ValidUntil
		out.Meta.check(t, tc.where)
		if out.Status != tc.status || len(out.Zones) != tc.zones || (tc.zones == 0) == (out.StatusNote == "") {
			t.Errorf("%s: %+v", tc.where, out)
		}
	}
	for _, tc := range []struct{ q, status string }{
		{"Americana", "en_lista_siapa"},
		{"Zapopan Centro", "sin_zona_en_siapa"},
		{"Tesistan", "sin_zona_en_siapa"},
		{"qqqqzzzz", "sin_resultados"},
	} {
		var out res
		getJSON(t, h, http.MethodPost, "/v1/colonias", `{"q":"`+tc.q+`"}`, &out)
		out.Meta.metaOut.ValidUntil = out.Meta.ValidUntil
		out.Meta.check(t, tc.q)
		if out.Status != tc.status || (tc.status == "en_lista_siapa") != (out.StatusNote == "") {
			t.Errorf("%s: status %q, note %q", tc.q, out.Status, out.StatusNote)
		}
	}
}

func TestColoniasCarryTheMapShares(t *testing.T) {
	h := agentAPI(t).routes()
	var out struct {
		Colonias []struct {
			Name     string
			Zones    []int
			MapZones []int `json:"map_zones"`
			Map      []struct {
				CP          string
				Shares      map[string]int
				ListDiffers bool `json:"list_differs"`
			}
		}
	}
	getJSON(t, h, http.MethodGet, "/v1/colonias?q=americana", "", &out)
	if len(out.Colonias) != 1 {
		t.Fatalf("%+v", out)
	}
	c := out.Colonias[0]
	if !slices.Equal(c.Zones, []int{1, 5, 6}) || !slices.Equal(c.MapZones, []int{1, 5, 6}) || len(c.Map) != 1 || c.Map[0].Shares["1"] != 48 || c.Map[0].Shares["6"] != 20 || c.Map[0].ListDiffers {
		t.Errorf("%+v", c)
	}
	getJSON(t, h, http.MethodGet, "/v1/colonias?q=oblatos", "", &out)
	if len(out.Colonias) == 0 || len(out.Colonias[0].Map) == 0 || !out.Colonias[0].Map[0].ListDiffers {
		t.Errorf("Oblatos's list and map disagree: %+v", out.Colonias)
	}
}

func TestVersionEndpointAndMeta(t *testing.T) {
	version, built = "abc123", "2026-11-02T00:00:00Z"
	defer func() { version, built = "dev", "" }()
	rec := httptest.NewRecorder()
	(&api{}).routes().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/version", nil))
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), `"sha":"abc123"`) || !strings.Contains(rec.Body.String(), `"built":"2026-11-02T00:00:00Z"`) {
		t.Fatalf("got %d %s", rec.Code, rec.Body)
	}
	if m := (&api{}).meta(); m.Version != "abc123" {
		t.Fatalf("meta version %q", m.Version)
	}
}
