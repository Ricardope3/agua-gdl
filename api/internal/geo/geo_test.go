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
	if got := zs.Lookup(20.6767, -103.3475); !slices.Equal(got, []int{6}) {
		t.Errorf("Catedral: got %v, want [6]", got)
	}
	if got := zs.Lookup(20.2950, -103.2560); got != nil {
		t.Errorf("Chapala: got %v, want none", got)
	}
}

// The site's map draws the zones from its own copy; it must match what the API looks up.
func TestSiteZonesMatch(t *testing.T) {
	site, err := os.ReadFile(filepath.Join("..", "..", "..", "web", "zonas.geojson"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(site, data.Zonas) {
		t.Error("web/zonas.geojson differs from api/data/zonas.geojson: copy it over")
	}
}
