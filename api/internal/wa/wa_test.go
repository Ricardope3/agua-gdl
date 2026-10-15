package wa

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"strings"
	"testing"
)

func TestValidSignature(t *testing.T) {
	secret, body := []byte("s3cret"), []byte(`{"object":"whatsapp_business_account"}`)
	mac := hmac.New(sha256.New, secret)
	mac.Write(body)
	good := "sha256=" + hex.EncodeToString(mac.Sum(nil))
	if !ValidSignature(secret, body, good) {
		t.Error("valid signature rejected")
	}
	if ValidSignature(secret, body, "sha256=00") || ValidSignature(secret, body, "") {
		t.Error("bad signature accepted")
	}
}

func TestTemplateRecipient(t *testing.T) {
	m := NewTemplate(Recipient{UserID: "MX.123", Phone: "5213300000000"}, "aviso_corte", "es_MX",
		BodyParams("jueves 15 de octubre", "2"), QuickReply(0, "BAJA"))
	b, _ := json.Marshal(m)
	s := string(b)
	for _, want := range []string{`"to":"5213300000000"`, `"index":"0"`, `"payload":"BAJA"`, `"code":"es_MX"`} {
		if !strings.Contains(s, want) {
			t.Errorf("missing %s in %s", want, s)
		}
	}
	if strings.Contains(s, `"recipient"`) {
		t.Error("send to the phone number while BSUID sending is unconfirmed")
	}
	if b, _ := json.Marshal(NewText(Recipient{UserID: "MX.9"}, "x")); !strings.Contains(string(b), `"recipient":"MX.9"`) {
		t.Error("fall back to the BSUID when there is no phone")
	}
}

func TestListTruncates(t *testing.T) {
	m := NewList(Recipient{UserID: "MX.1"}, "body", "Elegir una opción larga", []Row{{ID: "a", Title: "FRACCIONAMIENTO JARDINES DEL SAUZ"}})
	if got := []rune(m.Interactive.Action.Sections[0].Rows[0].Title); len(got) != 24 {
		t.Errorf("title not truncated: %d", len(got))
	}
	if got := []rune(m.Interactive.Action.Button); len(got) != 20 {
		t.Errorf("button not truncated: %d", len(got))
	}
}

func TestAPIErrorTruncatesMetaMessage(t *testing.T) {
	err := &APIError{Status: 400, Code: 100, Message: strings.Repeat("x", 5000)}
	if n := len(err.Error()); n > 250 {
		t.Errorf("error is %d bytes; Meta's message must be cut before it reaches the logs", n)
	}
}
