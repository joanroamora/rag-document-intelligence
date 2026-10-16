---
trigger: always_on
description: "Arquitectura general del proyecto RAG con Gemini: módulos 1-4 (Document Processing, Embeddings, Hybrid & Agentic Retrieval, Generation), contratos de datos, seguridad epistemológica y decisiones acordadas."
---

# RAG con Gemini — Arquitectura y Especificación de Módulos (v0.6)

> Fuente maestra: `@RAG_PROJECT_MASTER.md`. Los módulos son **límites lógicos y contratos de datos**; no implican microservicios desde el inicio. Cada implementación podrá reemplazarse sin romper las demás, siempre que respete su contrato.

## 1. Visión y alcance

Construir un RAG documental **multiformato**, capaz de responder preguntas precisas sobre grandes volúmenes de expedientes, con evidencia verificable en el documento original. Los expedientes iniciales no están sujetos a reserva, pero el sistema deberá aplicar controles de acceso y privacidad por cliente.

- Interfaz web amigable; backend desacoplado para habilitar en el futuro una aplicación de escritorio.
- Formatos iniciales: **PDF, DOCX, RTF y TXT**, extensibles.
- Soporte para documentos grandes y heterogéneos: texto digital, escaneos, mecanografiados antiguos, manuscritos, tablas, imágenes, páginas mixtas o deterioradas.
- Despliegue y ejecución **100% en Google Cloud Platform (GCP) y GitHub Actions** (cero uso de cómputo en la máquina local del desarrollador; el equipo local solo se usa para estructurar el repositorio y hacer push a remoto).
- Un stack inicial, preparado para concurrencia y para replicarse mediante **Infrastructure as Code (IaC)** para otros clientes.

## 2. Arquitectura general por módulos

```text
Carga de documentos
   ↓
MÓDULO 1 — Document Processing
Validación → router de formatos → clasificación por página/bloque
→ extracción → control de calidad → normalización estructural
→ chunking semántico y jerárquico → Chunk Corpus + metadata
   ↓
MÓDULO 2 — Embeddings & Vector Indexing
Embedding Provider → vectores → Vector Store + metadatos
   ↓
MÓDULO 3 — Retrieval
Pregunta → embedding compatible → búsqueda híbrida
→ selección/reranking → expansión jerárquica del contexto
   ↓
MÓDULO 4 — Generation [por diseñar]
Contexto con evidencias + pregunta → Gemini → respuesta citada
```

## 3. Módulo 1 — Document Processing

### 3.1 Recepción

- Upload de archivos pesados sin cargarlos íntegramente en memoria del servidor.
- Validación de formato, tamaño y archivo; almacenamiento del original según modalidad.
- Estudiar carga directa a **Google Cloud Storage (GCS)** y procesamiento asíncrono.
- Registrar identificadores de tenant, proyecto, expediente, documento y trabajo.

### 3.2 Router inteligente de extracción

La selección se hará **por página** y, cuando sea útil, **por bloque de contenido**; una página puede combinar rutas (por ejemplo, OCR del texto y análisis especializado de una tabla).

| Ruta | Situación | Técnica candidata |
|---|---|---|
| A | PDF/documento con texto digital | Extracción directa en servicio GCP |
| B | Escaneo legible | OCR open source en Python (en contenedor GCP) |
| C | Manuscrito, mecanografía degradada o OCR insuficiente | Preprocesamiento de imagen y segunda pasada de OCR en contenedor GCP; si persiste baja calidad, escalar a Gemini |
| D | Tablas, diagramas e imágenes que requieran interpretación | **Gemini Flash**, modelo multimodal eficiente disponible en el plan gratuito de Gemini API, verificado en tiempo de implementación |
| E | Páginas o regiones extremadamente deterioradas con extracción convencional fallida | **Gemini Pro**, elegir el de mayor capacidad adecuada a la tarea que esté disponible para la cuenta; sujeto a cuotas y acceso real del Free Tier |

La estrategia prevista es **diagnóstico previo barato → extracción → evaluación posterior → aceptar o escalar**. El **Extraction Quality Score** y sus umbrales deberán validarse con páginas de referencia revisadas manualmente. Para reducir costos, enviar a proveedores externos solo páginas o regiones problemáticas.

### 3.2.1 Extracción multimodal de máxima capacidad (fallback especializado)

- **Decisión confirmada de proveedor:** **Gemini en las rutas D y E**. No se hará selección competitiva entre Gemini, GPT y Claude para estas rutas.
- **Ruta D — Gemini eficiente:** utilizar un **Gemini Flash** multimodal disponible en el Free Tier para tablas, diagramas, imágenes y casos que requieran visión con baja latencia y consumo controlado.
- **Ruta E — Gemini de máxima capacidad:** preferir el **Gemini Pro más capaz para lectura documental** que esté realmente habilitado dentro del Free Tier de la cuenta. Si ningún Pro es gratuito, la ruta E quedará **no disponible sin facturación** y se deberá informar al usuario u ofrecer revisión humana; **nunca activar cobros automáticamente**.
- **Política de actualización:** los IDs de modelo serán parametrizables; usar IDs explícitos de versión en producción y registrar cada ejecución.
- **Separación transcripción vs. inferencia:** conservar por separado **texto observado**, **pasajes inciertos** e **hipótesis inferidas por contexto**. Las deducciones nunca deben presentarse como transcripción cierta ni convertirse silenciosamente en hechos del expediente.
- **Regla de seguridad epistemológica:** que un modelo complete un vacío con una palabra probable **no demuestra que esa palabra esté en el documento**. La extracción debe privilegiar fidelidad y auditabilidad sobre fluidez. Cuando no pueda leerse, registrar `ilegible` o una incertidumbre explícita; jamás inventar una cita.
- **Evaluación obligatoria:** construir un conjunto de páginas difíciles con transcripción de referencia y comparar **CER/WER** para texto, exactitud de entidades críticas (nombres, fechas, cifras), fidelidad de tablas, porcentaje de elementos marcados como inciertos, latencia, costo por página y tasa de inferencias no sustentadas.

### 3.3 Document Normalizer

Convertir los resultados heterogéneos a una **representación documental interna común** que preserve texto, tablas, elementos visuales, estructura, orden, páginas, posiciones y procedencia. No hacer chunking directamente sobre texto crudo.

### 3.4 Chunking semántico, overlap y jerarquía

- Respetar títulos, capítulos, secciones, párrafos y límites de tablas; dividir por tokens solo unidades excesivamente grandes.
- **Chunk size y overlap configurables** y sujetos a experimentación.
- Conservar **relaciones padre/hijo** (chunk → sección → capítulo → documento → expediente), **vecindad** (chunk anterior/siguiente) y **ubicación física** (página/región).
- **Context Expansion:** recuperar chunks pequeños para precisión y, cuando haga falta, añadir vecinos, sección padre y contexto documental antes de generar la respuesta.

### 3.5 Contrato de salida: Chunk Corpus

Cada chunk debe tener texto normalizado y metadata estructurada. Campos candidatos:
`tenant_id`, `project_id`, `case_id`, `document_id`, `chunk_id`, `parent_id`, `section_id`, `page_number`/rango, `previous_chunk_id`, `next_chunk_id`, posición, región, método de extracción, `extraction_quality_score`, `chunking_version`, referencia al original, `extraction_provider`, `extraction_model_version`, `transcription_uncertainty`, `human_review_status`. El contrato deberá versionarse.

### 3.6 Paralelismo

Procesamiento asíncrono con cola y workers para páginas/bloques independientes; recomposición determinista de resultados en orden. Controlar concurrencia y límites de APIs externas.

## 4. Módulo 2 — Embeddings & Vector Indexing

- **Embedding Provider intercambiable**, con **Gemini Embedding API como preferencia inicial** (Free Tier), manteniendo alternativas open source CPU (**Qwen3-Embedding-0.6B**, **BGE-M3**). Vertex AI no será dependencia inicial.
- **Vector Store intercambiable** (ChromaDB vs. Qdrant u otros candidatos).
- El índice se construye al incorporar documentos, **no en cada consulta**; permitir indexación incremental, idempotencia y reconstrucción.
- **Regla de compatibilidad de embeddings:** la pregunta debe vectorizarse con el **mismo modelo y versión compatible** que los chunks del índice consultado. Versionar `embedding_model`, `embedding_model_version`, `embedding_dimension` y `chunking_version`.
- **Benchmark obligatorio en primera iteración:** evaluar Recall@K, MRR/nDCG, precisión de evidencia, latencia, throughput y recursos CPU/RAM con preguntas reales en español/inglés y material difícil.

## 5. Módulo 3 — Hybrid & Agentic Retrieval

Dos modos de recuperación que comparten índices, controles de autorización y trazabilidad:

1. **Modo estándar — Hybrid Retrieval:**
   - Alcance autorizado (`tenant_id`, `project_id`, `document_id`) aplicado **antes o durante la recuperación** (responsabilidad del backend).
   - Búsqueda vectorial + búsqueda léxica (BM25 o equivalente) → fusión (RRF) → deduplicación y reranking → Context Expansion → evidencias con referencias verificables.
2. **Modo profundo — Agentic Retrieval:**
   - `Pregunta → Gemini Query Planner → plan estructurado (JSON validable) → búsquedas paralelas/iterativas ejecutadas por el backend → fusión y reranking → expansión estructural → validación de evidencia → Gemini generador → respuesta citada.`
   - Gemini **no recibe acceso directo irrestricto** a índices, credenciales o documentos de otros clientes.
   - Definir presupuestos máximos por consulta (iteraciones, subconsultas, paralelismo, tokens, tiempo y costo).
   - Para peticiones de exhaustividad («todos los expedientes», «cada pago»), no equiparar Top-K con cobertura completa.
   - Si la evidencia es insuficiente o contradictoria, reportar incertidumbre con fuentes, **sin fabricar información**.

## 6. Modos de uso, almacenamiento e infraestructura

- **Modos de uso:** Quick RAG (temporal con TTL), Corpus persistente (durable por tenant), Proyecto temático (durable, aislado lógicamente).
- **Almacenamiento:** GCS para originales y artefactos durables; originales + metadata como fuente de verdad; índice vectorial reconstruible.
- **Aislamiento multi-tenant desde el diseño**, con autorización en cada consulta y acceso a documentos.

## 7. Pendientes de diseño e implementación

1. Esquemas versionados de documentos, páginas, bloques, chunks, evidencias, embeddings y permisos.
2. Confirmar acceso real a modelos Gemini gratuitos, establecer configuraciones y fallback para ruta E.
3. Ejecutar benchmark OCR y benchmark Gemini Embedding API frente a CPU open source.
4. Elegir Vector Store (ChromaDB frente a Qdrant u otros), índice BM25, fusión, reranking y escalado.
5. Diseñar detalladamente **Módulo 4 — Generation**: citas verificables, validación de evidencia, no respuesta, contradicciones, cronologías e informes.
6. Diseñar frontend/API, esquema transaccional, permisos, seguridad y arquitectura GCP concreta.
7. Definir SLO, límites de concurrencia, costos, observabilidad, plan de recuperación y tareas codificables.
