package rotation

import (
	"slices"
	"testing"
	"time"

	"aguagdl/api/data"
)

func load(t *testing.T, raw []byte) *Schedule {
	t.Helper()
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		t.Fatal(err)
	}
	s, err := Load(raw, loc)
	if err != nil {
		t.Fatal(err)
	}
	return s
}

func day(s *Schedule, v string) time.Time {
	d, err := s.ParseDate(v)
	if err != nil {
		panic(err)
	}
	return d
}

func TestZonesOn(t *testing.T) {
	s := load(t, data.Rotation)
	cases := map[string][]int{
		"2026-10-14": nil,
		"2026-10-15": {2, 4},
		"2026-10-18": {1, 2, 7},
		"2026-10-19": {4, 6},
		"2026-10-24": {3, 5, 7},
		"2027-04-01": nil,
	}
	for d, want := range cases {
		if got := s.ZonesOn(day(s, d)); !slices.Equal(got, want) {
			t.Errorf("%s: got %v, want %v", d, got, want)
		}
	}
}

func TestNextAndPrevCut(t *testing.T) {
	s := load(t, data.Rotation)
	got := s.NextCuts(4, day(s, "2026-10-13"), 3)
	want := []string{"2026-10-15", "2026-10-19", "2026-10-22"}
	for i, d := range got {
		if d.Format(DateLayout) != want[i] {
			t.Errorf("next[%d] = %s, want %s", i, d.Format(DateLayout), want[i])
		}
	}
	if p, ok := s.PrevCut(4, day(s, "2026-10-19")); !ok || p.Format(DateLayout) != "2026-10-15" {
		t.Errorf("prev = %v %v", p, ok)
	}
	if _, ok := s.PrevCut(4, day(s, "2026-10-15")); ok {
		t.Error("no cut before the rotation starts")
	}
}

func TestOverrides(t *testing.T) {
	s := load(t, []byte(`{"start":"2026-10-15","zones":{"2":["thu"]},
		"skip":[{"date":"2026-10-15","zone":2}],"extra":[{"date":"2026-10-16","zone":2}]}`))
	if s.IsCut(2, day(s, "2026-10-15")) || !s.IsCut(2, day(s, "2026-10-16")) {
		t.Error("overrides not applied")
	}
}

func TestSpanish(t *testing.T) {
	s := load(t, data.Rotation)
	if got := DateES(day(s, "2026-10-15")); got != "jueves 15 de octubre" {
		t.Error(got)
	}
	if got := DaysES(s.Weekdays(2)); got != "martes, jueves y domingo" {
		t.Error(got)
	}
	if got := HourES(20); got != "8 p. m." {
		t.Error(got)
	}
}

func TestExpired(t *testing.T) {
	s := load(t, data.Rotation)
	if s.Expired(day(s, "2027-04-29")) || !s.Expired(day(s, "2027-04-30")) {
		t.Error("subscribers are deleted on the 30th day after the rotation's end (31 Mar 2027)")
	}
	open := load(t, []byte(`{"start": "2026-10-15", "zones": {"1": ["fri"]}}`))
	if open.Expired(day(open, "2030-01-01")) {
		t.Error("without an end date nothing expires")
	}
}

func TestBlocks(t *testing.T) {
	s := load(t, data.Rotation)
	cases := []struct {
		zone       int
		day        string
		start, end bool
		block      string
		first      string
	}{
		{5, "2026-10-20", true, false, "martes 20 y miércoles 21 de octubre", "2026-10-20"},
		{5, "2026-10-21", false, true, "miércoles 21 de octubre", "2026-10-20"},
		{1, "2026-10-16", true, false, "viernes 16 y domingo 18 de octubre", "2026-10-16"},
		{1, "2026-10-21", true, false, "miércoles 21, viernes 23 y domingo 25 de octubre", "2026-10-21"},
		{1, "2026-10-25", false, true, "domingo 25 de octubre", "2026-10-21"},
		{2, "2026-10-18", true, false, "domingo 18, martes 20 y jueves 22 de octubre", "2026-10-18"},
		{2, "2026-10-20", false, false, "martes 20 y jueves 22 de octubre", "2026-10-18"},
		{7, "2026-10-31", true, false, "sábado 31 de octubre y domingo 1 de noviembre", "2026-10-31"},
		{4, "2026-10-19", true, true, "lunes 19 de octubre", "2026-10-19"},
		{4, "2026-10-20", false, false, "", ""},
	}
	for _, c := range cases {
		d := day(s, c.day)
		if got := s.StartsBlock(c.zone, d); got != c.start {
			t.Errorf("zone %d %s: starts a block = %v, want %v", c.zone, c.day, got, c.start)
		}
		if got := s.EndsBlock(c.zone, d); got != c.end {
			t.Errorf("zone %d %s: ends a block = %v, want %v", c.zone, c.day, got, c.end)
		}
		if got := DatesES(s.Block(c.zone, d)); got != c.block {
			t.Errorf("zone %d %s: block %q, want %q", c.zone, c.day, got, c.block)
		}
		first, ok := s.BlockStart(c.zone, d)
		if got := first.Format(DateLayout); ok != (c.first != "") || (ok && got != c.first) {
			t.Errorf("zone %d %s: block starts %s %v, want %q", c.zone, c.day, got, ok, c.first)
		}
	}
}
