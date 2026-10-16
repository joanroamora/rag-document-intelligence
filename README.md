# RAG Document Intelligence

Plataforma RAG documental multiformato con evidencia verificable, aislamiento multi-tenant y orquestación inteligente con Gemini.

## Descripción General

Sistema diseñado para procesar expedientes extensos y heterogéneos (PDF, DOCX, RTF, TXT), extrayendo texto, tablas y diagramas con enrutamiento de calidad y fallback especializado con Gemini Vision, búsqueda híbrida y generación con citas verificables.

## Estructura de Documentación

- **Documento Maestro de Arquitectura:** [`RAG_PROJECT_MASTER.md`](RAG_PROJECT_MASTER.md)
- **Instrucciones Generales de Antigravity:** [`AGENTS.md`](AGENTS.md)
- **Reglas del Proyecto:** [`.agents/rules/`](.agents/rules/)
  - [`00-environment-isolation.md`](.agents/rules/00-environment-isolation.md): Aislamiento estricto de entorno y dependencias.
  - [`01-project-architecture-and-rag.md`](.agents/rules/01-project-architecture-and-rag.md): Especificación de Módulos 1 a 4.
  - [`02-devops-git-and-gemini-quotas.md`](.agents/rules/02-devops-git-and-gemini-quotas.md): DevOps, Conventional Commits y cuotas de Gemini Free Tier.
