# Conexiones a la red

*Español · [English](en/network.md)*

Descargo **no hace ninguna conexión a la red** salvo que pases una opción explícita para un
fin concreto ([ADR 001](adr/001-local-first.md)). Este archivo lista todas esas conexiones.

| Función | Opción | Destino | Datos enviados |
|---|---|---|---|
| *(ninguna en esta versión)* | | | |

La versión para el navegador solo pide sus propios archivos al sitio que la sirve; su
política de seguridad de contenido (Content Security Policy) prohíbe cualquier otra
petición ([ADR 007](adr/007-web-build.md)). Al compilar esa versión
(`scripts/build_web.py`) se descarga Pyodide desde GitHub y jsDelivr, y tres paquetes wheel
desde PyPI, cada uno comprobado con una huella SHA-256 fijada de antemano. Eso ocurre en el
equipo de quien desarrolla, al compilar, nunca en el dispositivo del estudiante.
