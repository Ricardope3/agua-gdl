// Package informe counts a week of neighbours' reports, Monday to Sunday, for the weekly count
// published on /informes and sent to SIAPA, the CEA, the municipios, the Congreso and the CEDHJ.
package informe

import (
	"bytes"
	"cmp"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"html/template"
	"slices"
	"strconv"
	"strings"
	"time"

	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
)

// Colonia is one colonia's reports in the week.
type Colonia struct {
	Name, Municipio, CP     string
	Zones                   []int
	SinAgua, Baja, ConAgua  int
	Turbia, Olor, Sedimento int
	DryDays                 int // local days with at least one «sin agua» report
	CutDays                 int // cut days SIAPA's calendar gave its main zone that week
}

func (c Colonia) total() int { return c.SinAgua + c.Baja + c.ConAgua }

// Zone is the bot's answers in one zone; the split shows only from Min answers.
type Zone struct {
	Zone         int
	No, Poca, Si int
	Shown        bool
}

// Week is the count for the seven days from From.
type Week struct {
	From                    time.Time
	Colonias                []Colonia
	Zones                   []Zone
	SinAgua, Baja, ConAgua  int
	Turbia, Olor, Sedimento int
	Min                     int
}

// Build counts the reports and the bot's answers that fall in the week starting at from, a
// local midnight. coloniasMapa is api/data/colonias_mapa.json.
func Build(from time.Time, reports []store.WebReport, bot []store.DayCount, coloniasMapa []byte, sched *rotation.Schedule, min int) (*Week, error) {
	var rows [][4]string
	if err := json.Unmarshal(coloniasMapa, &rows); err != nil {
		return nil, fmt.Errorf("colonias_mapa.json: %w", err)
	}
	known := make(map[string][4]string, len(rows))
	for _, r := range rows {
		known[r[0]+"|"+r[1]+"|"+r[2]] = r
	}
	loc := from.Location()
	to := from.AddDate(0, 0, 7)
	w := &Week{From: from, Min: min}
	byKey := map[string]*Colonia{}
	dry := map[string]map[string]bool{}
	for _, r := range reports {
		if r.At.Before(from) || !r.At.Before(to) {
			continue
		}
		c := byKey[r.Colonia]
		if c == nil {
			row, ok := known[r.Colonia]
			if !ok {
				continue
			}
			c = &Colonia{Name: row[0], Municipio: row[1], CP: row[2], Zones: zones(row[3])}
			if len(c.Zones) > 0 && sched.HasZone(c.Zones[0]) {
				for d := from; d.Before(to); d = d.AddDate(0, 0, 1) {
					if sched.IsCut(c.Zones[0], d) {
						c.CutDays++
					}
				}
			}
			byKey[r.Colonia] = c
			dry[r.Colonia] = map[string]bool{}
		}
		switch r.Status {
		case "sin_agua":
			c.SinAgua++
			w.SinAgua++
			dry[r.Colonia][r.At.In(loc).Format(time.DateOnly)] = true
		case "baja":
			c.Baja++
			w.Baja++
		case "con_agua":
			c.ConAgua++
			w.ConAgua++
		}
		c.Turbia, w.Turbia = c.Turbia+b2i(r.Turbia), w.Turbia+b2i(r.Turbia)
		c.Olor, w.Olor = c.Olor+b2i(r.Olor), w.Olor+b2i(r.Olor)
		c.Sedimento, w.Sedimento = c.Sedimento+b2i(r.Sedimento), w.Sedimento+b2i(r.Sedimento)
	}
	for key, c := range byKey {
		c.DryDays = len(dry[key])
		w.Colonias = append(w.Colonias, *c)
	}
	slices.SortFunc(w.Colonias, func(a, b Colonia) int {
		return cmp.Or(cmp.Compare(b.DryDays, a.DryDays), cmp.Compare(b.SinAgua, a.SinAgua),
			cmp.Compare(b.total(), a.total()), cmp.Compare(a.Name, b.Name), cmp.Compare(a.Municipio, b.Municipio))
	})
	first, last := from.Format(time.DateOnly), to.AddDate(0, 0, -1).Format(time.DateOnly)
	byZone := map[int]*Zone{}
	for _, d := range bot {
		if day := d.Day.Format(time.DateOnly); day < first || day > last {
			continue
		}
		z := byZone[d.Zone]
		if z == nil {
			z = &Zone{Zone: d.Zone}
			byZone[d.Zone] = z
		}
		// The same answers as the map's: «no» and «no regresó» are without water.
		switch d.Answer {
		case "no", "no_regreso":
			z.No += d.Count
		case "poca":
			z.Poca += d.Count
		case "si", "normal", "turbia":
			z.Si += d.Count
		}
	}
	for _, z := range byZone {
		z.Shown = z.No+z.Poca+z.Si >= min
		w.Zones = append(w.Zones, *z)
	}
	slices.SortFunc(w.Zones, func(a, b Zone) int { return cmp.Compare(a.Zone, b.Zone) })
	return w, nil
}

func zones(s string) []int {
	var zs []int
	for f := range strings.SplitSeq(s, ",") {
		if z, err := strconv.Atoi(strings.TrimSpace(f)); err == nil {
			zs = append(zs, z)
		}
	}
	return zs
}

func b2i(b bool) int {
	if b {
		return 1
	}
	return 0
}

// Total counts the week's reports from the map.
func (w *Week) Total() int { return w.SinAgua + w.Baja + w.ConAgua }

// ID names the week's files: the Monday's date.
func (w *Week) ID() string { return w.From.Format(time.DateOnly) }

// Title reads «Semana del 19 al 25 de octubre de 2026».
func (w *Week) Title() string {
	last := w.From.AddDate(0, 0, 6)
	if last.Month() == w.From.Month() {
		return fmt.Sprintf("Semana del %d al %d de %s de %d", w.From.Day(), last.Day(), months[last.Month()-1], last.Year())
	}
	if last.Year() == w.From.Year() {
		return fmt.Sprintf("Semana del %d de %s al %d de %s de %d", w.From.Day(), months[w.From.Month()-1], last.Day(), months[last.Month()-1], last.Year())
	}
	return fmt.Sprintf("Semana del %d de %s de %d al %d de %s de %d", w.From.Day(), months[w.From.Month()-1], w.From.Year(), last.Day(), months[last.Month()-1], last.Year())
}

var months = [...]string{"enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"}

// LongDry counts the colonias with «sin agua» reports on more days than SIAPA's one a cut.
func (w *Week) LongDry() int {
	n := 0
	for _, c := range w.Colonias {
		if c.DryDays > 1 {
			n++
		}
	}
	return n
}

func pct(n, total int) int {
	if total == 0 {
		return 0
	}
	return (200*n + total) / (2 * total)
}

// CSV is one row per colonia, for whoever wants to check or reuse the count.
func (w *Week) CSV() ([]byte, error) {
	var b bytes.Buffer
	cw := csv.NewWriter(&b)
	_ = cw.Write([]string{"colonia", "municipio", "cp", "zonas", "sin_agua", "baja_presion", "con_agua", "turbia", "olor", "sedimento", "dias_con_reportes_sin_agua", "dias_de_corte_del_siapa"})
	for _, c := range w.Colonias {
		zs := make([]string, len(c.Zones))
		for i, z := range c.Zones {
			zs[i] = strconv.Itoa(z)
		}
		_ = cw.Write([]string{c.Name, c.Municipio, c.CP, strings.Join(zs, " "), strconv.Itoa(c.SinAgua), strconv.Itoa(c.Baja), strconv.Itoa(c.ConAgua),
			strconv.Itoa(c.Turbia), strconv.Itoa(c.Olor), strconv.Itoa(c.Sedimento), strconv.Itoa(c.DryDays), strconv.Itoa(c.CutDays)})
	}
	cw.Flush()
	return b.Bytes(), cw.Error()
}

// Main renders the page's <main>.
func (w *Week) Main() (string, error) {
	var b strings.Builder
	err := page.Execute(&b, w)
	return b.String(), err
}

var page = template.Must(template.New("week").Funcs(template.FuncMap{
	"pct": pct,
	"zones": func(zs []int) string {
		s := make([]string, len(zs))
		for i, z := range zs {
			s[i] = strconv.Itoa(z)
		}
		return strings.Join(s, " y ")
	},
	"plural": func(n int, one, many string) string {
		if n == 1 {
			return one
		}
		return many
	},
}).Parse(`  <main>
    <p class="crumbs"><a href="/informes">El conteo de cada semana</a></p>
    <h1>{{.Title}}</h1>
{{- if .Total}}
    <p class="lede">Llegaron <strong>{{.Total}} {{plural .Total "reporte" "reportes"}}</strong> de vecinos de {{len .Colonias}} {{plural (len .Colonias) "colonia" "colonias"}}: {{pct .SinAgua .Total}} % sin agua, {{pct .Baja .Total}} % con poca presión y {{pct .ConAgua .Total}} % con agua.{{if .LongDry}} En <strong>{{.LongDry}} {{plural .LongDry "colonia" "colonias"}}</strong> hubo reportes «sin agua» en más de un día.{{end}} El <a href="https://rotaciondeserviciosiapa.jalisco.gob.mx/" rel="noopener">SIAPA</a> anunció racionamientos «por máximo un día» y dijo: «No serán cortes totales».</p>
    <div class="table-wrap">
      <table>
        <thead><tr><th scope="col">Colonia</th><th scope="col">Zona</th><th scope="col">Sin agua</th><th scope="col">Poca presión</th><th scope="col">Con agua</th><th scope="col">Días con reportes «sin agua»</th><th scope="col">Días de corte según el SIAPA</th></tr></thead>
        <tbody>
{{- range .Colonias}}
          <tr><th scope="row">{{.Name}}<small>{{.Municipio}}{{if .CP}} · C.P. {{.CP}}{{end}}{{if or .Turbia .Olor .Sedimento}} · {{if .Turbia}}turbia {{.Turbia}} {{end}}{{if .Olor}}olor {{.Olor}} {{end}}{{if .Sedimento}}sedimento {{.Sedimento}}{{end}}{{end}}</small></th><td>{{zones .Zones}}</td><td>{{.SinAgua}}</td><td>{{.Baja}}</td><td>{{.ConAgua}}</td><td>{{.DryDays}}</td><td>{{.CutDays}}</td></tr>
{{- end}}
        </tbody>
      </table>
    </div>
    <p class="via">{{if or .Turbia .Olor .Sedimento}}También {{.Turbia}} {{plural .Turbia "reporte dijo" "reportes dijeron"}} que el agua llegó turbia, {{.Olor}} con olor y {{.Sedimento}} con sedimento. {{end}}<a href="/semana/{{.ID}}.csv">Descarga los datos (CSV)</a>.</p>
{{- else}}
    <p class="lede">Esta semana no llegaron reportes al <a href="/reportes">mapa</a>. El <a href="https://rotaciondeserviciosiapa.jalisco.gob.mx/" rel="noopener">SIAPA</a> anunció racionamientos «por máximo un día» y dijo: «No serán cortes totales».</p>
{{- end}}
{{- if .Zones}}

    <section aria-labelledby="telegram">
      <h2 id="telegram">Lo que contestaron en Telegram</h2>
      <p>Quienes reciben nuestros avisos contestan si tienen agua. Mostramos cuántos dijeron que no, que poca o que sí cuando en su zona son al menos {{.Min}} respuestas, para no exponer a nadie.</p>
      <ul>
{{- range .Zones}}
        <li>Zona {{.Zone}}: {{if .Shown}}{{.No}} sin agua, {{.Poca}} con poca y {{.Si}} con agua{{else}}menos de {{$.Min}} respuestas{{end}}.</li>
{{- end}}
      </ul>
    </section>
{{- end}}

    <section aria-labelledby="como">
      <h2 id="como">Cómo contamos</h2>
      <ul>
        <li>Son los reportes del <a href="/reportes">mapa de los vecinos</a> de lunes a domingo, en hora de Guadalajara. Son anónimos: no guardamos IP, ubicación ni nombre.</li>
        <li>Los días de corte son los del calendario del SIAPA para la zona principal de cada colonia.</li>
        <li>No son datos oficiales: son lo que dicen los vecinos. Por eso le pedimos al SIAPA que publique cuánta agua llega a cada zona y cuándo.</li>
      </ul>
      <a class="button glow" href="/reportes"><svg class="i" aria-hidden="true"><use href="/icons.svg?v=5#map-pin"/></svg>Reportar mi colonia</a>
    </section>
  </main>
`))
