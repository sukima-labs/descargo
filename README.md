# Descargo

*Español · [English](README.en.md)*

**Prueba de autoría.** Descargo es un conjunto de herramientas libre y local que ayuda a
estudiantes universitarios a defenderse de los **falsos positivos** de los detectores de
plagio y de textos escritos con IA (Turnitin, Compilatio, Copyleaks, SafeAssign,
StrikePlagiarism, GPTZero, Originality.ai, Pangram…). Sirve para trabajos, ensayos,
informes, trabajos de fin de grado y de máster (TFG, TFM), tesis de pregrado y maestría, y
tesis doctorales, en cualquier país. Está pensado primero para estudiantes que hablan
español.

> [!IMPORTANT]
> **Descargo no es asesoramiento legal.** Te ayuda a ordenar pruebas y a ejercer derechos
> que quizá ya tienes. Las leyes, los reglamentos universitarios y los plazos cambian y
> varían según el país, la institución y el caso. Comprueba las fuentes que cita y, si te
> juegas mucho, habla con la defensoría universitaria, la representación estudiantil o un
> abogado.

## Qué hace (objetivos de la fase 1, en curso)

- **Antes de entregar (`pre`)**: revisa tu archivo en busca de caracteres Unicode invisibles
  o de control y de metadatos que puedan levantar dudas, para que *tú* decidas qué hacer.
  Informa; nunca modifica tu archivo.
- **Después de una alerta (`post`)**:
  - redacta la solicitud de acceso al informe del detector según la ley que te ampara
    (art. 15 del RGPD, UK GDPR, FERPA, Ley 1581 de 2012 de Colombia…);
  - audita un informe de similitud: descuenta las citas bien hechas y referenciadas, la
    bibliografía, el texto de las plantillas y tus trabajos anteriores declarados, y explica
    cada descuento frente al umbral publicado por tu institución.
- **Perfiles de instituciones**: recogen la política de IA de cada universidad, sus
  umbrales de similitud, reglamentos y plazos. Cada dato lleva la URL de su fuente, la fecha
  en que entra en vigor y si está verificado.

## Lo que nunca hará

Descargo aporta pruebas. **No** reescribe, parafrasea ni «humaniza» textos, no predice ni
baja la puntuación de los detectores y no elimina marcas de agua. Ver el
[ADR 002](docs/adr/002-non-goals.md).

## Principios

1. **Local.** Todo se ejecuta en tu dispositivo. Sin servidor, sin telemetría, sin cuentas.
   Cualquier conexión a la red es opcional, explícita y está documentada.
2. **Pruebas verificables.** Formatos abiertos, huellas (hashes) y firmas que un tercero
   puede comprobar sin fiarse de nosotros.
3. **Neutral.** Todo lo que es propio de una universidad, un detector o un país va en
   adaptadores, perfiles y paquetes de jurisdicción intercambiables.

## Estado

Prealfa, fase 1. Todavía no está listo para estudiantes. La hoja de ruta y las decisiones de
diseño están en [`docs/adr/`](docs/adr/) (en inglés). Los cambios, en
[`CHANGELOG.md`](CHANGELOG.md).

## Estructura del repositorio

```text
src/descargo/
  core/report_schema/   formato común de informes (JSON Schema versionado + pydantic)
  core/evidence/        paquetes de pruebas del proceso de escritura (fase 2)
  core/stylometry/      estilo personal de referencia (fase 2)
  adapters/             lectores de informes de detectores → report_schema
  modules/pre/          revisiones antes de entregar
  modules/post/         defensa después de una alerta
  cli/                  interfaz de línea de comandos
  web/                  lo que llama la versión en el navegador (sin la CLI)
web/                    la página para el navegador (HTML, JavaScript, CSS)
scripts/                compilar y servir la versión en el navegador
profiles/               perfiles de instituciones (YAML), con fuentes
jurisdictions/          bases legales y plantillas de documentos por país o región
schemas/                JSON Schemas generados
docs/adr/               registro de decisiones de arquitectura
docs/research/          estudios de proyectos previos y componentes reutilizables
tests/fixtures/         solo datos de prueba inventados
```

## Uso (por ahora)

```bash
uv run descargo profile list
uv run descargo profile show es/uah --path escuela-doctorado
uv run descargo profile unverified          # datos que una persona aún tiene que comprobar

# Redactar la solicitud de acceso al informe del detector (Markdown + PDF, en tu equipo)
cp examples/student.example.yaml ~/mis-datos.yaml   # edítalo FUERA del repositorio
uv run descargo access-request --profile es/uah --student ~/mis-datos.yaml --language es
# Si tu institución no tiene perfil: carta genérica del paquete del país (ar, cl, co, es, eu, mx, pe, uk, us)
uv run descargo access-request --institution "Universidad Ejemplo" --jurisdiction co \
    --student ~/mis-datos.yaml --language es

# Antes de entregar: caracteres invisibles, metadatos, control de cambios, texto oculto…
uv run descargo inspect mi-ensayo.docx --language es

# Leer un informe descargado de Turnitin o Compilatio (PDF) y pasarlo a JSON de Descargo
uv run descargo import-report informe-turnitin.pdf --out informe.json

# Auditar un informe de similitud: el PDF de Turnitin tal cual, o el JSON de Descargo
uv run descargo audit informe-turnitin.pdf --document mi-ensayo.docx \
    --declarations ~/mis-declaraciones.yaml --profile es/uah --format pdf --out auditoria.pdf \
    --language es
```

El inspector cuenta qué contiene tu archivo además del texto visible y qué suele significar
cada cosa. Nunca cambia el archivo y no da ninguna puntuación. Ver
[`docs/inspect.md`](docs/inspect.md) y el [ADR 006](docs/adr/006-pre-submission-inspector.md).

Los adaptadores leen estos informes PDF:
- de Turnitin, el informe de similitud (clásico, de Feedback Studio, y el nuevo) y el
  informe de escritura con IA, en inglés y en español, con los pasajes que Turnitin
  atribuye a la IA;
- de Compilatio, el informe de análisis y el certificado (Magister hasta 2025 y Magister+
  desde 2026), en español, con los pasajes que Compilatio atribuye a la IA.

Eliminan el nombre del autor o de quien depositó el trabajo que aparece en el informe. Ver
[`docs/import.md`](docs/import.md) y el [ADR 009](docs/adr/009-first-three-detectors.md).
**Pendiente:** todavía no lee Copyleaks.

La auditoría descuenta los pasajes citados y referenciados, la bibliografía, el texto de
las plantillas de la institución y tus trabajos anteriores declarados, y explica cada
descuento. Ver [`docs/audit.md`](docs/audit.md) y el
[ADR 005](docs/adr/005-similarity-auditor.md).

### Qué fases tiene el procedimiento

Cómo es el procedimiento formal en España y en Colombia, con sus plazos y su fuente, y en
qué fase ayuda cada comando: [`docs/procedimientos.md`](docs/procedimientos.md). México, con el
ejemplo de la UNAM: [`docs/procedimientos-mx.md`](docs/procedimientos-mx.md).

## Licencia

Copyright © 2026 nyakojiru. Código bajo [AGPL-3.0-or-later](LICENSE): puedes usarlo, estudiarlo,
cambiarlo y compartirlo, y si ofreces a otras personas una versión modificada, también por
internet, tienes que darles su código fuente. Antes de mandar un cambio, lee
[CONTRIBUTING.md](CONTRIBUTING.md) (en inglés).

El nombre y el isotipo de Sukima Labs (`web/favicon.svg` y la cabecera de la página) no
están bajo la AGPL; son de Sukima Labs.
