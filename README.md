# RAG Document Intelligence

Plataforma RAG documental multiformato con evidencia verificable, aislamiento multi-tenant y orquestación inteligente con Gemini.

## Descripción General

Sistema nativo de nube (**100% ejecutado en Google Cloud Platform y GitHub Actions**, cero cómputo local) diseñado para procesar expedientes extensos y heterogéneos (PDF, DOCX, RTF, TXT), extrayendo texto, tablas y diagramas con enrutamiento de calidad y fallback especializado con Gemini Vision, búsqueda híbrida y generación con citas verificables.

## Estructura de Documentación

- **Documento Maestro de Arquitectura:** [`RAG_PROJECT_MASTER.md`](RAG_PROJECT_MASTER.md)
- **Instrucciones Generales de Antigravity:** [`AGENTS.md`](AGENTS.md)
- **Reglas del Proyecto:** [`.agents/rules/`](.agents/rules/)
  - [`00-environment-isolation.md`](.agents/rules/00-environment-isolation.md): Directiva de Cero Cómputo Local (Cloud-Only Execution) y aislamiento del host.
  - [`01-project-architecture-and-rag.md`](.agents/rules/01-project-architecture-and-rag.md): Especificación de Módulos 1 a 4 en GCP.
  - [`02-devops-git-and-gemini-quotas.md`](.agents/rules/02-devops-git-and-gemini-quotas.md): DevOps, CI/CD, estrategia de ramas/commits y cuotas de Gemini Free Tier.

