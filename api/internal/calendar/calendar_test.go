package calendar

import (
	"bytes"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"aguagdl/api/data"
	"aguagdl/api/internal/rotation"
)

func schedule(t *testing.T) *rotation.Schedule {
	t.Helper()
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		t.Fatal(err)
	}
	s, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		t.Fatal(err)
	}
	return s
}

func TestPublishedCalendarsMatchTheRotation(t *testing.T) {
	s := schedule(t)
	for _, z := range s.Zones() {
		path := filepath.Join("..", "..", "..", "web", "calendario", "zona-"+strconv.Itoa(z)+".ics")
		got, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(got, Zone(s, z)) {
			t.Errorf("%s is out of date: run `go run ./cmd/calendars` from api/", path)
		}
	}
}

func TestZoneSixFirstWeek(t *testing.T) {
	ics := string(Zone(schedule(t), 6))
	for _, want := range []string{"DTSTART;VALUE=DATE:20261016\r\n", "DTSTART;VALUE=DATE:20261019\r\n", "TRIGGER:-PT4H\r\n", "X-WR-CALNAME:Agua GDL · Zona 6\r\n"} {
		if !strings.Contains(ics, want) {
			t.Errorf("missing %q", want)
		}
	}
	if strings.Contains(ics, "DTSTART;VALUE=DATE:20261017\r\n") {
		t.Error("zone 6 has no cut on Saturday 17 Oct")
	}
	for _, l := range strings.Split(ics, "\r\n") {
		if len(l) > 75 {
			t.Errorf("line longer than 75 octets: %q", l)
		}
	}
}

func TestOneAlarmPerRunOfCutDays(t *testing.T) {
	ics := string(Zone(schedule(t), 5))
	tuesday := ics[strings.Index(ics, "DTSTART;VALUE=DATE:20261020\r\n"):]
	tuesday = tuesday[:strings.Index(tuesday, "END:VEVENT")]
	if !strings.Contains(tuesday, "TRIGGER:-PT4H") || !strings.Contains(strings.ReplaceAll(tuesday, "\r\n ", ""), "Mañana martes 20 y miércoles 21 de octubre") {
		t.Errorf("Tuesday's alarm must cover Tuesday and Wednesday:\n%s", tuesday)
	}
	wednesday := ics[strings.Index(ics, "DTSTART;VALUE=DATE:20261021\r\n"):]
	wednesday = wednesday[:strings.Index(wednesday, "END:VEVENT")]
	if strings.Contains(wednesday, "VALARM") {
		t.Errorf("Wednesday continues Tuesday's cut: its alarm would ring in the middle of it:\n%s", wednesday)
	}
}
