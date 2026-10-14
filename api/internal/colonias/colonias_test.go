package colonias

import (
	"testing"

	"aguagdl/api/data"
)

func TestNormalize(t *testing.T) {
	cases := map[string]string{
		"Col. Las Juntas":          "LAS JUNTAS",
		"fracc. jardines del sauz": "JARDINES DEL SAUZ",
		"  Tonalá ":                "TONALA",
		"Colón":                    "COLON",
	}
	for in, want := range cases {
		if got := Normalize(in); got != want {
			t.Errorf("Normalize(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestSearch(t *testing.T) {
	ix, err := Load(data.Colonias)
	if err != nil {
		t.Fatal(err)
	}
	m, exact := ix.Search("col. chapalita", 5)
	if !exact || len(m) != 2 {
		t.Fatalf("Chapalita is in Guadalajara and Zapopan: %v %v", m, exact)
	}
	m, exact = ix.Search("Chapalita, Zapopan", 5)
	if !exact || len(m) != 1 || m[0].Municipio != "ZAPOPAN" {
		t.Fatalf("exact: %v %v", m, exact)
	}
	m, exact = ix.Search("Americana, Guadalajara", 5)
	if !exact || !m[0].Multi || len(m[0].Zones) < 2 {
		t.Fatalf("multi-zone: %v %v", m, exact)
	}
	m, exact = ix.Search("chapalitta", 5)
	if exact || len(m) == 0 || m[0].Name != "CHAPALITA" {
		t.Fatalf("fuzzy: %v %v", m, exact)
	}
	if c, ok := ix.ByKey(m[0].Key()); !ok || c.Name != "CHAPALITA" {
		t.Fatal("ByKey")
	}
	if m, _ := ix.Search("xyzzy qwerty", 5); len(m) != 0 {
		t.Fatalf("nonsense matched %v", m)
	}
}

func TestNamesEndingInMunicipio(t *testing.T) {
	ix, _ := Load(data.Colonias)
	for _, q := range []string{"Lomas de Tlaquepaque", "Centro Guadalajara", "Altos Tonalá", "Lomas de Tlaquepaque, Tlaquepaque"} {
		if m, exact := ix.Search(q, 5); !exact || len(m) != 1 {
			t.Errorf("%q: exact=%v %v", q, exact, m)
		}
	}
}

func TestKeysAreUnique(t *testing.T) {
	ix, _ := Load(data.Colonias)
	seen := map[string]bool{}
	for _, c := range ix.all {
		if seen[c.Key()] {
			t.Errorf("duplicate key %s", c.Key())
		}
		seen[c.Key()] = true
	}
	m, _ := ix.Search("Jardines del Sauz", 5)
	zones := map[int]bool{}
	for _, c := range m {
		got, _ := ix.ByKey(c.Key())
		zones[got.Zones[0]] = true
	}
	if !zones[5] || !zones[6] {
		t.Errorf("Fracc. Jardines del Sauz (zone 5) and Jardines del Sauz (zone 6) must stay apart: %v", m)
	}
}

func TestLastRowOfPDFPage(t *testing.T) {
	ix, err := Load(data.Colonias)
	if err != nil {
		t.Fatal(err)
	}
	m, exact := ix.Search("Niños Héroes", 5)
	if !exact || len(m) != 1 || len(m[0].Zones) != 1 || m[0].Zones[0] != 6 {
		t.Fatalf("Niños Héroes is the last row of a PDF page: %v %v", m, exact)
	}
	m, _ = ix.Search("Medrano", 5)
	if len(m) == 0 || len(m[0].Zones) != 2 {
		t.Fatalf("Medrano is in zones 2 and 3: %v", m)
	}
}
