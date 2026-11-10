# Medición

Descargo **no tiene analítica y no la va a tener** para medir la promoción
([ADR 001](../docs/adr/001-local-first.md)): nada de cookies, píxeles, parámetros de
seguimiento ni acortadores. Se mide solo con lo que ya es público o llega por decisión de
quien escribe.

## Qué se mide

| Señal | De dónde sale | Frecuencia | Qué dice (y qué no) |
|---|---|---|---|
| Estrellas, forks, seguidores | GitHub | Semanal | Interés de la comunidad técnica; no son usuarios |
| Visitas y visitantes únicos del repositorio | `gh api repos/sukima-labs/descargo/traffic/views` | Semanal; **GitHub solo guarda 14 días** | Alcance del repositorio |
| Referentes (de dónde llega la gente) | `…/traffic/popular/referrers` | Semanal | Qué canal funciona. Solo el repositorio; la web no registra nada |
| Clones | `…/traffic/clones` | Semanal | **Ruidoso**: incluye el CI y robots (403 clones y 100 únicos el 11-11 con 1 visita). No es una meta |
| Issues y PR de gente ajena | GitHub | Semanal | Contribución real |
| Impresiones, clics y consultas por página | Search Console (lo gestiona `maquina`) | Mensual, tras la indexación de las páginas por país | La señal más útil del canal orgánico: qué preguntas llegan |
| Mensajes de la pestaña «Enviar comentarios» | Buzón (#24) | Cada vez que llega uno | Calidad: qué falta, qué falló, datos de instituciones. Se resume sin datos personales |
| Enlaces entrantes y menciones | Búsqueda del nombre «Descargo» con «Turnitin» o «detector» | Mensual | Reputación |

**No se mide y no se afirma**: número de usuarios, de informes auditados, de estudiantes
ayudados ni tasas de éxito. No hay forma honesta de saberlo sin recoger datos.

## Instantánea semanal

Cada lunes, en una sola pasada, se añade una línea a [metricas.csv](metricas.csv):

```bash
R=sukima-labs/descargo
gh api repos/$R --jq '[.stargazers_count,.forks_count,.subscribers_count]|@csv'
gh api repos/$R/traffic/views  --jq '[.count,.uniques]|@csv'
gh api repos/$R/traffic/clones --jq '[.count,.uniques]|@csv'
gh api repos/$R/traffic/popular/referrers --jq '[.[]|"\(.referrer):\(.uniques)"]|join(";")'
```

Las columnas están en la primera línea del CSV. Solo cifras públicas, nunca nombres ni
direcciones.

## Cómo se lee

- Una semana no dice nada; se miran tendencias de 4 semanas.
- Una subida sin canal que la explique (por ejemplo, un enlace de un tercero) se anota en
  [REGISTRO.md](REGISTRO.md) para saber de dónde vino.
- Las metas de [PLAN.md](PLAN.md) son hipótesis. Se revisan el 28-02-2027 con al menos un mes
  de datos con las páginas por país ya indexadas.

## Cómo se sabe si algo ha ido mal

| Alarma | Qué hacer |
|---|---|
| Un comentario o issue dice que un plazo o un artículo de una guía es erróneo | Comprobar la fuente el mismo día; corregir la guía y su inglés por PR; anotarlo en el CHANGELOG; si es grave, avisar en el canal donde se anunció |
| Quejas por spam o por mensajes no pedidos | Parar ese canal, responder con una disculpa breve y anotar la lección en [REGISTRO.md](REGISTRO.md) |
| Alguien comparte datos de un caso en un comentario | No usarlo, no reenviarlo y borrarlo de donde se pueda; recordar que no se piden |
