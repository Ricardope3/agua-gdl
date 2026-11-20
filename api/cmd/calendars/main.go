// Command calendars writes web/calendario/zona-N.ics from the embedded rotation; run it
// from api/ after changing rotation.json. With -check it instead verifies the published
// files against the rotation and exits 1 on any mismatch, without writing. The check also
// catches files for zones the rotation no longer has, which internal/calendar's test
// doesn't; and it runs without the Go toolchain, so the Pages build can gate on it.
package main

import (
	"bytes"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata"

	"aguagdl/api/data"
	"aguagdl/api/internal/calendar"
	"aguagdl/api/internal/rotation"
)

func main() {
	check := flag.Bool("check", false, "report published calendars that differ from the rotation, or that have no zone in it, without writing")
	flag.Parse()
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		log.Fatal(err)
	}
	s, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		log.Fatal(err)
	}
	dir := filepath.Join("..", "web", "calendario")
	if *check {
		bad, err := staleFiles(dir, s)
		if err != nil {
			log.Fatal(err)
		}
		if len(bad) > 0 {
			for _, b := range bad {
				fmt.Println(b)
			}
			os.Exit(1)
		}
		fmt.Println("web/calendario matches rotation.json")
		return
	}
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

// staleFiles lists published calendars that differ from what the rotation renders now,
// and files whose zone the rotation no longer has (left over after an edit).
func staleFiles(dir string, s *rotation.Schedule) ([]string, error) {
	var bad []string
	live := map[int]bool{}
	for _, z := range s.Zones() {
		live[z] = true
		path := filepath.Join(dir, "zona-"+strconv.Itoa(z)+".ics")
		pub, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		if !bytes.Equal(pub, calendar.Zone(s, z)) {
			bad = append(bad, path+" differs from rotation.json; run `go run ./cmd/calendars` from api/")
		}
	}
	files, err := filepath.Glob(filepath.Join(dir, "zona-*.ics"))
	if err != nil {
		return nil, err
	}
	for _, path := range files {
		z, err := strconv.Atoi(strings.TrimSuffix(strings.TrimPrefix(filepath.Base(path), "zona-"), ".ics"))
		if err != nil || !live[z] {
			bad = append(bad, path+" has no zone in rotation.json; remove it")
		}
	}
	return bad, nil
}
