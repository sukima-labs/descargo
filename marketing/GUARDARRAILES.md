# Guardarraíles de la promoción

Estas reglas valen para cualquier acción de promoción, la haga una persona o un agente.
Si una regla choca con un plan, gana la regla.

## 1. Veracidad

- Solo se afirma lo que el producto hace hoy. Lo previsto se llama «previsto».
- Cada cifra, cita o estudio lleva su fuente leída (no de memoria) y se anota en
  [MENSAJES.md](MENSAJES.md).
- Se dice el estado real: prealfa, versión de prueba, guías con puntos por verificar.
- No se inventan testimonios, estrellas, descargas ni usuarios. Las cifras públicas de GitHub
  se citan tal cual.

## 2. Nada de evasión, ni siquiera por inferencia

- No se anuncia nada que suene a «pasar el detector», «bajar la puntuación» o «humanizar».
- No se compite por búsquedas de evasión («cómo evitar Turnitin», «humanizar texto IA»), ni
  siquiera para desviar tráfico. Se compite por «qué hacer si me marcan», «mis derechos»,
  «solicitud de acceso al informe».
- No se enseña a ocultar el uso de IA. Si alguien usó IA contra la norma de su universidad,
  Descargo no es para eso, y la web ya lo dice.

## 3. No es asesoramiento legal

- Todo texto que mencione leyes o plazos enlaza a la guía del país y repite el aviso.
- No se promete un resultado ni se sugiere que sustituye a un abogado, a la defensoría o a la
  representación estudiantil.
- Nada de acusar a una universidad, a un docente o a una persona concreta.

## 4. Privacidad

- Ningún dato de estudiantes: ni casos, ni capturas, ni informes, ni anonimizados.
- Si alguien cuenta su caso en una conversación pública, no se cita, no se reenvía y no se
  usa como ejemplo.
- La web no tiene analítica y no se le añade para medir la promoción
  ([ADR 001](../docs/adr/001-local-first.md)). Tampoco parámetros de seguimiento ni acortadores
  que registren clics.
- Los contactos de personas (correos, teléfonos, nombres) no se escriben en este repositorio
  público: van a la nota privada del vault.

## 5. Plataformas y personas

- Se respeta la norma de cada comunidad (autopromoción, enlaces, frecuencia). Si no se ha
  podido leer, no se publica.
- Se dice quién publica y que es el desarrollador. Una mención por comunidad y sin repetir.
- Sin spam: ni mensajes masivos, ni respuestas en hilos ajenos solo para poner el enlace, ni
  seguir a gente para que nos siga.
- Se responde a quien pregunta con ayuda real, aunque no use Descargo.
- No se crean cuentas ni se rodean muros de verificación, CAPTCHA o bloqueos. Una plataforma
  que bloquea las herramientas queda fuera del plan.

## 6. Marca y terceros

- Descargo es una submarca de Sukima Labs: se usa el isotipo sin modificar a 32 px o más y
  lo que fija `marca/` del repositorio de la portada. Los cambios de marca esperan a los dos
  fundadores (issue #2 de la portada).
- No se usan logotipos, capturas de interfaz de pago ni textos de Turnitin, Compilatio,
  Copyleaks u otros: solo sus nombres, para decir qué informes se leen.
- No se sugiere afiliación con ninguna universidad, defensoría, sindicato o detector.

## 7. Quién autoriza qué

| Acción | Quién la autoriza |
|---|---|
| Cambios en el repositorio y la web (por PR) | Claude, con CI en verde (regla de Patricio del 08-11-2026) |
| Publicar o enviar un texto con el nombre de Patricio o de Sukima Labs, la primera vez en cada canal | **Patricio**, sobre el texto exacto; después, el mismo tipo de texto en el mismo canal se puede repetir |
| Cualquier cosa que cambie ajustes del repositorio o de la organización (Discussions, avatar, miembros) | Patricio |
| Search Console, Cloudflare, dominios | `maquina` (por mensaje, en inglés) |
| Escribir a personas o instituciones concretas | Patricio, sobre cada destinatario nuevo |
