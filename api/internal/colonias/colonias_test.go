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
