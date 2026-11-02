package bot

import (
	"strings"
	"testing"
)

func TestSignatureBindsTheAnswer(t *testing.T) {
	SignButtons("test")
	data := signed("A:2:2026-10-20:no", "chat", "A", 2, "2026-10-20", "no")
	sig := data[strings.LastIndex(data, ":")+1:]
	if !zoneTrusted("chat", "A", 2, "2026-10-20", "no", sig) {
		t.Fatal("the button's own answer must verify")
	}
	if zoneTrusted("chat", "A", 2, "2026-10-20", "si", sig) {
		t.Fatal("a flipped answer must not verify")
	}
	if zoneTrusted("otro", "A", 2, "2026-10-20", "no", sig) {
		t.Fatal("another chat must not verify")
	}
	if zoneTrusted("chat", "R", 2, "2026-10-20", "no", sig) {
		t.Fatal("another kind must not verify")
	}
}
