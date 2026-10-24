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

func TestAlarmsOnlyBeforeEachBlock(t *testing.T) {
	event := func(ics, date string) string {
		e := ics[strings.Index(ics, "DTSTART;VALUE=DATE:"+date+"\r\n"):]
		return strings.ReplaceAll(e[:strings.Index(e, "END:VEVENT")], "\r\n ", "")
	}
	zone2 := string(Zone(schedule(t), 2))
	sunday := event(zone2, "20261018")
	for _, want := range []string{"TRIGGER:-P1DT4H", "TRIGGER:-PT4H", "zona 2: domingo 18\\, martes 20 y jueves 22 de octubre"} {
		if !strings.Contains(sunday, want) {
			t.Errorf("zone 2's Sunday starts the block; missing %q in:\n%s", want, sunday)
		}
	}
	for _, date := range []string{"20261020", "20261022"} {
		if e := event(zone2, date); strings.Contains(e, "VALARM") {
			t.Errorf("%s continues the block: an alarm would ring in the middle of it:\n%s", date, e)
		}
	}
}
