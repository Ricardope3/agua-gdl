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

// Other is a colonia in INE's cartography that isn't on SIAPA's rotation list. Zones are
// the zones whose map area it overlaps; none means the rotation doesn't reach it.
type Other struct {
	Name      string `json:"name"`
	Municipio string `json:"municipio"`
	Zones     []int  `json:"zones"`
	norm      string
	munNorm   string
}

type Index struct {
	all    []Colonia
	others []Other
}

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

// LoadOthers adds the colonias that aren't on SIAPA's list, for Others.
func (ix *Index) LoadOthers(raw []byte) error {
	if err := json.Unmarshal(raw, &ix.others); err != nil {
		return fmt.Errorf("otras colonias: %w", err)
	}
	for i := range ix.others {
		ix.others[i].norm = Normalize(ix.others[i].Name)
		ix.others[i].munNorm = Normalize(ix.others[i].Municipio)
	}
	return nil
}

// Others returns the colonias off SIAPA's list whose name is exactly q, optionally
// followed by its municipio.
func (ix *Index) Others(q string) []Other {
	if len([]rune(q)) > MaxQuery {
		return nil
	}
	nq := Normalize(q)
	var out []Other
	for _, o := range ix.others {
		if o.norm == nq || nq == o.norm+" "+o.munNorm || (o.munNorm == "TLAQUEPAQUE" && nq == o.norm+" SAN PEDRO TLAQUEPAQUE") {
			out = append(out, o)
		}
	}
	return out
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
		} else if !unicode.Is(unicode.Mn, r) { // a decomposed accent belongs to its letter
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

// MaxQuery bounds a search: the longest colonia name has 43 characters, and
// trigram matching on long input costs CPU on every call.
const MaxQuery = 80

// Search returns exact name matches if any (exact = true), otherwise the closest names,
// at most limit of them (limit <= 0: all).
func (ix *Index) Search(q string, limit int) (matches []Colonia, exact bool) {
	if len([]rune(q)) > MaxQuery {
		return nil, false
	}
	nq, mun := Normalize(q), ""
	if nq == "" {
		return nil, false
	}
	// Try the whole query first: names like "Lomas de Tlaquepaque" end in a municipio.
	if matches = ix.exact(nq, ""); len(matches) > 0 {
		return matches, true
	}
	for _, m := range municipios {
		if rest, ok := strings.CutSuffix(nq, " "+m.alias); ok {
			nq, mun = rest, m.norm
			break
		}
	}
	if mun != "" {
		if matches = ix.exact(nq, mun); len(matches) > 0 {
			return matches, true
		}
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
		// Trigrams can't match one or two letters, so short queries match word starts.
		if len([]rune(nq)) < 3 && strings.Contains(" "+c.norm, " "+nq) {
			s = max(s, 0.5)
		}
		if s >= 0.3 {
			cands = append(cands, scored{c, s})
		}
	}
	sort.SliceStable(cands, func(i, j int) bool { return cands[i].s > cands[j].s })
	for i := 0; i < len(cands) && (limit <= 0 || i < limit); i++ {
		matches = append(matches, cands[i].c)
	}
	return matches, false
}

func (ix *Index) exact(nq, mun string) []Colonia {
	var out []Colonia
	for _, c := range ix.all {
		if c.norm == nq && (mun == "" || c.munNorm == mun) {
			out = append(out, c)
		}
	}
	return out
}

// stopwords don't tell colonias apart, so they don't count toward similarity:
// otherwise "los pino" matches LOS PATOS and LOS POCITOS on "LOS" alone.
var stopwords = map[string]bool{"EL": true, "LA": true, "LOS": true, "LAS": true, "DE": true, "DEL": true, "Y": true}

func trigrams(s string) map[string]bool {
	words := strings.Fields(s)
	var kept []string
	for _, w := range words {
		if !stopwords[w] {
			kept = append(kept, w)
		}
	}
	if len(kept) > 0 {
		words = kept
	}
	g := map[string]bool{}
	for _, w := range words {
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
