// Package tg talks to the Telegram Bot API: outgoing messages, webhook updates and the secret check.
package tg

import (
	"bytes"
	"context"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
)

type Client struct {
	BaseURL string // https://api.telegram.org
	Token   string
	HTTP    *http.Client
}

type APIError struct {
	Status      int
	Description string
	RetryAfter  int // seconds, on 429
}

// Rejected reports that Telegram refused the request, so the message was not sent.
func (e *APIError) Rejected() bool { return e.Status >= 400 && e.Status < 500 }

// Gone reports a chat the bot can never write to again, e.g. the user blocked it.
func (e *APIError) Gone() bool { return e.Status == http.StatusForbidden }

// Permanent reports errors that retrying won't fix.
func (e *APIError) Permanent() bool {
	return e.Rejected() && e.Status != http.StatusUnauthorized && e.Status != http.StatusTooManyRequests
}

func (e *APIError) Error() string { return fmt.Sprintf("tg: %d: %.200s", e.Status, e.Description) }

// Call invokes a Bot API method and decodes its result into out, if given.
func (c *Client) Call(ctx context.Context, method string, params, out any) error {
	body, err := json.Marshal(params)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+"/bot"+c.Token+"/"+method, bytes.NewReader(body))
	if err != nil {
		return errors.New("tg: bad request URL") // the URL holds the token: never echo it
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.HTTP.Do(req)
	if err != nil {
		var ue *url.Error
		if errors.As(err, &ue) {
			err = ue.Err
		}
		return fmt.Errorf("tg: %s: %w", method, err)
	}
	defer resp.Body.Close()
	var r struct {
		OK          bool            `json:"ok"`
		Result      json.RawMessage `json:"result"`
		Description string          `json:"description"`
		Parameters  struct {
			RetryAfter int `json:"retry_after"`
		} `json:"parameters"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&r); err != nil {
		return fmt.Errorf("tg: %s: status %d: %w", method, resp.StatusCode, err)
	}
	if !r.OK || resp.StatusCode != http.StatusOK {
		return &APIError{Status: resp.StatusCode, Description: r.Description, RetryAfter: r.Parameters.RetryAfter}
	}
	if out == nil {
		return nil
	}
	return json.Unmarshal(r.Result, out)
}

// Send posts a message and returns its ID within the chat.
func (c *Client) Send(ctx context.Context, m Message) (int64, error) {
	var sent struct {
		MessageID int64 `json:"message_id"`
	}
	err := c.Call(ctx, "sendMessage", m, &sent)
	return sent.MessageID, err
}

// AnswerCallback stops the spinner Telegram shows on a pressed button.
func (c *Client) AnswerCallback(ctx context.Context, id string) error {
	return c.Call(ctx, "answerCallbackQuery", map[string]string{"callback_query_id": id}, nil)
}

// ValidSecret checks the X-Telegram-Bot-Api-Secret-Token header set with setWebhook.
func ValidSecret(secret, header string) bool {
	return secret != "" && subtle.ConstantTimeCompare([]byte(secret), []byte(header)) == 1
}
