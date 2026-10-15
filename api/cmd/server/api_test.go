package main

import (
	"bytes"
	"context"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/geo"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
)

func TestV1ErrorsAllowAnyOrigin(t *testing.T) {
	h := (&api{}).routes()
	for _, path := range []string{"/v1/zone?lat=x", "/v1/colonias?q=a", "/v1/nope"} {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
		if rec.Code < 400 || rec.Header().Get("Access-Control-Allow-Origin") != "*" {
			t.Errorf("%s: status %d, allow-origin %q", path, rec.Code, rec.Header().Get("Access-Control-Allow-Origin"))
		}
	}
}

func TestWebhookVerifyEchoesChallengeAsPlainText(t *testing.T) {
	h := (&api{verifyToken: "tok"}).routes()
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
