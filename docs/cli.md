# Interfaz de línea de comandos

*Español · [English](en/cli.md)*

Todos los comandos leen archivos de tu dispositivo y solo escriben el resultado que pides.
Ninguno usa la red. `descargo COMMAND --help` lista todas las opciones.

**No es asesoramiento legal.**

| Comando | Qué hace | Detalles |
|---|---|---|
| `profile list`, `profile show`, `profile validate`, `profile unverified` | Lista, comprueba y muestra perfiles de instituciones, y los datos que una persona aún tiene que verificar | [Contribuir](../CONTRIBUTING.md#adding-or-updating-data) (en inglés) |
| `access-request` | Redacta una solicitud de acceso al informe del detector según la ley que te ampara | [README](../README.md#uso-por-ahora); para quien escribe paquetes: [plantillas](templates.md) |
| `import-report` | Lee un informe de detector descargado y lo pasa a JSON de Descargo | [Importar](import.md) |
| `audit` | Recalcula un porcentaje de similitud después de descontar citas, bibliografía, plantillas y tu trabajo anterior declarado | [Auditoría](audit.md) |
| `inspect` | Lista lo que contiene un archivo además del texto visible, antes de entregarlo | [Inspección](inspect.md) |

## Idioma

- `descargo --lang en|es COMMAND …` fija el idioma de la interfaz: los mensajes y el
  idioma por defecto de los informes que escriben `audit` e `inspect`. Sin esta opción,
  Descargo usa `DESCARGO_LANG`, después `LC_ALL`, `LC_MESSAGES` y `LANG`, y si no, inglés.
- `audit --language` e `inspect --language` fijan solo el idioma del informe.
  `access-request --language` fija el idioma de la carta, que necesita una plantilla en ese
  idioma en el paquete de jurisdicción; por defecto es el idioma de la institución.
- `access-request --institution NAME --jurisdiction PACK` redacta una carta genérica para
  una institución sin perfil, solo a partir del paquete. `--office` y `--office-email` la
  dirigen a una oficina que encontró el estudiante; ese destinatario se marca como no
  verificado.
- Los textos de ayuda y los errores de uso (una opción desconocida, un archivo que falta)
  están en inglés por ahora.

## Archivos de salida

- `--out FILE` escribe en un archivo en lugar de en la terminal. La salida en PDF necesita
  `--out`. `access-request --out` recibe una ruta sin extensión y añade `.md` y `.pdf`.
- Un archivo que ya existe nunca se sobrescribe, salvo que pases `--force`.
- Un archivo de entrada nunca se sobrescribe, ni siquiera con `--force`: `--out` no puede
  ser el informe, el documento, las declaraciones ni el archivo de datos que lee el comando.
- Cuando `import-report` muestra el JSON en la terminal, su resumen y sus notas van a la
  salida de error estándar, para que el JSON se pueda pasar por una tubería o redirigir
  por separado.

## Fechas

`--date YYYY-MM-DD` fija la fecha que aparece en una carta, una auditoría o un informe de
inspección, para que las mismas entradas den el mismo resultado. Por defecto es la de hoy.

## Código de salida

| Código | Significado |
|---|---|
| 0 | Hecho. En `inspect`, vale para cualquier contenido del archivo: los hallazgos no son fallos ([ADR 006](adr/006-pre-submission-inspector.md)). |
| 1 | Descargo no pudo o no quiso hacerlo: un archivo ilegible, un perfil desconocido, una salida que sobrescribiría un archivo, un perfil no válido en `profile validate`. El mensaje dice por qué. |
| 2 | Error de uso: una opción o un valor de opción desconocidos, o un archivo que no existe. |

## Carpetas de datos

`--profiles-dir` y `--jurisdictions-dir` apuntan a tus propias copias de las carpetas
[`profiles/`](../profiles/) y [`jurisdictions/`](../jurisdictions/), por ejemplo para probar
un perfil antes de contribuirlo. Por defecto se usan las que vienen incluidas.
