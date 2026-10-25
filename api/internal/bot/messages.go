package bot

import (
	"fmt"
	"strconv"
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

*El agua es un derecho. Exígelo.*

🗺️ ¿Hay agua en tu colonia? Reporta la tuya, sin registrarte: cada reporte es una prueba de dónde falla el gobierno. Mira lo que reportan tus vecinos: ` + base + `/reportes
📢 Exígele a quien le toca que lo arregle: ` + base + `/exige
🚚 ¿Sin agua? Escribe *PIPA* y te digo cómo pedir una.

🔔 También te aviso por ` + appName(channel) + ` de los cortes de agua de tu zona por la rotación del SIAPA: ` + whenES(channel) + `. Para recibir los avisos, mándame una de estas:
📍 Tu *ubicación* (` + how + `)
🏘️ El *nombre de tu colonia*, por ejemplo: _Las Juntas_
🔢 Tu zona, por ejemplo: *ZONA 4*

Servicio ciudadano, gratuito, no oficial y sin partido.
🔒 Aviso de privacidad: ` + base + `/privacidad`
}

// whenES is when the reminders come: Telegram also gets a notice two days before, and cuts
// close together (rotation.BlockGap) get one round, before the first.
func whenES(channel string) string {
	if channel == store.Telegram {
		return "dos días antes y otra vez la noche antes (una vez por tanda cuando los cortes van seguidos)"
	}
	return "la noche antes (una vez por tanda cuando los cortes van seguidos)"
}

func msgHelp(base, channel string) string {
	write := ""
	if channel == store.Telegram {
		write = "✉️ *ESCRIBIR*: escribirle al Congreso de Jalisco sobre el agua\n"
	}
	return `Esto es lo que puedo hacer 💧

🗺️ Mira y reporta cómo está el agua en tu colonia: ` + base + `/reportes
📢 Exígele a quien le toca que lo arregle: ` + base + `/exige
📍 Manda tu *ubicación* o el *nombre de tu colonia*: te digo tu zona y te suscribo a sus avisos
🔢 *ZONA 1* a *ZONA 7*: suscribirte o cambiar de zona
📝 *REPORTAR*: contar cómo regresó el agua después del último corte
🚚 *PIPA*: cómo pedir una pipa
` + write + `🛑 *BAJA*: dejar de recibir avisos y borrar tus datos

🗺️ Mapa oficial del SIAPA: ` + MapURL + `
🔒 Aviso de privacidad: ` + base + `/privacidad`
}

// msgUseButtons answers a typed «sí», «ya no» or «poca»: the buttons carry the answer, and the
// bot can't tell whether it answers a reminder or «¿Es la tuya?» about a colonia.
const msgUseButtons = `Para contestar, toca uno de los botones del mensaje 👆

Si es sobre tu colonia, mándame tu 📍 *ubicación* o escribe su nombre de otra forma.

Si lo que quieres es dejar de recibir avisos, escribe *BAJA*. Para ver todo lo que puedo hacer, escribe *AYUDA*.`

// msgCancelled answers «cancelar», typed to back out of a list rather than to unsubscribe.
const msgCancelled = `Listo, no cambié nada.

Si lo que quieres es dejar de recibir avisos y borrar tus datos, escribe *BAJA*. Para ver todo lo que puedo hacer, escribe *AYUDA*.`

// echoed drops the * and _ from what someone typed before it's shown back, so it can't turn
// into bold or italics (on Telegram, tags that don't nest and a refused message).
var echoed = strings.NewReplacer("*", "", "_", "")

func msgNotFound(q string) string {
	return fmt.Sprintf(`No encontré «%s» en la lista de colonias del SIAPA 😕

Puede que tu colonia no esté en la rotación. Para revisarlo, mándame tu 📍 *ubicación* o consulta el mapa oficial: %s`, strings.TrimSpace(echoed.Replace(q)), MapURL)
}

const msgOutside = `Tu ubicación no cae en ninguna zona del mapa del SIAPA.

Puede que no te toque la rotación, pero el mapa y la lista de colonias del SIAPA no siempre coinciden. Para revisarlo, mándame el *nombre de tu colonia* o, si ya sabes tu zona, escribe por ejemplo *ZONA 4*.

🗺️ Mapa oficial: ` + MapURL

// msgColoniaOutside is msgOutside for a colonia on SIAPA's list without a zone the rotation has days for.
func msgColoniaOutside(name string) string {
	return fmt.Sprintf(`No tengo días de corte para *%s* en el calendario del SIAPA 😕

Puede que no le toque la rotación, pero el mapa y la lista de colonias del SIAPA no siempre coinciden. Para revisarlo, mándame tu 📍 *ubicación* o consulta el mapa oficial: %s`, name, MapURL)
}

func msgMunicipio(name string) string {
	return fmt.Sprintf(`*%s* tiene colonias en varias zonas de la rotación 🤔

Mándame tu 📍 *ubicación* o el *nombre de tu colonia*, por ejemplo: _Las Juntas_`, name)
}

const msgPickColonia = "Encontré varias colonias parecidas. ¿Cuál es la tuya? 👇"

const msgPickOneColonia = "Encontré una colonia parecida. ¿Es la tuya? 👇"

// msgOtherColonia is for a colonia that exists but isn't on SIAPA's rotation list;
// mun is its municipio as people write it, and zones the zones whose map area it overlaps.
func msgOtherColonia(name, mun string, zones []int) string {
	if len(zones) == 0 {
		return fmt.Sprintf("✅ *%s* (%s) no está en la lista de colonias de la rotación del SIAPA y queda fuera de las zonas de su mapa, así que no le toca racionamiento.", name, mun)
	}
	return fmt.Sprintf("⚠️ *%s* (%s) no está en la lista de colonias de la rotación del SIAPA, pero queda dentro del mapa de %s. El mapa y la lista no siempre coinciden: mándame tu 📍 *ubicación* para confirmarlo.", name, mun, theZoneLabel(zones))
}

const msgOrOneOfThese = "¿O es alguna de estas? 👇"

const msgOrThisOne = "¿O es esta? 👇"

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
// msgPipa gives SIAPA's own line for a free pipa (siapa.gob.mx/medios-para-solicitar-una-pipa,
// checked 20 Oct 2026); the municipios' lines, with their sources, are on /pipas.
func msgPipa(base string) string {
	return `🚚 Para pedir una *pipa* gratis, llama al SIAPATEL: *33 3668 2482* o *073*, las 24 horas. Ten a la mano tu domicilio y tu número de cuenta del SIAPA.

Zapopan, Tlaquepaque y Tonalá también tienen líneas propias: ` + base + `/pipas

Agua GDL no es del SIAPA y no puede mandar pipas.`
}

func msgWrite(base string) string {
	return `✉️ Pídeles a las y los 38 diputados del Congreso de Jalisco que voten en contra del contrato APP del acueducto Chapala–Guadalajara, por correo, X o Messenger desde tu propia cuenta. Ahí también puedes firmar la solicitud de Contraloría Social en el IEPC:

` + base + `/escribe

📢 Y exígele al gobernador, al SIAPA, a la CEA y a tu presidencia municipal que arreglen el agua de tu colonia:

` + base + `/exige

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
	{"si", "✅ Sí", "🙏 ¡Gracias! Aprovecha para llenar tu tinaco y tus garrafones mientras tengas agua."},
	{"poca", "🟡 Poca", "🙏 ¡Gracias! Llena lo que puedas mientras salga."},
	{"no", "❌ No", "🙏 Gracias por avisarnos: nos ayuda a avisar con más tiempo."},
}

var reportAnswers = []struct{ key, title string }{
	{"normal", "✅ Regresó normal"},
	{"baja", "🟡 Poca presión"}, // not «Baja…»: a typed «baja» is BAJA
	{"no_regreso", "❌ No ha regresado"},
	{"turbia", "🟤 Turbia o con olor"},
}

type subscribedInfo struct {
	zone         int
	days         string
	fresh        bool
	cutTomorrow  []time.Time // set when no reminder comes for tomorrow's cut: tonight's run has passed or it continues a block
	cutsLeft     []time.Time // the rest of the block under way, from today: no reminder comes for them
	off          bool        // reminders are switched off on the server
	over         bool        // the rotation has ended: zone changes are refused, BAJA still works
	nextReminder string
	nextCut      []time.Time // the block the next message is about
	hour         string
	base         string
	channel      string
}

func msgSubscribed(i subscribedInfo) string {
	var b strings.Builder
	if i.fresh {
		fmt.Fprintf(&b, "✅ ¡Listo! Te avisaré de los cortes de agua de la *Zona %d*: %s.\n\n", i.zone, whenES(i.channel))
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
	case i.off && !i.over:
		b.WriteString("🔔 Los avisos automáticos empiezan en unos días.\n")
	case i.nextReminder != "":
		fmt.Fprintf(&b, "🔔 Próximo aviso: *%s, %s* (%s)\n", i.nextReminder, i.hour, cutsES(i.nextCut))
	default:
		b.WriteString("🔔 Por ahora no hay más cortes programados en tu zona.\n")
	}
	commands := "Escribe *ZONA 1* a *ZONA 7* para cambiar de zona o *BAJA* para dejar de recibir avisos."
	if i.over {
		commands = "Escribe *BAJA* para borrar tu suscripción."
	}
	fmt.Fprintf(&b, "\n🗺️ ¿Cómo está el agua en tu colonia? Repórtalo y mira la de tus vecinos: %s/reportes\n📢 Exígele a quien le toca que lo arregle: %[1]s/exige\n%s\n🔒 Guardamos %s, tu zona y tus reportes. Todo lo que guardamos: %s/privacidad", i.base, commands, storedID(i.channel), i.base)
	return b.String()
}

func storedID(channel string) string {
	if channel == store.Telegram {
		return "tu ID de usuario de Telegram (no tu teléfono)"
	}
	return "tu número de WhatsApp"
}

const msgAskPlace = "Para elegir tu zona, mándame tu 📍 *ubicación*, el *nombre de tu colonia* o tu zona, por ejemplo: *ZONA 4*"

// ScheduleChange is cambio_rotacion's wording, for channels without templates.
func ScheduleChange(zone int, days, from string) string {
	return fmt.Sprintf(`⚠️ *Cambio en la rotación de la Zona %d*

El SIAPA cambió los días de racionamiento. Ahora son: *%s*, a partir del %s.

Te seguiré avisando antes de los cortes 💧

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
	coming := "Se acerca el corte"
	if len(days) > 1 {
		coming = "Se acercan los cortes"
	}
	return fmt.Sprintf(`🔔 *%s en la Zona %d:* según el calendario del SIAPA, el *%s*.

Vecinos nos cuentan que el agua se va desde un día antes y tarda más en volver. Si todavía tienes, llena con tiempo tu tinaco, cubetas y garrafones, y tápalos bien.

*¿Ahorita tienes agua?* Si ya se te fue, avísanos 👇

ℹ️ Aviso ciudadano, no oficial. Confirma tu colonia en el mapa del SIAPA.`, coming, zone, rotation.DatesES(days))
}

// msgFollowUp asks, the evening after a block, whoever said they had no water or little.
func msgFollowUp(days []time.Time, zone int) string {
	return fmt.Sprintf(`💧 *¿Ya regresó el agua?* Nos dijiste que te faltaba antes del corte de la *Zona %d* (%s).

Cuéntanos cómo está ahora 👇`, zone, rotation.DatesES(days))
}

// msgReportMap points whoever answered «No» or «Poca» to the map of neighbours' reports and to /exige.
func msgReportMap(base string) string {
	return "\n\n🗺️ Mira y reporta cómo está el agua en tu colonia: " + base + "/reportes\n📢 Exígele a quien le toca que lo arregle: " + base + "/exige"
}

// AvisosChange tells a zone's Telegram subscribers, once, about the notice two days before each
// block of cuts. It lists the zone's cuts for the coming week: a block already under way when the
// change is deployed got the old reminder, which named only its first day.
func AvisosChange(base string, zone int, next []time.Time) string {
	coming := ""
	if len(next) > 0 {
		coming = fmt.Sprintf("📅 Tus próximos cortes (Zona %d): *%s*.\n\n", zone, rotation.DatesES(next))
	}
	return `📣 *Cambiamos los avisos de Agua GDL*

Vecinos nos contaron que el agua se va desde antes del corte y tarda más en volver. Por eso, desde ahora:

🔔 Te avisamos *dos días antes* de los cortes y otra vez la noche antes. Si tu zona tiene cortes seguidos (con uno o ningún día de por medio), una vez por tanda, antes del primero.
💧 Te preguntamos si todavía tienes agua. Si ya se te fue, no te mandamos el aviso de la noche antes. Si no tienes o tienes poca, después de la tanda te preguntamos si ya regresó, salvo que esa noche te llegue el aviso de la siguiente.

` + coming + `Si prefieres no recibirlos, escribe *BAJA*. Todo lo que guardamos: ` + base + `/privacidad`
}

// msgTelegramReminder is the reminder for the block of cuts that starts tomorrow; it goes
// with buttons to answer whether the water is still on, for the map and for BAJA. Unlike
// WhatsApp's approved template, it doesn't repeat SIAPA's account as fact.
func msgTelegramReminder(days []time.Time, zone int) string {
	return fmt.Sprintf(`💧 La *Zona %d* tiene corte *mañana %s*%s, según el calendario del SIAPA.

El SIAPA dice que los racionamientos son «por máximo un día» y que «no serán cortes totales», pero vecinos nos cuentan que el agua se va desde antes y tarda más en volver.

🪣 Si todavía tienes agua, llena tu tinaco, cubetas y garrafones, y tápalos bien.

*¿Ahorita tienes agua?* Tu respuesta nos ayuda a avisar mejor 👇

ℹ️ Aviso ciudadano, no oficial. Confirma tu colonia en el mapa del SIAPA.`, zone, rotation.DateES(days[0]), alsoES(days))
}

// Button and list labels.
const (
	labelSeeColonias  = "Ver colonias"
	labelPickZone     = "Elegir zona"
	labelPickAnswer   = "Elegir respuesta"
	labelSendLocation = "📍 Mandar mi ubicación"
	labelSIAPAMap     = "🗺️ Mapa del SIAPA"
	labelStop         = "Dejar de recibir avisos"
)

func zoneTitle(zone int) string { return fmt.Sprintf("Zona %d", zone) }

func zoneDays(days string) string { return "Cortes: " + days }

// zoneLabel is "zona 3" or "zonas 1, 5 y 6"; theZoneLabel adds the article.
func zoneLabel(zones []int) string {
	if len(zones) == 1 {
		return "zona " + zoneList(zones)
	}
	return "zonas " + zoneList(zones)
}

func theZoneLabel(zones []int) string {
	if len(zones) == 1 {
		return "la " + zoneLabel(zones)
	}
	return "las " + zoneLabel(zones)
}

func zoneList(zones []int) string {
	s := make([]string, len(zones))
	for i, z := range zones {
		s[i] = strconv.Itoa(z)
	}
	if len(s) < 2 {
		return strings.Join(s, "")
	}
	return strings.Join(s[:len(s)-1], ", ") + " y " + s[len(s)-1]
}

// reminderBody is the text of WhatsApp's approved aviso_corte template.
func reminderBody(date string, zone int) string {
	return fmt.Sprintf(`💧 *Mañana %s* hay racionamiento de agua en la *Zona %d* por la rotación del SIAPA: puede bajar la presión o faltar el agua hasta por un día.

🪣 Llena hoy tu tinaco, cubetas y garrafones.
🔒 Tapa bien los recipientes para que el agua no se ensucie.`, date, zone)
}
