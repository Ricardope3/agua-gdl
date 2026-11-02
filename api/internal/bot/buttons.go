package bot

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"slices"
)

// buttonKey signs the answer data in answer buttons, so the bot can tell its own
// buttons from callback data a modified client made up. Without it buttons go unsigned
// and only the subscriber's own zone is believed.
var buttonKey []byte

// SignButtons sets the key for answer buttons from a server secret. Call it once at startup.
func SignButtons(secret string) {
	k := sha256.Sum256([]byte("aguagdl botones " + secret))
	buttonKey = k[:]
}

// signature is a short MAC of a button's chat, kind, zone, date and answer; "" without
// a key. Binding the answer matters: otherwise a modified client could take a signed
// «sí» button and replay it as «no» for the same chat, kind, zone and date.
func signature(chat, kind string, zone int, date, answer string) string {
	if len(buttonKey) == 0 {
		return ""
	}
	m := hmac.New(sha256.New, buttonKey)
	fmt.Fprintf(m, "%s|%s|%d|%s|%s", chat, kind, zone, date, answer)
	return base64.RawURLEncoding.EncodeToString(m.Sum(nil)[:6])
}

// signed appends the signature to a button's callback data.
func signed(data, chat, kind string, zone int, date, answer string) string {
	if sig := signature(chat, kind, zone, date, answer); sig != "" {
		return data + ":" + sig
	}
	return data
}

// zoneTrusted reports whether to believe a button's zone and answer: the zone is the
// subscriber's own (the answer is theirs to give), or the bot signed exactly this
// combination for this chat (a report keeps the zone it was asked about after a zone
// change). Buttons signed before the answer was bound no longer verify: pressing one
// fails closed, and new messages carry new signatures.
func zoneTrusted(chat, kind string, zone int, date, answer, sig string, current ...int) bool {
	if slices.Contains(current, zone) {
		return true
	}
	want := signature(chat, kind, zone, date, answer)
	return sig != "" && want != "" && hmac.Equal([]byte(sig), []byte(want))
}
