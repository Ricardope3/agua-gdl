package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
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
