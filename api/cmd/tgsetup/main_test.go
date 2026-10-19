package main

import (
	"encoding/json"
	"io"
	"net/http"
	"path"
	"strings"
	"testing"
)

// telegramAPI answers every Bot API call with an empty success and keeps its parameters.
type telegramAPI map[string]map[string]any

func (calls telegramAPI) RoundTrip(r *http.Request) (*http.Response, error) {
	params := map[string]any{}
	if err := json.NewDecoder(r.Body).Decode(&params); err != nil {
		return nil, err
	}
	calls[path.Base(r.URL.Path)] = params
	return &http.Response{StatusCode: http.StatusOK, Header: http.Header{"Content-Type": {"application/json"}},
		Body: io.NopCloser(strings.NewReader(`{"ok":true,"result":{}}`)), Request: r}, nil
}

func TestRerunsKeepTheUpdatesTelegramHolds(t *testing.T) {
	t.Setenv("TG_TOKEN", "123:test")
	t.Setenv("TG_WEBHOOK_SECRET", "s3cret")
	calls := telegramAPI{}
	transport := http.DefaultTransport
	http.DefaultTransport = calls
	t.Cleanup(func() { http.DefaultTransport = transport })
	for _, drop := range []bool{false, true} {
		if err := run("https://api.test/tg/webhook", drop); err != nil {
			t.Fatal(err)
		}
		if got := calls["setWebhook"]["drop_pending_updates"]; got != drop {
			t.Errorf("-drop-pending=%v: setWebhook sent drop_pending_updates=%v", drop, got)
		}
	}
}
