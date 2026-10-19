// Package geo finds the rotation zones at a point on SIAPA's map: its colonia outlines,
// each with the zones SIAPA gives the colonia, and its seven zone polygons.
package geo

import (
	"encoding/json"
	"fmt"
	"math"
	"slices"
	"strconv"
	"strings"
)

// Zones is SIAPA's rotation map, read from the TopoJSON that pipelines/siapa_mapa.py
// writes (web/colonias_siapa.topo.json, embedded as data.Zonas).
type Zones struct {
	colonias []shape
	zones    []shape // one per zone; zones[i].zones holds its number
}

type shape struct {
	zones                  []int
	polys                  [][][]point // polygons, each a list of rings with the outer one first
	minX, minY, maxX, maxY float64
}

type point struct{ x, y float64 } // longitude, latitude

type geometry struct {
	Type       string          `json:"type"`
	Arcs       json.RawMessage `json:"arcs"`
	Properties struct {
		Z json.RawMessage `json:"z"` // "5,6" on a colonia ("" = outside the rotation), 5 on a zone
	} `json:"properties"`
}

// Load decodes the TopoJSON: quantized, delta-encoded arcs, where a negative index in a
// ring stands for arc ^i reversed.
func Load(raw []byte) (*Zones, error) {
	var topo struct {
		Transform struct {
			Scale     [2]float64 `json:"scale"`
			Translate [2]float64 `json:"translate"`
		} `json:"transform"`
		Arcs    [][][2]float64 `json:"arcs"`
		Objects struct {
			Colonias struct {
				Geometries []geometry `json:"geometries"`
			} `json:"colonias"`
			Zonas struct {
				Geometries []geometry `json:"geometries"`
			} `json:"zonas"`
		} `json:"objects"`
	}
	if err := json.Unmarshal(raw, &topo); err != nil {
		return nil, fmt.Errorf("geo: %w", err)
	}
	sx, sy := topo.Transform.Scale[0], topo.Transform.Scale[1]
	tx, ty := topo.Transform.Translate[0], topo.Transform.Translate[1]
	if sx == 0 || sy == 0 {
		return nil, fmt.Errorf("geo: the TopoJSON has no transform")
	}
	arcs := make([][]point, len(topo.Arcs))
	for i, arc := range topo.Arcs {
		var x, y float64
		arcs[i] = make([]point, len(arc))
		for j, d := range arc {
			x, y = x+d[0], y+d[1]
			arcs[i][j] = point{x*sx + tx, y*sy + ty}
		}
	}
	zs := &Zones{}
	for i, g := range topo.Objects.Colonias.Geometries {
		s, err := newShape(g, arcs)
		if err != nil {
			return nil, fmt.Errorf("geo: colonia %d: %w", i, err)
		}
		zs.colonias = append(zs.colonias, s)
	}
	for i, g := range topo.Objects.Zonas.Geometries {
		s, err := newShape(g, arcs)
		if err != nil {
			return nil, fmt.Errorf("geo: zone %d: %w", i, err)
		}
		if len(s.zones) != 1 {
			return nil, fmt.Errorf("geo: zone %d has zones %v", i, s.zones)
		}
		zs.zones = append(zs.zones, s)
	}
	if len(zs.colonias) == 0 || len(zs.zones) == 0 {
		return nil, fmt.Errorf("geo: %d colonias and %d zones", len(zs.colonias), len(zs.zones))
	}
	return zs, nil
}

func newShape(g geometry, arcs [][]point) (shape, error) {
	s := shape{minX: math.Inf(1), minY: math.Inf(1), maxX: math.Inf(-1), maxY: math.Inf(-1)}
	var err error
	if s.zones, err = zonesOf(g.Properties.Z); err != nil {
		return s, err
	}
	var polys [][][]int
	switch g.Type {
	case "Polygon":
		var p [][]int
		err = json.Unmarshal(g.Arcs, &p)
		polys = [][][]int{p}
	case "MultiPolygon":
		err = json.Unmarshal(g.Arcs, &polys)
	default:
		return s, fmt.Errorf("unsupported geometry %q", g.Type)
	}
	if err != nil {
		return s, err
	}
	for _, p := range polys {
		var rings [][]point
		for _, idx := range p {
			var ring []point
			for _, i := range idx {
				j := i
				if i < 0 {
					j = ^i
				}
				if j >= len(arcs) {
					return s, fmt.Errorf("arc %d of %d", j, len(arcs))
				}
				arc := arcs[j]
				if i < 0 {
					arc = slices.Clone(arc)
					slices.Reverse(arc)
				}
				// Consecutive arcs share their junction point.
				if len(ring) > 0 {
					ring = ring[:len(ring)-1]
				}
				ring = append(ring, arc...)
			}
			rings = append(rings, ring)
		}
		if len(rings) == 0 {
			continue
		}
		for _, pt := range rings[0] {
			s.minX, s.maxX = min(s.minX, pt.x), max(s.maxX, pt.x)
			s.minY, s.maxY = min(s.minY, pt.y), max(s.maxY, pt.y)
		}
		s.polys = append(s.polys, rings)
	}
	return s, nil
}

func zonesOf(raw json.RawMessage) ([]int, error) {
	var n int
	if err := json.Unmarshal(raw, &n); err == nil {
		return []int{n}, nil
	}
	var list string
	if err := json.Unmarshal(raw, &list); err != nil {
		return nil, fmt.Errorf("zones %s", raw)
	}
	var zones []int
	for _, f := range strings.Split(list, ",") {
		if f = strings.TrimSpace(f); f == "" {
			continue
		}
		z, err := strconv.Atoi(f)
		if err != nil {
			return nil, fmt.Errorf("zones %q", list)
		}
		zones = append(zones, z)
	}
	return zones, nil
}

// Lookup returns the zones at a point. Inside a colonia outline they are the zones SIAPA's
// map gives that colonia, none when it leaves the colonia out of the rotation, and when it
// gives several, only those whose zone polygon contains the point, if any does: SIAPA sets
// each colonia's zones by hand, so they don't always follow its zone polygons. Outside every
// outline they are the zones whose polygon contains the point.
func (zs *Zones) Lookup(lat, lon float64) []int {
	var ids []int
	inColonia := false
	for _, c := range zs.colonias {
		if !c.contains(lon, lat) {
			continue
		}
		inColonia = true
		own := c.zones
		if len(own) > 1 {
			var here []int
			for _, z := range own {
				if zs.inZone(z, lon, lat) {
					here = append(here, z)
				}
			}
			if len(here) > 0 {
				own = here
			}
		}
		ids = append(ids, own...)
	}
	if !inColonia {
		for _, z := range zs.zones {
			if z.contains(lon, lat) {
				ids = append(ids, z.zones[0])
			}
		}
	}
	slices.Sort(ids)
	return slices.Compact(ids)
}

func (zs *Zones) inZone(zone int, x, y float64) bool {
	for _, z := range zs.zones {
		if z.zones[0] == zone && z.contains(x, y) {
			return true
		}
	}
	return false
}

func (s *shape) contains(x, y float64) bool {
	if x < s.minX || x > s.maxX || y < s.minY || y > s.maxY {
		return false
	}
	for _, rings := range s.polys {
		if inPolygon(rings, x, y) {
			return true
		}
	}
	return false
}

func inPolygon(rings [][]point, x, y float64) bool {
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

func inRing(ring []point, x, y float64) bool {
	in := false
	for i, j := 0, len(ring)-1; i < len(ring); j, i = i, i+1 {
		xi, yi, xj, yj := ring[i].x, ring[i].y, ring[j].x, ring[j].y
		if (yi > y) != (yj > y) && x < (xj-xi)*(y-yi)/(yj-yi)+xi {
			in = !in
		}
	}
	return in
}
