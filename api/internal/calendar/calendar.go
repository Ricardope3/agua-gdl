// Package calendar renders each zone's rationing days as an iCalendar feed people can subscribe to.
package calendar

import (
	"fmt"
	"strings"

	"aguagdl/api/internal/rotation"
)

const mapURL = "https://rotaciondeserviciosiapa.jalisco.gob.mx/"

// Zone returns the feed for one zone: an all-day event per rationing day, with an alert at 8 p.m. the evening
// before each run of consecutive days (one on the evening of a cut day would come too late).
func Zone(s *rotation.Schedule, zone int) []byte {
	start, end := s.Span()
	if end.IsZero() {
		end = start.AddDate(1, 0, 0)
	}
	var b strings.Builder
	line := func(format string, args ...any) { b.WriteString(fold(fmt.Sprintf(format, args...))) }
	line("BEGIN:VCALENDAR")
	line("VERSION:2.0")
	line("PRODID:-//Agua GDL//Rotación del SIAPA//ES")
	line("CALSCALE:GREGORIAN")
	line("METHOD:PUBLISH")
	line("X-WR-CALNAME:Agua GDL · Zona %d", zone)
	line("X-WR-CALDESC:%s", escape(fmt.Sprintf("Días de racionamiento de la zona %d según el calendario del SIAPA. Agua GDL es una iniciativa ciudadana, no oficial.", zone)))
	line("X-WR-TIMEZONE:America/Mexico_City")
	line("REFRESH-INTERVAL;VALUE=DURATION:PT12H")
	line("X-PUBLISHED-TTL:PT12H")
	stamp := start.UTC().Format("20060102T150405Z")
	for d := start.AddDate(0, 0, -7); !d.After(end.AddDate(0, 0, 7)); d = d.AddDate(0, 0, 1) {
		if !s.IsCut(zone, d) {
			continue
		}
		line("BEGIN:VEVENT")
		line("UID:zona-%d-%s@aguagdl.com", zone, d.Format("20060102"))
		line("DTSTAMP:%s", stamp)
		line("DTSTART;VALUE=DATE:%s", d.Format("20060102"))
		line("DTEND;VALUE=DATE:%s", d.AddDate(0, 0, 1).Format("20060102"))
		line("SUMMARY:%s", escape(fmt.Sprintf("💧 Racionamiento de agua · Zona %d", zone)))
		line("DESCRIPTION:%s", escape("Corte según el calendario del SIAPA. El SIAPA dice que solo baja la presión y por un día; vecinos nos cuentan que el agua se va desde antes y tarda más en volver. Llena tu tinaco con tiempo. Mapa oficial: "+mapURL+" · Agua GDL (no oficial): https://aguagdl.com"))
		line("URL:%s", mapURL)
		line("TRANSP:TRANSPARENT")
		if s.StartsRun(zone, d) {
			line("BEGIN:VALARM")
			line("ACTION:DISPLAY")
			line("DESCRIPTION:%s", escape(fmt.Sprintf("Mañana %s hay racionamiento de agua en la zona %d", rotation.DatesES(s.Run(zone, d)), zone)))
			line("TRIGGER:-PT4H")
			line("END:VALARM")
		}
		line("END:VEVENT")
	}
	line("END:VCALENDAR")
	return []byte(b.String())
}

func escape(v string) string {
	return strings.NewReplacer(`\`, `\\`, ";", `\;`, ",", `\,`, "\n", `\n`).Replace(v)
}

// fold splits a content line into 75-octet pieces without breaking a UTF-8 character, ending each with CRLF.
func fold(v string) string {
	var b strings.Builder
	n := 0
	for _, r := range v {
		size := len(string(r))
		if n+size > 75 {
			b.WriteString("\r\n ")
			n = 1
		}
		b.WriteRune(r)
		n += size
	}
	b.WriteString("\r\n")
	return b.String()
}
