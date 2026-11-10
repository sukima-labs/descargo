# Marketing y promoción de Descargo

Este módulo recoge cómo se da a conocer Descargo: a quién, con qué mensaje, por qué
canales, con qué límites y cómo se mide. Es documentación; no añade código al producto ni
cambia lo que hace la herramienta (ver el [ADR 010](../docs/adr/010-marketing-module.md)).

> [!IMPORTANT]
> La promoción **nunca** puede prometer lo que el producto no hace. Descargo no reescribe,
> no «humaniza», no baja puntuaciones y no es asesoramiento legal
> ([ADR 002](../docs/adr/002-non-goals.md)). Las reglas completas están en
> [GUARDARRAILES.md](GUARDARRAILES.md) y mandan sobre cualquier texto de este módulo.

## Qué hay aquí

| Archivo | Para qué sirve |
|---|---|
| [ANALISIS.md](ANALISIS.md) | Evaluación del proyecto (11-11-2026): qué tiene, qué le falta, el mercado y los riesgos |
| [PLAN.md](PLAN.md) | El proyecto de promoción: objetivos, fases con sus puertas, calendario y responsables |
| [MENSAJES.md](MENSAJES.md) | Posicionamiento, frases, datos que se pueden citar (con fuente) y lo que no se puede decir |
| [CANALES.md](CANALES.md) | Cada canal: qué se hace, con qué herramienta, qué reglas tiene y qué queda fuera de alcance |
| [GUARDARRAILES.md](GUARDARRAILES.md) | Límites éticos, legales, de marca y de privacidad de toda acción de promoción |
| [MEDICION.md](MEDICION.md) | Qué se mide sin telemetría, cómo y con qué frecuencia |
| [metricas.csv](metricas.csv) | Instantáneas semanales de las cifras públicas (GitHub), para no perder la ventana de 14 días |
| [REGISTRO.md](REGISTRO.md) | Lo que se ha publicado o enviado de verdad, con fecha y enlace |
| [plantillas/](plantillas/) | Borradores de textos. **Un borrador no es una publicación**: hasta que aparece en el registro, no se ha enviado |

## Reglas de funcionamiento

1. **Todo texto sale de un hecho comprobado.** Cada cifra o afirmación de
   [MENSAJES.md](MENSAJES.md) lleva su fuente y la fecha en que se leyó. Si no se puede
   comprobar, no se usa.
2. **Se publica con la cara descubierta.** Quien publica dice que desarrolla Descargo. Nada
   de cuentas falsas, reseñas inventadas ni «un amigo me recomendó».
3. **Nada de datos de estudiantes**, ni siquiera anonimizados, ni casos reales como ejemplo
   ni como testimonio sin consentimiento por escrito y sin detalle del caso.
4. **Primero la puerta, luego el altavoz.** Las fases de [PLAN.md](PLAN.md) tienen puertas:
   no se amplía la audiencia mientras el producto no cumpla las de la fase anterior.
5. **El repositorio es público.** Aquí no van listas de contactos personales, correos,
   exportaciones de analítica ni conversaciones. Eso va en la nota privada del vault.
6. **Jeisson sigue fuera de Descargo** mientras Patricio no diga otra cosa: sin asignarle ni
   mencionarle en issues o PR de este módulo.

## Cómo se mantiene

- Cada hallazgo o cambio de rumbo entra por PR, con su línea en [REGISTRO.md](REGISTRO.md) si
  es una acción externa.
- Los pendientes de promoción son issues con la etiqueta `promoción` y están en el tablero
  Descargo del Portafolio de la organización.
- Cada lunes se anota una línea en [metricas.csv](metricas.csv) (ver [MEDICION.md](MEDICION.md)).
- Los datos de [ANALISIS.md](ANALISIS.md) caducan: se repiten las consultas y se corrigen
  antes de usarlos en un texto nuevo si tienen más de 60 días.
