# Mensajes y posicionamiento

Texto en español de España y de América, tuteo, sin jerga legal. La versión en inglés se
hace solo cuando un canal en inglés lo pida.

## Posicionamiento (una frase)

> Descargo es la herramienta libre y local para quien ha recibido un aviso de un detector de
> plagio o de IA y necesita **ordenar pruebas y conocer sus derechos**, no «arreglar» el
> texto. No sube tus archivos a ningún sitio.

**Contra qué nos medimos.** Casi todo lo que sale en español al buscar «falso positivo
Turnitin» son blogs de herramientas comerciales (varias venden «humanizadores» que
reescriben el texto). Descargo hace lo contrario y eso es su ventaja: **un tribunal puede
fiarse de pruebas que no vienen de una herramienta que también vende el disfraz**
([ADR 002](../docs/adr/002-non-goals.md)).

## Tres pilares

| Pilar | Qué decimos | Qué lo respalda |
|---|---|---|
| **Local y privado** | Tus archivos no salen de tu dispositivo. Sin cuentas, sin analítica, sin cookies | [ADR 001](../docs/adr/001-local-first.md); la página solo pide sus propios archivos (CSP del [ADR 007](../docs/adr/007-web-build.md)) y el código es auditable |
| **Pruebas, no trucos** | Te ayuda a entender el informe, descontar lo que está bien citado y pedir lo que te corresponde. No reescribe ni baja puntuaciones | ADR 002; la web y la CLI no modifican tu archivo |
| **Derechos por país** | Guías con artículos y plazos, con la fuente y la fecha en que se comprobó cada cita | `docs/procedimientos*.md`: España, Colombia, México, Argentina, Chile y Perú |

## Frases que se pueden usar

- «Prueba de autoría.» (lema de la web)
- «Si un detector marca tu trabajo y es tuyo, necesitas pruebas, no un disfraz.»
- «Entiende el informe, ordena tus pruebas y conoce tus plazos.»
- «Gratis, de código abierto y en tu navegador: tus archivos no se suben.»
- «Cada dato legal lleva su fuente y la fecha en que se comprobó. Si algo está sin verificar,
  lo dice.»

## Datos que se pueden citar

Cada uno con su fuente, leída el día indicado. Si una cifra tiene más de 60 días o la
fuente cambia, se vuelve a comprobar antes de usarla.

| Dato | Fuente | Leído |
|---|---|---|
| Un estudio de Stanford (Liang et al., *Patterns*, 2023) probó siete detectores con 91 ensayos TOEFL de estudiantes cuyo idioma materno no era el inglés: **marcaron como IA el 61,22 %** de los ensayos; los siete coincidieron en 18 de 91 (19 %), y **al menos uno marcó 89 de 91 (97 %)**. Con ensayos de estudiantes estadounidenses de 8.º curso, casi sin errores | [Stanford HAI](https://hai.stanford.edu/news/ai-detectors-biased-against-non-native-english-writers); [arXiv 2304.02819](https://arxiv.org/abs/2304.02819) | 11-11-2026 |
| Weber-Wulff et al. (*International Journal for Educational Integrity*, 2023) probaron 14 herramientas, entre ellas Turnitin y PlagiarismCheck, y concluyen que no son «ni precisas ni fiables»; se inclinan a clasificar como texto humano, y ofuscar el contenido empeora su rendimiento | [arXiv 2306.15666](https://arxiv.org/abs/2306.15666) | 11-11-2026 |
| Turnitin dice de sí misma (14-06-2023): tasa de falsos positivos por documento **menor del 1 %** en documentos con un 20 % o más de IA; **en torno al 4 % por frase**; no hay puntuación «correcta» y los resaltados son para «iniciar una conversación, no para llegar a una conclusión» | [Blog de Turnitin](https://www.turnitin.com/blog/understanding-the-false-positive-rate-for-sentences-of-our-ai-writing-detection-capability) | 11-11-2026 |
| Aumento de las búsquedas de «detector de IA» en Google Colombia (sin cifras ni fuente de los datos) | [FayerWayer, 26-09-2026](https://www.fayerwayer.com/internet/2026/09/26/detector-de-ia-crece-en-google-colombia-por-una-razon-muy-especifica-el-miedo-a-ser-acusado-sin-serlo/) | 11-11-2026 |

**Cómo se citan.** Siempre con el nombre del estudio o la fuente y el año; nunca como «la
IA falla el 61 %»: es una cifra de un estudio concreto sobre un tipo concreto de texto. La
cifra de Turnitin es de 2023 y es la que la propia empresa publica: se dice «según
Turnitin, en 2023».

## Lo que NO se dice

| No decir | Por qué | Decir en su lugar |
|---|---|---|
| «Evita que te marquen», «pasa Turnitin», «baja tu puntuación» | Es lo que Descargo se niega a hacer (ADR 002) y desacredita las pruebas | «Defiéndete con pruebas si te marcan» |
| «Te defiende», «gana tu caso», «garantiza» | No es asesoramiento legal ni garantiza resultados | «Te ayuda a ordenar pruebas y a ejercer derechos que quizá ya tienes» |
| «Los detectores no funcionan» / «mienten» | Es falso en general y afirma más de lo que los estudios dicen | «Los detectores pueden equivocarse; hay estudios que lo muestran» |
| «Lo usan estudiantes de [universidad]» | No hay datos ni consentimiento | Nada, hasta que haya consentimiento escrito |
| «Aprobado/recomendado por [defensoría, universidad, Turnitin]» | No hay ninguna relación | Nada |
| Logotipos de Turnitin, Compilatio u otras marcas | Marcas ajenas, sin permiso | Solo el nombre en texto, como referencia (uso nominativo) |
| Cualquier plazo o artículo sin su guía | Cambian y varían | Enlace a la guía del país, que lleva la fecha de comprobación |
| «Para todo el mundo» o «para cualquier universidad» | Hay seis países con guía, pero solo 3 perfiles de universidad | Decir qué países cubre hoy |

## Una verdad incómoda que no se esconde

Descargo está en **prealfa**: la web es una versión de prueba y varias guías tienen
puntos «por verificar». Se dice. Pedir confianza prometiendo más de lo que hay es lo que
hacen los competidores. La honestidad sobre el estado es parte del mensaje.

## Tono

Sereno, concreto y del lado del estudiante sin atacar a docentes. Quien recibe un aviso
suele estar asustado: primero se le dice qué hacer (los tres pasos de la página), después
por qué.
