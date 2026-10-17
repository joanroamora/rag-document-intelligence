# AETHER RAG — Enterprise Document Intelligence Platform

Plataforma empresarial **RAG (Retrieval-Augmented Generation)** multiformato con **evidencia verificable**, **seguridad epistemológica**, **aislamiento multi-tenant nativo** y orquestación con **Gemini API Free Tier**, ejecutada **100% en Google Cloud Platform (GCP) y GitHub Actions** bajo la directiva de *Cero Cómputo Local*.

---

## 1. Arquitectura General (Módulos 1 al 4)

```mermaid
flowchart TD
    UI["AETHER RAG Web Console (GET /) & REST API (FastAPI)"]
    M1["MÓDULO 1 — Document Processing\nRecepción Streaming → Router Inteligente (Rutas A-E)\n→ Escalado por Calidad → Normalizador → Semantic Chunker"]
    M2["MÓDULO 2 — Embeddings & Vector Indexing\nGemini Embedding Free Tier / CPU Hash → Circuit Breaker\n→ Vector Store Multi-Tenant + Validación de Espacio Vectorial"]
    M3["MÓDULO 3 — Hybrid & Agentic Retrieval\nPre-filtro TenantScope → Vector + Okapi BM25 → RRF Fusion\n→ Reranking → Context Expansion / Query Planner Exhaustivo"]
    M4["MÓDULO 4 — Grounded Generation\nAbstención Automática → Síntesis Citada → Citation Guard\n→ Segregación de Hipótesis Inferidas e Incertidumbre"]

    UI --> M1
    M1 --> M2
    M2 --> M3
    M3 --> M4
    M4 --> UI
```

---

## 2. Invariantes Críticas de Ingeniería

1. **Cero Cómputo Local (*Cloud-Only Execution*):**
   - La máquina local se utiliza únicamente como estación de edición y Git. Toda validación, linting (`Ruff`), pruebas (`Pytest`), construcción de contenedores (`Docker`) y despliegue (`Terraform` / `Cloud Run`) se ejecuta en **GitHub Actions y GCP**.
2. **Seguridad Epistemológica y Fidelidad Documental:**
   - Separación estricta a nivel de contrato entre **transcripción observada** (`observed_text`), **pasajes inciertos** (`[ilegible]`) e **hipótesis inferidas** (`inferred_context_notes`).
   - El **Citation Guard** ([`generator.py`](src/rag_platform/generation/generator.py)) lanza `CitationVerificationError` si un sintetizador intenta citar un `chunk_id` inexistente o presentar una hipótesis inferida como hecho observado.
3. **Aislamiento Multi-Tenant Pre-Retrieval:**
   - Todo acceso requiere cabeceras obligatorias `X-Tenant-Id` y `X-Project-Id`. Los almacenes vectorial ([`vector_store.py`](src/rag_platform/indexing/vector_store.py)) y léxico BM25 ([`lexical_bm25.py`](src/rag_platform/retrieval/lexical_bm25.py)) filtran mediante [`TenantScope.matches_filter`](src/rag_platform/contracts/tenant.py) **antes** de puntuar similitud.
4. **FinOps y Candado Gemini API Free Tier:**
   - Uso estricto del **Free Tier de Gemini API** (`allow_paid_tier=False` validado por contrato), con división por lotes, *circuit breaker* ante errores `429` y degradación automática al modo extractivo/CPU sin activar cobros.
5. **Compatibilidad Matemática de Embeddings:**
   - [`assert_embedding_compatibility`](src/rag_platform/contracts/embedding.py) verifica proveedor, modelo, versión, dimensión y versión de chunking antes de cada indexación o búsqueda.

---

## 3. Estructura del Repositorio

```text
├── .agents/rules/                     # Reglas obligatorias de arquitectura, aislamiento y DevOps
├── .github/workflows/
│   ├── ci.yml                         # Gobernanza de commits (Feature<N>:), Ruff Lint y Pytest (33 tests)
│   ├── terraform-plan.yml             # Validación fmt, validate y plan de infraestructura GCP
│   ├── terraform-apply.yml            # Despliegue manual de infraestructura base en GCP (DEV)
│   ├── deploy-dev.yml                 # Build de imagen inmutable y despliegue a Cloud Run (DEV)
│   └── terraform-destroy.yml          # Teardown total (Cloud Run + Artifact Registry + Buckets) a $0.00
├── infra/
│   ├── modules/{identity,storage,compute}/
│   └── envs/dev/                      # Estado remoto en GCS y definición declarativa del entorno DEV
├── src/rag_platform/
│   ├── contracts/                     # Contratos Pydantic v2 (tenant, document, chunk, embedding, retrieval, generation)
│   ├── processing/                    # Módulo 1: reception.py, router.py (Rutas A-E), normalizer.py, chunker.py
│   ├── indexing/                      # Módulo 2: embedder.py, vector_store.py
│   ├── retrieval/                     # Módulo 3: lexical_bm25.py, hybrid_retriever.py, agentic_retriever.py
│   ├── generation/                    # Módulo 4: generator.py (GroundedAnswerGenerator & Citation Guard)
│   ├── adapters/                      # Cliente HTTPX para Gemini Developer API Free Tier (gemini_client.py)
│   ├── benchmark/                     # Suite reproducible de métricas CER, WER, Recall@K, MRR y nDCG@K
│   ├── api/                           # Servicio FastAPI (app.py, schemas.py) y Consola Web AETHER RAG (ui.py)
│   └── orchestrator.py                # Fachada End-to-End (RAGPlatformOrchestrator)
├── tests/unit/                        # Suite de 33 pruebas unitarias e integración E2E (>90% cobertura)
├── Dockerfile                         # Imagen multi-stage sin privilegios (appuser) para Cloud Run
└── pyproject.toml                     # Configuración declarativa del paquete, Ruff y Pytest
```

---

## 4. API REST y Consola Ejecutiva Web (`AETHER RAG`)

El servicio FastAPI ([`src/rag_platform/api/app.py`](src/rag_platform/api/app.py)) expone tanto la interfaz gráfica corporativa como los endpoints REST:

| Método y Ruta | Descripción | Cabeceras Requeridas |
|---|---|---|
| `GET /` | Consola ejecutiva interactiva **AETHER RAG** (estilo Apple/Fluent Glassmorphic) con expediente corporativo demo de 1 clic, conmutador multi-tenant y visualización epistemológica. | Ninguna |
| `GET /health` | Estado operativo del motor, versión y conteo de chunks indexados por tenant. | Ninguna |
| `POST /v1/documents/ingest` | Ingesta documental multipágina, enrutamiento inteligente M1 e indexación híbrida M2/M3 (`201 Created`). | `X-Tenant-Id`, `X-Project-Id` |
| `POST /v1/rag/ask` | Consulta RAG en modo `standard_hybrid` o `deep_agentic` con respuesta citada, advertencias `[ilegible]` e hipótesis segregadas (`200 OK`). | `X-Tenant-Id`, `X-Project-Id` |
| `DELETE /v1/documents/{document_id}` | Eliminación aislada por tenant de todos los vectores y registros léxicos de un documento. | `X-Tenant-Id`, `X-Project-Id` |
| `GET /docs` | Documentación interactiva OpenAPI / Swagger UI. | Ninguna |

---

## 5. Ciclo de Vida de Pruebas en la Nube (Costo $0.00)

Todos los flujos se ejecutan desde la pestaña **Actions** de GitHub:

1. **Integración Continua Automática (`CI — Governance, Lint & Contract Tests`):**
   - Se dispara automáticamente en cada `push` a `main`, `dev` o `Feature*`. Verifica el formato de commit (`Feature<N>: ...`), ejecuta `ruff check src tests` y corre los **33 tests** con `pytest --cov=rag_platform`.
2. **Desplegar Servicio y Consola Web en Cloud Run (`CD — Deploy RAG Service & UI to Cloud Run (DEV)`):**
   - Selecciona el workflow manual **`CD — Deploy RAG Service & UI to Cloud Run (DEV)`** (`deploy-dev.yml`) -> **Run workflow**.
   - Construye el contenedor, lo publica con digest inmutable en Artifact Registry y despliega `rag-api-dev` en **Google Cloud Run** (`--min-instances=0`, escalado a cero).
   - Al finalizar, abre la **Live Console URL** impresa en el resumen del job para interactuar con **AETHER RAG**.
3. **Destrucción Total a Costo Cero (`IaC — Terraform Destroy (Teardown to Zero Cost)`):**
   - Al finalizar las pruebas, ejecuta el workflow **`IaC — Terraform Destroy (Teardown to Zero Cost)`** (`terraform-destroy.yml`) escribiendo `DESTROY`.
   - Elimina el servicio de Cloud Run, el repositorio de Artifact Registry, los recursos de Terraform y el bucket de estado, dejando la cuenta de GCP en **$0.00 de costo residual**.

---

## 6. Documentación Maestra y Reglas

- **Documento Maestro de Arquitectura:** [`RAG_PROJECT_MASTER.md`](RAG_PROJECT_MASTER.md)
- **Instrucciones Generales del Agente:** [`AGENTS.md`](AGENTS.md)
- **Reglas Modulares Activas:**
  - [`00-environment-isolation.md`](.agents/rules/00-environment-isolation.md) — Cero Cómputo Local y aislamiento del host.
  - [`01-project-architecture-and-rag.md`](.agents/rules/01-project-architecture-and-rag.md) — Especificación de Módulos 1 a 4.
  - [`02-devops-git-and-gemini-quotas.md`](.agents/rules/02-devops-git-and-gemini-quotas.md) — Gobierno Git, CI/CD, Terraform y cuotas del Free Tier de Gemini API.
