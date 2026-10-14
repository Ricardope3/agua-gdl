package main

import (
	"net/http"
	"net/http/httptest"
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
