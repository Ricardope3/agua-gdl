package tg

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestSend(t *testing.T) {
	var got map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/botSECRET/sendMessage" {
			t.Errorf("path %s", r.URL.Path)
		}
		json.NewDecoder(r.Body).Decode(&got)
		io.WriteString(w, `{"ok":true,"result":{"message_id":42}}`)
	}))
	defer srv.Close()
	c := &Client{BaseURL: srv.URL, Token: "SECRET", HTTP: srv.Client()}
	m := NewHTML(777, "<b>hola</b>")
	m.ReplyMarkup = InlineKeyboard{InlineKeyboard: [][]InlineButton{{{Text: "Baja", CallbackData: "BAJA"}}}}
	id, err := c.Send(context.Background(), m)
	if err != nil || id != 42 {
		t.Fatalf("id=%d err=%v", id, err)
	}
	if got["chat_id"] != float64(777) || got["parse_mode"] != "HTML" || !strings.Contains(mustJSON(got["reply_markup"]), `"callback_data":"BAJA"`) {
		t.Errorf("request: %v", got)
	}
}

func TestErrors(t *testing.T) {
	for _, c := range []struct {
		status                    int
		body                      string
		rejected, gone, permanent bool
		retryAfter                int
	}{
		{403, `{"ok":false,"error_code":403,"description":"Forbidden: bot was blocked by the user"}`, true, true, true, 0},
		{429, `{"ok":false,"error_code":429,"description":"Too Many Requests: retry after 3","parameters":{"retry_after":3}}`, true, false, false, 3},
		{400, `{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}`, true, false, true, 0},
		{502, `{"ok":false,"error_code":502,"description":"Bad Gateway"}`, false, false, false, 0},
	} {
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(c.status)
			io.WriteString(w, c.body)
		}))
		_, err := (&Client{BaseURL: srv.URL, Token: "T", HTTP: srv.Client()}).Send(context.Background(), NewHTML(1, "x"))
		srv.Close()
		var apiErr *APIError
		if !errors.As(err, &apiErr) || apiErr.Rejected() != c.rejected || apiErr.Gone() != c.gone || apiErr.Permanent() != c.permanent || apiErr.RetryAfter != c.retryAfter {
			t.Errorf("%d: %+v", c.status, err)
		}
	}
}

func TestNetworkErrorHidesTheToken(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { time.Sleep(200 * time.Millisecond) }))
	defer srv.Close()
	c := &Client{BaseURL: srv.URL, Token: "123:SECRET", HTTP: &http.Client{Timeout: 10 * time.Millisecond}}
	_, err := c.Send(context.Background(), NewHTML(1, "x"))
	var apiErr *APIError
	var notSent *NotSentError
	if err == nil || errors.As(err, &apiErr) || strings.Contains(err.Error(), "SECRET") {
		t.Fatalf("err=%v", err)
	}
	if errors.As(err, &notSent) {
		t.Fatalf("the request went out before the timeout, so it may have been delivered: %v", err)
	}
}

func TestUnreachableIsNotSent(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr := ln.Addr().String()
	ln.Close() // nobody listens there now
	c := &Client{BaseURL: "http://" + addr, Token: "123:SECRET", HTTP: &http.Client{Timeout: 2 * time.Second}}
	_, err = c.Send(context.Background(), NewHTML(1, "x"))
	var refused interface{ Rejected() bool }
	if err == nil || !errors.As(err, &refused) || !refused.Rejected() || strings.Contains(err.Error(), "SECRET") {
		t.Fatalf("a refused connection sends nothing, so it can be retried: %v", err)
	}
}

func TestValidSecret(t *testing.T) {
	if !ValidSecret("abc", "abc") || ValidSecret("abc", "abd") || ValidSecret("", "") {
		t.Error("secret check")
	}
}

func mustJSON(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}
