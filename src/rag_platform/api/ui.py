"""Enterprise Apple/Fluent-inspired Glassmorphic Web UI for the RAG Platform."""

# ruff: noqa: E501

ENTERPRISE_UI_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>AETHER RAG — Enterprise Document Intelligence</title>
<style>
  :root {
    --bg-base: #07090e;
    --bg-surface: rgba(18, 22, 32, 0.72);
    --bg-elevated: rgba(28, 34, 48, 0.65);
    --bg-glass-hover: rgba(42, 50, 70, 0.55);
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-highlight: rgba(255, 255, 255, 0.16);
    --text-primary: #f5f7fa;
    --text-secondary: #9ba3b5;
    --text-muted: #636b7e;
    --accent-primary: #3b82f6;
    --accent-glow: rgba(59, 130, 246, 0.32);
    --emerald: #10b981;
    --emerald-bg: rgba(16, 185, 129, 0.12);
    --amber: #f59e0b;
    --amber-bg: rgba(245, 158, 11, 0.12);
    --indigo: #818cf8;
    --indigo-bg: rgba(129, 140, 248, 0.12);
    --rose: #f43f5e;
    --rose-bg: rgba(244, 63, 94, 0.12);
    --radius-lg: 18px;
    --radius-md: 12px;
    --radius-sm: 8px;
    --ease-spring: cubic-bezier(0.16, 1, 0.3, 1);
    --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI Variable",
                 "Inter", system-ui, sans-serif;
    --font-mono: "SF Mono", "Cascadia Code", "JetBrains Mono", monospace;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    background-color: var(--bg-base);
    background-image:
      radial-gradient(circle at 15% 10%, rgba(59, 130, 246, 0.11), transparent 40%),
      radial-gradient(circle at 85% 15%, rgba(129, 140, 248, 0.08), transparent 35%),
      radial-gradient(circle at 50% 90%, rgba(16, 185, 129, 0.06), transparent 45%);
    color: var(--text-primary);
    font-family: var(--font-sans);
    min-height: 100vh;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden;
  }

  /* Top Acrylic Navigation Bar */
  .topbar {
    position: sticky;
    top: 0;
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 32px;
    background: rgba(10, 13, 20, 0.78);
    backdrop-filter: blur(24px) saturate(180%);
    -webkit-backdrop-filter: blur(24px) saturate(180%);
    border-bottom: 1px solid var(--border-subtle);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .brand-orb {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    background: linear-gradient(135deg, #3b82f6 0%, #6366f1 55%, #10b981 100%);
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: -0.5px;
  }

  .brand-title {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }

  .brand-subtitle {
    font-size: 11px;
    color: var(--text-secondary);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .telemetry-bar {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 13px;
    border-radius: 999px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    font-size: 12px;
    color: var(--text-secondary);
    transition: all 0.3s var(--ease-spring);
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--emerald);
    box-shadow: 0 0 8px var(--emerald);
  }

  /* Main Layout Grid */
  .workspace {
    max-width: 1480px;
    margin: 28px auto;
    padding: 0 28px 48px;
    display: grid;
    grid-template-columns: 430px 1fr;
    gap: 24px;
  }

  @media (max-width: 1100px) {
    .workspace {
      grid-template-columns: 1fr;
    }
  }

  /* Glass Panels */
  .glass-card {
    background: var(--bg-surface);
    backdrop-filter: blur(20px) saturate(160%);
    -webkit-backdrop-filter: blur(20px) saturate(160%);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 22px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45);
    transition: border-color 0.35s var(--ease-spring), transform 0.35s var(--ease-spring);
  }

  .glass-card:hover {
    border-color: var(--border-highlight);
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .section-title {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
  }

  .badge-tag {
    font-size: 11px;
    font-family: var(--font-mono);
    padding: 3px 9px;
    border-radius: 6px;
    background: rgba(59, 130, 246, 0.14);
    color: #93c5fd;
    border: 1px solid rgba(59, 130, 246, 0.25);
  }

  /* Form Controls */
  .field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 13px;
  }

  .field-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
  }

  input, select, textarea {
    width: 100%;
    padding: 10px 13px;
    border-radius: var(--radius-sm);
    background: rgba(9, 12, 18, 0.72);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 13px;
    outline: none;
    transition: all 0.25s var(--ease-spring);
  }

  input:focus, select:focus, textarea:focus {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 3px var(--accent-glow);
  }

  textarea {
    resize: vertical;
    min-height: 76px;
    line-height: 1.45;
  }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.25s var(--ease-spring);
  }

  .btn-primary {
    background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
    color: #ffffff;
    box-shadow: 0 4px 18px rgba(37, 99, 235, 0.38);
  }

  .btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 24px rgba(59, 130, 246, 0.52);
  }

  .btn-secondary {
    background: var(--bg-elevated);
    color: var(--text-primary);
    border-color: var(--border-subtle);
  }

  .btn-secondary:hover {
    background: var(--bg-glass-hover);
    border-color: var(--border-highlight);
  }

  /* Segmented Control (Apple Style) */
  .segmented-control {
    display: grid;
    grid-template-columns: 1fr 1fr;
    background: rgba(8, 10, 16, 0.85);
    padding: 4px;
    border-radius: 11px;
    border: 1px solid var(--border-subtle);
    margin-bottom: 16px;
  }

  .segment-btn {
    padding: 9px 12px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s var(--ease-spring);
  }

  .segment-btn.active {
    background: rgba(59, 130, 246, 0.22);
    color: #ffffff;
    border: 1px solid rgba(59, 130, 246, 0.45);
    box-shadow: 0 2px 12px rgba(59, 130, 246, 0.22);
  }

  /* Quick Prompt Chips */
  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
  }

  .chip {
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.22s var(--ease-spring);
  }

  .chip:hover {
    background: rgba(59, 130, 246, 0.14);
    color: var(--text-primary);
    border-color: rgba(59, 130, 246, 0.4);
    transform: translateY(-1px);
  }

  /* Epistemic Status Banner */
  .status-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 13px 16px;
    border-radius: var(--radius-md);
    margin-bottom: 18px;
    font-size: 13px;
    font-weight: 600;
    animation: fadeSlideIn 0.4s var(--ease-spring);
  }

  .status-certain {
    background: var(--emerald-bg);
    border: 1px solid rgba(16, 185, 129, 0.35);
    color: #34d399;
  }

  .status-uncertain {
    background: var(--amber-bg);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: #fbbf24;
  }

  .status-abstained {
    background: var(--rose-bg);
    border: 1px solid rgba(244, 63, 94, 0.35);
    color: #fb7185;
  }

  .answer-box {
    background: rgba(10, 14, 22, 0.76);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 18px;
    font-size: 14px;
    line-height: 1.65;
    white-space: pre-wrap;
    margin-bottom: 20px;
    animation: fadeSlideIn 0.45s var(--ease-spring);
  }

  .evidence-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .citation-card {
    background: rgba(16, 20, 30, 0.8);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 14px 16px;
    transition: all 0.25s var(--ease-spring);
    animation: fadeSlideIn 0.5s var(--ease-spring);
  }

  .citation-card:hover {
    border-color: rgba(59, 130, 246, 0.4);
    transform: translateX(2px);
  }

  .citation-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;
    font-family: var(--font-mono);
    font-size: 11.5px;
    color: var(--text-secondary);
  }

  .epistemic-box {
    border-radius: var(--radius-md);
    padding: 14px 16px;
    margin-top: 14px;
    font-size: 12.5px;
    animation: fadeSlideIn 0.5s var(--ease-spring);
  }

  .epistemic-hypothesis {
    background: var(--indigo-bg);
    border: 1px solid rgba(129, 140, 248, 0.32);
    color: #c7d2fe;
  }

  .epistemic-warning {
    background: var(--amber-bg);
    border: 1px solid rgba(245, 158, 11, 0.32);
    color: #fde68a;
  }

  .left-stack {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  @keyframes fadeSlideIn {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
</head>
<body>

<header class="topbar">
  <div class="brand">
    <div class="brand-orb">Æ</div>
    <div>
      <div class="brand-title">AETHER RAG • Document Intelligence</div>
      <div class="brand-subtitle">Multi-Tenant Epistemic Verification Engine</div>
    </div>
  </div>
  <div class="telemetry-bar">
    <div class="pill">
      <span class="status-dot"></span>
      <span id="health-status">Cloud Engine Online</span>
    </div>
    <div class="pill">
      <span>Chunks Indexados:</span>
      <strong id="stat-chunks" style="color: var(--text-primary);">0</strong>
    </div>
    <button class="btn btn-primary" onclick="loadEnterpriseDemoDossier()">
      ✦ Cargar Expediente Corporativo Demo
    </button>
  </div>
</header>

<main class="workspace">
  <!-- Left Column: Multi-Tenant Context & Ingestion -->
  <div class="left-stack">
    <section class="glass-card">
      <div class="section-header">
        <span class="section-title">1. Bóveda de Aislamiento Multi-Tenant</span>
        <span class="badge-tag">INVARIANT #3</span>
      </div>
      <div class="field-row">
        <div class="field-group">
          <label for="tenant-id">Tenant ID (X-Tenant-Id)</label>
          <input id="tenant-id" value="bufete-lex-corp" />
        </div>
        <div class="field-group">
          <label for="project-id">Project ID (X-Project-Id)</label>
          <input id="project-id" value="litigios-2026" />
        </div>
      </div>
      <div class="field-group" style="margin-bottom: 8px;">
        <label for="case-id">Expediente / Dossier (case_id)</label>
        <input id="case-id" value="EXP-ARB-904" />
      </div>
      <div class="chip-row" style="margin-top: 10px; margin-bottom: 0;">
        <span class="chip" onclick="switchTenant('bufete-lex-corp', 'litigios-2026')">
          Cliente A: bufete-lex-corp
        </span>
        <span class="chip" onclick="switchTenant('auditoria-externa-z', 'litigios-2026')">
          Cliente B: auditoria-externa-z (Aislado)
        </span>
      </div>
    </section>

    <section class="glass-card">
      <div class="section-header">
        <span class="section-title">2. Ingesta Documental & Router M1</span>
        <span class="badge-tag">RUTAS A–E</span>
      </div>
      <div class="field-row">
        <div class="field-group">
          <label for="doc-id">Document ID</label>
          <input id="doc-id" value="doc-laudo-904" />
        </div>
        <div class="field-group">
          <label for="doc-filename">Archivo Original</label>
          <input id="doc-filename" value="laudo_arbitral_infraestructura.pdf" />
        </div>
      </div>
      <div class="field-group">
        <label for="page1-text">Página 1 (Ruta A — Capa Digital)</label>
        <textarea id="page1-text">Sección 1 (Objeto y Penalidades): El consorcio constructor pagará una cláusula penal por mora de 420,000 USD si supera los 180 días de ejecución.</textarea>
      </div>
      <div class="field-group">
        <label for="page2-text">Página 2 (Ruta D — Tabla / Sello con Incertidumbre)</label>
        <textarea id="page2-text">Sección 2 (Liquidación de Pagos): Pago número uno por 150,000 USD ejecutado en enero. Pago número dos por 270,000 USD con sello notarial parcialmente [ilegible] en marzo.</textarea>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
        <span id="ingest-feedback" style="font-size: 12px; color: var(--text-secondary);">
          Listo para indexar en VectorStore + BM25
        </span>
        <button class="btn btn-secondary" onclick="ingestCustomDocument()">
          Indexar Documento
        </button>
      </div>
    </section>
  </div>

  <!-- Right Column: Intelligence & Epistemic Verification Console -->
  <section class="glass-card" style="display: flex; flex-direction: column;">
    <div class="section-header">
      <span class="section-title">3. Consola de Recuperación Híbrida / Agéntica & Generación Citada</span>
      <span class="badge-tag">MÓDULOS 3 & 4</span>
    </div>

    <div class="segmented-control">
      <button id="mode-hybrid" class="segment-btn active" onclick="setMode('standard_hybrid')">
        Standard Hybrid (Vector + BM25 + RRF)
      </button>
      <button id="mode-agentic" class="segment-btn" onclick="setMode('deep_agentic')">
        Deep Agentic (Query Planner + Exhaustive Scan)
      </button>
    </div>

    <div class="chip-row">
      <span class="chip" onclick="runPresetQuery('¿Cuál es la cláusula penal por mora y el plazo de 180 días?', 'standard_hybrid')">
        ✦ Consulta Cierta (Página 1)
      </span>
      <span class="chip" onclick="runPresetQuery('¿Cuál es el pago número dos de 270,000 USD con sello en marzo?', 'standard_hybrid')">
        ⚠ Consulta con Incertidumbre [ilegible] (Página 2)
      </span>
      <span class="chip" onclick="runPresetQuery('¿Cuál es la cláusula penal por mora y además listar cada pago del expediente?', 'deep_agentic')">
        ⚡ Barrido Exhaustivo Agéntico ("cada pago")
      </span>
      <span class="chip" onclick="runPresetQuery('¿Existe algún dictamen ambiental o peritaje geológico?', 'standard_hybrid')">
        🛡 Prueba de Abstención Epistemológica
      </span>
    </div>

    <div style="display: flex; gap: 10px; margin-bottom: 22px;">
      <input
        id="query-input"
        placeholder="Escribe una consulta jurídica o técnica verificable..."
        value="¿Cuál es la cláusula penal por mora y el plazo de 180 días?"
        onkeydown="if(event.key==='Enter') executeQuery()"
      />
      <button class="btn btn-primary" style="min-width: 155px;" onclick="executeQuery()">
        Consultar Evidencia
      </button>
    </div>

    <div id="results-container" style="flex: 1;">
      <div style="text-align: center; padding: 64px 24px; color: var(--text-muted);">
        Haz clic en <strong>"✦ Cargar Expediente Corporativo Demo"</strong> en la barra superior
        para inicializar el índice y verificar el motor de extremo a extremo.
      </div>
    </div>
  </section>
</main>

<script>
  let activeMode = "standard_hybrid";

  function setMode(mode) {
    activeMode = mode;
    document.getElementById("mode-hybrid").classList.toggle("active", mode === "standard_hybrid");
    document.getElementById("mode-agentic").classList.toggle("active", mode === "deep_agentic");
  }

  function switchTenant(tenantId, projectId) {
    document.getElementById("tenant-id").value = tenantId;
    document.getElementById("project-id").value = projectId;
    executeQuery();
  }

  async function refreshHealth() {
    try {
      const res = await fetch("/health");
      const data = await res.json();
      document.getElementById("stat-chunks").textContent = data.indexed_chunks;
    } catch (err) {
      console.error(err);
    }
  }

  async function ingestCustomDocument() {
    const tenantId = document.getElementById("tenant-id").value.trim();
    const projectId = document.getElementById("project-id").value.trim();
    const caseId = document.getElementById("case-id").value.trim();
    const docId = document.getElementById("doc-id").value.trim();
    const filename = document.getElementById("doc-filename").value.trim();
    const p1 = document.getElementById("page1-text").value.trim();
    const p2 = document.getElementById("page2-text").value.trim();
    const fb = document.getElementById("ingest-feedback");

    fb.textContent = "Procesando e indexando...";
    const res = await fetch("/v1/documents/ingest", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Tenant-Id": tenantId,
        "X-Project-Id": projectId
      },
      body: JSON.stringify({
        job_id: "job-" + Date.now(),
        document_id: docId,
        filename: filename,
        case_id: caseId || null,
        raw_content_text: "%PDF-1.7 " + p1 + "\n" + p2,
        pages: [
          { page_number: 1, digital_text: p1, block_type: "header" },
          {
            page_number: 2,
            digital_text: p2,
            has_complex_tables_or_diagrams: true,
            block_type: "table"
          }
        ]
      })
    });

    if (!res.ok) {
      const err = await res.json();
      fb.style.color = "var(--rose)";
      fb.textContent = "Error: " + (err.detail || res.statusText);
      return false;
    }

    const data = await res.json();
    fb.style.color = "var(--emerald)";
    fb.textContent = "✓ Indexados " + data.chunks_indexed + " chunks en " + data.receipt.gcs_uri;
    await refreshHealth();
    return true;
  }

  async function loadEnterpriseDemoDossier() {
    document.getElementById("tenant-id").value = "bufete-lex-corp";
    document.getElementById("project-id").value = "litigios-2026";
    const ok = await ingestCustomDocument();
    if (ok) {
      await executeQuery();
    }
  }

  function runPresetQuery(questionText, mode) {
    document.getElementById("query-input").value = questionText;
    setMode(mode);
    executeQuery();
  }

  async function executeQuery() {
    const tenantId = document.getElementById("tenant-id").value.trim();
    const projectId = document.getElementById("project-id").value.trim();
    const caseId = document.getElementById("case-id").value.trim();
    const question = document.getElementById("query-input").value.trim();
    const container = document.getElementById("results-container");

    const t0 = performance.now();
    const res = await fetch("/v1/rag/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Tenant-Id": tenantId,
        "X-Project-Id": projectId
      },
      body: JSON.stringify({
        question: question,
        case_id: caseId || null,
        mode: activeMode,
        top_k: 4
      })
    });
    const elapsedMs = Math.round(performance.now() - t0);

    if (!res.ok) {
      const err = await res.json();
      container.innerHTML = `<div class="status-banner status-abstained">
        <span>Error de Autorización (${res.status})</span>
        <span>${err.detail || "Acceso denegado"}</span>
      </div>`;
      return;
    }

    const data = await res.json();
    renderRAGResponse(data, elapsedMs);
  }

  function renderRAGResponse(data, elapsedMs) {
    const container = document.getElementById("results-container");
    let statusClass = "status-certain";
    let statusLabel = "✓ GROUNDED CERTAIN — Evidencia Verificada sin Incertidumbre";

    if (data.epistemic_status === "grounded_with_uncertainty") {
      statusClass = "status-uncertain";
      statusLabel = "⚠ GROUNDED WITH UNCERTAINTY — Contiene Pasajes [ilegible] o Revisión Pendiente";
    } else if (data.epistemic_status === "abstained_insufficient_evidence") {
      statusClass = "status-abstained";
      statusLabel = "🛡 ABSTAINED — Insuficiencia de Evidencia (Cero Alucinación)";
    }

    const citationsHtml = (data.citations || []).map(c => `
      <div class="citation-card">
        <div class="citation-meta">
          <span><strong>Chunk:</strong> ${c.chunk_id} • <strong>Pág:</strong> ${c.page_start}-${c.page_end}</span>
          <span>RRF: ${c.rrf_score} | Rerank: ${c.rerank_score ?? "N/A"}</span>
        </div>
        <div style="font-size: 13px; color: var(--text-primary); margin-bottom: 6px;">
          "${c.observed_excerpt}"
        </div>
        <div style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">
          Origen GCS: ${c.source_reference}
        </div>
      </div>
    `).join("");

    const warningsHtml = (data.uncertainty_warnings || []).length > 0
      ? `<div class="epistemic-box epistemic-warning">
          <strong>Advertencias de Incertidumbre Documental:</strong><br/>
          ${data.uncertainty_warnings.map(w => "• " + w).join("<br/>")}
         </div>`
      : "";

    const hypothesesHtml = (data.segregated_inferential_hypotheses || []).length > 0
      ? `<div class="epistemic-box epistemic-hypothesis">
          <strong>Hipótesis Inferidas Segregadas (No mezcladas con hechos):</strong><br/>
          ${data.segregated_inferential_hypotheses.map(h => "• " + h).join("<br/>")}
         </div>`
      : "";

    container.innerHTML = `
      <div class="status-banner ${statusClass}">
        <span>${statusLabel}</span>
        <span style="font-family: var(--font-mono); font-size: 11.5px;">
          ${data.mode.toUpperCase()} • ${elapsedMs} ms • Tenant: ${data.scope.tenant_id}
        </span>
      </div>
      <div class="answer-box">${data.synthesized_answer}</div>
      <div class="section-header" style="margin-top: 8px;">
        <span class="section-title">Citas Documentales Verificables (${(data.citations || []).length})</span>
        <span class="badge-tag">${data.generator_model_version}</span>
      </div>
      <div class="evidence-grid">${citationsHtml}</div>
      ${warningsHtml}
      ${hypothesesHtml}
    `;
  }

  refreshHealth();
</script>
</body>
</html>
"""
