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

func TestTemplateUsesBSUID(t *testing.T) {
	m := NewTemplate(Recipient{UserID: "MX.123", Phone: "5213300000000"}, "aviso_corte", "es_MX",
		BodyParams("jueves 15 de octubre", "2"), QuickReply(0, "REPORT:none"), QuickReply(1, "BAJA"))
	b, _ := json.Marshal(m)
	s := string(b)
	for _, want := range []string{`"recipient":"MX.123"`, `"index":"1"`, `"payload":"BAJA"`, `"code":"es_MX"`} {
		if !strings.Contains(s, want) {
			t.Errorf("missing %s in %s", want, s)
		}
	}
	if strings.Contains(s, `"to"`) {
		t.Error("phone must not be sent when a BSUID is known")
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
