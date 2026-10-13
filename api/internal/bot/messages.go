package bot

import (
	"fmt"
	"strings"
)

// All Spanish copy lives here so it can be edited without touching the logic.

const MapURL = "https://rotaciondeserviciosiapa.jalisco.gob.mx/"

const msgWelcome = `¡Hola! 👋 Soy *Agua GDL*.

Te aviso por WhatsApp la noche antes de cada corte de agua en tu zona por la rotación del SIAPA 💧

Para empezar, mándame una de estas:
📍 Tu *ubicación* (📎 › Ubicación)
🏘️ El *nombre de tu colonia*, por ejemplo: _Las Juntas_
🔢 Tu zona, por ejemplo: *ZONA 4*

Servicio ciudadano, gratuito, no oficial y sin partido.`

func msgHelp(base string) string {
	return `Esto es lo que puedo hacer 💧

📍 Manda tu *ubicación* o el *nombre de tu colonia* para saber tu zona
🔢 *ZONA 1* a *ZONA 7*: suscribirte o cambiar de zona
🛑 *BAJA*: dejar de recibir avisos y borrar tus datos

🗺️ Mapa oficial del SIAPA: ` + MapURL + `
🔒 Aviso de privacidad: ` + base + `/privacidad`
}

func msgNotFound(q string) string {
	return fmt.Sprintf(`No encontré «%s» en la lista de colonias del SIAPA 😕

Puede que tu colonia no esté en la rotación. Para revisarlo, mándame tu 📍 *ubicación* o consulta el mapa oficial: %s`, q, MapURL)
}

const msgOutside = `Tu ubicación no está dentro de ninguna zona de la rotación 🙌

Si crees que es un error, revisa el mapa oficial: ` + MapURL

const msgPickColonia = "Encontré varias colonias parecidas. ¿Cuál es la tuya? 👇"

func msgPickZone(colonia string, zones string) string {
	return fmt.Sprintf(`*%s* recibe agua de varios acueductos, así que está repartida en la rotación (zonas %s) 🤔

Mándame tu 📍 *ubicación* para saber cuál te toca, o elige tu zona si ya la sabes 👇`, colonia, zones)
}

const msgPickZoneAtPoint = "Tu ubicación queda en el límite entre zonas 🤔 Elige la tuya o revisa el mapa del SIAPA 👇"

const msgUnsubscribed = "👋 Listo, ya no recibirás avisos y borramos tus datos. Si quieres volver, escribe *HOLA*."

const msgNotSubscribed = "No tienes avisos activos. Escribe *HOLA* para empezar."

const msgNoUserID = "⚠️ No pude registrarte en este momento. Intenta de nuevo más tarde, por favor."

const msgUnsupported = "Por ahora solo entiendo texto y ubicación 📍 Escribe *AYUDA* para ver opciones."

const msgNoReportYet = "Todavía no hay un corte que reportar en tu zona 👍"

const msgReportClosed = "Ese reporte ya cerró. ¡Gracias de todos modos! 🙏"

func msgAskReport(date string) string {
	return fmt.Sprintf("¿Cómo regresó el agua después del corte del *%s*? 👇", date)
}

func msgThanks(base string) string {
	return "🙏 ¡Gracias! Tu reporte ayuda a ver cómo está tu zona.\n\n📊 Resultados: " + base + "/resultados"
}

var reportAnswers = []struct{ key, title string }{
	{"normal", "✅ Regresó normal"},
	{"baja", "🟡 Baja presión"},
	{"no_regreso", "❌ No ha regresado"},
	{"turbia", "🟤 Turbia o con olor"},
}

type subscribedInfo struct {
	zone         int
	days         string
	fresh        bool
	cutTomorrow  string // non-empty when tomorrow's cut is too close for a reminder
	nextReminder string
	nextCut      string
	hour         string
	base         string
}

func msgSubscribed(i subscribedInfo) string {
	var b strings.Builder
	if i.fresh {
		fmt.Fprintf(&b, "✅ ¡Listo! Te avisaré la noche antes de cada corte de agua en la *Zona %d*.\n\n", i.zone)
	} else {
		fmt.Fprintf(&b, "👋 Estás suscrito a los avisos de la *Zona %d*.\n\n", i.zone)
	}
	fmt.Fprintf(&b, "📅 Días de corte: *%s*\n", i.days)
	if i.cutTomorrow != "" {
		fmt.Fprintf(&b, "⚠️ ¡Ojo! *Mañana %s* hay corte. Llena hoy tu tinaco.\n", i.cutTomorrow)
	}
	if i.nextReminder != "" {
		fmt.Fprintf(&b, "🔔 Próximo aviso: *%s, %s* (corte del %s)\n", i.nextReminder, i.hour, i.nextCut)
	} else {
		b.WriteString("🔔 Por ahora no hay más cortes programados en tu zona.\n")
	}
	fmt.Fprintf(&b, "\nEscribe *ZONA 1* a *ZONA 7* para cambiar de zona o *BAJA* para dejar de recibir avisos.\n🔒 Solo guardamos tu identificador de WhatsApp y tu zona: %s/privacidad", i.base)
	return b.String()
}
