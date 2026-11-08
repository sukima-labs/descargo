# Importar un informe de detector

*Español · [English](en/import.md)*

`descargo import-report` convierte el informe que descargaste al
[formato de informe](../schemas/report/0.1.json) de Descargo (JSON), que es el que leen los
demás comandos. `descargo audit` acepta directamente el PDF descargado y hace la misma
importación. El diseño está en el [ADR 004](adr/004-report-schema.md).

```bash
uv run descargo import-report informe-turnitin.pdf --out informe.json
uv run descargo import-report informe-compilatio.pdf --out informe.json
uv run descargo audit informe-turnitin.pdf --document mi-ensayo.docx --profile es/uah --language es
```

El archivo solo se lee. El JSON registra la huella SHA-256 del informe, para que cualquiera
pueda comprobar que se refiere al mismo archivo. **No es asesoramiento legal.**

## Turnitin

La guía de Turnitin
([Downloading and sharing the Similarity Report](https://guides.turnitin.com/hc/en-us/articles/27881575386125))
describe los PDF que se pueden descargar. Descargo lee tres de ellos:

| Formato | Cómo reconocerlo | Qué se lee |
|---|---|---|
| Feedback Studio ("Current View"), en inglés y en español | el trabajo y después una página con el encabezado "ORIGINALITY REPORT" ("INFORME DE ORIGINALIDAD") | índice de similitud; cifras de Internet, de publicaciones y de trabajos de estudiantes; las fuentes principales con sus porcentajes; "Exclude quotes / bibliography / matches"; fecha de entrega, ID, número de palabras y de caracteres |
| Enhanced Similarity Report, en inglés y en español | una Cover Page ("Portada") y después un "Integrity Overview" ("Descripción general de integridad") | similitud general; filtros; exclusiones; los cuatro grupos de coincidencias (solo en inglés); cifras por base de datos; las alertas de integridad y lo que dice el informe de cada una, como el texto oculto; las fuentes principales; ID de la entrega, fecha, páginas, palabras y caracteres; las secciones que contiene el PDF |
| AI Writing Report, en inglés y en español, solo o después del Similarity Report en el mismo PDF | un "AI Writing Overview" ("Descripción general de la escritura con IA") que empieza con "23% detected as AI" ("detectado como IA") | la parte del texto atribuida a la IA, o "*%" cuando está por debajo del umbral del 20 % de Turnitin; los dos grupos de detección (solo en inglés); los pasajes resaltados en cian, página por página; los mismos datos de la entrega que en el Similarity Report |

No se guardan: el nombre del autor ni el nombre del archivo que aparecen en el informe. En
la portada del informe nuevo (enhanced), el título solo se guarda cuando es el nombre del
archivo (lo que Turnitin pone por defecto), porque el título y el nombre del autor aparecen
en un orden que varía.

Cada importación dice lo que no ha podido leer. En particular:

- **Sin texto coincidente.** Los PDF de Turnitin muestran los pasajes coincidentes como
  resaltados de color, que no se pueden extraer de forma fiable, así que la auditoría usa
  su método aproximado ([ADR 005](adr/005-similarity-auditor.md)).
- **Nombres recortados.** El informe nuevo corta los nombres largos de las fuentes y los
  termina en "...".
- **Etiquetas sin comprobar.** Los nombres de filtros que aún no se han visto en un informe
  real producen un aviso cuando aparecen.

- **Extractos.** Cuando el PDF tiene menos páginas de las que indican los pies de página del
  informe ("Page 2 of 13"), la importación dice que es un extracto y que pueden faltar
  partes.
- **Reimpresiones.** Un informe que se volvió a guardar con otro programa, como Word, puede
  perder los números de su lista de fuentes; la importación lo dice. Usa el PDF descargado
  de Turnitin.
- **Los informes en español no imprimen los recuentos** de coincidencias excluidas ni de
  alertas de integridad ("N.º de coincidencias excluidas"), así que esos recuentos quedan
  vacíos.

El formato nuevo (enhanced) se comprobó en octubre de 2026 con cinco informes reales leídos
solo en el equipo del responsable del proyecto ([ADR 009](adr/009-first-three-detectors.md)):
uno en inglés y cuatro en español (uno completo y tres extractos, uno de ellos reimpreso con
Word).

El AI Writing Report se comprobó en noviembre de 2026 con tres informes reales leídos solo
en el equipo del responsable del proyecto: dos en inglés (23 % y 0 %) y uno en español,
después de su Similarity Report, con una puntuación por debajo del umbral. En el informe en
inglés del 23 %, los pasajes resaltados forman 6 tramos y 473 palabras, cerca del 17 % de
todas las palabras de las páginas del trabajo; el 23 % de Turnitin es una parte del texto
que su modelo considera apto para el análisis, que deja fuera tablas, listas y referencias. Sobre el AI
Writing Report:

- **El resultado es de la herramienta.** La importación lo registra tal como lo da Turnitin
  y la auditoría no lo recalcula ([ADR 009](adr/009-first-three-detectors.md)).
- **"\*%"** significa que la puntuación está por debajo del 20 %: en ese caso Turnitin no da
  ninguna cifra ni resalta nada porque, como dice el informe, es más probable que esas
  puntuaciones sean falsos positivos. La importación guarda "\*%" como la etiqueta mostrada.
- **Los pasajes se leen por el resaltado que tienen detrás,** un trozo de texto cada vez,
  así que un pasaje que empieza o termina a mitad de línea puede ganar o perder ahí unas
  pocas palabras.
- **El texto parafraseado aún no se lee.** Turnitin resalta en morado el texto que además
  se parafraseó con IA, un color que ningún informe real ha mostrado hasta ahora; cuando
  ese grupo está por encima del 0 %, la importación dice que faltan esos pasajes.
- **En un PDF con los dos informes,** solo se buscan resaltados en las páginas propias del
  AI Writing Report, que se distinguen por el total de páginas de sus pies de página.

El formato de Feedback Studio en español se comprobó en noviembre de 2026 con tres informes
reales de mayo, junio y agosto de 2026, leídos solo en el equipo del responsable del
proyecto. Los tres se leen con cada fuente emparejada con su porcentaje (2, 50 y 61
fuentes). Los informes parten el título en dos líneas e imprimen el autor más abajo
("por …"); el título se guarda tal como Turnitin lo vuelve a imprimir en una sola línea
encima de "INFORME DE ORIGINALIDAD", y el autor se descarta. Algunos imprimen dos
interruptores en una misma línea ("Excluir citas Apagado Excluir coincidencias Apagado"), y
"TRABAJOS DEL ESTUDIANTE" en una línea o en dos; ambos casos se leen. Un cuarto informe en
español, reimpreso con Word como imágenes, no tiene texto que leer.

**Pendiente.** Las copias escaneadas o solo de imagen de un informe no tienen texto que
leer.

### Datos útiles de la documentación de Turnitin

- Cuando las mismas palabras coinciden con varias fuentes, el informe muestra **una sola
  fuente principal** para ellas, y prefiere Internet, después Publications y después
  Submitted Works
  ([Navigating the new, enhanced Similarity Report](https://guides.turnitin.com/hc/en-us/articles/27395528629517)).
  La auditoría aproximada se basa en esto.
- Los **grupos de coincidencias** ("Cited and Quoted", "Missing Citation"…) los producen
  modelos entrenados en inglés, solo están disponibles para trabajos en inglés y reconocen
  citas APA, MLA, Turabian e IEEE
  ([How do the Match Groups work](https://guides.turnitin.com/hc/en-us/articles/28057483210637)).
  En trabajos en español no dicen nada sobre si las citas están bien hechas.
- Las **alertas de integridad** abarcan el texto oculto y los caracteres sustituidos
  ([Integrity Flags](https://guides.turnitin.com/hc/en-us/articles/27397357797517)).
  `descargo inspect` muestra ambos tipos de contenido en tu propio archivo.
- Los **Submission Details** de Turnitin muestran a quien investiga el autor del archivo,
  «modificado por última vez por», el tamaño del papel, el software, las fuentes
  tipográficas y un recuento de grafías estadounidenses y británicas
  ([Submission Details and Document Details](https://guides.turnitin.com/hc/en-us/articles/30872471895821)).

## Compilatio

Descargo lee el PDF del informe de análisis de Compilatio en español, en sus dos formatos.
Ambos se aprendieron con informes reales leídos solo en el equipo del responsable del
proyecto ([ADR 009](adr/009-first-three-detectors.md)): tres informes de Magister de
septiembre a diciembre de 2025, y cinco informes y un certificado de Magister+ de marzo a
julio de 2026.

### Magister (hasta 2025, "INFORME DE ANÁLISIS")

| Parte del informe | Qué se lee |
|---|---|
| Resultados de la primera página | similitud (la cifra general); "Textos potencialmente generados por la IA"; además, guardados como extensiones, texto sospechoso, similitud entre comillas, similitud con fuentes citadas e idiomas no reconocidos. Un resultado marcado "(ignorado)" se incluye en `marked_ignored` |
| Datos del documento | nombre del documento (como título, sin su extensión), número de palabras y de caracteres, fechas de depósito y de análisis |
| "Fuentes principales detectadas" y "Fuentes con similitudes fortuitas" | cada fuente con su etiqueta, su URL (cuando no está recortada), su porcentaje y sus palabras idénticas; de qué tabla viene |
| "Fuentes mencionadas" | las URL que cita el documento sin ninguna similitud |
| Las páginas del documento | los pasajes dibujados en el color que Compilatio usa para la IA, con su página |

### Magister+ (desde 2026, "Informe de análisis" y "Certificado de análisis")

| Parte del informe | Qué se lee |
|---|---|
| Sección 1, el resumen | texto sospechoso; similitud, con su división en "Sintáctica" y "Semántica"; "Detección de IA"; idiomas no reconocidos; texto entre comillas; y, para cada uno, si el informe lo cuenta en el porcentaje de texto sospechoso ("Incluido" o "No incluido") |
| Datos del documento | nombre del archivo (como título, sin su extensión), número de palabras y de caracteres, fechas de depósito y de análisis |
| Sección 2, las fuentes | cada fuente con su etiqueta, su URL (tal como aparece, sin "https://", cuando no está recortada) y su porcentaje; de qué tabla viene ("Fuente principal detectada" o "Fuente con similitudes fortuitas"); si es un documento de otro usuario o de la biblioteca de la cuenta, y si se encontró por detección semántica |
| "Fuente mencionada (sin similitudes detectadas)" | las URL que cita el documento sin ninguna similitud |
| Sección 3, el documento (solo en el informe completo) | los pasajes subrayados en el color que Compilatio usa para la IA, con su página |

El certificado solo tiene las secciones 1 y 2, así que no tiene pasajes de IA; la
importación lo dice. Las tablas de fuentes salen del PDF columna a columna, así que cada
fila se reconstruye a partir de dónde están dibujadas sus piezas.

No se guardan, en ninguno de los dos formatos: el nombre de quien depositó el trabajo, el
ID del documento, el tamaño del archivo original ni el tipo de carga.

Lo que no puede leer:

- **Sin texto coincidente.** Los pasajes coincidentes están resaltados detrás del texto, y
  el texto del PDF no lo deja ver, así que la auditoría usa su método aproximado, como con
  Turnitin.
- **Los pasajes de IA salen de un color o de un subrayado.** Compruébalos con el informe;
  la importación lo dice. En los informes reales, las palabras de los pasajes leídos
  quedaron a menos de un punto porcentual de la cifra de IA que da Compilatio.
- **Cotas.** "< 1 %" se guarda como 1 % con la marca de cota superior.
- **Informes copiados dentro de otro documento.** Un certificado pegado dentro del PDF de
  una tesis no se lee; usa el PDF descargado de Compilatio.

La auditoría muestra la cifra de IA y los pasajes como lo que afirma la herramienta. No los
recalcula ni los descuenta.

## Copyleaks

Descargo lee el PDF que exporta Copyleaks, en inglés, en dos formatos. Se aprendieron con
cuatro informes reales leídos solo en el equipo del responsable del proyecto
([ADR 009](adr/009-first-three-detectors.md)): la muestra que Copyleaks publicó en octubre
de 2022, dos muestras de su web de abril y junio de 2023 y un informe que publicó un blog en
mayo de 2023. Los tres de 2023 se recuperaron del Internet Archive.

### 2023 ("Plagiarism and AI Content Detector Report" o "Plagiarism report")

| Parte del informe | Qué se lee |
|---|---|
| "Scan details" | título del documento, número de páginas y de palabras; la fecha del análisis, como extensión |
| "Plagiarism Detection" | la similitud global y su división en idéntico, cambios menores, parafraseado y palabras omitidas, con su porcentaje y sus palabras |
| "AI Content Detection" | el porcentaje y las palabras de texto de IA y de texto humano. Si el informe muestra "N/A", no trae resultado de IA, y la importación lo dice |
| "Alerts" | el título y la gravedad de cada alerta ("2/5 Severity") |
| "Plagiarism Results" | cada fuente con su título, su URL y su porcentaje. Si el informe divide el porcentaje por tipo de coincidencia, se guarda esa división y el porcentaje es su suma: también la similitud global del informe es la suma de sus tipos (comprobado en los tres informes reales). Las fuentes de "Copyleaks Internal Database" se marcan como `other` |
| "Scanned AI content" | los pasajes dibujados sobre el tono más oscuro de la escala de IA de Copyleaks, con su página. En la muestra con un 100 % de IA, sus palabras coinciden con las que da Copyleaks |

### 2022

El formato anterior trae la similitud global, las palabras por tipo de coincidencia, las
fuentes y la fecha del análisis, sin resultado de IA. Imprime los porcentajes de las
fuentes en una columna aparte de los nombres: se emparejan en orden, y la importación avisa
si no salen los mismos.

No se guardan, en ninguno de los dos formatos: el nombre de quien envió el análisis ("Submitted
by") ni el identificador del análisis ("Scan id").

Lo que no puede leer:

- **Sin texto coincidente.** Los pasajes coincidentes están resaltados por tipo, pero el
  resaltado no dice de qué fuente son, así que la auditoría usa su método aproximado.
- **Tonos claros de la escala de IA.** Copyleaks colorea los pasajes de IA en una escala del
  20 % al 99 %, y en un informe real solo se ha visto el tono del 99 %. Si los pasajes leídos
  no suman el porcentaje que da Copyleaks, la importación avisa de que pueden faltar los de
  tonos más claros.
- **Otros idiomas y el formato actual.** Solo se han visto informes en inglés y hasta 2023.

La auditoría muestra la cifra de IA y los pasajes como lo que afirma la herramienta. No los
recalcula ni los descuenta.

## Añadir un formato o un idioma

Las etiquetas que buscan los adaptadores están en `labels.yaml`, junto a cada adaptador
([Turnitin](../src/descargo/adapters/turnitin/labels.yaml),
[Compilatio](../src/descargo/adapters/compilatio/labels.yaml),
[Copyleaks](../src/descargo/adapters/copyleaks/labels.yaml)). Para que lea un informe en
otro idioma, añade sus etiquetas bajo una nueva clave de idioma (en Compilatio, dentro de su
formato) y una prueba con datos inventados en `tests/test_<tool>_adapter.py`. Nunca subas
un informe real al repositorio: compruébalo en tu propio equipo y describe en la pull
request qué etiquetas viste.
