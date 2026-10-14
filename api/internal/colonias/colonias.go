// Package colonias searches SIAPA's list of colonias in the rotation.
package colonias

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"unicode"
)

type Colonia struct {
	Name      string `json:"name"`
	Municipio string `json:"municipio"`
	Zones     []int  `json:"zones"`
	Multi     bool   `json:"multi"`
	key       string
	norm      string
	munNorm   string
	grams     map[string]bool
}

// Key identifies a colonia across messages, e.g. in WhatsApp list replies. It keeps
// prefixes: SIAPA lists "Fracc. Jardines del Sauz" and "Jardines del Sauz" in different zones.
func (c Colonia) Key() string { return c.key }

type Index struct{ all []Colonia }

func Load(raw []byte) (*Index, error) {
	var all []Colonia
	if err := json.Unmarshal(raw, &all); err != nil {
		return nil, fmt.Errorf("colonias: %w", err)
	}
	for i := range all {
		all[i].norm = Normalize(all[i].Name)
		all[i].munNorm = Normalize(all[i].Municipio)
		all[i].key = fold(all[i].Name) + "|" + all[i].munNorm
		all[i].grams = trigrams(all[i].norm)
	}
	return &Index{all: all}, nil
}

var accents = strings.NewReplacer("Á", "A", "É", "E", "Í", "I", "Ó", "O", "Ú", "U", "Ü", "U", "Ñ", "N")

var prefixes = []string{"COLONIA ", "COL ", "FRACCIONAMIENTO ", "FRACC ", "FRAC "}

var municipios = []struct{ alias, norm string }{
	{"SAN PEDRO TLAQUEPAQUE", "TLAQUEPAQUE"},
	{"TLAQUEPAQUE", "TLAQUEPAQUE"},
	{"GUADALAJARA", "GUADALAJARA"},
	{"GDL", "GUADALAJARA"},
	{"ZAPOPAN", "ZAPOPAN"},
	{"TONALA", "TONALA"},
}

// Normalize uppercases, strips accents and punctuation, and drops "Col."/"Fracc." prefixes.
func Normalize(s string) string {
	s = fold(s)
	for _, p := range prefixes {
		if rest, ok := strings.CutPrefix(s, p); ok {
			return rest
		}
	}
	return s
}

func fold(s string) string {
	s = accents.Replace(strings.ToUpper(s))
	var b strings.Builder
	for _, r := range s {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			b.WriteRune(r)
		} else {
			b.WriteByte(' ')
		}
	}
	return strings.Join(strings.Fields(b.String()), " ")
}

func (ix *Index) ByKey(key string) (Colonia, bool) {
	for _, c := range ix.all {
		if c.Key() == key {
			return c, true
		}
	}
	return Colonia{}, false
}

// Search returns exact name matches if any (exact = true), otherwise the closest names.
func (ix *Index) Search(q string, limit int) (matches []Colonia, exact bool) {
	nq, mun := Normalize(q), ""
	for _, m := range municipios {
		if rest, ok := strings.CutSuffix(nq, " "+m.alias); ok {
			nq, mun = rest, m.norm
			break
		}
	}
	if nq == "" {
		return nil, false
	}
	for _, c := range ix.all {
		if c.norm == nq && (mun == "" || c.munNorm == mun) {
			matches = append(matches, c)
		}
	}
	if len(matches) > 0 {
		return matches, true
	}
	type scored struct {
		c Colonia
		s float64
	}
	qg := trigrams(nq)
	var cands []scored
	for _, c := range ix.all {
		if mun != "" && c.munNorm != mun {
			continue
		}
		s := similarity(qg, c.grams)
		if len(nq) >= 4 && strings.Contains(c.norm, nq) {
			s = max(s, 0.5)
		}
		if s >= 0.3 {
			cands = append(cands, scored{c, s})
		}
	}
	sort.SliceStable(cands, func(i, j int) bool { return cands[i].s > cands[j].s })
	for i := 0; i < len(cands) && i < limit; i++ {
		matches = append(matches, cands[i].c)
	}
	return matches, false
}

func trigrams(s string) map[string]bool {
	g := map[string]bool{}
	for _, w := range strings.Fields(s) {
		r := []rune("  " + w + " ")
		for i := 0; i+3 <= len(r); i++ {
			g[string(r[i:i+3])] = true
		}
	}
	return g
}

func similarity(a, b map[string]bool) float64 {
	inter := 0
	for g := range a {
		if b[g] {
			inter++
		}
	}
	union := len(a) + len(b) - inter
	if union == 0 {
		return 0
	}
	return float64(inter) / float64(union)
}
