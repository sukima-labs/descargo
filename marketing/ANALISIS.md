# Análisis del proyecto para la promoción

**Fecha:** 11-11-2026, sobre `main` en `96b6eba`. Método: lectura del repositorio, de la
web pública y de las guías; consultas a un buscador (9 en español, 6 en inglés, repetibles:
ver el apéndice); lectura de los estudios citados; métricas públicas de GitHub. Lo que no se
ha podido comprobar se dice.

> **Actualización del 11-11-2026 (noche).** Este análisis es una fotografía de la mañana. Tres
> de sus debilidades ya están resueltas en `main` y en la web pública: las guías sin dirección
> propia (14 páginas estáticas, #41), el valor enterrado bajo el texto largo (cuatro tarjetas
> «¿Por dónde empiezo?», #39) y la imposibilidad de probar sin un informe real (botón de
> informe de ejemplo, #40). Siguen vigentes el buzón (#24), la prealfa, los puntos «por
> verificar» de las guías, la carga de 20 MB, la cobertura desigual y la falta de la fase 2 del
> producto. El estado de cada punto está en [PLAN.md](PLAN.md).

## 1. En una página

| | |
|---|---|
| **Qué es** | Herramienta libre (AGPL-3.0) y local para estudiantes que reciben un aviso de un detector de plagio o de IA: inspección antes de entregar, auditoría del informe, solicitud de acceso y guías de procedimiento de seis países |
| **Qué tiene de raro (en el buen sentido)** | Principios cerrados y verificables: sin servidor, sin telemetría, sin evasión. Guías con artículos, plazos, fuente y fecha de comprobación. 524 tests, cobertura del 98 % |
| **Dónde está** | Prealfa, fase 1. Web de prueba en Pages; 3 adaptadores (Turnitin, Compilatio, Copyleaks); solo 3 perfiles de universidad (Alcalá, Luis Amigó y Texas en Austin) |
| **Audiencia hoy** | Prácticamente cero: 1 estrella, 0 forks, 1 visita única al repositorio en 14 días (GitHub, 11-11-2026). El grupo de WhatsApp de estudiantes conocidos de Patricio y los testers de Colombia son los únicos usuarios |
| **Diagnóstico** | El producto está por delante de su distribución. Hay un hueco real de mercado (nadie ofrece esto gratis, local y sin evasión), pero **faltan tres cosas antes de gritar**: un camino de entrada claro, un buzón de comentarios y páginas que Google pueda leer |

## 2. Fortalezas

| Fortaleza | Por qué importa para promocionar |
|---|---|
| **Credibilidad por principios**: ADR 001 y 002 hacen que lo prometido sea comprobable en el código | En un mercado de «humanizadores», la única diferencia que no se puede copiar es no venderlos |
| **Cada dato legal con fuente y fecha**; los puntos dudosos están marcados | Es lo que un estudiante asustado y una defensoría necesitan para fiarse. Casi nadie lo hace |
| **Seis países, dos idiomas** (es/en) | Permite hablar con la audiencia de cada país con su propia guía en lugar de un texto genérico |
| **Local y gratis**: sin cuenta, sin servidor | Quita la objeción número uno (¿qué haces con mi trabajo?) y no hay coste por usuario |
| **Código abierto y en español primero** | Atrae a colaboradores (adaptadores, paquetes legales, perfiles) además de usuarios |
| **Marca ya hecha** (Sukima Labs v1.1, tarjeta para compartir `og.jpg`, favicon) | No hace falta diseñar nada para empezar |

## 3. Debilidades

| Debilidad | Evidencia | Efecto en la promoción |
|---|---|---|
| **El valor está enterrado.** Al abrir la web (en inglés por el idioma del navegador de prueba, modo oscuro) hay un bloque largo de texto antes de la primera acción; quien llega asustado no ve «me han marcado: empieza aquí» | Captura de la web pública, 11-11-2026 | Se pierde a quien llega con prisa, que es el más motivado |
| **Las guías, lo más valioso, no se pueden encontrar.** La web es una sola página y las guías se dibujan con JavaScript al abrir una pestaña; no tienen URL propia ni se ven en una búsqueda. Solo existen indexables en GitHub (`docs/*.md`) | Estructura de `web/` y `docs/web.md`; `robots.txt` del proyecto da 404 (en Pages, el de la raíz lo sirve la portada y sí existe, igual que el `sitemap.xml`, que ya lista `/descargo/`) | Sin páginas por país y tema, no hay tráfico orgánico: es el canal más barato y con más intención |
| **No hay forma de que el estudiante responda.** `FEEDBACK_EMAIL` está vacío (issue #24) | `web/app.js:285` | Se puede llevar gente, pero no se puede aprender de ella ni recoger los datos de instituciones que pide el [ADR 008](../docs/adr/008-institution-facts-from-students.md) |
| **No hay forma de probarlo sin un informe real.** La acción principal exige un PDF de Turnitin, Compilatio o Copyleaks | `web/index.html` | Un curioso o un periodista no puede ver el resultado en 30 segundos |
| **Carga pesada**: unos 20 MB la primera vez (33 s medidos por Funnel en una prueba anterior) | `docs/web.md`, vault | Abandono en móvil y con datos limitados, justo el caso de muchos estudiantes de Latinoamérica |
| **La prealfa lo dice el README**: «Todavía no está listo para estudiantes» | `README.md` | Hay que decidir si se promociona ya o se sube de estado primero (ver el plan, fase 0) |
| **Guías con puntos «por verificar» y consejos de prudencia míos, no de una norma** (por ejemplo, contar como corridos los plazos de la UBA); sin revisión jurídica | Issue #21, `CHANGELOG.md` | Un error en un plazo puede perjudicar a un estudiante. Riesgo reputacional y ético: no se amplía la audiencia sin una revisión humana de lo más sensible |
| **Cobertura desigual**: solo 3 perfiles de universidad (ninguno de MX, AR, CL ni PE); Copyleaks verificado solo con el formato de 2023; Turnitin IA y Compilatio, con muestras reales | Issues #22 y #25 | Hay que decir qué cubre hoy; «para cualquier universidad» sería falso |
| **Falta lo que más pide el estudiante antes de que le acusen**: el historial del proceso de escritura (fase 2, no construida) | README, ADR 001 | La mayor parte de las guías que compiten giran en torno a «guarda tu historial de Google Docs». Hoy no tenemos respuesta propia |
| **Un solo mantenedor con la ayuda de agentes**; Jeisson fuera de Descargo por decisión de Patricio | Memoria del proyecto | La capacidad de responder a comunidades es limitada: conviene pocos canales y bien atendidos |

## 4. Mercado y competencia

### Demanda

- El tema es de actualidad en español: sobre el «detector de IA» en Colombia, FayerWayer
  (26-09-2026) habla de un alza de búsquedas por «el miedo a ser acusado sin serlo»; no da
  cifras ni fuente, así que es una señal, no una medida.
- La evidencia académica de que los detectores se equivocan es sólida y citable (Liang et al.
  2023; Weber-Wulff et al. 2023) y la propia Turnitin dice que no hay puntuación «correcta»
  (ver [MENSAJES.md](MENSAJES.md)).
- **Medida real pendiente:** volumen de búsquedas por país y por frase. No se ha podido sacar
  de herramientas gratuitas; Search Console (central, lo gestiona `maquina`) dará las cifras
  propias en cuanto haya impresiones.

### Quién ocupa hoy el espacio (por categorías)

En las consultas en español y en inglés (ver apéndice), lo que aparece es:

| Categoría | Qué hace | Cómo se distingue Descargo |
|---|---|---|
| **Blogs de herramientas comerciales** (detectores, «humanizadores», asesorías de TFG), muchos con contenido en serie y fecha «2026» en el título | Captan la búsqueda «qué hacer si me marcan» para vender su producto; varios venden reescritura | Gratis, local, sin evasión y con fuentes legales. No compite por «humanizar» |
| **Guías de defensa en inglés** (historial de Google Docs, «cómo probar que lo escribiste») | Consejos generales | Nosotros sumamos derechos por país y análisis del informe |
| **Páginas institucionales** (p. ej., una facultad que explica su herramienta de detección) | Explican la política de su centro | Complemento: Descargo las enlaza como perfil, no compite |
| **Hilos de Reddit** | Gente contando su caso | Lugar de ayuda, no de anuncio. Fuera de alcance de nuestras herramientas (ver [CANALES.md](CANALES.md)) |
| **Proyectos de código abierto** | Casi todo son detectores o repositorios de «precisión de detectores», no defensa del estudiante | Posición poco ocupada |

No se ha encontrado, en esas consultas, otra herramienta gratuita, local, de código abierto y
en español dedicada a la defensa del estudiante. **Eso es una observación de unas pocas
búsquedas, no un estudio de mercado completo**: no se debe afirmar «somos los únicos».

### Segmentos

| Segmento | Necesidad | Prioridad | Palanca |
|---|---|---|---|
| **A. Estudiante ya marcado** | Qué hago hoy, qué plazo tengo, qué pedir | Máxima (más intención) | Buscadores y comunidades, con una entrada clara |
| **B. Estudiante de TFG/TFM/tesis que quiere prevenir** | Qué revisar antes de entregar y qué guardar | Alta | `pre` hoy; fase 2 (historial) mañana |
| **C. Intermediarios**: defensorías universitarias, representación estudiantil, sindicatos de estudiantes, asesores de tesis, bibliotecas | Un recurso fiable para derivar | Alta (multiplican y dan confianza) | Presentación breve y las guías por país |
| **D. Comunidad técnica y de integridad académica**: código abierto, privacidad, investigadores | Contribuir con adaptadores, leyes o perfiles | Media (aporta datos y credibilidad) | GitHub, Show HN, listas de proyectos locales |
| **E. Docentes y universidades** | Entender qué hacen los estudiantes | Baja; no hostil | No se les ataca; las guías son neutrales |

### Geografía y calendario (inferencia mía, no un dato medido)

- **Colombia** primero: hay testers, el grupo de WhatsApp, la plantilla de la Ley 1581 y la
  señal de búsquedas. Cierre de semestre en noviembre.
- **España**: el país con perfiles y más contenido legal; convocatorias de TFG/TFM en enero-
  febrero y en junio-julio.
- **Chile, Argentina y Perú**: final del curso (noviembre-diciembre) y defensas de tesis;
  Chile tiene un tema de actualidad con fecha (la Ley 21.719 de protección de datos, el
  01-12-2026, pendiente de la #20). Solo se usa si la #20 sigue en pie el 24-11.
- **México**: la guía de la UNAM es la más delicada (el Estatuto no dice «plagio»; ver #38).

## 5. Embudo: dónde se pierde la gente

| Etapa | Estado hoy | Cuello de botella |
|---|---|---|
| Conocer | ~0 | Sin tráfico orgánico ni canales activos |
| Llegar | Directo o por enlace | Guías sin URL propia; metaetiquetas ya hechas (`og:*`, canonical) |
| Entender | Texto largo antes de actuar | Sin un camino «me han marcado» |
| Probar | Requiere un informe real | Sin ejemplo de demostración |
| Usar | Funciona (3 detectores) | Descarga de 20 MB; informes de 2025-2026 sin verificar |
| Responder | **No es posible** | `FEEDBACK_EMAIL` vacío (#24) |
| Recomendar | Compartir el enlace | Tarjeta `og.jpg` ya hecha |

## 6. Riesgos

| Riesgo | Gravedad | Mitigación |
|---|---|---|
| Un plazo o artículo erróneo en una guía perjudica a un estudiante | **Alta** | Revisión humana de lo más sensible antes de promocionar un país; mantener las marcas «por verificar»; no prometer |
| Que nos lean como una herramienta para hacer trampa | Alta | El mensaje arranca por «no reescribe, no baja puntuaciones»; no competir por palabras de evasión |
| Autopromoción mal recibida (spam) | Media | Un anuncio por comunidad, con cara descubierta y tras leer su norma; ayudar primero |
| Uso de marcas ajenas (Turnitin, etc.) | Media | Solo el nombre, sin logotipos ni capturas de pago |
| Datos de estudiantes que llegan sin pedirlos (comentarios, mensajes) | Media | El formulario ya prohíbe datos personales; no se citan ni reenvían casos |
| Quedar abrumados sin capacidad de atender | Media | Pocos canales; la puerta (buzón) antes del altavoz |
| Cambio de la Ley 21.719 u otras normas tras publicar una guía | Media | Fechas de comprobación visibles; vigilancia en #20 |
| Hostilidad de proveedores o universidades | Baja-media | Tono neutral; solo hechos |

## 7. Conclusión

**Se recomienda una promoción en tres tiempos**, y no empezar por el altavoz:

1. Quitar los tres cuellos de botella (camino de entrada, buzón, páginas indexables) y
   completar la revisión de las partes legales más sensibles. Dos semanas.
2. Un lanzamiento suave a quienes ya están en contacto (grupo de estudiantes, testers) y a
   los multiplicadores (defensorías, representación estudiantil), y a la comunidad técnica.
3. Con lo aprendido, contenido orgánico por país y por tema en las temporadas de entrega.

Detalle, fechas y puertas en [PLAN.md](PLAN.md).

## Apéndice: consultas hechas el 11-11-2026

Buscador propio (SearXNG, motores Brave y DuckDuckGo; Brave dio «too many requests» en dos
consultas), en español: «falso positivo Turnitin IA estudiante qué hacer»; «me acusan de
plagio Turnitin IA universidad recurso»; «herramienta defensa estudiante falso positivo
detector IA»; «Turnitin detector IA falsos positivos estudiantes universidades desactivan»;
«descargo sukima-labs prueba de autoría» (para ver qué sale de nosotros: solo el
repositorio, la web y la portada); «defensor universitario falsos positivos IA estudiantes
España 2026 TFG»; «Colombia estudiantes universidad detector IA falso positivo tutela 2026»; «Compilatio falso positivo estudiante reclamar informe acceso RGPD artículo 15»; «UNAM estudiantes acusados plagio inteligencia artificial Turnitin 2026» (solo salió el escándalo de trampas en el examen de admisión de 2026, que no trata de falsos positivos y no se usa).
En inglés: «GitHub open source student false positive AI detector defense evidence»;
«Show HN open source tool students falsely accused AI detection»; y las del estudio de
Liang et al., Weber-Wulff et al. y la tasa de falsos positivos de Turnitin. Reddit no se
pudo leer con ninguna de mis herramientas.
