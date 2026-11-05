# Escribir plantillas de documentos

*Español · [English](en/templates.md)*

Los paquetes de jurisdicción (`jurisdictions/<id>/`) contienen plantillas Jinja2 que
Descargo genera en el dispositivo del estudiante. Las plantillas se ejecutan en el
**entorno aislado** (sandbox) de Jinja2 con `StrictUndefined`: una variable mal escrita es
un error, no una cadena vacía.

## Reglas

- Escribe **solo la carta**. Descargo añade desde el código la nota para el estudiante al
  principio y el pie de «no es asesoramiento legal» al final; una plantilla no puede
  quitarlos.
- Mantén un tono objetivo. Una solicitud de acceso pide información; no defiende el caso.
- Cita solo disposiciones que estén listadas, con su fuente, en los `legal_bases` del
  paquete.
- Usa el subconjunto de Markdown que entiende el generador de PDF: encabezados con `#`,
  párrafos, listas con `1.` y `-`, `**negrita**` y una `\` al final para un salto de línea.
- Una plantilla por idioma (`access_request.<lang>.md.j2`). Un paquete que extiende otro
  hereda las plantillas del paquete padre para los idiomas que no define.

## Variables para `access_request`

| Variable | Tipo | Notas |
|---|---|---|
| `student.name`, `student.email` | str | siempre presentes |
| `student.student_id`, `student.identity_document`, `student.postal_address`, `student.programme` | str o none | opcionales |
| `request.submission_title`, `request.course` | str o none | opcionales |
| `request.extra_items` | lista de str | numéralos después de los puntos estándar |
| `submission_date` | str o none | ya formateada para el idioma de la carta |
| `tools` | lista de str | nombres para mostrar, p. ej. `Turnitin`; por defecto, las herramientas del perfil |
| `institution` | str | nombre de la institución según el perfil |
| `recipient` | contacto o none | se elige del perfil según los `recipient_roles` del paquete |
| `recipient_block` | str o none | nombre, dirección y correo unidos con saltos de línea |
| `date` | str | fecha de la carta, formateada para el idioma |
| `deadline` | objeto o none | el plazo de respuesta del paquete |
| `duration(deadline)` | función | p. ej. "one month", "10 días hábiles" |
| `localized(text)` | función | elige el idioma de la carta en un texto traducido del paquete |

## Añadir una jurisdicción

1. Crea `jurisdictions/<id>/pack.yaml` (esquema: `schemas/jurisdiction/0.1.json`), con
   `extends` si existe un paquete más general.
2. Cada base legal, plazo y autoridad es un dato: `source_url` a un texto **oficial**, una
   `quote` breve y literal, y `verification: needs_verification`, salvo que tú hayas
   comprobado la cita con la fuente (en ese caso, añade `checked_on`).
3. Añade una plantilla por idioma y ejecuta `uv run pytest`: cada plantilla se genera con
   datos del estudiante completos y mínimos, y el resultado debe llevar el aviso legal.
