// Command informe writes the week's count of neighbours' reports, Monday to Sunday, to
// web/semana/<Monday>.html and .csv, lists it on web/informes.html, and prints the email that
// goes with it to SIAPA, the CEA, the municipios, the Congreso and the CEDHJ. It only reads the
// database. Run it from api/ on Mondays, then review, commit and push:
//
//	DATABASE_URL='…' go run ./cmd/informe              # last week
//	DATABASE_URL='…' go run ./cmd/informe -week 2026-10-19
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"html"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"
	"time"
	_ "time/tzdata"

	"aguagdl/api/data"
	"aguagdl/api/internal/informe"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
)

func main() {
	week := flag.String("week", "", "Monday of the week to count, YYYY-MM-DD (default: last week)")
	web := flag.String("web", "../web", "the site's directory")
	min := flag.Int("min", 10, "fewest bot answers in a zone before its split shows (MIN_REPORTS_SHOWN)")
	flag.Parse()
	if err := run(context.Background(), *week, *web, *min, time.Now()); err != nil {
		log.Fatal(err)
	}
}

func run(ctx context.Context, week, web string, min int, now time.Time) error {
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		return err
	}
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		return err
	}
	from, err := monday(week, now.In(loc))
	if err != nil {
		return err
	}
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		return errors.New("set DATABASE_URL")
	}
	db, err := store.Open(ctx, url)
	if err != nil {
		return err
	}
	defer db.Close()
	reports, err := db.WebReportsSince(ctx, from)
	if err != nil {
		return err
	}
	bot, err := db.BotAnswersByDay(ctx, from)
	if err != nil {
		return err
	}
	w, err := informe.Build(from, reports, bot, data.ColoniasMapa, sched, min)
	if err != nil {
		return err
	}
	if err := write(w, web); err != nil {
		return err
	}
	fmt.Print(email(w))
	return nil
}

// monday parses -week, which must be a Monday, or picks the Monday before this week's.
func monday(week string, now time.Time) (time.Time, error) {
	if week == "" {
		d := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
		return d.AddDate(0, 0, -(int(d.Weekday())+6)%7-7), nil
	}
	d, err := time.ParseInLocation(time.DateOnly, week, now.Location())
	if err != nil {
		return time.Time{}, err
	}
	if d.Weekday() != time.Monday {
		return time.Time{}, fmt.Errorf("%s is a %s, not a Monday", week, d.Weekday())
	}
	return d, nil
}

var listed = regexp.MustCompile(`(?s)<!--INFORMES-->.*<!--/INFORMES-->`)

// write builds the week's page from informes.html's head, menu and footer, and relists the weeks.
func write(w *informe.Week, web string) error {
	index := filepath.Join(web, "informes.html")
	raw, err := os.ReadFile(index)
	if err != nil {
		return err
	}
	shell := string(raw)
	i, j := strings.Index(shell, "  <main>"), strings.Index(shell, "  <footer>")
	if i < 0 || j < 0 || !listed.MatchString(shell) {
		return errors.New("informes.html lost its <main>, <footer> or <!--INFORMES--> markers")
	}
	main, err := w.Main()
	if err != nil {
		return err
	}
	title := html.EscapeString(w.Title())
	head := strings.NewReplacer(
		"<title>El conteo de cada semana · Agua GDL</title>", "<title>"+title+" · Agua GDL</title>",
		`href="https://aguagdl.com/informes"`, `href="https://aguagdl.com/semana/`+w.ID()+`"`,
		`content="https://aguagdl.com/informes"`, `content="https://aguagdl.com/semana/`+w.ID()+`"`,
		`<meta property="og:title" content="El conteo de cada semana">`, `<meta property="og:title" content="`+title+`">`,
	).Replace(shell[:i])
	dir := filepath.Join(web, "semana")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, w.ID()+".html"), []byte(head+main+"\n"+shell[j:]), 0o644); err != nil {
		return err
	}
	csv, err := w.CSV()
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, w.ID()+".csv"), csv, 0o644); err != nil {
		return err
	}
	pages, err := filepath.Glob(filepath.Join(dir, "*.html"))
	if err != nil {
		return err
	}
	slices.Sort(pages)
	slices.Reverse(pages)
	var items strings.Builder
	for _, p := range pages {
		id := strings.TrimSuffix(filepath.Base(p), ".html")
		d, err := time.Parse(time.DateOnly, id)
		if err != nil {
			continue
		}
		fmt.Fprintf(&items, "        <li><a href=\"/semana/%s\">%s</a></li>\n", id, html.EscapeString((&informe.Week{From: d}).Title()))
	}
	shell = listed.ReplaceAllLiteralString(shell, "<!--INFORMES-->\n"+items.String()+"        <!--/INFORMES-->")
	return os.WriteFile(index, []byte(shell), 0o644)
}

// email is the week's message, for the maintainer to send from soporte@aguagdl.com.
func email(w *informe.Week) string {
	var b strings.Builder
	fmt.Fprintf(&b, "Asunto: Reportes de vecinos sobre el agua, %s\n\n", strings.ToLower(w.Title()[:1])+w.Title()[1:])
	b.WriteString("Buenos días:\n\nSomos Agua GDL (aguagdl.com), una iniciativa ciudadana sin partido. Cada semana contamos los reportes que los vecinos hacen en nuestro mapa sobre el agua en su colonia.\n\n")
	if t := w.Total(); t > 0 {
		fmt.Fprintf(&b, "Esa semana llegaron %d reportes de %d colonias: %d sin agua, %d con poca presión y %d con agua.",
			t, len(w.Colonias), w.SinAgua, w.Baja, w.ConAgua)
		if n := w.LongDry(); n > 0 {
			fmt.Fprintf(&b, " En %d colonias hubo reportes «sin agua» en más de un día, aunque el SIAPA anunció racionamientos «por máximo un día».", n)
		}
		b.WriteString("\n\n")
	} else {
		b.WriteString("Esta semana no llegaron reportes a nuestro mapa.\n\n")
	}
	fmt.Fprintf(&b, "El conteo completo, colonia por colonia, está en https://aguagdl.com/semana/%s\n\n", w.ID())
	b.WriteString("Les pedimos que atiendan las colonias de la lista y que publiquen cuánta agua llega a cada zona y a qué horas.\n\nAtentamente,\nRicardo Espinoza\nAgua GDL\n")
	return b.String()
}
