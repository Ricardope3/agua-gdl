package wa

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
)

// ValidSignature checks Meta's X-Hub-Signature-256 header against the app secret.
func ValidSignature(secret, body []byte, header string) bool {
	mac := hmac.New(sha256.New, secret)
	mac.Write(body)
	want := "sha256=" + hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(want), []byte(header))
}

type Payload struct {
	Object string  `json:"object"`
	Entry  []Entry `json:"entry"`
}

type Entry struct {
	ID      string   `json:"id"`
	Changes []Change `json:"changes"`
}

type Change struct {
	Field string `json:"field"`
	Value Value  `json:"value"`
}

type Value struct {
	Metadata Metadata  `json:"metadata"`
	Contacts []Contact `json:"contacts"`
	Messages []Inbound `json:"messages"`
	Statuses []Status  `json:"statuses"`
}

type Metadata struct {
	PhoneNumberID string `json:"phone_number_id"`
}

type Contact struct {
	WaID   string `json:"wa_id"`
	UserID string `json:"user_id"`
}

type Inbound struct {
	ID          string           `json:"id"`
	From        string           `json:"from"`
	FromUserID  string           `json:"from_user_id"`
	Type        string           `json:"type"`
	Text        *InboundText     `json:"text,omitempty"`
	Location    *Location        `json:"location,omitempty"`
	Button      *Button          `json:"button,omitempty"`
	Interactive *InboundInteract `json:"interactive,omitempty"`
	System      *System          `json:"system,omitempty"`
}

// System reports a user's new phone number or business-scoped user ID.
type System struct {
	Type           string `json:"type"`  // user_changed_number or user_changed_user_id
	WaID           string `json:"wa_id"` // the new phone number, omitted when Meta can't share it
	UserID         string `json:"user_id"`
	PreviousUserID string `json:"previous_user_id"`
}

type InboundText struct {
	Body string `json:"body"`
}

type Location struct {
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
}

type Button struct {
	Payload string `json:"payload"`
	Text    string `json:"text"`
}

type InboundInteract struct {
	Type        string `json:"type"`
	ListReply   *Reply `json:"list_reply,omitempty"`
	ButtonReply *Reply `json:"button_reply,omitempty"`
}

type Reply struct {
	ID    string `json:"id"`
	Title string `json:"title"`
}

type Status struct {
	ID     string `json:"id"`
	Status string `json:"status"`
	Errors []struct {
		Code  int    `json:"code"`
		Title string `json:"title"`
	} `json:"errors"`
}
