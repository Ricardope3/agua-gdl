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

func msgHelp(base, channel string) string {
	write := ""
	if channel == store.Telegram {
		write = "✉️ *ESCRIBIR*: escribirle al Congreso de Jalisco sobre el agua\n"
	}
	return `Esto es lo que puedo hacer 💧

📍 Manda tu *ubicación* o el *nombre de tu colonia* para saber tu zona
🔢 *ZONA 1* a *ZONA 7*: suscribirte o cambiar de zona
📝 *REPORTAR*: contar cómo regresó el agua después del último corte
🚚 *PIPA*: cómo pedir una pipa al SIAPA
` + write + `🛑 *BAJA*: dejar de recibir avisos y borrar tus datos

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

// msgOtherColonia is for a colonia that exists but isn't on SIAPA's rotation list;
// mun is its municipio as people write it, and zones the zones whose map area it overlaps.
func msgOtherColonia(name, mun string, zones []int) string {
	if len(zones) == 0 {
		return fmt.Sprintf("✅ *%s* (%s) no está en la lista de colonias de la rotación del SIAPA y queda fuera de las zonas de su mapa, así que no le toca racionamiento.", name, mun)
	}
	return fmt.Sprintf("⚠️ *%s* (%s) no está en la lista de colonias de la rotación del SIAPA, pero queda dentro del mapa de la %s. El mapa y la lista no siempre coinciden: mándame tu 📍 *ubicación* para confirmarlo.", name, mun, zoneLabel(zones))
}

const msgOrOneOfThese = "¿O es alguna de estas? 👇"

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

func msgWrite(base string) string {
	return `✉️ Pídeles a las y los 38 diputados del Congreso de Jalisco que voten en contra del contrato APP del acueducto Chapala–Guadalajara, por correo, X o Messenger desde tu propia cuenta. Ahí también puedes firmar la solicitud de Contraloría Social en el IEPC:

` + base + `/escribe

Agua GDL no envía el correo ni guarda tus datos, y escribimos a todas las diputaciones por igual.`
}

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

const msgReportBeforeJoin = "Solo contamos reportes de cortes que empezaron después de tu suscripción. Podrás reportar el próximo 🙏"

func msgRotationOver(base string) string {
	return `🗓️ La rotación de agua del SIAPA ya terminó, así que ya no mandamos avisos ni guardamos suscripciones.

Novedades: ` + base
}

func msgAskReport(date string) string {
	return fmt.Sprintf("¿Cómo regresó el agua después del corte del *%s*? 👇", date)
}

const msgThanks = "🙏 ¡Gracias! Tu reporte ayuda a ver cómo está tu zona."

// waterAnswers are the Telegram reminder's buttons for «¿Ahorita tienes agua?» and what
// each answer gets back.
var waterAnswers = []struct{ key, title, thanks string }{
	{"si", "✅ Sí", "🙏 ¡Gracias! Aprovecha para llenar tu tinaco y tus garrafones antes del corte."},
	{"poca", "🟡 Poca", "🙏 ¡Gracias! Llena lo que puedas mientras salga."},
	{"no", "❌ No", "🙏 Gracias por avisarnos: nos ayuda a avisar con más tiempo.\n\n" + msgPipa},
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
	cutTomorrow  string // non-empty when no reminder comes for tomorrow's cut: too late, reminders off, or it continues today's
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
		fmt.Fprintf(&b, "⚠️ ¡Ojo! *Mañana %s* hay corte. Si todavía tienes agua, llena hoy tu tinaco.\n", i.cutTomorrow)
	}
	switch {
	case i.off:
		b.WriteString("🔔 Los avisos automáticos empiezan en unos días.\n")
	case i.nextReminder != "":
		fmt.Fprintf(&b, "🔔 Próximo aviso: *%s, %s* (corte del %s)\n", i.nextReminder, i.hour, i.nextCut)
	default:
		b.WriteString("🔔 Por ahora no hay más cortes programados en tu zona.\n")
	}
	fmt.Fprintf(&b, "\n📝 Después de cada corte escribe *REPORTAR* para contar cómo regresó el agua.\nEscribe *ZONA 1* a *ZONA 7* para cambiar de zona o *BAJA* para dejar de recibir avisos.\n🔒 Guardamos %s, tu zona y tus reportes. Todo lo que guardamos: %s/privacidad", storedID(i.channel), i.base)
	return b.String()
}

func storedID(channel string) string {
	if channel == store.Telegram {
		return "tu ID de chat de Telegram"
	}
	return "tu número de WhatsApp"
}

const msgAskPlace = "Para elegir tu zona, mándame tu 📍 *ubicación*, el *nombre de tu colonia* o tu zona, por ejemplo: *ZONA 4*"

// ScheduleChange is cambio_rotacion's wording, for channels without templates.
func ScheduleChange(zone int, days, from string) string {
	return fmt.Sprintf(`⚠️ *Cambio en la rotación de la Zona %d*

El SIAPA cambió los días de racionamiento. Ahora son: *%s*, a partir del %s.

Te seguiré avisando la noche anterior 💧

ℹ️ Aviso ciudadano, no oficial. Confirma en el mapa del SIAPA.`, zone, days, from)
}

// ManualReminder is the aviso_corte template as a normal text, for nights the template
// can't be used (cmd/notify -tomorrow). A normal text can't carry the template's buttons.
func ManualReminder(date string, zone int) string {
	return reminderBody(date, zone) + `

ℹ️ Aviso ciudadano, no oficial. Confirma tu colonia en el mapa del SIAPA: ` + MapURL + `

Agua GDL · Escribe *BAJA* para no recibir avisos`
}

// msgTelegramReminder is the reminder for the run of cut days that starts tomorrow; it goes
// with buttons to answer whether the water is still on, for the map and for BAJA. Unlike
// WhatsApp's approved template, it doesn't repeat SIAPA's account as fact.
func msgTelegramReminder(dates string, zone int) string {
	return fmt.Sprintf(`💧 La *Zona %d* tiene corte *mañana %s*, según el calendario del SIAPA.

El SIAPA dice que solo baja la presión y por un día, pero vecinos nos cuentan que el agua se va desde antes y tarda más en volver.

🪣 Si todavía tienes agua, llena tu tinaco, cubetas y garrafones, y tápalos bien.

*¿Ahorita tienes agua?* Tu respuesta nos ayuda a avisar mejor 👇

ℹ️ Aviso ciudadano, no oficial. Confirma tu colonia en el mapa del SIAPA.`, zone, dates)
}

// reminderBody is the text of WhatsApp's approved aviso_corte template.
func reminderBody(date string, zone int) string {
	return fmt.Sprintf(`💧 *Mañana %s* hay racionamiento de agua en la *Zona %d* por la rotación del SIAPA: puede bajar la presión o faltar el agua hasta por un día.

🪣 Llena hoy tu tinaco, cubetas y garrafones.
🔒 Tapa bien los recipientes para que el agua no se ensucie.`, date, zone)
}
