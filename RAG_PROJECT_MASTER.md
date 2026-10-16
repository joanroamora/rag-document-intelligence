# RAG con Gemini — Documento maestro del proyecto

**Estado:** diseño conceptual. **Versión:** 0.6 — 15 de octubre de 2026.

> Documento vivo para registrar decisiones, pendientes y posteriormente convertirlas en tareas para Codex. No representa implementación existente.

## 1. Visión y alcance

Construir un RAG documental **multiformato**, capaz de responder preguntas precisas sobre grandes volúmenes de expedientes, con evidencia verificable en el documento original. Los expedientes iniciales no están sujetos a reserva, pero el sistema deberá aplicar controles de acceso y privacidad por cliente.

- Interfaz web amigable; backend desacoplado para habilitar en el futuro una aplicación de escritorio.
- Formatos iniciales: **PDF, DOCX, RTF y TXT**, extensibles.
- Soporte para documentos grandes y heterogéneos: texto digital, escaneos, mecanografiados antiguos, manuscritos, tablas, imágenes, páginas mixtas o deterioradas.
- Despliegue y ejecución **100% en Google Cloud Platform (GCP) y GitHub Actions** con recursos limitados por la prueba gratuita (cero cómputo en la máquina local del desarrollador; el equipo local se usa exclusivamente para montar el repositorio y hacer push a remoto).
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

Los módulos son **límites lógicos y contratos de datos**; no implican microservicios desde el inicio. Cada implementación podrá reemplazarse sin romper las demás, siempre que respete su contrato.

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
| A | PDF/documento con texto digital | Extracción directa en contenedor GCP |
| B | Escaneo legible | OCR open source en Python (ejecutado en contenedor GCP) |
| C | Manuscrito, mecanografía degradada o OCR insuficiente | Preprocesamiento de imagen y segunda pasada de OCR en contenedor GCP; si persiste baja calidad, escalar a Gemini |
| D | Tablas, diagramas e imágenes que requieran interpretación | **Gemini Flash**, modelo multimodal eficiente disponible en el plan gratuito de Gemini API, verificado en tiempo de implementación |
| E | Páginas o regiones extremadamente deterioradas con extracción convencional fallida | **Gemini Pro**, elegir el de mayor capacidad adecuada a la tarea que esté disponible para la cuenta; sujeto a cuotas y acceso real del Free Tier |

La estrategia prevista es **diagnóstico previo barato → extracción → evaluación posterior → aceptar o escalar**. La evaluación previa puede considerar capa de texto, resolución, contraste, tipo de contenido y degradación; la posterior, confianza del motor OCR, caracteres anómalos, consistencia y legibilidad. Ninguna métrica aislada garantiza exactitud: el **Extraction Quality Score** y sus umbrales deberán validarse con páginas de referencia revisadas manualmente.

Para reducir costos, enviar a proveedores externos solo páginas o regiones problemáticas. Pendiente definir políticas de privacidad, cuotas, fallos y reintentos.

### 3.2.1 Extracción multimodal de máxima capacidad (fallback especializado)

**Objetivo:** recuperar la mayor cantidad posible de información legible de documentos de baja calidad: manuscritos, tinta corrida, pliegues, copias al carbón, textos mecanografiados deteriorados y escaneos complejos. Esta ruta complementa la extracción directa y OCR local; **no los sustituye**.

**Decisión confirmada de proveedor:** **Gemini en las rutas D y E**. No se hará selección competitiva entre Gemini, GPT y Claude para estas rutas. Los nombres históricos Gemini 1.5 Pro, GPT-4o y Claude 3.5 Sonnet dejan de ser candidatos de implementación; solo quedan como antecedentes de la discusión.

- **Ruta D — Gemini eficiente:** utilizar un **Gemini Flash** multimodal disponible en el Free Tier para tablas, diagramas, imágenes y casos que requieran visión con baja latencia y consumo controlado.
- **Ruta E — Gemini de máxima capacidad:** preferir el **Gemini Pro más capaz para lectura documental** que esté realmente habilitado dentro del Free Tier de la cuenta. Comprobar catálogo, elegibilidad, límites y precio antes de habilitarlo. Si ningún Pro es gratuito, la ruta E quedará **no disponible sin facturación** y se deberá informar al usuario u ofrecer revisión humana; nunca activar cobros automáticamente. Validar fidelidad documental mediante benchmark.
- **Política de actualización:** los IDs de modelo serán parametrizables; revisar periódicamente el catálogo oficial de Gemini y probar nuevas versiones Pro de mayor capacidad, sin modificar contratos ni código de negocio. Usar IDs explícitos de versión en producción y registrar cada ejecución.

Fuentes de verificación del catálogo y capacidades PDF: https://ai.google.dev/gemini-api/docs/models y https://ai.google.dev/gemini-api/docs/document-processing .

**Enrutamiento y ejecución:**

1. Evaluar tipo de contenido y calidad por página o región; intentar la extracción directa/OCR cuando proceda.
2. Si el control de calidad falla, elegir según diagnóstico entre una segunda pasada de OCR local, **Gemini Flash (ruta D)** o **Gemini Pro (ruta E), si está disponible en Free Tier**. La ruta E se activa para los casos de mayor dificultad o cuando la D no alcance los umbrales. No se presupone que un modelo sea siempre superior: medirlo sobre el corpus.
3. Enviar solo la página/región relevante, junto con contexto documental mínimo autorizado cuando sea útil, y solicitar una **transcripción fiel**, estructura (tablas, campos, párrafos), coordenadas y señalamiento explícito de incertidumbres.
4. Conservar por separado **texto observado**, **pasajes inciertos** e **hipótesis inferidas por contexto**. Las deducciones nunca deben presentarse como transcripción cierta ni convertirse silenciosamente en hechos del expediente.
5. Cuando haya discrepancias materiales entre extractores (nombres, montos, fechas, números de expediente), comparar con la imagen original y derivar a revisión humana si no pueden resolverse de modo verificable.
6. Normalizar los resultados al mismo contrato de salida del Módulo 1; preservar procedencia, proveedor, versión, costo, latencia y estado de verificación.

**Regla de seguridad epistemológica:** que un modelo complete un vacío con una palabra probable **no demuestra que esa palabra esté en el documento**. La extracción debe privilegiar fidelidad y auditabilidad sobre fluidez. Cuando no pueda leerse, registrar `ilegible` o una incertidumbre explícita; jamás inventar una cita.

**Evaluación obligatoria:** construir un conjunto de páginas difíciles con transcripción de referencia y comparar **CER/WER** para texto, exactitud de entidades críticas (nombres, fechas, cifras), fidelidad de tablas, porcentaje de elementos marcados como inciertos, latencia, costo por página y tasa de inferencias no sustentadas. Integrar este benchmark a CI/evaluación, con revisión humana para casos críticos.

**Privacidad/costos:** políticas por tenant sobre envío de documentos a proveedores externos, límites de gasto, redacción cuando proceda, retención, auditoría y fallback ante fallos/cuotas.

### 3.3 Document Normalizer

Convertir los resultados heterogéneos a una **representación documental interna común** que preserve texto, tablas, elementos visuales, estructura, orden, páginas, posiciones y procedencia. No hacer chunking directamente sobre texto crudo.

### 3.4 Chunking semántico, overlap y jerarquía

- Respetar cuando sea posible títulos, capítulos, secciones, párrafos y límites de tablas; dividir por tokens solo unidades excesivamente grandes.
- **Chunk size y overlap configurables** y sujetos a experimentación; evitar duplicación excesiva.
- Conservar **relaciones padre/hijo** (chunk → sección → capítulo → documento → expediente), **vecindad** (chunk anterior/siguiente) y **ubicación física** (página/región).
- Un documento puede tener páginas procesadas por extractores distintos; la normalización permite un chunking coherente posterior.
- **Context Expansion:** recuperar chunks pequeños para precisión y, cuando haga falta, añadir vecinos, sección padre y contexto documental antes de generar la respuesta.
- La estructura lógica (sección/capítulo) y la ubicación física (página) son relaciones complementarias, no siempre una jerarquía lineal única.

### 3.5 Contrato de salida: Chunk Corpus

Cada chunk debe tener texto normalizado y metadata estructurada. Campos candidatos:

`tenant_id`, `project_id`, `case_id`, `document_id`, `chunk_id`, `parent_id`, `section_id`, `page_number`/rango, `previous_chunk_id`, `next_chunk_id`, posición, región, método de extracción, `extraction_quality_score`, `chunking_version`, referencia al original, `extraction_provider`, `extraction_model_version`, `transcription_uncertainty`, `human_review_status` cuando corresponda.

**Pendiente:** definir schema exacto, tipos, campos obligatorios y cómo representar tablas/imágenes. El contrato deberá versionarse.

### 3.6 Paralelismo

Procesamiento asíncrono con cola y workers para páginas/bloques independientes; recomposición determinista de resultados en orden. Workers escalables en número, sin asumir que cada uno requiere una máquina distinta. Controlar concurrencia y límites de APIs externas.

## 4. Módulo 2 — Embeddings & Vector Indexing

### 4.1 Flujo

```text
Chunk Corpus → Embedding Provider → vector + chunk_id
→ Vector Store (vector + metadata de búsqueda)
```

- El modelo transforma el texto de cada chunk en un vector multidimensional que permite comparar similitud semántica.
- **Embedding Provider intercambiable**, con **Gemini Embedding API como preferencia inicial** por alineación con Google AI Studio/GCP y uso de su Free Tier, sujeto a cuotas y disponibilidad. Mantener implementaciones open source CPU como alternativa. Vertex AI no será dependencia inicial.
- **Vector Store intercambiable**; **ChromaDB** es candidato, no decisión cerrada. Evaluar filtros, concurrencia, persistencia, aislamiento, backups y escalabilidad.
- El índice se construye al incorporar documentos, **no en cada consulta**; permitir indexación incremental, idempotencia y reconstrucción.
- Separar metadata estructural y relaciones jerárquicas del vector semántico; considerar un almacén de metadatos/relaciones cuando haga falta.

### 4.2 Compatibilidad de embeddings

**Regla acordada:** la pregunta debe vectorizarse con el **mismo modelo y versión compatible** que los chunks del índice consultado. No mezclar espacios vectoriales incompatibles, aunque tengan igual dimensionalidad. Versionar `embedding_model`, `embedding_model_version`, `embedding_dimension` y `chunking_version`; planificar reindexación al cambiar de modelo.

### 4.3 Candidatos y benchmark obligatorio en primera iteración

Candidatos a comparar: **Gemini Embedding API** (preferencia inicial), **Qwen3-Embedding-0.6B** y **BGE-M3** como alternativas open source CPU (ningún modelo seleccionado definitivamente). Evaluar con preguntas reales y documentos representativos, incluidos español, inglés y material difícil:

- Calidad de recuperación: **Recall@K**, **MRR/nDCG** y precisión de evidencia, con respuestas relevantes etiquetadas.
- Latencia de embedding e indexación; throughput de chunks; RAM/CPU y, si aplica, GPU; tamaño de índice y costo.
- Efecto del chunking y de los filtros por metadata.
- Documentar dataset de evaluación, configuración, resultados y **justificación de la elección** como línea base reproducible. Repetir benchmark cuando cambie el modelo o el pipeline.

**Restricción actual:** GCP Free Trial con US$300 promocionales vigentes, sin GPU durante el trial; preferir embeddings vía Gemini API Free Tier y benchmark CPU como respaldo. Los créditos promocionales de GCP y las cuotas gratuitas de Gemini API son beneficios independientes: no asumir que la suscripción personal a Gemini/Google AI Pro incluya consumo de API.

## 5. Módulo 3 — Hybrid & Agentic Retrieval

**Decisión arquitectónica aprobada:** ofrecer dos modos de recuperación que compartan índices, controles de autorización y trazabilidad:

### 5.1 Modo estándar — Hybrid Retrieval

Para preguntas directas y de baja complejidad, evitando llamadas innecesarias al LLM:

1. Recibir la pregunta y determinar el alcance autorizado (tenant, proyecto, documentos).
2. Transformar la pregunta en embedding mediante un modelo compatible con el índice.
3. Ejecutar **búsqueda vectorial + búsqueda léxica (BM25 o equivalente)**; priorizar coincidencias exactas cuando haya nombres, fechas, importes e identificadores.
4. Fusionar candidatos (evaluar **Reciprocal Rank Fusion, RRF**), deduplicar y aplicar **reranking**.
5. Expandir contexto mediante la jerarquía documental, vecinos y secciones padre.
6. Entregar a Gemini evidencias seleccionadas con referencias verificables a documentos y páginas.

**Los filtros de acceso por tenant/proyecto/documento deben aplicarse antes o durante la recuperación**, no solo después de que el modelo vea resultados. El backend es responsable de garantizar esos límites.

### 5.2 Modo profundo — Agentic Retrieval

Para preguntas analíticas, de varias partes, comparaciones entre expedientes, búsquedas temporales y detección de contradicciones:

**Pregunta → Gemini Query Planner → plan estructurado → búsquedas paralelas/iterativas → fusión y reranking → expansión estructural → validación de evidencia → Gemini generador → respuesta citada.**

- **Gemini actúa como planificador**: identifica intención, entidades, condiciones, rangos temporales, subpreguntas y criterios de cobertura; produce un plan estructurado validable (por ejemplo, JSON bajo esquema).
- **El backend ejecuta las consultas** a las bases vectorial y léxica. Gemini **no recibe acceso directo irrestricto** a índices, credenciales o documentos de otros clientes.
- El orquestador puede lanzar subconsultas en paralelo, comprobar qué partes siguen sin evidencia y repetir búsquedas si es necesario.
- La planificación y la generación serán roles desacoplados: empezar con **un Gemini ligero configurable** para planificar y escalar a uno más capaz solo si la complejidad o el benchmark lo justifican.
- Para peticiones de exhaustividad («todos los expedientes», «cada pago») no equiparar Top-K con cobertura completa: usar filtros estructurados, paginación/barrido del corpus y mecanismos explícitos para verificar cobertura.
- Definir presupuestos máximos por consulta: **número de iteraciones, cantidad de subconsultas, paralelismo, tokens, tiempo y costo**; prevenir bucles y limitar uso abusivo.
- Si la evidencia es insuficiente o contradictoria, reportar incertidumbre o insuficiencia con fuentes, **sin fabricar información**.

### 5.3 Selección de modo y experiencia del usuario

El usuario podrá elegir **Estándar** o **Investigación profunda**. Más adelante un clasificador de intención podrá **recomendar** modo automáticamente; no debe obligar a usar el modo costoso para cada pregunta.

### 5.4 Validación y experimentación obligatorias

Comparar enfoques incrementalmente en un conjunto de preguntas reales anotadas: vectorial, híbrido, híbrido + reranker, contextual, y Agentic Retrieval. Registrar **Recall@K, MRR/nDCG, precisión de citas, cobertura de subpreguntas, latencia p95, tokens y costo por consulta**, además de aislamiento multi-tenant. Las pruebas deben incluir nombres, fechas, importes, documentos OCR imperfectos, evidencia ausente y contradicciones entre documentos.

**Pendientes:** motor vectorial/léxico (comparar ChromaDB y Qdrant), modelos y versiones concretas de Gemini para planificación/generación, schemas de planes y resultados, algoritmo de fusión, reranker, límites operativos, elección de modo automático, definición de cobertura y umbrales de evaluación.

## 6. Modos de uso y ciclo de vida

| Modo | Alcance | Persistencia |
|---|---|---|
| **Quick RAG** | Documentos de una sesión | Temporal con TTL; no borrar necesariamente al cerrar el navegador |
| **Corpus persistente** | Base de conocimiento incremental del tenant | Durable |
| **Proyecto temático** | Corpus delimitado por proyecto/expediente | Durable, aislado lógicamente |

La base vectorial **no debe recrearse en cada pregunta**. Usar IDs y filtros para consultar documentos concretos, un proyecto o el corpus autorizado. Definir políticas de retención, borrado verificable y recuperación.

## 7. Almacenamiento y resiliencia

- **GCS** como candidato para documentos originales y artefactos durables.
- **Originales + metadata** como fuente de verdad; el índice vectorial es reconstruible.
- Separar almacenamiento de objetos, metadatos y motor vectorial; no asumir que una base de datos productiva equivale a un archivo dentro de un bucket.
- Diseñar backups, reprocesamiento, versionado, control de duplicados y recuperación ante fallos.

## 8. Enfoque enterprise e infraestructura

- **Un stack inicial** que soporte varios usuarios concurrentes, tanto en ingesta como en consultas.
- Colas, workers, procesamiento por lotes y **autoescalado según carga**, reduciendo capacidad cuando no haya trabajo; no asumir costo cero para todos los componentes persistentes.
- Aislamiento multi-tenant desde el diseño, con autorización en cada consulta y acceso a documentos.
- Reproducibilidad mediante **IaC**, parametrización por entorno/cliente y configuration management cuando proceda.
- Posibilidad futura de replicar stacks por cliente, sin imponer ese aislamiento físico desde el primer día.
- Observabilidad, presupuestos y control de cuotas como requisitos operativos.

## 9. Decisiones acordadas

1. Pipeline multiformato, modular, con contratos explícitos.
2. Extracción local prioritaria; **Gemini Flash (D)** y **Gemini Pro (E)** como únicos proveedores remotos contemplados para extracción avanzada, sujetos a las cuotas reales gratuitas.
3. Diagnóstico de calidad antes y después de extraer.
4. Normalización común previa al chunking.
5. Chunking semántico con jerarquía, vecindad, ubicación y overlap configurable.
6. Embedding Provider y Vector Store desacoplados; **Gemini Embedding API Free Tier es opción preferente**, con alternativas CPU open source.
7. Modelo de embeddings compatible entre indexación y consulta; versionado.
8. **Benchmark documentado desde la primera iteración**, con resultados que justifiquen la elección.
9. Retrieval híbrido y context expansion como objetivos de diseño.
10. Tres modalidades: temporal, corpus persistente y proyectos.
11. GCP, un stack inicial, concurrencia y replicabilidad por IaC.
12. Cultura DevOps integrada desde la primera iteración: CI/CD con GitHub Actions, calidad automatizada y seguridad.
13. Terraform modular con ambientes DEV, TEST, STAGE y PROD, aislamiento de estado y configuración.
14. Conventional Commits obligatorios, pull requests protegidos y promoción trazable del mismo artefacto.

## 10. Próximas decisiones

- Definir schema canónico del Chunk Corpus y metadata.
- Seleccionar extractores concretos y medir calidad del OCR.
- Diseñar benchmark de **Gemini Embedding API vs. modelos open source CPU** y elegir modelo basado en resultados.
- Evaluar ChromaDB frente a alternativas según los requisitos de producción.
- **Diseñar en detalle Módulo 3: búsqueda híbrida, reranking y expansión de contexto.**
- Definir generación con Gemini, citación y evaluación de respuestas.
- Definir componentes específicos de GCP, costos, seguridad y despliegue.
- Seleccionar ejecución de SonarQube/SonarCloud según capacidades y costos; definir umbrales del Quality Gate.
- Definir estrategia de despliegue/rollback, cuotas por ambiente y mecanismos de aprobación.

---

## 11. Plataforma DevOps: CI/CD, IaC y gobierno de cambios

**Decisión arquitectónica:** desarrollar y operar el RAG con prácticas DevOps integradas desde la primera iteración. Código de aplicación, infraestructura, pruebas, políticas de calidad y pipelines deben versionarse en GitHub. La meta es un proceso reproducible, auditable, automatizado y apto para promover cambios entre entornos sin improvisación manual.

### 11.1 Ambientes independientes

| Ambiente | Propósito | Controles mínimos |
|---|---|---|
| **DEV** | Integración frecuente y experimentación | Despliegue automatizado, recursos pequeños, datos sintéticos |
| **TEST** | Pruebas funcionales, integración, contratos y rendimiento inicial | Suite automática y datos de prueba reproducibles |
| **STAGE** | Validación preproductiva de la misma versión destinada a producción | Configuración análoga a PROD, smoke tests y aprobación |
| **PROD** | Servicio real | Aprobaciones, monitoreo, backups, rollback y controles de seguridad |

Aislar por ambiente los recursos, identidades de servicio, secretos, configuraciones, presupuestos y **estado remoto de Terraform**. Evaluar proyectos GCP separados por ambiente (preferencia para aislamiento fuerte) frente a alternativas de menor costo durante la prueba gratuita. La separación de entornos es un objetivo; el despliegue simultáneo de todos los recursos queda sujeto a presupuesto y cuotas.

### 11.2 Infrastructure as Code — Terraform

- Terraform será la fuente de verdad declarativa de infraestructura GCP; **no configurar manualmente en consola lo que administra Terraform** salvo procedimientos de emergencia documentados.
- Diseñar módulos reutilizables según responsabilidades, por ejemplo: **networking, IAM/service accounts, GCS, compute/runtime, queues, observability, secrets, vector-store/storage** (solo si ese recurso finalmente se adopta).
- Mantener capas de composición por ambiente (`envs/dev`, `envs/test`, `envs/stage`, `envs/prod`) con variables, límites y dimensionamiento propios; evitar duplicar módulos.
- Estado remoto en GCS, con versionado del bucket, acceso restringido, estrategia de bloqueo/concurrencia y recuperación. **Nunca compartir el mismo state file entre ambientes.** Proteger especialmente el bucket de estado contra destrucción accidental.
- Ejecutar `terraform fmt -check`, `terraform validate`, análisis de seguridad IaC y `terraform plan` dentro de CI/CD; publicar planes revisables en pull requests cuando corresponda. Aplicar cambios (`apply`) únicamente desde flujos autorizados.
- Fijar versiones de Terraform, providers y módulos; revisar cambios de esquema y migraciones de estado.
- Aplicar etiquetas/labels consistentes (proyecto, ambiente, propietario, centro de costo) y políticas de mínimo privilegio. Usar **GitHub Actions OIDC + GCP Workload Identity Federation** en vez de llaves JSON de larga duración, cuando sea viable.
- Configuration management complementario solo para sistemas que lo requieran (por ejemplo, VMs); priorizar imágenes inmutables y configuración declarativa para servicios contenerizados.

**Estructura sugerida (ajustable en implementación):**

```text
infra/
  modules/
    networking/
    identity/
    storage/
    compute/
    queues/
    observability/
  envs/
    dev/
    test/
    stage/
    prod/
.github/
  workflows/
    ci.yml
    terraform-plan.yml
    deploy-dev.yml
    deploy-test.yml
    deploy-stage.yml
    deploy-prod.yml
```

### 11.3 CI — GitHub Actions

Al abrir/actualizar un PR o hacer push a ramas autorizadas, ejecutar un pipeline automatizado con **fallo rápido**:

1. Checkout, preparación de runtime y caché de dependencias con versiones fijadas.
2. **Validación de commits** con **Conventional Commits** y revisión de formato para pull requests.
3. **Linting y formato:** Python (por ejemplo, Ruff) y frontend (por ejemplo, ESLint/Prettier), según tecnologías seleccionadas.
4. **Pruebas unitarias** y cobertura de los módulos; verificar contratos entre Document Processing, Chunk Corpus, Embedding Provider, Vector Store y Retrieval.
5. **Pruebas de integración** con dependencias efímeras o aisladas, incluyendo extracción, indexación y consulta; usar fixtures PDF/DOCX/RTF/TXT y mocks de APIs pagas.
6. **SonarQube o SonarQube Cloud (candidato)** para análisis estático, duplicación, cobertura, vulnerabilidades y Quality Gate. Confirmar disponibilidad y restricciones del plan antes de hacerlo bloqueante; si no es viable, implementar controles equivalentes open source sin eliminar el objetivo.
7. **Seguridad:** secret scanning, análisis de dependencias/SCA, escaneo de contenedores y de Terraform; gestión de hallazgos críticos como criterio de bloqueo.
8. **Benchmark de RAG controlado**: pruebas reproducibles de extracción/retrieval con conjunto pequeño de casos etiquetados; reservar evaluaciones costosas y de alto volumen para jobs programados o ejecución manual, con resultados históricos.
9. **Build** de imagen o artefacto **una sola vez** después de aprobar los controles; publicar en **Artifact Registry** con tag de versión y SHA de commit, y desplegar mediante **digest inmutable**.
10. Adjuntar reportes de pruebas, cobertura, seguridad, evaluaciones y referencias del artefacto a la ejecución.

Los umbrales de cobertura y Quality Gate se definirán antes de considerar estable el pipeline; no inventar valores hasta contar con línea base.

### 11.4 CD — promoción entre ambientes

- **DEV:** despliegue automático del artefacto aprobado al integrar cambios en la rama principal de desarrollo definida.
- **TEST:** promoción automática o por workflow autorizado al pasar pruebas de integración; verificar migraciones, configuración y smoke tests.
- **STAGE:** despliegue del **mismo artefacto inmutable** que pasó TEST; pruebas end-to-end, de carga y validación de calidad RAG; gate de aprobación según criticidad.
- **PROD:** aprobación explícita mediante GitHub Environments/branch protection, verificación de plan Terraform y despliegue controlado del artefacto ya validado; smoke tests, monitoreo y rollback preparado.
- No reconstruir imágenes diferentes por ambiente: **promover el digest existente** y cambiar únicamente configuración/secretos autorizados.
- Separar cambios de infraestructura (`plan`/`apply`) y despliegues de aplicación, con orden de ejecución, compatibilidad de migraciones y procedimiento de rollback documentados.
- Configurar **concurrency groups** para evitar despliegues o `terraform apply` solapados sobre el mismo ambiente.
- Si no hay suficiente presupuesto para cuatro ambientes activos, mantener sus definiciones IaC y activar recursos de TEST/STAGE bajo demanda, sin asumir que un servicio gratuito permite toda la topología a la vez.

### 11.5 Gobierno Git y formato obligatorio de commits

Adoptar **Conventional Commits** con formato obligatorio:

```text
<type>(<scope>): <short imperative description>
```

**Tipos permitidos:** `feat`, `fix`, `docs`, `refactor`, `test`, `perf`, `build`, `ci`, `chore`, `revert`.

**Scopes iniciales permitidos:** `ingestion`, `ocr`, `chunking`, `embeddings`, `indexing`, `retrieval`, `generation`, `api`, `web`, `infra`, `security`, `observability`, `deps`, `docs` (lista extensible mediante PR documentado).

Reglas:

- `type` y `scope` obligatorios, en minúsculas; descripción obligatoria, concisa y sin punto final.
- Asunto **máximo de 72 caracteres**; verbo en imperativo; no aceptar commits genéricos como `update`, `changes` o `fix stuff`.
- Para breaking changes, usar `!` antes de `:` y un cuerpo con `BREAKING CHANGE:` que explique impacto y migración.
- Proteger ramas principales: prohibir push directo, exigir PR, revisiones, checks verdes y resolución de conversaciones. Definir si el merge será **squash**, y en ese caso validar también el título del PR como Conventional Commit para preservar cumplimiento.
- Usar **commitlint** con hook local opcional mediante Husky/pre-commit, pero **validación obligatoria en GitHub Actions**: el control no depende del equipo de cada desarrollador.

Ejemplos válidos:

```text
feat(ingestion): add page-level extraction routing
fix(retrieval): enforce tenant filters before search
ci(infra): validate terraform plans on pull requests
test(embeddings): add multilingual retrieval benchmark
```

### 11.6 Seguridad, observabilidad y documentación como parte del delivery

- Los pipelines deben operar con identidades dedicadas, tokens de corta duración y mínimo privilegio; nunca escribir credenciales, PDFs o datos sensibles en logs o artefactos públicos.
- Mantener secretos en gestor de secretos/variables protegidas por ambiente, nunca en Git o archivos `.tfvars` versionados con valores sensibles.
- Registrar correlación entre `commit SHA` → versión del artefacto → ambiente → cambios Terraform → métricas y alertas.
- Incorporar métricas de latencia, throughput, errores, cola/workers, costo por documento y consulta, calidad OCR y calidad de recuperación.
- Cada módulo incluirá README operativo, contratos, pruebas y criterios de aceptación; generar changelog y decisiones arquitectónicas (**ADR**) para cambios significativos.
- Aplicar el mismo estándar de entrega a código de IA, backend, frontend e infraestructura: **DevOps y evaluación de calidad RAG como parte de una sola cadena de entrega**.

### 11.7 Criterios de aceptación de la primera iteración DevOps

- Existe repositorio con reglas de ramas, commits y PR documentadas y verificadas por CI.
- Cada PR ejecuta lint, pruebas, validación Terraform y controles de seguridad; SonarQube integrado si el plan y la operación lo permiten.
- Terraform crea al menos DEV con módulos reutilizables y configuración separada para DEV, TEST, STAGE y PROD; cada ambiente tendrá su propio estado cuando se active.
- Un artefacto identificado por digest puede promoverse sin reconstrucción; despliegues generan registro auditable.
- Hay smoke tests, rollback básico, documentación de operación y presupuestos/alertas de GCP.
- El pipeline de benchmarks conserva evidencia reproducible de las decisiones sobre embeddings y retrieval.

**Pendiente de diseño:** estrategia definitiva de ramas (trunk-based frente a GitFlow ligero), runtime GCP, proveedor SonarQube, recursos realmente activos por ambiente en free trial, políticas de aprobación y umbrales cuantitativos.

---

**Decisión actualizada (v0.6):** solo Gemini API en extracción avanzada: Flash en D y el Pro más capaz accesible bajo cuotas gratuitas en E; si Pro requiere facturación, E queda deshabilitada y se permite revisión humana. El proveedor de embeddings preferido es Gemini Embedding API Free Tier. Mantener IDs y versiones configurables, benchmark documental y separación estricta entre transcripción e inferencia. No se incluyen proveedores externos adicionales de OCR.


## 12. Integración de Gemini API Free Tier y control de cuotas (v0.6)

- **Decisión comercial/técnica:** usar **Gemini API Free Tier** como servicio de IA remoto para extracción visual, embeddings, planificación y generación, en la medida en que cada modelo y función esté efectivamente disponibles sin cargo. No asumir acceso al nivel más alto de Pro.
- **Credenciales:** una **misma API key de Google AI Studio** puede autenticar llamadas a distintos endpoints/modelos de Gemini API autorizados para el proyecto, incluidos embeddings y generación/extracción. Es una credencial de proyecto, no una asignación común de cuota: los límites dependen del modelo y del proyecto. Guardar en Secret Manager o secretos protegidos; nunca en cliente web o Git.
- **Facturación:** **Google AI Pro de US$20/mes no incorpora automáticamente cuota pagada de Gemini API**. Los **US$300 de GCP Free Trial** no equivalen a crédito para consumo de la API Developer en AI Studio. No activar tier pagado sin decisión explícita.
- **Cuotas/resiliencia:** límites por modelo, backoff exponencial ante 429/5xx, timeout, circuit breaker, cola, prioridad entre trabajos, límites de tokens/tamaño de archivos, métricas de uso por tenant y estado degradado cuando la cuota se agote.
- **Privacidad:** verificar las condiciones vigentes de tratamiento de datos para el Free Tier antes de enviar cualquier archivo de cliente. Aunque un expediente no tenga reserva legal, puede contener datos personales. En la primera iteración usar corpus público, sintético o expresamente autorizado; registrar consentimiento/permisos según corresponda.
- **Embeddings:** elegir el modelo del endpoint de embeddings vigente tras consultar https://ai.google.dev/gemini-api/docs/embeddings y https://ai.google.dev/gemini-api/docs/rate-limits . Registrar versión, dimensión y tipo de tarea (documento frente a consulta) conforme a lo requerido por el modelo; utilizar el **mismo modelo y espacio compatible** en indexación y consulta, con roles de tarea correctos.
- **Modelos D/E:** consultar https://ai.google.dev/gemini-api/docs/models y precios/cuotas antes de fijar un ID, porque nombres y elegibilidad Free Tier pueden cambiar. Separar selección de modelo de lógica de negocio.

## 13. Enfoque de producto y validación comercial (hipótesis)

- **Propuesta:** plataforma de investigación de expedientes extensos y heterogéneos con evidencia verificable, no solo chatbot para PDFs.
- **Clientes potenciales prioritarios:** firmas jurídicas y litigio documental; secundarios: auditoría, aseguradoras, cumplimiento, archivos institucionales e investigación histórica.
- **Diferenciadores a validar:** mayor recuperación en escaneos antiguos, consultas complejas entre múltiples expedientes, cronologías y contradicciones citadas, trazabilidad página/región y gobierno de datos por tenant.
- **Modelo de negocio candidato:** suscripción SaaS por usuarios/proyectos más cuotas de páginas y consultas profundas; pilotos pagados antes de fijar precios definitivos. Los valores exploratorios de mercado no equivalen a demanda ni rentabilidad demostradas.
- **Validación:** entrevistas con compradores, pruebas comparativas con expedientes difíciles, medición del tiempo ahorrado, calidad de citas y disposición de pago.

## 14. Pendientes para Codex y siguiente diseño

1. Esquemas versionados de documentos, páginas, bloques, chunks, evidencias, embeddings y permisos.
2. Confirmar acceso real a modelos Gemini gratuitos, establecer configuraciones y fallback para ruta E.
3. Ejecutar benchmark OCR y benchmark Gemini Embedding API frente a CPU open source.
4. Elegir Vector Store (ChromaDB frente a Qdrant u otros), índice BM25, fusión, reranking y escalado.
5. Diseñar detalladamente **Módulo 4 — Generation**: citas verificables, validación de evidencia, no respuesta, contradicciones, cronologías e informes.
6. Diseñar frontend/API, esquema transaccional, permisos, seguridad y arquitectura GCP concreta.
7. Definir SLO, límites de concurrencia, costos, observabilidad, plan de recuperación y tareas codificables para Codex.

**Uso con Codex:** al cerrar decisiones, convertir cada módulo en especificación de interfaces, criterios de aceptación, pruebas, tareas pequeñas y prompts de implementación. Este archivo es el registro maestro de arquitectura, no código ejecutable.
