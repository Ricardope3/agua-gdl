"""Copy rules shared by pipelines/promesas.py, scripts/lint_copy.py and scripts/check_known_errors.py."""
import re
import unicodedata

# Wording that claims intent; allowed only inside a quote. Matched against plain() text.
BANNED = re.compile(r"\b(miente|mienten|mintio|mintieron|mintiendo|mentira|mentiras|engana|enganan|enganando|engano|enganaron|traiciono|traicionaron)\b")

# Errors we published or filed once and must not repeat. Each is matched per line against fold()
# text: `wrong` must match, `near` (if set) must match the same line, and a line matching `ok`
# (the correct form, or text that discusses the error) passes. Add one whenever a fact-check
# finds an error that could come back; `bad` and `good` are examples test_copy_rules.py checks.
KNOWN_ERRORS = [
    dict(id="ut329-adaptadas",
         bad='de la orden dice que se adoptó «a partir de consultas realizadas con expertos en la materia»', good='de la orden dice que «fueron adaptadas medidas a partir de consultas realizadas con expertos en la materia»',
         wrong=r"\badopt\w*", near=r"expert|ut-?329|0217|consultas realizadas", ok=r"adaptad",
         msg="the CEA oficio UT-329 says «fueron adaptadas medidas», not adopted",
         found="2 Nov 2026; recurred 3 Nov on /promesas"),
    dict(id="rotation-end",
         bad='Vigencia: 15 de octubre de 2026 a 31 de marzo de 2027.', good='Vigencia: desde el 15 de octubre de 2026, hasta marzo de 2027.',
         wrong=r"31 de marzo,? del? 2027|31 mar\w*\.? 2027|mar\w* 31,? 2027|31/0?3/2027",
         ok=r"supuest|assum|asumid|hasta marzo|tomamos|seguimos|our reading|nuestra lectura|success|`end`",
         msg="SIAPA says «hasta marzo de 2027»; 31 March is our assumption, not a stated date",
         found="3 Nov 2026"),
    dict(id="corte-promise",
         bad='El SIAPA prometió que cada corte duraría «por máximo un día».', good='El Gobierno de Jalisco prometió que cada racionamiento duraría «por máximo un día».',
         wrong=r"\bcortes?\b[^«»]{0,30}«?(por )?maximo",
         msg="the promise is about «racionamientos» and says «No serán cortes totales»; don't put «corte» beside «por máximo un día»",
         found="3 Nov 2026"),
    dict(id="zamora-david",
         bad='David Zamora, secretario general de Gobierno', good='David Zamora, secretario de Infraestructura y Obra Pública (SIOP)',
         wrong=r"david zamora[^.;|)]{0,40}secretari\w* general",
         msg="David Zamora is SIOP; the Secretario General is Salvador Zamora",
         found="2 Nov 2026"),
    dict(id="zamora-salvador",
         bad='Salvador Zamora, titular de la SIOP', good='Salvador Zamora, secretario general de Gobierno',
         wrong=r"salvador zamora[^.;|)]{0,40}\bsiop\b",
         msg="Salvador Zamora is the Secretario General; SIOP is David Zamora",
         found="2 Nov 2026"),
    dict(id="granja-53-colonias",
         bad='Ciudad Granja aparece entre 53 colonias atendidas por 22 pipas.', good='En una nota sobre 22 pipas que atienden 53 colonias de Guadalajara, La Silla Rota menciona a Ciudad Granja.',
         wrong=r"53 colonias", near=r"granja", ok=r"de guadalajara",
         msg="La Silla Rota's 22 pipas serve 53 colonias de Guadalajara; Ciudad Granja (Zapopan) is only named as reporting shortages",
         found="3 Nov 2026"),
    dict(id="congreso-turno-app",
         bad='El 23 de octubre, el Congreso ya no turnó a comisiones la iniciativa de la APP.', good='El 21 de octubre, la presidenta anunció que la Federación pondrá entre 12 mil y 13 mil millones para el acueducto.',
         wrong=r"(ya no|dejo de) (turn|procesar)\w*[^.;]{0,30} comisiones|stopped processing the app",
         msg="no source says Congress stopped turning the APP to committee on 23 Oct; the cited Crónica story is about something else",
         found="3 Nov 2026 (fact-check #7)"),
    dict(id="rotation-promise-siapa",
         bad='El SIAPA prometió racionamientos «por máximo un día».', good='El Gobierno de Jalisco prometió racionamientos «por máximo un día».',
         wrong=r"siapa(</a>)? (prometio|dijo|dice|anuncio)[^.;]{0,40}(un dia|cortes totales|racionamiento)|prometio el siapa|(segun|dice) el siapa[^.;]{0,40}(maximo un dia|cortes totales|racionamientos? (dura|por semana))|(maximo un dia|cortes totales|racionamiento)»?[^.;]{0,30}segun el siapa|segun el <a[^>]*rotaciondeservicio[^>]*>siapa</a>",
         ok=r"sistema|director|ajustar|tandeo|lista",
         msg="the rotation page that promises «por máximo un día» and «no serán cortes totales» speaks as the Gobierno de Jalisco, not SIAPA",
         found="3 Nov 2026 (fact-check #5); still on 2,238 pages, the bot and the calendars on 4 Nov"),
    dict(id="dos-a-tres-presente",
         bad='Según el SIAPA, cada zona tiene de 2 a 3 racionamientos por semana.', good='El Gobierno de Jalisco prometió de 2 a 3 racionamientos por semana; desde el 3 de noviembre su calendario marca cuatro días a las zonas 1, 2, 4 y 5.',
         wrong=r"cada zona tiene (de )?(2|dos) (a|y) (3|tres)|tiene entre (2|dos) y (3|tres) racionamientos|each zone has 2 to 3",
         msg="«de 2 a 3 racionamientos» is the promise; since 4 Nov zones 1, 2, 4 and 5 have four cut days",
         found="4 Nov 2026 (error hunt)"),
    dict(id="exhorto-seis",
         bad='MC votó en contra del exhorto para indemnizar a las seis personas detenidas.', good='MC votó en contra del exhorto para indemnizar a las personas detenidas y golpeadas el 11 de octubre.',
         wrong=r"exhorto[^.;]{0,40}indemniz\w*[^.;]{0,20}\b(seis|6)\b",
         msg="per Nación321 the approved exhorto covers the people «detenidas y golpeadas»; the six are the separate request to the Fiscalía",
         found="3 Nov 2026 (fact-check #8)"),
    dict(id="rotation-site-siapa",
         bad='los archivos que su sitio de rotación publica', good='los archivos con su nombre que publica el sitio de rotación al que remite',
         wrong=r"su (sitio|portal|pagina) (oficial )?de rotacion|(sitio|portal|pagina)( web| oficial)? de rotacion (de|del) siapa|siapa publica y actualiza|siapa (publica|habilito)[^.;]{0,30}(sitio|lista|mapa)",
         ok=r"refuted|gobierno de jalisco[^.;]{0,40}habilito|credits the site to the state",
         msg="SIAPA's 15 Oct bulletin says the Gobierno de Jalisco «habilitó un sitio de consulta»; SIAPA only links to it",
         found="4 Nov 2026 (transparency dodge review: R4 plan row and note)"),
]


def plain(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold()


def fold(s):
    """plain() that keeps «» and other non-accent symbols."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold()


_KNOWN = [(e, re.compile(e["wrong"]), re.compile(e.get("near") or ""), re.compile(e.get("ok") or r"(?!)"))
          for e in KNOWN_ERRORS]


def known_errors(line):
    """(entry, match) for each KNOWN_ERRORS entry the line repeats."""
    p = fold(line)
    return [(e, m) for e, wrong, near, ok in _KNOWN
            if (m := wrong.search(p)) and near.search(p) and not ok.search(p)]
