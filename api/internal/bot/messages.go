package bot

import (
	"fmt"
	"strings"

	"aguagdl/api/internal/store"
)

// All Spanish copy lives here so it can be edited without touching the logic.

const MapURL = "https://rotaciondeserviciosiapa.jalisco.gob.mx/"

// appName is the messaging app a subscriber uses.
func appName(channel string) string {
	if channel == store.Telegram {
		return "Telegram"
	}
	return "WhatsApp"
}

func msgWelcome(base, channel string) string {
	how := "📎 o + › Ubicación"
	if channel == store.Telegram {
		how = "con el botón de abajo o 📎 › Ubicación"
	}
	return `¡Hola! 👋 Soy *Agua GDL*.

Te aviso por ` + appName(channel) + ` la noche antes de cada corte de agua en tu zona por la rotación del SIAPA 💧

Para empezar, mándame una de estas:
📍 Tu *ubicación* (` + how + `)
🏘️ El *nombre de tu colonia*, por ejemplo: _Las Juntas_
🔢 Tu zona, por ejemplo: *ZONA 4*

Servicio ciudadano, gratuito, no oficial y sin partido.
🔒 Aviso de privacidad: ` + base + `/privacidad`
}

func msgHelp(base string) string {
	return `Esto es lo que puedo hacer 💧

📍 Manda tu *ubicación* o el *nombre de tu colonia* para saber tu zona
🔢 *ZONA 1* a *ZONA 7*: suscribirte o cambiar de zona
📝 *REPORTAR*: contar cómo regresó el agua después del último corte
🚚 *PIPA*: cómo pedir una pipa al SIAPA
🛑 *BAJA*: dejar de recibir avisos y borrar tus datos

🗺️ Mapa oficial del SIAPA: ` + MapURL + `
🔒 Aviso de privacidad: ` + base + `/privacidad`
}

func msgNotFound(q string) string {
	return fmt.Sprintf(`No encontré «%s» en la lista de colonias del SIAPA 😕

Puede que tu colonia no esté en la rotación. Para revisarlo, mándame tu 📍 *ubicación* o consulta el mapa oficial: %s`, q, MapURL)
}

const msgOutside = `Tu ubicación no cae en ninguna zona del mapa del SIAPA.

Puede que no te toque la rotación, pero el mapa y la lista de colonias del SIAPA no siempre coinciden. Para revisarlo, mándame el *nombre de tu colonia* o, si ya sabes tu zona, escribe por ejemplo *ZONA 4*.

🗺️ Mapa oficial: ` + MapURL

func msgMunicipio(name string) string {
	return fmt.Sprintf(`*%s* tiene colonias en varias zonas de la rotación 🤔

Mándame tu 📍 *ubicación* o el *nombre de tu colonia*, por ejemplo: _Las Juntas_`, name)
}

const msgPickColonia = "Encontré varias colonias parecidas. ¿Cuál es la tuya? 👇"

func msgPickZone(colonia string, zones []int) string {
	where := "así que está repartida en la rotación (" + zoneLabel(zones) + ")"
	if len(zones) == 1 {
		where = "y el SIAPA la marca como repartida, aunque solo la lista en la " + zoneLabel(zones)
	}
	return fmt.Sprintf(`*%s* recibe agua de varios acueductos, %s 🤔

Mándame tu 📍 *ubicación* para saber cuál te toca, o elige tu zona si ya la sabes 👇`, colonia, where)
}

const msgPickZoneAtPoint = "Tu ubicación queda en el límite entre zonas 🤔 Elige la tuya o revisa el mapa del SIAPA 👇"

// Contacts as published on rotaciondeserviciosiapa.jalisco.gob.mx (checked 14 Oct 2026).
const msgPipa = `🚚 Para pedir una *pipa* o reportar que no te llega el agua, contacta al SIAPA:

💬 WhatsApp SIAPABOT: 33 51 64 44 40
☎️ SIAPATEL: 073

Agua GDL no es del SIAPA y no puede mandar pipas.`

func msgFull(base string) string {
	return `😔 Por ahora llegamos al máximo de avisos que WhatsApp nos deja enviar cada noche. Estamos trabajando para ampliarlo.

Vuelve a escribir *HOLA* en unos días. Mientras tanto, revisa tus días de corte en el mapa del SIAPA: ` + MapURL + `

Novedades: ` + base
}

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
	off          bool   // reminders are switched off on the server
	nextReminder string
	nextCut      string
	hour         string
	base         string
	channel      string
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
	switch {
	case i.off:
		b.WriteString("🔔 Los avisos automáticos empiezan en unos días.\n")
	case i.nextReminder != "":
		fmt.Fprintf(&b, "🔔 Próximo aviso: *%s, %s* (corte del %s)\n", i.nextReminder, i.hour, i.nextCut)
	default:
		b.WriteString("🔔 Por ahora no hay más cortes programados en tu zona.\n")
	}
	fmt.Fprintf(&b, "\n📝 Después de cada corte escribe *REPORTAR* para contar cómo regresó el agua.\nEscribe *ZONA 1* a *ZONA 7* para cambiar de zona o *BAJA* para dejar de recibir avisos.\n🔒 Solo guardamos %s y tu zona: %s/privacidad", storedID(i.channel), i.base)
	return b.String()
}

func storedID(channel string) string {
	if channel == store.Telegram {
		return "tu ID de chat de Telegram"
	}
	return "tu número de WhatsApp"
}

const msgAskPlace = "Para elegir tu zona, mándame tu 📍 *ubicación*, el *nombre de tu colonia* o tu zona, por ejemplo: *ZONA 4*"

// ManualReminder is the aviso_corte template as a normal text, for nights the template
// can't be used (cmd/notify -tomorrow). A normal text can't carry the template's buttons.
func ManualReminder(date string, zone int) string {
	return fmt.Sprintf(`💧 *Mañana %s* hay racionamiento de agua en la *Zona %d* por la rotación del SIAPA: puede bajar la presión o faltar el agua hasta por un día.

🪣 Llena hoy tu tinaco, cubetas y garrafones.
🔒 Tapa bien los recipientes para que el agua no se ensucie.

ℹ️ Aviso ciudadano, no oficial. Confirma tu colonia en el mapa del SIAPA: %s

Agua GDL · Escribe *BAJA* para no recibir avisos`, date, zone, MapURL)
}
