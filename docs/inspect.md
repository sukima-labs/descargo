# Inspección antes de entregar

*Español · [English](en/inspect.md)*

`descargo inspect` lista lo que contiene un archivo además del texto visible: caracteres
invisibles o poco habituales, metadatos, control de cambios, comentarios, texto oculto y
otros contenidos que una persona o una herramienta pueden notar. Explica qué suele
significar cada cosa y qué no demuestra. El diseño está en el
[ADR 006](adr/006-pre-submission-inspector.md).

**Informa y nunca cambia tu archivo.** No te dice qué cambiar, no da ninguna puntuación ni
ningún aprobado o suspenso, y termina con el código 0 siempre que haya podido leer el
archivo. Si editas el archivo con tus propias herramientas, guarda una copia del original.

**No es asesoramiento legal.**

```bash
uv run descargo inspect mi-ensayo.docx --language es
uv run descargo --lang es inspect mi-ensayo.odt --format pdf --out inspeccion.pdf
```

| Opción | Qué hace |
|---|---|
| `--format md\|json\|pdf` | Formato de salida (Markdown por defecto). |
| `--out FILE` | Escribe en un archivo en lugar de en la terminal (obligatorio para PDF). |
| `--language en\|es` | Idioma del informe; por defecto, el de la interfaz. |
| `--date YYYY-MM-DD` | Fecha que aparece en el informe; por defecto, la de hoy. |
| `--force` | Sobrescribe un archivo de salida que ya existe. El archivo inspeccionado nunca se sobrescribe. |

Archivos admitidos: `.docx` (y `.docm`), `.odt`, `.pdf`, y `.txt` o `.md` en UTF-8.

## Niveles

- **Para revisar**: es probable que una persona o una herramienta lo note. No significa que
  haya algo mal.
- **Para tu información**: es habitual y suele ser inocente.

## Qué se revisa

### Caracteres (en todos los formatos)

| Hallazgo | Nivel | Notas |
|---|---|---|
| Caracteres de ancho cero y otros caracteres de formato invisibles | revisar | U+200B, U+2060, U+FEFF dentro del texto, operadores invisibles… |
| Caracteres de unión y de no unión de ancho cero | información | Normales en persa, árabe, escrituras índicas y emojis |
| Guiones blandos | información | Los inserta la división en sílabas |
| Marcas y controles de dirección del texto | información | Normales en texto de derecha a izquierda |
| Forzado de la dirección del texto (U+202D, U+202E) | revisar | |
| Controles de dirección del texto sin cerrar | revisar | Se comprueba por párrafo ("Trojan Source", CVE-2021-42574) |
| Caracteres de etiqueta (U+E0000–E007F) | revisar | Se muestra el texto ASCII que forman |
| Banderas emoji formadas con caracteres de etiqueta | información | Inglaterra, Escocia, Gales… |
| Selectores de variación | información | Uno solo después de un carácter |
| Datos ocultos en selectores de variación | revisar | Series de selectores, decodificadas a bytes (y a texto cuando se puede leer) |
| Credenciales de contenido (manifiesto C2PA) | revisar | El envoltorio de texto de C2PA 2.4: solo presencia y tamaño |
| Caracteres de control | revisar | Distintos del tabulador y los saltos de línea |
| Caracteres de uso privado | información | Fuentes de símbolos como Wingdings |
| Puntos de código sin asignar | revisar | Depende de la versión de Unicode, que el informe registra |
| Espacios poco habituales | revisar | Espacio de media eme, de eme, fino, ideográfico… |
| Espacios de no separación | información | U+00A0 y U+202F |
| Caracteres que parecen en blanco | revisar | Rellenos hangul, patrón braille en blanco |
| Separadores Unicode de línea y de párrafo | información | |
| Palabras que mezclan alfabetos | revisar | Latino con cirílico, o con letras griegas que parecen latinas. Las demás letras griegas (μm, células β) no se informan |
| Marca de orden de bytes al principio de un archivo de texto | información | |

En los archivos DOCX, los caracteres se revisan en el cuerpo, los encabezados, los pies de
página, las notas al pie, las notas finales y los comentarios, incluido el texto eliminado
que conserva el control de cambios. En los ODT se revisan en `content.xml` y `styles.xml`
(encabezados y pies de página). En los PDF se revisan en el texto que extrae pypdf.

### Documentos

| Hallazgo | DOCX | ODT | PDF |
|---|---|---|---|
| Metadatos | `core.xml`, `app.xml`, `custom.xml` | `meta.xml` | Diccionario Info, XMP |
| Tiempo de edición | `TotalTime` | `editing-duration` | |
| Ciclos de edición | | `editing-cycles` | |
| Identificadores de sesión de guardado (RSID) | número, sesiones que usa el texto del cuerpo, mayor proporción | | |
| Control de cambios, con nombres y fechas | sí | sí | |
| Comentarios, con nombres | sí | sí | |
| Texto oculto, blanco y diminuto (< 2 pt), incluso a través de estilos | sí | sí | modos de representación invisibles, relleno blanco |
| Campos por tipo (incluidos los de gestores de referencias) | sí | | |
| Partes de contenido importado (`altChunk`) | sí | | |
| Objetos incrustados, macros | sí | sí | |
| Plantilla adjunta | sí | | |
| Actualizaciones incrementales, cifrado, archivos adjuntos | | | sí |

## Cómo leer los resultados

- **Los metadatos pueden engañar.** Las herramientas copian propiedades de sus plantillas.
  Por ejemplo, un DOCX generado con pandoc lleva el nombre de la aplicación, el tiempo de
  edición y la plantilla del documento de referencia de pandoc, no los de tu propio trabajo.
- **Los RSID, el tiempo de edición y los ciclos de edición** son contadores que lleva el
  programa de edición. Dependen del editor, vuelven a empezar en un archivo nuevo y no
  muestran cómo se escribió el texto. Un registro del proceso de escritura es una prueba más
  sólida.
- **Los PDF escaneados con reconocimiento de texto (OCR)** suelen contener una capa de texto
  invisible sobre la imagen de cada página.

## Límites conocidos

- Todavía no se revisan las letras parecidas dentro de un mismo alfabeto, el texto
  estropeado por codificaciones incorrectas, el texto dentro de imágenes ni el contenido de
  los manifiestos C2PA.
- La detección de texto invisible en PDF sigue la extracción de texto de pypdf, que trabaja
  por fragmentos: puede incluir texto que está junto a texto invisible o blanco en el mismo
  fragmento.
- Para el texto oculto, blanco y diminuto se sigue la herencia de estilos, pero no todas las
  formas en que un procesador de textos puede ocultar texto (por ejemplo, texto detrás de
  imágenes o fuera de la página).
- Los caracteres que la fuente de un informe en PDF no puede dibujar se escriben como
  `[U+XXXX]`.
