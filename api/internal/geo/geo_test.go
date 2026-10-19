package geo

import (
	"bytes"
	"os"
	"path/filepath"
	"slices"
	"testing"

	"aguagdl/api/data"
)

func TestLookup(t *testing.T) {
	zs, err := Load(data.Zonas)
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range []struct {
		where    string
		lat, lon float64
		want     []int
	}{
		{"Catedral", 20.6767, -103.3475, []int{6}},
		// SIAPA's map puts Vallarta Norte in zone 6, though its outline is outside the zone polygons.
		{"Vallarta Norte", 20.67714, -103.38829, []int{6}},
		// Americana is in zones 1, 5 and 6: the zone polygon under the point tells which.
		{"Americana, zone 1 side", 20.66702, -103.36702, []int{1}},
		{"Americana, zone 5 side", 20.67096, -103.37727, []int{5}},
		{"Americana, zone 6 side", 20.67458, -103.37727, []int{6}},
		{"Chapala", 20.2950, -103.2560, nil},
	} {
		if got := zs.Lookup(c.lat, c.lon); !slices.Equal(got, c.want) {
			t.Errorf("%s: got %v, want %v", c.where, got, c.want)
		}
	}
}

// The site's maps and the API read the same copy of SIAPA's map.
func TestSiteMapMatches(t *testing.T) {
	site, err := os.ReadFile(filepath.Join("..", "..", "..", "web", "colonias_siapa.topo.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(site, data.Zonas) {
		t.Error("web/colonias_siapa.topo.json differs from api/data/colonias_siapa.topo.json: run pipelines/siapa_mapa.py, which writes both")
	}
}
