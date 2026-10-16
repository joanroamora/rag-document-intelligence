---
trigger: always_on
description: "Reglas obligatorias de DevOps, CI/CD, Terraform IaC, formato de Conventional Commits, seguridad y control de cuotas del Free Tier de Gemini API."
---

# Plataforma DevOps, Gobierno Git y Cuotas de Gemini API

## 1. Ambientes independientes (DEV, TEST, STAGE, PROD)

| Ambiente | Propósito | Controles mínimos |
|---|---|---|
| **DEV** | Integración frecuente y experimentación | Despliegue automatizado, recursos pequeños, datos sintéticos |
| **TEST** | Pruebas funcionales, integración, contratos y rendimiento inicial | Suite automática y datos de prueba reproducibles |
| **STAGE** | Validación preproductiva de la misma versión destinada a producción | Configuración análoga a PROD, smoke tests y aprobación |
| **PROD** | Servicio real | Aprobaciones, monitoreo, backups, rollback y controles de seguridad |

- Aislar por ambiente los recursos, identidades de servicio, secretos, configuraciones, presupuestos y **estado remoto de Terraform**.

## 2. Infrastructure as Code — Terraform

- Terraform es la fuente de verdad declarativa de infraestructura GCP; **no configurar manualmente en consola lo que administra Terraform** salvo procedimientos de emergencia documentados.
- Estructura sugerida:
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
- Estado remoto en GCS con versionado del bucket, acceso restringido y bloqueo. **Nunca compartir el mismo state file entre ambientes.**
- Ejecutar `terraform fmt -check`, `terraform validate`, análisis de seguridad IaC y `terraform plan` en CI/CD.
- Fijar versiones de Terraform, providers y módulos. Usar **GitHub Actions OIDC + GCP Workload Identity Federation** en vez de llaves JSON de larga duración cuando sea viable.

## 3. CI/CD — GitHub Actions y Promoción

- **CI con fallo rápido:**
  1. Checkout y caché de dependencias con versiones fijadas.
  2. Validación de **Conventional Commits** y formato de PR.
  3. Linting y formato (por ejemplo, Ruff en Python y ESLint/Prettier en frontend).
  4. Pruebas unitarias y verificación de contratos entre módulos.
  5. Pruebas de integración con fixtures PDF/DOCX/RTF/TXT y mocks de APIs pagas.
  6. Análisis estático / cobertura / Quality Gate (SonarQube/SonarCloud o controles equivalentes open source).
  7. Seguridad: secret scanning, análisis de dependencias (SCA), escaneo de contenedores y Terraform.
  8. Benchmark de RAG controlado reproducible.
  9. Build de imagen o artefacto **una sola vez** tras aprobar controles; publicar en Artifact Registry con tag de versión + SHA y desplegar mediante **digest inmutable**.
- **Promoción CD:** no reconstruir imágenes diferentes por ambiente; promover el mismo digest inmutable cambiando solo configuración/secretos autorizados.

## 4. Gobierno Git y Formato Obligatorio de Commits (Conventional Commits)

Todo commit y título de PR (en caso de squash merge) debe cumplir estrictamente el formato:

```text
<type>(<scope>): <short imperative description>
```

- **Tipos permitidos (`type`):** `feat`, `fix`, `docs`, `refactor`, `test`, `perf`, `build`, `ci`, `chore`, `revert`.
- **Scopes permitidos (`scope`):** `ingestion`, `ocr`, `chunking`, `embeddings`, `indexing`, `retrieval`, `generation`, `api`, `web`, `infra`, `security`, `observability`, `deps`, `docs` (extensible mediante PR documentado).
- **Reglas estrictas:**
  - `type` y `scope` obligatorios, en minúsculas.
  - Descripción obligatoria, en verbo imperativo, concisa y **sin punto final**.
  - Asunto de **máximo 72 caracteres**.
  - Prohibidos commits genéricos como `update`, `changes` o `fix stuff`.
  - Para breaking changes, usar `!` antes de `:` y un cuerpo con `BREAKING CHANGE:`.
- **Ejemplos válidos:**
  - `feat(ingestion): add page-level extraction routing`
  - `fix(retrieval): enforce tenant filters before search`
  - `ci(infra): validate terraform plans on pull requests`
  - `test(embeddings): add multilingual retrieval benchmark`

## 5. Integración de Gemini API Free Tier y Control de Cuotas (v0.6)

- **Uso exclusivo del Free Tier sin cargos automáticos:** usar **Gemini API Free Tier** para extracción visual (Ruta D con Flash, Ruta E con el Pro gratuito más capaz si existe), embeddings, planificación y generación. **Nunca activar tier pagado ni cobros automáticamente.**
- **Credenciales:** la API key de Google AI Studio autentica llamadas a los distintos modelos/endpoints autorizados, pero las cuotas dependen del modelo y proyecto. Guardar siempre en Secret Manager o variables de entorno locales no versionadas (`.env` ignorado en Git); jamás exponer en cliente web ni en el repositorio.
- **Facturación separada:** Google AI Pro (US$20/mes) no incluye cuota pagada de Gemini API, y los US$300 de GCP Free Trial no equivalen a crédito para consumo de Gemini Developer API en AI Studio.
- **Resiliencia ante cuotas:** implementar límites por modelo, backoff exponencial ante `429`/`5xx`, timeouts, circuit breaker, colas con prioridad, límites de tokens/tamaño y modo degradado cuando se agote la cuota.
- **Privacidad:** en la primera iteración usar corpus público, sintético o expresamente autorizado; verificar políticas vigentes de tratamiento de datos del Free Tier antes de enviar documentos.
- **Documentación oficial de referencia:**
  - Modelos: `https://ai.google.dev/gemini-api/docs/models`
  - Procesamiento documental: `https://ai.google.dev/gemini-api/docs/document-processing`
  - Embeddings: `https://ai.google.dev/gemini-api/docs/embeddings`
  - Rate limits: `https://ai.google.dev/gemini-api/docs/rate-limits`
