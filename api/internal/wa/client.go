package wa

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

type Client struct {
	BaseURL       string // https://graph.facebook.com/<version>
	PhoneNumberID string
	Token         string
	HTTP          *http.Client
}

type APIError struct {
	Status  int
	Code    int
	Message string
}

// Rejected reports that Meta refused the request, so the message was not sent.
func (e *APIError) Rejected() bool { return e.Status >= 400 && e.Status < 500 }

// Gone reports that the recipient can't be reached because they blocked the bot or
// their number left WhatsApp, as Telegram's 403 does: the subscription is an opt-out,
// so the caller forgets it like BAJA instead of retrying forever.
func (e *APIError) Gone() bool {
	if e.Status == http.StatusForbidden {
		return true
	}
	// Meta's undeliverable codes: 131026 (can't deliver, e.g. blocked) and
	// 131047 (re-engagement required), when the request itself was refused.
	// A 429 means throttling, not an opt-out: wait it out.
	return e.Rejected() && e.Status != http.StatusTooManyRequests && (e.Code == 131026 || e.Code == 131047)
}

// Permanent reports errors that retrying won't fix, like a recipient who can't receive messages.
func (e *APIError) Permanent() bool {
	return e.Rejected() && e.Status != 401 && e.Status != 429
}

func (e *APIError) Error() string {
	return fmt.Sprintf("wa: %d (code %d): %.200s", e.Status, e.Code, e.Message)
}

// Send posts a message and returns its WhatsApp message ID (wamid).
func (c *Client) Send(ctx context.Context, m Message) (string, error) {
	body, err := json.Marshal(m)
	if err != nil {
		return "", err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+"/"+c.PhoneNumberID+"/messages", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return "", fmt.Errorf("wa: %w", err)
	}
	defer resp.Body.Close()
	var out struct {
		Messages []struct {
			ID string `json:"id"`
		} `json:"messages"`
		Error *struct {
			Message string `json:"message"`
			Code    int    `json:"code"`
		} `json:"error"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&out); err != nil {
		return "", fmt.Errorf("wa: status %d: %w", resp.StatusCode, err)
	}
	if out.Error != nil {
		return "", &APIError{Status: resp.StatusCode, Code: out.Error.Code, Message: out.Error.Message}
	}
	if resp.StatusCode != http.StatusOK || len(out.Messages) == 0 {
		return "", fmt.Errorf("wa: unexpected status %d", resp.StatusCode)
	}
	return out.Messages[0].ID, nil
}
