// Package data embeds SIAPA's rotation zones, colonia list and weekly schedule.
package data

import _ "embed"

//go:embed zonas.geojson
var Zonas []byte

//go:embed colonias.json
var Colonias []byte

//go:embed rotation.json
var Rotation []byte
