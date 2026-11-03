# Glosario

What words mean here. Rules for each field are in `.claude/rules/evidence.md`; this file only fixes meanings.

## `web/publicaciones.json` fields

- `fuente`: `medio` (news outlet, counts without a threshold) or `vecinos` (neighbours' post, needs `regla`).
- `quien`: who published it: the outlet, «Grupo «…»» or «Cuenta de vecinos …». Never a private person's name.
- `dias`: days without water the source itself gives; `null` when it gives none. Not our estimate.
- `regreso`: ISO date the source says the water came back. The source's claim, not a confirmation.
- `parcial`: the source reports low or intermittent supply, not none.
- `calidad`: the complaint is about water quality only, not about missing water.
- `causa`: the cause the source names (1–80 chars), in its terms. Not ours.
- `bloqueo`: the source reports a street blockade.
- `eco`: the post's reactions, comments and shares, with the date they were read.
- `de`: the post a story retells; the story counts as that post's source.
- `en`: the post a neighbour's comment sits in (`tipo: comentario`); the comment counts only if `en` meets the rule.
- `vista`: our 480 px JPEG of the post's preview in `web/fuentes/`; `null` for a logo or stock picture.
- `captura`: our screenshot of the top of a news article (`web/fuentes/<hash>-t.jpg`). In `promesas.json`, `"captura": "privada"` instead means a private copy in the notes repo.

## SIAPA's terms: quote them, don't paraphrase

- «racionamiento(s)», «por máximo un día», «no serán cortes totales», «disminución de la presión», «menos agua pero de mejor calidad». Put them in «…» and say they are SIAPA's; neighbours' reports stay theirs.

## Pairs agents got wrong (from git log)

| Write | Not | Commit |
|---|---|---|
| avisos «de los cortes», «una vez por tanda cuando los cortes van seguidos» | «de cada corte» | 922b162 |
| SIAPA: «por máximo un día», «no serán cortes totales» (quoted) | «solo baja la presión y por un día» | 922b162 |
| «ID de usuario de Telegram» | «ID de chat» | 922b162, e7a6bb9 |
| te suscribes al mandar ubicación, colonia o zona | aceptas al tocar «Iniciar» | e7a6bb9 |
| hashes / con hash | «cifradas» | e7a6bb9 |
| «proceso» | «juicio» | 69d703d |
| «20 o 25 años» (the APP term) | «25 años» | 69d703d |
| «territorios palestinos ocupados» (Amnistía's scope) | «Cisjordania» | 69d703d |
| figures credited to who gave them («según la oposición») | figures as fact | 69d703d |
| CEA (UT-329): «fueron adaptadas medidas» | «adoptó», «adopted» | 3 Nov fact-check |
| the rotation runs «hasta marzo de 2027» (31 Mar is our assumption) | «termina el 31 de marzo de 2027» | 3 Nov fact-check |
| «racionamiento» beside «por máximo un día» | «corte» beside it | 3 Nov fact-check |
