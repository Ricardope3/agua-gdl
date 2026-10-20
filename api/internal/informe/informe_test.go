package informe

import (
	"strings"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
)

var mx, _ = time.LoadLocation("America/Mexico_City")

const colonias = `[["LAS JUNTAS","San Pedro Tlaquepaque","45590","3"],["CHAPALITA","Guadalajara","44500","5,6"]]`

func at(day, hour int) time.Time { return time.Date(2026, 10, day, hour, 0, 0, 0, mx) }

func week(t *testing.T) *Week {
	t.Helper()
	sched, err := rotation.Load(data.Rotation, mx)
	if err != nil {
		t.Fatal(err)
	}
	juntas, chapalita := "LAS JUNTAS|San Pedro Tlaquepaque|45590", "CHAPALITA|Guadalajara|44500"
	reports := []store.WebReport{
		{Colonia: juntas, Status: "sin_agua", At: at(19, 9)},
		{Colonia: juntas, Status: "sin_agua", At: at(19, 21)},
		{Colonia: juntas, Status: "sin_agua", At: at(20, 8)},
		{Colonia: juntas, Status: "sin_agua", At: at(25, 23)},
		{Colonia: juntas, Status: "baja", Turbia: true, At: at(22, 7)},
		{Colonia: chapalita, Status: "con_agua", At: at(21, 12)},
		{Colonia: chapalita, Status: "sin_agua", At: at(26, 0)},               // next week
		{Colonia: "NOWHERE|Zapopan|45000", Status: "sin_agua", At: at(20, 9)}, // not on the map
	}
	day := func(d int) time.Time { return time.Date(2026, 10, d, 0, 0, 0, 0, time.UTC) }
	bot := []store.DayCount{
		{Zone: 3, Day: day(20), Answer: "no", Count: 6},
		{Zone: 3, Day: day(21), Answer: "poca", Count: 2},
		{Zone: 3, Day: day(24), Answer: "si", Count: 2},
		{Zone: 5, Day: day(22), Answer: "no", Count: 1},
		{Zone: 5, Day: day(27), Answer: "no", Count: 30}, // next week
	}
	w, err := Build(at(19, 0), reports, bot, []byte(colonias), sched, 10)
	if err != nil {
		t.Fatal(err)
	}
	return w
}

func TestBuildCountsTheWeekByColonia(t *testing.T) {
	w := week(t)
	if w.Total() != 6 || w.SinAgua != 4 || w.Baja != 1 || w.ConAgua != 1 || w.Turbia != 1 {
		t.Fatalf("totals: %d reports, %d/%d/%d, turbia %d", w.Total(), w.SinAgua, w.Baja, w.ConAgua, w.Turbia)
	}
	if len(w.Colonias) != 2 || w.Colonias[0].Name != "LAS JUNTAS" {
		t.Fatalf("colonias: %+v", w.Colonias)
	}
	// Three days with «sin agua» reports (19, 20 and 25); zone 3 is cut on Wednesday and Saturday.
	if c := w.Colonias[0]; c.DryDays != 3 || c.SinAgua != 4 || c.CutDays != 2 || c.Turbia != 1 {
		t.Errorf("LAS JUNTAS: %+v", c)
	}
	if c := w.Colonias[1]; c.DryDays != 0 || c.ConAgua != 1 || c.SinAgua != 0 || len(c.Zones) != 2 {
		t.Errorf("CHAPALITA: %+v", c)
	}
	if w.LongDry() != 1 {
		t.Errorf("LongDry = %d, want 1", w.LongDry())
	}
	if len(w.Zones) != 2 || !w.Zones[0].Shown || w.Zones[0].No != 6 || w.Zones[1].Shown || w.Zones[1].No != 1 {
		t.Errorf("bot zones: %+v", w.Zones)
	}
}

func TestPageAndCSV(t *testing.T) {
	w := week(t)
	main, err := w.Main()
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"Semana del 19 al 25 de octubre de 2026", "LAS JUNTAS", "En <strong>1 colonia</strong> hubo reportes «sin agua» en más de un día",
		"Zona 3: 6 sin agua, 2 con poca y 2 con agua", "Zona 5: menos de 10 respuestas", `href="/semana/2026-10-19.csv"`} {
		if !strings.Contains(main, want) {
			t.Errorf("page lacks %q", want)
		}
	}
	csv, err := w.CSV()
	if err != nil {
		t.Fatal(err)
	}
	if lines := strings.Split(strings.TrimSpace(string(csv)), "\n"); len(lines) != 3 || !strings.HasPrefix(lines[1], "LAS JUNTAS,San Pedro Tlaquepaque,45590,3,4,1,0,1,0,0,3,2") {
		t.Errorf("csv:\n%s", csv)
	}
}

func TestTitleAcrossMonths(t *testing.T) {
	if got := (&Week{From: at(26, 0)}).Title(); got != "Semana del 26 de octubre al 1 de noviembre de 2026" {
		t.Errorf("Title = %q", got)
	}
}
