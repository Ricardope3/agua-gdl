package bot

import (
	"fmt"
	"strings"
	"time"

	"aguagdl/api/internal/rotation"
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

Te aviso por ` + appName(channel) + ` ` + whenES(channel) + ` de cada corte de agua en tu zona por la rotación del SIAPA 💧

Para empezar, mándame una de estas:
📍 Tu *ubicación* (` + how + `)
🏘️ El *nombre de tu colonia*, por ejemplo: _Las Juntas_
🔢 Tu zona, por ejemplo: *ZONA 4*

Servicio ciudadano, gratuito, no oficial y sin partido.
🔒 Aviso de privacidad: ` + base + `/privacidad`
}

// whenES is when the reminders come: Telegram also gets a notice two days before.
func whenES(channel string) string {
	if channel == store.Telegram {
		return "dos días antes y otra vez la noche antes"
	}
	return "la noche antes"
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
	cutTomorrow  []time.Time // set when no reminder comes for tomorrow's cut: tonight's run has passed or it continues a block
	cutsLeft     []time.Time // the rest of a block that started today: no reminder comes for them
	off          bool        // reminders are switched off on the server
	nextReminder string
	nextCut      []time.Time // the block the next message is about
	hour         string
	base         string
	channel      string
}

func msgSubscribed(i subscribedInfo) string {
	var b strings.Builder
	if i.fresh {
		fmt.Fprintf(&b, "✅ ¡Listo! Te avisaré %s de cada corte de agua en la *Zona %d*.\n\n", whenES(i.channel), i.zone)
	} else {
		fmt.Fprintf(&b, "👋 Estás suscrito a los avisos de la *Zona %d*.\n\n", i.zone)
	}
	fmt.Fprintf(&b, "📅 Días de corte: *%s*\n", i.days)
	if len(i.cutTomorrow) > 0 {
		fmt.Fprintf(&b, "⚠️ ¡Ojo! *Mañana %s* hay corte%s. Si todavía tienes agua, llena hoy tu tinaco.\n", rotation.DateES(i.cutTomorrow[0]), alsoES(i.cutTomorrow))
	} else if len(i.cutsLeft) > 0 {
		fmt.Fprintf(&b, "⚠️ ¡Ojo! Hoy hay corte en tu zona, y también el *%s*. De esos días no te llegará aviso: si todavía tienes agua, llena tu tinaco.\n", rotation.DatesES(i.cutsLeft))
	}
	switch {
	case i.off:
		b.WriteString("🔔 Los avisos automáticos empiezan en unos días.\n")
	case i.nextReminder != "":
		fmt.Fprintf(&b, "🔔 Próximo aviso: *%s, %s* (%s)\n", i.nextReminder, i.hour, cutsES(i.nextCut))
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

Te seguiré avisando antes de cada corte 💧

ℹ️ Aviso ciudadano, no oficial. Confirma en el mapa del SIAPA.`, zone, days, from)
}

// ManualReminder is the aviso_corte template as a normal text, for nights the template
// can't be used (cmd/notify -tomorrow). A normal text can't carry the template's buttons.
func ManualReminder(date string, zone int) string {
	return reminderBody(date, zone) + `

ℹ️ Aviso ciudadano, no oficial. Confirma tu colonia en el mapa del SIAPA: ` + MapURL + `

Agua GDL · Escribe *BAJA* para no recibir avisos`
}

// alsoES is ", y también el viernes 23 y domingo 25 de octubre" for a block's days after the
// first, or "" for a single day.
func alsoES(days []time.Time) string {
	if len(days) < 2 {
		return ""
	}
	return ", y también el " + rotation.DatesES(days[1:])
}

// cutsES is "corte del lunes 19 de octubre", or "cortes del …" for a block of several days.
func cutsES(days []time.Time) string {
	if len(days) == 1 {
		return "corte del " + rotation.DatesES(days)
	}
	return "cortes del " + rotation.DatesES(days)
}

// msgNotice is Telegram's notice two days before a block of cuts, with the same buttons as
// the reminder: neighbours report the water goes a day early, so the evening before can be late.
func msgNotice(days []time.Time, zone int) string {
	return fmt.Sprintf(`🔔 *Se acerca el corte en la Zona %d:* según el calendario del SIAPA, el *%s*.

Vecinos nos cuentan que el agua se va desde un día antes y tarda más en volver. Si todavía tienes, llena con tiempo tu tinaco, cubetas y garrafones, y tápalos bien.

*¿Ahorita tienes agua?* Si ya se te fue, avísanos 👇

ℹ️ Aviso ciudadano, no oficial. Confirma tu colonia en el mapa del SIAPA.`, zone, rotation.DatesES(days))
}

// msgFollowUp asks, the evening after a block, whoever said they had no water or little.
func msgFollowUp(days []time.Time, zone int) string {
	return fmt.Sprintf(`💧 *¿Ya regresó el agua?* Nos dijiste que te faltaba antes del corte de la *Zona %d* (%s).

Cuéntanos cómo está ahora 👇`, zone, rotation.DatesES(days))
}

// msgReportMap points whoever answered «No» or «Poca» to the map of neighbours' reports.
func msgReportMap(base string) string {
	return "\n\n🗺️ Mira y reporta cómo está el agua en tu colonia: " + base + "/reportes"
}

// AvisosChange tells a zone's Telegram subscribers, once, about the notice two days before each
// cut. It lists the zone's cuts for the coming week: a block already under way when the change is
// deployed got the old reminder, which named only its first day.
func AvisosChange(base string, zone int, next []time.Time) string {
	coming := ""
	if len(next) > 0 {
		coming = fmt.Sprintf("📅 Tus próximos cortes (Zona %d): *%s*.\n\n", zone, rotation.DatesES(next))
	}
	return `📣 *Cambiamos los avisos de Agua GDL*

Vecinos nos contaron que el agua se va desde antes del corte y tarda más en volver. Por eso, desde ahora:

🔔 Te avisamos *dos días antes* de cada corte y otra vez la noche antes.
💧 Te preguntamos si todavía tienes agua. Si ya se te fue, no te mandamos el aviso de la noche antes y, después del corte, te preguntamos si ya regresó.
🗓️ Si tu zona tiene cortes con uno o ningún día de por medio, te avisamos una sola vez por tanda.

` + coming + `Si prefieres no recibirlos, escribe *BAJA*. Todo lo que guardamos: ` + base + `/privacidad`
}

// msgTelegramReminder is the reminder for the block of cuts that starts tomorrow; it goes
// with buttons to answer whether the water is still on, for the map and for BAJA. Unlike
// WhatsApp's approved template, it doesn't repeat SIAPA's account as fact.
func msgTelegramReminder(days []time.Time, zone int) string {
	return fmt.Sprintf(`💧 La *Zona %d* tiene corte *mañana %s*%s, según el calendario del SIAPA.

El SIAPA dice que solo baja la presión y por un día, pero vecinos nos cuentan que el agua se va desde antes y tarda más en volver.

🪣 Si todavía tienes agua, llena tu tinaco, cubetas y garrafones, y tápalos bien.

*¿Ahorita tienes agua?* Tu respuesta nos ayuda a avisar mejor 👇

ℹ️ Aviso ciudadano, no oficial. Confirma tu colonia en el mapa del SIAPA.`, zone, rotation.DateES(days[0]), alsoES(days))
}

// reminderBody is the text of WhatsApp's approved aviso_corte template.
func reminderBody(date string, zone int) string {
	return fmt.Sprintf(`💧 *Mañana %s* hay racionamiento de agua en la *Zona %d* por la rotación del SIAPA: puede bajar la presión o faltar el agua hasta por un día.

🪣 Llena hoy tu tinaco, cubetas y garrafones.
🔒 Tapa bien los recipientes para que el agua no se ensucie.`, date, zone)
}
