// Package rotation knows SIAPA's weekly rotation: which zones lose service on which days.
package rotation

import (
	"encoding/json"
	"fmt"
	"slices"
	"strconv"
	"time"
)

const DateLayout = "2006-01-02"

var weekdayKeys = map[string]time.Weekday{
	"sun": time.Sunday, "mon": time.Monday, "tue": time.Tuesday, "wed": time.Wednesday,
	"thu": time.Thursday, "fri": time.Friday, "sat": time.Saturday,
}

type Schedule struct {
	loc   *time.Location
	start time.Time
	end   time.Time
	days  map[int][]time.Weekday
	skip  map[string]bool
	extra map[string]bool
}

type override struct {
	Date string `json:"date"`
	Zone int    `json:"zone"`
}

func Load(raw []byte, loc *time.Location) (*Schedule, error) {
	var f struct {
		Start string              `json:"start"`
		End   string              `json:"end"`
		Zones map[string][]string `json:"zones"`
		Skip  []override          `json:"skip"`
		Extra []override          `json:"extra"`
	}
	if err := json.Unmarshal(raw, &f); err != nil {
		return nil, fmt.Errorf("rotation: %w", err)
	}
	s := &Schedule{loc: loc, days: map[int][]time.Weekday{}, skip: map[string]bool{}, extra: map[string]bool{}}
	var err error
	if s.start, err = time.ParseInLocation(DateLayout, f.Start, loc); err != nil {
		return nil, fmt.Errorf("rotation start: %w", err)
	}
	if f.End != "" {
		if s.end, err = time.ParseInLocation(DateLayout, f.End, loc); err != nil {
			return nil, fmt.Errorf("rotation end: %w", err)
		}
	}
	for k, names := range f.Zones {
		zone, err := strconv.Atoi(k)
		if err != nil {
			return nil, fmt.Errorf("rotation zone %q: %w", k, err)
		}
		for _, n := range names {
			wd, ok := weekdayKeys[n]
			if !ok {
				return nil, fmt.Errorf("rotation zone %d: unknown day %q", zone, n)
			}
			s.days[zone] = append(s.days[zone], wd)
		}
		slices.SortFunc(s.days[zone], func(a, b time.Weekday) int { return isoDay(a) - isoDay(b) })
	}
	for _, list := range []struct {
		items []override
		into  map[string]bool
	}{{f.Skip, s.skip}, {f.Extra, s.extra}} {
		for _, o := range list.items {
			if _, err := time.Parse(DateLayout, o.Date); err != nil {
				return nil, fmt.Errorf("rotation override: %w", err)
			}
			list.into[key(o.Date, o.Zone)] = true
		}
	}
	return s, nil
}

func key(date string, zone int) string { return date + "/" + strconv.Itoa(zone) }

func isoDay(w time.Weekday) int { return (int(w) + 6) % 7 }

func (s *Schedule) Location() *time.Location { return s.loc }

// Day returns midnight of t's calendar day in Guadalajara.
func (s *Schedule) Day(t time.Time) time.Time {
	y, m, d := t.In(s.loc).Date()
	return time.Date(y, m, d, 0, 0, 0, 0, s.loc)
}

func (s *Schedule) ParseDate(v string) (time.Time, error) {
	return time.ParseInLocation(DateLayout, v, s.loc)
}

func (s *Schedule) Zones() []int {
	zones := make([]int, 0, len(s.days))
	for z := range s.days {
		zones = append(zones, z)
	}
	slices.Sort(zones)
	return zones
}

func (s *Schedule) HasZone(zone int) bool {
	_, ok := s.days[zone]
	return ok
}

func (s *Schedule) Weekdays(zone int) []time.Weekday { return s.days[zone] }

func (s *Schedule) IsCut(zone int, t time.Time) bool {
	d := s.Day(t)
	k := key(d.Format(DateLayout), zone)
	if s.extra[k] {
		return true
	}
	if s.skip[k] || d.Before(s.start) || (!s.end.IsZero() && d.After(s.end)) {
		return false
	}
	return slices.Contains(s.days[zone], d.Weekday())
}

func (s *Schedule) ZonesOn(t time.Time) []int {
	var zones []int
	for _, z := range s.Zones() {
		if s.IsCut(z, t) {
			zones = append(zones, z)
		}
	}
	return zones
}

// NextCuts returns up to n cut days for zone, starting with t's day.
func (s *Schedule) NextCuts(zone int, t time.Time, n int) []time.Time {
	var cuts []time.Time
	d := s.Day(t)
	for i := 0; i < 366 && len(cuts) < n; i++ {
		if s.IsCut(zone, d) {
			cuts = append(cuts, d)
		}
		d = d.AddDate(0, 0, 1)
	}
	return cuts
}

// PrevCut returns the last cut day for zone strictly before t's day.
func (s *Schedule) PrevCut(zone int, t time.Time) (time.Time, bool) {
	d := s.Day(t)
	for i := 0; i < 31; i++ {
		d = d.AddDate(0, 0, -1)
		if s.IsCut(zone, d) {
			return d, true
		}
	}
	return time.Time{}, false
}
