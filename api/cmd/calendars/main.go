// Command calendars writes web/calendario/zona-N.ics from the embedded rotation; run it from api/ after changing rotation.json.
package main

import (
	"log"
	"os"
	"path/filepath"
	"strconv"
	"time"
	_ "time/tzdata"

	"aguagdl/api/data"
	"aguagdl/api/internal/calendar"
	"aguagdl/api/internal/rotation"
)

func main() {
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		log.Fatal(err)
	}
	s, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		log.Fatal(err)
	}
	dir := filepath.Join("..", "web", "calendario")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		log.Fatal(err)
	}
	for _, z := range s.Zones() {
		path := filepath.Join(dir, "zona-"+strconv.Itoa(z)+".ics")
		if err := os.WriteFile(path, calendar.Zone(s, z), 0o644); err != nil {
			log.Fatal(err)
		}
		log.Printf("wrote %s", path)
	}
}
