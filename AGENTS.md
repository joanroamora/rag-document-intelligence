# Instrucciones Generales del Proyecto — RAG con Gemini

Este repositorio implementa una plataforma RAG documental multiformato con evidencia verificable y aislamiento multi-tenant.

## 1. Documentación Maestra y Reglas de Antigravity

- **Documento Maestro de Arquitectura:** `@RAG_PROJECT_MASTER.md`
- **Reglas modulares activas (`.agents/rules/`):**
  - `@.agents/rules/00-environment-isolation.md` — Directiva obligatoria de Cero Cómputo Local (Cloud-Only Execution) y aislamiento del host.
  - `@.agents/rules/01-project-architecture-and-rag.md` — Arquitectura por módulos (1–4), seguridad epistemológica y contratos de datos.
  - `@.agents/rules/02-devops-git-and-gemini-quotas.md` — DevOps, CI/CD, Terraform IaC, estrategia de ramas/commits y cuotas del Free Tier de Gemini API.

## 2. Invariantes Críticas de Trabajo

1. **Cero Cómputo Local (Cloud-Only Execution) y aislamiento del host:**
   - **El equipo local NO se usará para ejecutar el proyecto** (ni pruebas, ni modelos, ni servidores, ni contenedores); su único rol es estructurar/editar los archivos del repositorio y empujarlos (`git push`) a remoto.
   - **Prohibido instalar paquetes o dependencias en la máquina local.**
   - Toda validación, linting, test, build y plan de infraestructura se ejecuta en **GitHub Actions / Cloud Build**, y todo el runtime del sistema RAG corre exclusivamente en **Google Cloud Platform (GCP)**.
2. **Seguridad epistemológica y fidelidad documental:**
   - Separar siempre **texto observado**, **pasajes inciertos** e **hipótesis inferidas por contexto**.
   - Jamás inventar citas ni presentar deducciones como transcripción cierta; registrar `ilegible` o incertidumbre explícita cuando corresponda.
3. **Aislamiento multi-tenant:**
   - Los filtros de acceso (`tenant_id`, `project_id`, `case_id`, `document_id`) deben aplicarse en el backend **antes o durante la recuperación**, nunca únicamente después.
   - Gemini nunca recibe acceso directo irrestricto a índices, credenciales o documentos de otros clientes.
4. **Control de costos y Gemini API Free Tier:**
   - Uso estricto del **Free Tier de Gemini API** (Flash en Ruta D; Pro en Ruta E solo si está habilitado sin cargo; Gemini Embedding API Free Tier preferente).
   - **Nunca activar cobros o facturación automáticamente.**
5. **Contratos modulares y compatibilidad de embeddings:**
   - Respetar los contratos de datos versionados entre Módulos 1, 2, 3 y 4.
   - La consulta siempre debe vectorizarse con el **mismo modelo y versión compatible** que el índice consultado.
6. **Estrategia de ramas y formato de commits:**
   - Ramas principales: `main` (producción) y `dev` (integración previa a `main`).
   - Ramas de trabajo: `Feature<N>-<descripcion>` (o `Feature<N>/<descripcion>`), derivadas de `dev`.
   - **Merges a `dev` y a `main` únicamente bajo autorización explícita.**
   - Formato obligatorio de commit: debe iniciar siempre con el identificador de la Feature: `Feature<N>: <descripción>` (ej. `Feature1: Updating ci pipeline`).
