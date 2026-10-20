package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"aguagdl/api/internal/informe"
)

var mx, _ = time.LoadLocation("America/Mexico_City")

func date(s string) time.Time {
	d, _ := time.ParseInLocation(time.DateOnly, s, mx)
	return d
}

func TestMondayPicksTheLastWholeWeek(t *testing.T) {
	for now, want := range map[string]string{"2026-10-20": "2026-10-12", "2026-10-25": "2026-10-12", "2026-10-26": "2026-10-19"} {
		got, err := monday("", date(now).Add(15*time.Hour))
		if err != nil || got.Format(time.DateOnly) != want {
			t.Errorf("on %s: %v, %v; want %s", now, got, err, want)
		}
	}
	if _, err := monday("2026-10-20", date("2026-10-27")); err == nil {
		t.Error("-week took a Tuesday")
	}
}

func TestWriteListsEachWeekNewestFirst(t *testing.T) {
	dir := t.TempDir()
	shell := "<html><head><title>El conteo de cada semana · Agua GDL</title>\n<link rel=\"canonical\" href=\"https://aguagdl.com/informes\">\n</head><body>\n" +
		"  <main>\n<ul>\n<!--INFORMES-->\n<li>Pronto</li>\n<!--/INFORMES-->\n</ul>\n  </main>\n  <footer>Pie</footer>\n</body></html>\n"
	if err := os.WriteFile(filepath.Join(dir, "informes.html"), []byte(shell), 0o644); err != nil {
		t.Fatal(err)
	}
	for _, d := range []string{"2026-10-19", "2026-10-26"} {
		if err := write(&informe.Week{From: date(d), Min: 10}, dir); err != nil {
			t.Fatal(err)
		}
	}
	page, err := os.ReadFile(filepath.Join(dir, "semana", "2026-10-19.html"))
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"<title>Semana del 19 al 25 de octubre de 2026 · Agua GDL</title>", `href="https://aguagdl.com/semana/2026-10-19"`, "Esta semana no llegaron reportes", "<footer>Pie</footer>"} {
		if !strings.Contains(string(page), want) {
			t.Errorf("week page lacks %q", want)
		}
	}
	index, err := os.ReadFile(filepath.Join(dir, "informes.html"))
	if err != nil {
		t.Fatal(err)
	}
	i := strings.Index(string(index), `<a href="/semana/2026-10-26">Semana del 26 de octubre al 1 de noviembre de 2026</a>`)
	j := strings.Index(string(index), `<a href="/semana/2026-10-19">Semana del 19 al 25 de octubre de 2026</a>`)
	if i < 0 || j < 0 || i > j || strings.Contains(string(index), "Pronto") {
		t.Errorf("informes.html lists:\n%s", index)
	}
	if got := email(&informe.Week{From: date("2026-10-19")}); !strings.HasPrefix(got, "Asunto: Reportes de vecinos sobre el agua, semana del 19 al 25 de octubre de 2026") {
		t.Errorf("email starts %q", got[:80])
	}
}
