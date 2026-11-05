# Auditoría de similitud

*Español · [English](en/audit.md)*

`descargo audit` recalcula un porcentaje de similitud después de descontar las coincidencias
que no son plagio, y explica cada descuento. Aplica reglas y muestra sus pruebas. Nunca
decide si algo es plagio o no, y nunca oculta la cifra que da el propio informe. El diseño
está en el [ADR 005](adr/005-similarity-auditor.md).

**No es asesoramiento legal.**

## Entradas

| Entrada | Obligatoria | Para qué sirve |
|---|---|---|
| `REPORT` | sí | El informe del detector: un Similarity Report o un AI Writing Report de Turnitin, o un informe de análisis de Compilatio, en el PDF tal como lo descargaste (ver [`import.md`](import.md)); o JSON de Descargo ([esquema del informe](../schemas/report/0.1.json)). |
| `--document` | no | El trabajo que entregaste (`.docx`, `.odt`, `.pdf`, `.txt`, `.md`). Sirve para encontrar cada pasaje coincidente en su contexto. Sin él, solo se aplican las reglas basadas en declaraciones. |
| `--declarations` | no | Tus declaraciones: tus trabajos anteriores y el texto de las plantillas de la institución. Ver [`examples/declarations.example.yaml`](../examples/declarations.example.yaml). |
| `--profile`, `--path` | no | Perfil de institución que se usa para comparar con el umbral y para la regla sobre reutilizar tu propio trabajo. |

Si un informe trae un resultado de escritura con IA, este se muestra tal como lo da la
herramienta, con los pasajes que marca, y nunca se recalcula
([ADR 009](adr/009-first-three-detectors.md)). Un informe que **solo** trae un resultado de
escritura con IA, como el AI Writing Report de Turnitin por sí solo, no tiene nada que
descontar: el resultado se titula «Resultado de escritura con IA», muestra ese resultado y
lo dice, y su JSON no tiene cifras de similitud (`overall_percent`, `adjusted_percent`,
`method` y `filters` son `null`).

Los archivos solo se leen. El resultado (`--format md|json|pdf`, `--out FILE`) registra la
huella SHA-256 de cada entrada, para que cualquiera pueda comprobar que la auditoría se
refiere a los mismos archivos.

## Reglas

| Regla | Se descuenta | Prueba que se muestra |
|---|---|---|
| Entre comillas **y** con cita: dentro de comillas (“ ”, « », " ", „ “, ‘ ’) o de una cita en bloque, con una cita bibliográfica cerca | sí | las comillas y la cita encontradas |
| Bibliografía: después del último encabezado de referencias del cuerpo, hasta un encabezado de anexo | sí | el encabezado |
| Plantilla de la institución: parte de un texto que declaraste | sí | tu descripción de la plantilla |
| Tu trabajo anterior: una fuente que declaraste | sí, con una advertencia que cita la norma de tu institución cuando el perfil la tiene | tu declaración, literal |
| Entre comillas pero sin cita encontrada | **no**, se informa | el pasaje |
| Con cita pero sin comillas | **no**, se informa | el pasaje y la cita |

Estilos de cita que reconoce:

- autor-fecha (APA, Harvard, Chicago), incluidos «y», «s. f.» y «pág.» en español;
- citas narrativas como `Smith (2020)`;
- MLA;
- IEEE `[n]` y Vancouver `(n)`;
- números en superíndice;
- Ibid., Ibíd. y op. cit.;
- DOI;
- llamadas a notas al pie y notas finales en DOCX y ODT.

Los patrones están en
[`rules.yaml`](../src/descargo/modules/post/audit/rules.yaml). Para añadir un idioma o un
estilo, añade ahí un patrón y un ejemplo en `tests/test_audit_rules.py`.

## Cifras exactas y aproximadas

- **Exacta:** cada coincidencia que lista el informe se encontró en tu documento, y juntas
  suman la cifra del informe (con un margen de 2 puntos). Entonces los descuentos se miden
  en palabras.
- **Aproximada:** faltan coincidencias en el informe, o no se dio ningún documento.
  - Las fuentes enteras restan el porcentaje que da el informe.
  - Los pasajes restan su parte del número de palabras del informe, con el porcentaje de su
    fuente como máximo.
  - Las fuentes que aparecen como `<1%` no se restan.

En caso de duda, el auditor descuenta menos, nunca más.

## Límites conocidos

- La detección de comillas y de citas es heurística. Se le escapan las maquetaciones poco
  habituales y puede emparejar una cita textual con una cita bibliográfica vecina. Cada
  descuento muestra su prueba para que una persona pueda comprobarlo.
- Las citas en bloque se reconocen por un estilo de párrafo (Quote, Cita, Quotations) o por
  el prefijo `>` de Markdown, no por la sangría.
- Los PDF no tienen estilos de párrafo, así que en ellos no se reconocen las citas en
  bloque.
- El número de palabras varía un poco de una herramienta a otra. Por eso el método exacto
  resta los puntos descontados de la cifra del propio informe.
