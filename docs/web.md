# La versión para el navegador

*Español · [English](en/web.md)*

Descargo también funciona como página web: el mismo código Python, en tu navegador, a
través de [Pyodide](https://pyodide.org/). No hay ningún servidor detrás. La página es un
conjunto de archivos estáticos; tus archivos y tus datos se quedan dentro de la pestaña del
navegador y desaparecen al cerrarla o recargarla. Ver el [ADR 007](adr/007-web-build.md).

Ofrece tres de los comandos de la CLI y las guías de procedimientos, en inglés y en español:

| Pestaña | Equivale a |
|---|---|
| «Antes de entregar» | `descargo inspect` |
| «Revisar un informe del detector» | `descargo audit` (e `import-report`: descargar el informe en JSON) |
| «Pedir el informe» | `descargo access-request`, con un formulario en lugar del archivo YAML; las opciones «No está en la lista: carta genérica» de cada país redactan la carta genérica (`--institution`) |
| «Si te acusan» | sin equivalente en la CLI: las guías de procedimientos de `docs/` (España, Colombia, México, Argentina, Chile y Perú), con el país a elegir |
| «Enviar comentarios» | sin equivalente en la CLI: un formulario breve que prepara un mensaje para que el estudiante lo copie o lo abra en su propio correo |

Encima de las pestañas, una breve introducción explica qué es Descargo, cómo usarlo, qué
informes lee hoy, qué no hace y que se trata de una versión de prueba.

Las guías salen de `docs/procedimientos*.md` y `docs/en/procedures*.md`: el build las
convierte en `guides.json`, una lista de bloques (títulos, párrafos, listas, tablas y
enlaces) que la página dibuja con llamadas al DOM, sin insertar HTML, como el resto de
resultados. La guía de España y Colombia se separa por país. Los enlaces a otra guía cambian
de país dentro de la página; los enlaces a otros archivos del repositorio llevan a GitHub, y
un test comprueba que cada enlace a un apartado existe. No necesitan Python: se cargan la
primera vez que se abre la pestaña.

El formulario de comentarios no necesita Python, así que funciona aunque la página no
consiga cargar. No se envía nada: el estudiante ve el mensaje completo, que solo lleva lo
que escribió, la versión y el idioma de la página y, si marca la casilla, el último mensaje
de estado de la página. Si no hay ninguna dirección configurada, la página le pide que lo
envíe a quien le pasó la página; configura `FEEDBACK_EMAIL` en `web/app.js` para ofrecer
además un enlace «Abrir en mi correo» (`mailto:`).

Cada resultado se puede descargar en Markdown y en PDF (el mismo PDF que escribe la CLI), y
la inspección y la auditoría también en JSON.

## Compilarla

```bash
uv run python scripts/build_web.py          # escribe build/web/ (unos 20 MB)
node tests/web/smoke.mjs build/web          # ejecuta Descargo en ese Pyodide (Node 18+)
```

La compilación descarga Pyodide y los paquetes wheel que necesita el navegador, comprueba
cada archivo con una huella SHA-256 fijada de antemano (el archivo tar de la versión de
Pyodide, el archivo de bloqueo de Pyodide y `uv.lock`) y guarda las descargas en caché en
`.cache/web/`. Es el único paso que usa la red; el sitio compilado no pide nada salvo sus
propios archivos.

`build/web/build.json` registra la versión de Descargo, el commit y la versión de Pyodide,
y la página los muestra en su pie. `build/web/SHA256SUMS` lista la huella de cada archivo,
para que cualquiera pueda comprobar que una copia publicada coincide con una compilación.

## Servirla

```bash
uv run python scripts/serve_web.py          # http://127.0.0.1:8040/
```

El servidor de desarrollo envía las cabeceras de seguridad y no guarda ningún registro de
accesos. Sirve cualquier alojamiento estático, incluidos los que no pueden enviar
cabeceras, como GitHub Pages, donde está la página pública
(`https://sukima-labs.github.io/descargo/`). La página lleva su
`Content-Security-Policy` en una etiqueta `<meta>`, y el Web Worker donde se ejecuta Python
arranca desde una URL `blob:`, que hereda esa política, así que un archivo solo puede
llegar al sitio del que vino. Abrir `index.html` desde el disco no funciona, porque los
navegadores no arrancan workers de módulo desde URL `file://`.

## Límites

- La primera visita descarga unos 20 MB; las siguientes usan la caché del navegador.
- En un archivo de declaraciones, da el texto de cada plantilla directamente (`text:`) o
  indica la fuente del informe (`source:`): la página no puede abrir un segundo archivo al
  que apunte `file:`.
- Solo están disponibles los perfiles de instituciones incluidos; `--profiles-dir` no tiene
  equivalente.
- La validación de perfiles y la lista de datos sin verificar se quedan en la CLI.
