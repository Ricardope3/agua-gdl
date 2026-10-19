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
	zone1 := string(Zone(schedule(t), 1))
	wednesday := event(zone1, "20261021")
	for _, want := range []string{"TRIGGER:-P1DT4H", "TRIGGER:-PT4H", "zona 1: miércoles 21\\, viernes 23 y domingo 25 de octubre"} {
		if !strings.Contains(wednesday, want) {
			t.Errorf("zone 1's Wednesday starts the block; missing %q in:\n%s", want, wednesday)
		}
	}
	for _, date := range []string{"20261023", "20261025"} {
		if e := event(zone1, date); strings.Contains(e, "VALARM") {
			t.Errorf("%s continues the block: an alarm would ring in the middle of it:\n%s", date, e)
		}
	}
}
