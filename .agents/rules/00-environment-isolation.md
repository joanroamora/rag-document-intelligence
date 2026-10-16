---
trigger: always_on
description: "Directiva obligatoria de Cero Cómputo Local (Cloud-Only Execution) y aislamiento estricto del host."
---

# Directiva de Cero Cómputo Local (Cloud-Only Execution) y Aislamiento del Host

1. **Uso exclusivo del equipo local como estación de código y Git:**
   - El equipo local **NO** se utilizará para ejecutar el proyecto, levantar servidores, correr modelos, procesar documentos ni ejecutar contenedores o pruebas.
   - La máquina local se usa **únicamente para estructurar/editar el código y empujar (push) el repositorio a remoto (GitHub)**.
2. **Ejecución 100% remota (GitHub Actions + GCP):**
   - Toda validación, linting, pruebas unitarias/integración, construcción de imágenes Docker (`Build`) y planificación de infraestructura (`Terraform`) se ejecutará en **GitHub Actions / Cloud Build**.
   - Todo el procesamiento del sistema RAG (ingesta, OCR open-source, chunking, embeddings, indexación, búsqueda y generación) correrá exclusivamente sobre recursos de **Google Cloud Platform (GCP)**.
3. **Prohibición absoluta de instalaciones en el host local:**
   - Prohibido instalar paquetes, runtimes, librerías de Python/Node o herramientas CLI en el sistema operativo local (ni globales ni locales pesados).
   - Todas las dependencias deben declararse de forma declarativa en archivos del repositorio (`pyproject.toml`, `requirements.txt`, `package.json`, `Dockerfile`, manifiestos de Terraform y workflows de `.github/workflows/`) para ser aprovisionadas e instanciadas únicamente en la nube.

