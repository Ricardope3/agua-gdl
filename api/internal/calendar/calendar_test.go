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

// The alarms must ring when the bot sends (REMINDER_HOUR, 20 by default; the triggers
// assume 20): 20:00 two days before a block and
// 20:00 the evening before. An all-day event starts at 00:00, so count back from there.
func TestAlarmsRingWhenTheBotSends(t *testing.T) {
	s := schedule(t)
	loc := s.Location()
	ics := strings.ReplaceAll(string(Zone(s, 2)), "\r\n ", "")
	start := strings.Index(ics, "DTSTART;VALUE=DATE:20261018\r\n")
	if start < 0 {
		t.Fatal("zone 2's Sunday 18 Oct event is missing")
	}
	event := ics[start:]
	event = event[:strings.Index(event, "END:VEVENT")]
	day := time.Date(2026, 10, 18, 0, 0, 0, 0, loc)
	want := map[string]time.Time{
		"En dos días": time.Date(2026, 10, 16, 20, 0, 0, 0, loc),
		"Mañana":      time.Date(2026, 10, 17, 20, 0, 0, 0, loc),
	}
	for _, alarm := range strings.Split(event, "BEGIN:VALARM")[1:] {
		var when, trigger string
		for _, l := range strings.Split(alarm, "\r\n") {
			if v, ok := strings.CutPrefix(l, "TRIGGER:"); ok {
				trigger = v
			}
			if v, ok := strings.CutPrefix(l, "DESCRIPTION:"); ok {
				for w := range want {
					if strings.HasPrefix(v, w) {
						when = w
					}
				}
			}
		}
		at, ok := want[when]
		if !ok {
			t.Fatalf("alarm with unexpected description:\n%s", alarm)
		}
		if got := day.Add(-icsDuration(t, trigger)); !got.Equal(at) {
			t.Errorf("«%s» rings %s, the bot sends %s", when, got.Format(time.RFC3339), at.Format(time.RFC3339))
		}
		delete(want, when)
	}
	if len(want) != 0 {
		t.Errorf("missing alarms: %v", want)
	}
}

func icsDuration(t *testing.T, v string) time.Duration {
	t.Helper()
	rest, ok := strings.CutPrefix(v, "-P")
	if !ok {
		t.Fatalf("trigger %q is not a negative duration", v)
	}
	var d time.Duration
	days, clock, _ := strings.Cut(rest, "T")
	if days != "" {
		n, err := strconv.Atoi(strings.TrimSuffix(days, "D"))
		if err != nil {
			t.Fatalf("trigger %q: %v", v, err)
		}
		d += time.Duration(n) * 24 * time.Hour
	}
	if clock != "" {
		n, err := strconv.Atoi(strings.TrimSuffix(clock, "H"))
		if err != nil {
			t.Fatalf("trigger %q: %v", v, err)
		}
		d += time.Duration(n) * time.Hour
	}
	return d
}
