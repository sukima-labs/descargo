# Plan de promoción

**Versión del 11-11-2026.** Parte de [ANALISIS.md](ANALISIS.md); los límites están en
[GUARDARRAILES.md](GUARDARRAILES.md). Coste previsto: **0 €** (solo trabajo y herramientas
que ya existen).

## Objetivo

> Que un estudiante hispanohablante que recibe un aviso de un detector encuentre Descargo
> **antes de hacer algo irreversible**, y que defensorías, representaciones estudiantiles y
> comunidad técnica lo conozcan y lo recomienden, sin prometer más de lo que hace.

### Metas (hipótesis que se revisan el 28-02-2027, tras medir un mes entero)

| Meta | Cómo se mide ([MEDICION.md](MEDICION.md)) | Hoy |
|---|---|---|
| Las 6 guías de país, encontrables en buscadores | Páginas con impresiones en Search Console | 0 (no tienen URL propia) |
| ≥ 1.000 impresiones al mes en buscadores | Search Console | 0 |
| ≥ 200 visitantes únicos del repositorio cada 14 días | `gh api …/traffic/views` | 1 |
| ≥ 30 estrellas y ≥ 2 contribuyentes ajenos (issue o PR útil) | GitHub | 1 y 0 |
| ≥ 10 mensajes de comentarios con datos de instituciones (ADR 008) | Pestaña «Enviar comentarios» → buzón | 0 (no hay buzón) |
| ≥ 3 intermediarios (defensoría, representación estudiantil, asesoría, biblioteca) que enlazan o derivan | Registro | 0 |

Las cifras son prudentes a propósito. Una promoción sin analítica no puede medir
«usuarios»; mide señales públicas y aprendizaje.

## Estrategia en una frase

**Primero la puerta, después el altavoz.** El mayor retorno no está en publicar más, sino en
que quien llegue encuentre qué hacer, pueda responder y pueda ser encontrado por Google.
Después, pocos canales y atendidos, con cara descubierta.

## Fases y puertas

### Fase 0: la puerta (11-11 → 24-11-2026)

Todo es trabajo por PR en el repositorio y en la web. Salida: se cumplen las cuatro puertas.

| # | Trabajo | Issue | Quién |
|---|---|---|---|
| 0.1 | **Camino «me han marcado»**: antes del texto largo, cuatro tarjetas (según tu caso) que llevan a la acción; resumen de «qué es» plegado | #39 · **hecho** (#47) | Claude (PR) |
| 0.2 | **Demostración sin informe real**: botón «probar con un informe de ejemplo» con un informe, un trabajo y declaraciones sintéticos (`web/demo/`) | #40 · **hecho** (#49) | Claude (PR) |
| 0.3 | **Páginas estáticas por país e idioma** (`/guias/<país>/`) generadas en la compilación, con título y descripción propios, sin JavaScript necesario y con la fecha de comprobación visible; se añaden a `sitemap.xml` de la portada | #41 · **hecho** (#46; sitemap de la portada `cc4cdb1`) | Claude (PR en descargo y en la portada) |
| 0.3b | Pedir a `maquina` la indexación de esas URL en Search Console | **hecho** el 11-11: sitemap reenviado e indexación pedida de las dos listas | Claude → `maquina` (inglés) |
| 0.4 | **Buzón de comentarios** (#24): decide Patricio cuál; después se rellena `FEEDBACK_EMAIL` | #24 · **pendiente**: alias `descargo@jirulabs.com` propuesto; Patricio debe crearlo en Infomaniak y `maquina` confirmarlo. No se publica la dirección antes | Decisión de Patricio; PR de Claude |
| 0.5 | **Reglas de contenido legal**: cada guía muestra de forma visible qué partes están por verificar (ya lo hace) y se revisa que ningún texto de promoción dé plazos sin enlace | #21 | Claude |
| 0.6 | **README de la primera pantalla**: tres líneas, el enlace a la web y el aviso del estado; lo demás, más abajo | #42 · **hecho** (#48) | Claude (PR) |
| 0.7 | **Primera instantánea** de métricas y línea base en [metricas.csv](metricas.csv) | — | Claude (hecho el 11-11) |

**Puertas para pasar a la fase 1** (todas):

1. 0.1 y 0.3 integrados y comprobados en la web pública con el Chrome de browserhub.
2. Buzón (#24) elegido y funcionando.
3. Ningún texto de la fase 1 contradice [GUARDARRAILES.md](GUARDARRAILES.md) (revisión de los borradores).
4. La #20 (Chile) comprobada el 24-11; si se pospone la Ley 21.719, la guía de Chile está al día antes de promocionarla.

### Fase 1: lanzamiento suave (25-11 → 15-12-2026)

Pocas personas y muy buenas. Se aprende antes de ampliar.

| Canal | Qué | Textos |
|---|---|---|
| **Ya en contacto** (grupo de estudiantes y testers de Colombia) | Aviso de la nueva versión y petición de comentarios | [mensaje-testers](plantillas/mensaje-testers.md) |
| **Intermediarios** (defensorías, representaciones estudiantiles, asesorías de tesis, bibliotecas) | Presentación breve y enlace a la guía de su país. Empezar por Colombia y España | [mensaje-intermediarios](plantillas/mensaje-intermediarios.md) |
| **Comunidad técnica** | Anuncio en la plataforma de proyectos abiertos (p. ej. Show HN), con el aviso de prealfa; issues `good first issue` abiertos para adaptadores, paquetes legales y perfiles | [show-hn](plantillas/show-hn.md) |
| **Comunidades de estudiantes** | Un mensaje por comunidad, con cara descubierta, tras leer su norma | [anuncio-comunidad](plantillas/anuncio-comunidad.md) |

**Puerta para pasar a la fase 2:** 3 semanas de datos; al menos 5 comentarios leídos y
respondidos; ninguna queja grave sin resolver (sobre todo, sobre un error en una guía).

### Fase 2: contenido orgánico (16-12-2026 → 28-02-2027)

Coincide con entregas de fin de curso y con las convocatorias de TFG de enero-febrero (ver el
calendario como inferencia en [ANALISIS.md](ANALISIS.md)).

- Una página corta por **pregunta real** que se haya visto en los comentarios o en Search
  Console («qué es el asterisco del informe», «cómo pedir el informe de similitud», «qué
  plazo tengo»), siempre enlazando la guía del país. **Sin producción en serie**: solo lo que
  se pueda comprobar con una fuente.
- Una **nota de prensa** para medios de educación, privacidad y tecnología
  ([nota-de-prensa](plantillas/nota-de-prensa.md)), solo si hay datos propios que contar.
- Si la fase 1 trajo intermediarios, una charla o seminario breve con una representación
  estudiantil.
- **Fase 2 del producto** (historial del proceso de escritura): cuando exista, cambia el
  mensaje de «defensa» a «prevención» y se anuncia aparte.

### Fase 3: revisión (28-02-2027)

Se comparan las metas con las cifras, se cierran los canales que no han dado nada y se
decide si se mantiene, se amplía o se para. Resultado: una nota en el vault y una revisión de
este plan por PR.

## Calendario

| Fecha | Hito |
|---|---|
| 11-11 | Módulo y análisis (este PR); issues y tablero; primera instantánea de métricas |
| 11-11 → 17-11 | 0.1, 0.2 y 0.6 |
| 17-11 → 24-11 | 0.3 y 0.3b; #24 resuelto |
| **24-11** | Revisión de las puertas; comprobación de la #20 |
| 25-11 | Si se cumplen las puertas: empieza la fase 1 |
| Cada lunes | Instantánea de métricas |
| 01-12 | Fecha de la Ley 21.719 (Chile): solo se usa en mensajes si la #20 sigue en pie |
| 15-12 | Revisión de la fase 1 |
| 28-02-2027 | Revisión de las metas y decisión |

## Cómo se ejecuta (herramientas)

| Tarea | Herramienta | Límite |
|---|---|---|
| Cambios en la web, README y guías | PR en `sukima-labs/descargo`; CI y Pages | Los integra Claude con CI en verde |
| Comprobar la web publicada, en escritorio y móvil | Chrome de browserhub | Solo puerto 8040 para pruebas locales; la web pública, directa |
| Leer páginas que dan 403 o piden JavaScript | Extensión de Claude en el Brave de Patricio | Algunos sitios los bloquea la propia extensión (Reddit); no se rodea |
| Buscar y vigilar el tema | SearXNG propio | No abusar de Brave (429) |
| Métricas públicas | `gh api` | La ventana de tráfico es de 14 días: instantánea semanal |
| Indexación y consultas de búsqueda | `maquina` (Search Console, Cloudflare) | Se le pide en inglés, por mensaje |
| Estado y decisiones | Issues y tablero (canal común) y la nota privada del vault | Sin contactos personales en el repositorio |
| Publicar con el nombre de Patricio o de Sukima Labs | Navegador de Patricio, solo en canales permitidos | Primera vez por canal, sobre el texto exacto, con su aprobación ([GUARDARRAILES.md](GUARDARRAILES.md) §7) |

Lo que **ninguna** herramienta mía puede hacer: crear cuentas, usar Reddit, escribir en
WhatsApp o Telegram, enviar correo desde un buzón que no esté decidido. Los textos para esos
canales se dejan preparados en [plantillas/](plantillas/) y [CANALES.md](CANALES.md) dice por
qué cada uno queda fuera.

## Decisiones que son de Patricio (una vez, no tareas)

1. **Buzón de comentarios** (#24): cuál es.
2. **Aprobar el paquete de textos** de la fase 1 para poder publicarlos con su nombre.
3. **Ajustes del repositorio**: activar Discussions y subir la imagen de vista previa social
   (`web/og.jpg`) en la configuración de GitHub. Son ajustes suyos.
