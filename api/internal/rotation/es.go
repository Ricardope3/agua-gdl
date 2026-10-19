package rotation

import (
	"fmt"
	"strings"
	"time"
)

var weekdayNames = [...]string{"domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"}

var monthNames = [...]string{"", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"}

func WeekdayES(w time.Weekday) string { return weekdayNames[w] }

// DateES formats t as "jueves 15 de octubre".
func DateES(t time.Time) string {
	return fmt.Sprintf("%s %d de %s", weekdayNames[t.Weekday()], t.Day(), monthNames[t.Month()])
}

// DatesES formats days as "martes 20 y miércoles 21 de octubre", naming each month once:
// "viernes 30 de octubre y domingo 1 de noviembre".
func DatesES(days []time.Time) string {
	names := make([]string, len(days))
	for i, d := range days {
		names[i] = DateES(d)
		if i < len(days)-1 && d.Month() == days[i+1].Month() {
			names[i] = fmt.Sprintf("%s %d", weekdayNames[d.Weekday()], d.Day())
		}
	}
	return joinES(names)
}

func joinES(names []string) string {
	if len(names) < 2 {
		return strings.Join(names, "")
	}
	return strings.Join(names[:len(names)-1], ", ") + " y " + names[len(names)-1]
}

// DaysES formats weekdays as "martes, jueves y domingo".
func DaysES(ws []time.Weekday) string {
	names := make([]string, len(ws))
	for i, w := range ws {
		names[i] = weekdayNames[w]
	}
	return joinES(names)
}

// HourES formats a 24-hour clock hour as "8 p. m.".
func HourES(h int) string {
	switch {
	case h == 0:
		return "12 a. m."
	case h < 12:
		return fmt.Sprintf("%d a. m.", h)
	case h == 12:
		return "12 p. m."
	default:
		return fmt.Sprintf("%d p. m.", h-12)
	}
}
