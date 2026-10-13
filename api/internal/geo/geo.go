// Package geo finds which rotation zone contains a point, using SIAPA's zone polygons.
package geo

import (
	"encoding/json"
	"fmt"
	"math"
	"slices"
	"strings"
)

type Zones struct{ zones []zone }

type zone struct {
	id                             int
	polys                          [][][][]float64
	minLon, minLat, maxLon, maxLat float64
}

func Load(raw []byte) (*Zones, error) {
	var fc struct {
		Features []struct {
			Properties struct {
				Zona string `json:"zona"`
			} `json:"properties"`
			Geometry struct {
				Type        string          `json:"type"`
				Coordinates json.RawMessage `json:"coordinates"`
			} `json:"geometry"`
		} `json:"features"`
	}
	if err := json.Unmarshal(raw, &fc); err != nil {
		return nil, fmt.Errorf("geo: %w", err)
	}
	zs := &Zones{}
	for _, f := range fc.Features {
		var id int
		if _, err := fmt.Sscanf(strings.ToUpper(strings.TrimSpace(f.Properties.Zona)), "ZONA %d", &id); err != nil {
			return nil, fmt.Errorf("geo: zone name %q: %w", f.Properties.Zona, err)
		}
		var polys [][][][]float64
		switch f.Geometry.Type {
		case "MultiPolygon":
			if err := json.Unmarshal(f.Geometry.Coordinates, &polys); err != nil {
				return nil, fmt.Errorf("geo: zone %d: %w", id, err)
			}
		case "Polygon":
			var p [][][]float64
			if err := json.Unmarshal(f.Geometry.Coordinates, &p); err != nil {
				return nil, fmt.Errorf("geo: zone %d: %w", id, err)
			}
			polys = [][][][]float64{p}
		default:
			return nil, fmt.Errorf("geo: zone %d: unsupported geometry %s", id, f.Geometry.Type)
		}
		z := zone{id: id, polys: polys, minLon: math.Inf(1), minLat: math.Inf(1), maxLon: math.Inf(-1), maxLat: math.Inf(-1)}
		for _, p := range polys {
			for _, pt := range p[0] {
				z.minLon, z.maxLon = min(z.minLon, pt[0]), max(z.maxLon, pt[0])
				z.minLat, z.maxLat = min(z.minLat, pt[1]), max(z.maxLat, pt[1])
			}
		}
		zs.zones = append(zs.zones, z)
	}
	return zs, nil
}

// Lookup returns every zone whose polygons contain the point.
func (zs *Zones) Lookup(lat, lon float64) []int {
	var ids []int
	for _, z := range zs.zones {
		if lon < z.minLon || lon > z.maxLon || lat < z.minLat || lat > z.maxLat {
			continue
		}
		for _, p := range z.polys {
			if inPolygon(p, lon, lat) {
				ids = append(ids, z.id)
				break
			}
		}
	}
	slices.Sort(ids)
	return slices.Compact(ids)
}

func inPolygon(rings [][][]float64, x, y float64) bool {
	if len(rings) == 0 || !inRing(rings[0], x, y) {
		return false
	}
	for _, hole := range rings[1:] {
		if inRing(hole, x, y) {
			return false
		}
	}
	return true
}

func inRing(ring [][]float64, x, y float64) bool {
	in := false
	for i, j := 0, len(ring)-1; i < len(ring); j, i = i, i+1 {
		xi, yi, xj, yj := ring[i][0], ring[i][1], ring[j][0], ring[j][1]
		if (yi > y) != (yj > y) && x < (xj-xi)*(y-yi)/(yj-yi)+xi {
			in = !in
		}
	}
	return in
}
