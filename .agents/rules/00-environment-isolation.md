---
trigger: always_on
description: "Directiva obligatoria de aislamiento de entorno y dependencias: prohíbe instalaciones globales en el host y exige entornos locales (.venv, npx, Docker)."
---

# Directiva de aislamiento de entorno y dependencias

- Prohibido realizar instalaciones globales en el sistema operativo host.
- Nunca ejecutes comandos con flags globales (como `npm install -g`, `pip install --user`, `gem install`, etc.) ni uses `sudo` para instalar paquetes.
- Todo paquete, herramienta o runtime debe ser confinado estrictamente al directorio de trabajo local del proyecto.
- Si se requiere una herramienta CLI (por ejemplo, linters, formatters, test runners), ejecútala a través de wrappers de entorno local:
  - **En Node.js/JavaScript:** Usa dependencias locales en `devDependencies` y ejecútalas con `npx` o scripts en `package.json`.
  - **En Python:** Trabaja únicamente dentro de un entorno virtual activo (`.venv`). Si no existe, créalo (`python3 -m venv .venv` o `python -m venv .venv`), actívalo y usa `./.venv/bin/pip` (o `.\.venv\Scripts\pip` en Windows) o `uv`/`poetry`/`pipenv` local.
  - **En contenedores:** Si se requieren herramientas a nivel de sistema, encapsúlalas dentro de un `Dockerfile` / `docker-compose.yml` local sin tocar el host.
