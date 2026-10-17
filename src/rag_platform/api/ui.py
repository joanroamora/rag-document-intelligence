"""Minimalist Apple Control Center / Fluent Glassmorphic Web UI with PDF Upload and Knobs."""

# ruff: noqa: E501

ENTERPRISE_UI_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>AETHER RAG — Enterprise Document Intelligence</title>
<style>
  :root {
    --bg: #06080d;
    --panel: rgba(18, 23, 34, 0.74);
    --panel-elevated: rgba(28, 35, 52, 0.68);
    --border: rgba(255, 255, 255, 0.09);
    --border-active: rgba(59, 130, 246, 0.55);
    --text: #f8fafc;
    --muted: #94a3b8;
    --subtle: #64748b;
    --accent: #3b82f6;
    --emerald: #10b981;
    --amber: #f59e0b;
    --rose: #f43f5e;
    --indigo: #818cf8;
    --spring: cubic-bezier(0.16, 1, 0.3, 1);
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI Variable", system-ui, sans-serif;
    --mono: "SF Mono", "Cascadia Code", monospace;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    background-image:
      radial-gradient(circle at 12% 8%, rgba(59, 130, 246, 0.14), transparent 38%),
      radial-gradient(circle at 88% 12%, rgba(16, 185, 129, 0.08), transparent 36%);
    color: var(--text);
    font-family: var(--font);
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
  }

  /* Toast Notification */
  #toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 999;
    padding: 12px 18px;
    border-radius: 14px;
    background: rgba(15, 23, 42, 0.92);
    backdrop-filter: blur(20px);
    border: 1px solid var(--border-active);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55);
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
    transform: translateY(120%);
    opacity: 0;
    transition: all 0.35s var(--spring);
    pointer-events: none;
  }
  #toast.show {
    transform: translateY(0);
    opacity: 1;
  }

  /* Top Bar */
  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 28px;
    background: rgba(8, 11, 18, 0.8);
    backdrop-filter: blur(24px);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 50;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .orb {
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: linear-gradient(135deg, #3b82f6, #10b981);
    display: grid;
    place-items: center;
    font-weight: 700;
    font-size: 15px;
    box-shadow: 0 0 18px rgba(59, 130, 246, 0.45);
  }

  .top-stats {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .stat-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 999px;
    background: var(--panel-elevated);
    border: 1px solid var(--border);
    font-size: 12.5px;
    color: var(--muted);
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--emerald);
    box-shadow: 0 0 8px var(--emerald);
  }

  /* Main Layout */
  .layout {
    max-width: 1360px;
    margin: 24px auto;
    padding: 0 24px 40px;
    display: grid;
    grid-template-columns: 360px 1fr;
    gap: 22px;
  }

  @media (max-width: 980px) {
    .layout { grid-template-columns: 1fr; }
  }

  .card {
    background: var(--panel);
    backdrop-filter: blur(24px) saturate(160%);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 20px;
    box-shadow: 0 20px 45px rgba(0, 0, 0, 0.4);
  }

  .card-title {
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin-bottom: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  /* Dropzone */
  .dropzone {
    border: 1.5px dashed rgba(59, 130, 246, 0.45);
    background: rgba(59, 130, 246, 0.05);
    border-radius: 16px;
    padding: 22px 16px;
    text-align: center;
    cursor: pointer;
    transition: all 0.25s var(--spring);
    margin-bottom: 12px;
  }
  .dropzone:hover, .dropzone.dragover {
    background: rgba(59, 130, 246, 0.12);
    border-color: var(--accent);
    transform: scale(1.01);
  }
  .dropzone-icon {
    font-size: 26px;
    margin-bottom: 6px;
  }
  .dropzone-title {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text);
  }
  .dropzone-sub {
    font-size: 11.5px;
    color: var(--muted);
    margin-top: 3px;
  }

  /* Buttons */
  .btn {
    width: 100%;
    padding: 11px 16px;
    border-radius: 12px;
    border: 1px solid transparent;
    font-family: var(--font);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.22s var(--spring);
  }
  .btn:active { transform: scale(0.97); }
  .btn:disabled { opacity: 0.55; cursor: wait; }

  .btn-primary {
    background: linear-gradient(180deg, #3b82f6, #2563eb);
    color: #fff;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35);
  }
  .btn-primary:hover:not(:disabled) {
    box-shadow: 0 8px 25px rgba(59, 130, 246, 0.55);
    transform: translateY(-1px);
  }

  .btn-ghost {
    background: var(--panel-elevated);
    color: var(--text);
    border-color: var(--border);
  }
  .btn-ghost:hover:not(:disabled) {
    border-color: var(--border-active);
    background: rgba(59, 130, 246, 0.14);
  }

  /* Segmented Pills */
  .segmented {
    display: grid;
    grid-template-columns: 1fr 1fr;
    background: rgba(8, 11, 18, 0.85);
    padding: 4px;
    border-radius: 12px;
    border: 1px solid var(--border);
    margin-bottom: 14px;
  }
  .seg-btn {
    padding: 8px 10px;
    border-radius: 9px;
    border: none;
    background: transparent;
    color: var(--muted);
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s var(--spring);
  }
  .seg-btn.active {
    background: rgba(59, 130, 246, 0.24);
    color: #fff;
    border: 1px solid rgba(59, 130, 246, 0.5);
    box-shadow: 0 2px 10px rgba(59, 130, 246, 0.2);
  }

  /* Knobs / Sliders */
  .knob-row {
    margin-bottom: 14px;
    background: rgba(10, 14, 22, 0.55);
    padding: 11px 14px;
    border-radius: 12px;
    border: 1px solid var(--border);
  }
  .knob-header {
    display: flex;
    justify-content: space-between;
    font-size: 12.5px;
    font-weight: 500;
    margin-bottom: 8px;
  }
  .knob-val {
    font-family: var(--mono);
    color: #93c5fd;
    font-weight: 700;
  }
  input[type="range"] {
    -webkit-appearance: none;
    width: 100%;
    height: 6px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.12);
    outline: none;
  }
  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #fff;
    border: 3px solid var(--accent);
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
    transition: transform 0.15s ease;
  }
  input[type="range"]::-webkit-slider-thumb:hover {
    transform: scale(1.15);
  }

  /* iOS Toggle Switches */
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-radius: 12px;
    background: rgba(10, 14, 22, 0.55);
    border: 1px solid var(--border);
    margin-bottom: 10px;
    font-size: 12.5px;
    font-weight: 500;
  }
  .switch {
    position: relative;
    width: 42px;
    height: 24px;
  }
  .switch input { opacity: 0; width: 0; height: 0; }
  .slider {
    position: absolute;
    inset: 0;
    background: rgba(255, 255, 255, 0.14);
    border-radius: 999px;
    cursor: pointer;
    transition: 0.25s var(--spring);
  }
  .slider:before {
    content: "";
    position: absolute;
    height: 18px;
    width: 18px;
    left: 3px;
    bottom: 3px;
    background: #fff;
    border-radius: 50%;
    transition: 0.25s var(--spring);
  }
  .switch input:checked + .slider {
    background: var(--accent);
  }
  .switch input:checked + .slider:before {
    transform: translateX(18px);
  }

  /* Search & Chips */
  .search-bar {
    display: flex;
    gap: 10px;
    margin-bottom: 14px;
  }
  .search-input {
    flex: 1;
    padding: 13px 16px;
    border-radius: 14px;
    background: rgba(8, 11, 18, 0.85);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 14px;
    outline: none;
    transition: all 0.25s var(--spring);
  }
  .search-input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 20px;
  }
  .chip {
    padding: 7px 13px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--border);
    color: var(--muted);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s var(--spring);
  }
  .chip:hover {
    background: rgba(59, 130, 246, 0.16);
    color: #fff;
    border-color: var(--border-active);
    transform: translateY(-1px);
  }

  /* Results */
  .status-pill {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-radius: 14px;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 14px;
  }
  .st-certain { background: rgba(16, 185, 129, 0.14); border: 1px solid rgba(16, 185, 129, 0.4); color: #34d399; }
  .st-uncertain { background: rgba(245, 158, 11, 0.14); border: 1px solid rgba(245, 158, 11, 0.4); color: #fbbf24; }
  .st-abstained { background: rgba(244, 63, 94, 0.14); border: 1px solid rgba(244, 63, 94, 0.4); color: #fb7185; }

  .answer-card {
    background: rgba(9, 13, 22, 0.8);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px;
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
    margin-bottom: 16px;
  }

  .cite-card {
    background: rgba(15, 20, 32, 0.75);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 10px;
  }
  .cite-top {
    display: flex;
    justify-content: space-between;
    font-family: var(--mono);
    font-size: 11.5px;
    color: #93c5fd;
    margin-bottom: 6px;
  }
  .score-bar-bg {
    height: 4px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    overflow: hidden;
    margin-top: 8px;
  }
  .score-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6, #10b981);
    border-radius: 999px;
  }
</style>
</head>
<body>

<div id="toast">Listo</div>

<header class="topbar">
  <div class="brand">
    <div class="orb">Æ</div>
    <div>
      <div style="font-size: 15px; font-weight: 700; letter-spacing: -0.02em;">AETHER RAG</div>
      <div style="font-size: 11px; color: var(--muted);">Document Intelligence Studio</div>
    </div>
  </div>
  <div class="top-stats">
    <div class="stat-pill">
      <span class="dot"></span>
      <span>Cloud Run</span>
    </div>
    <div class="stat-pill">
      <span>Chunks:</span>
      <strong id="stat-chunks" style="color: #fff;">0</strong>
    </div>
  </div>
</header>

<main class="layout">
  <!-- Left Column: Upload & Tactile Controls -->
  <div style="display: flex; flex-direction: column; gap: 18px;">
    <section class="card">
      <div class="card-title">
        <span>1. Documento (PDF / TXT / DOCX)</span>
        <span id="file-badge" style="color: #93c5fd; font-family: var(--mono);">LISTO</span>
      </div>

      <input
        type="file"
        id="file-input"
        accept=".pdf,.txt,.rtf,.docx"
        style="display: none;"
      />
      <div class="dropzone" id="dropzone">
        <div class="dropzone-icon">📄</div>
        <div class="dropzone-title" id="dropzone-label">Subir archivo PDF o TXT</div>
        <div class="dropzone-sub">Arrastra aquí o haz clic para explorar</div>
      </div>

      <div id="progress-container" style="display: none; margin-bottom: 12px; background: rgba(10, 14, 22, 0.65); padding: 12px; border-radius: 14px; border: 1px solid var(--border);">
        <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
          <span id="progress-status" style="color: var(--muted); font-weight: 500;">Subiendo archivo...</span>
          <span id="progress-percent" style="font-family: var(--mono); color: #93c5fd; font-weight: 700;">0%</span>
        </div>
        <div style="height: 6px; background: rgba(255, 255, 255, 0.08); border-radius: 999px; overflow: hidden;">
          <div id="progress-bar-fill" style="height: 100%; width: 0%; background: linear-gradient(90deg, #3b82f6, #10b981); border-radius: 999px; transition: width 0.2s ease;"></div>
        </div>
      </div>

      <button class="btn btn-ghost" id="btn-demo">
        ✦ Cargar Expediente Demo (1-Clic)
      </button>
    </section>

    <section class="card">
      <div class="card-title">
        <span>2. Controles & Perillas</span>
        <span style="font-family: var(--mono); color: var(--emerald);">MULTI-TENANT</span>
      </div>

      <div style="font-size: 12px; color: var(--muted); margin-bottom: 6px;">Espacio de Cliente (Tenant)</div>
      <div class="segmented">
        <button class="seg-btn active" id="btn-tenant-a" type="button">🏢 LexCorp</button>
        <button class="seg-btn" id="btn-tenant-b" type="button">🔒 Auditoría</button>
      </div>

      <div style="font-size: 12px; color: var(--muted); margin-bottom: 6px;">Modo de Recuperación</div>
      <div class="segmented">
        <button class="seg-btn active" id="btn-mode-hybrid" type="button">⚡ Hybrid</button>
        <button class="seg-btn" id="btn-mode-agentic" type="button">🧠 Agentic</button>
      </div>

      <div class="knob-row">
        <div class="knob-header">
          <span>Precisión Top-K Evidencias</span>
          <span class="knob-val" id="val-topk">4</span>
        </div>
        <input type="range" id="knob-topk" min="1" max="10" value="4" />
      </div>

      <div class="knob-row">
        <div class="knob-header">
          <span>Presupuesto Subconsultas</span>
          <span class="knob-val" id="val-subq">3</span>
        </div>
        <input type="range" id="knob-subq" min="1" max="8" value="3" />
      </div>

      <div class="toggle-row">
        <span>Visión Tablas (Ruta D Flash)</span>
        <label class="switch">
          <input type="checkbox" id="toggle-routed" checked />
          <span class="slider"></span>
        </label>
      </div>

      <div class="toggle-row" style="margin-bottom: 0;">
        <span>Barrido Exhaustivo ("Todos")</span>
        <label class="switch">
          <input type="checkbox" id="toggle-exhaustive" />
          <span class="slider"></span>
        </label>
      </div>
    </section>
  </div>

  <!-- Right Column: Search & Visual Evidence -->
  <section class="card" style="display: flex; flex-direction: column;">
    <div class="card-title">
      <span>3. Consulta Verificable</span>
      <span id="active-scope-label" style="font-family: var(--mono); color: #93c5fd;">
        tenant: bufete-lex-corp
      </span>
    </div>

    <div class="search-bar">
      <input
        class="search-input"
        id="query-input"
        placeholder="Pregunta sobre tus documentos indexados..."
        value="¿Cuál es la cláusula penal por mora y el plazo de 180 días?"
      />
      <button class="btn btn-primary" id="btn-ask" style="width: 150px;">
        Consultar
      </button>
    </div>

    <div class="chips">
      <button class="chip" type="button" data-q="¿Cuál es la cláusula penal por mora y el plazo de 180 días?" data-m="standard_hybrid">
        ✦ Cláusula Penal
      </button>
      <button class="chip" type="button" data-q="¿Cuál es el pago número dos de 270,000 USD con sello en marzo?" data-m="standard_hybrid">
        ⚠ Pago [Ilegible]
      </button>
      <button class="chip" type="button" data-q="¿Cuál es la cláusula penal por mora y además listar cada pago del expediente?" data-m="deep_agentic">
        ⚡ Todos los Pagos
      </button>
      <button class="chip" type="button" data-q="¿Existe algún dictamen ambiental o geológico?" data-m="standard_hybrid">
        🛡 Abstención
      </button>
    </div>

    <div id="results-area" style="flex: 1;">
      <div style="text-align: center; padding: 70px 20px; color: var(--subtle); font-size: 13.5px;">
        Sube un archivo <strong>PDF / TXT</strong> a la izquierda o pulsa
        <strong>"✦ Cargar Expediente Demo (1-Clic)"</strong> para comenzar.
      </div>
    </div>
  </section>
</main>

<script>
  const state = {
    tenantId: "bufete-lex-corp",
    projectId: "litigios-2026",
    mode: "standard_hybrid",
    topK: 4,
    maxSubqueries: 3
  };

  function showToast(msg, isError = false) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.style.borderColor = isError ? "var(--rose)" : "var(--emerald)";
    t.classList.add("show");
    clearTimeout(window._toastTimer);
    window._toastTimer = setTimeout(() => t.classList.remove("show"), 3200);
  }

  async function refreshHealth() {
    try {
      const res = await fetch("/health");
      if (res.ok) {
        const data = await res.json();
        document.getElementById("stat-chunks").textContent = data.indexed_chunks;
      }
    } catch (e) {
      console.error(e);
    }
  }

  function setTenant(tenantId, isA) {
    state.tenantId = tenantId;
    document.getElementById("btn-tenant-a").classList.toggle("active", isA);
    document.getElementById("btn-tenant-b").classList.toggle("active", !isA);
    document.getElementById("active-scope-label").textContent = "tenant: " + tenantId;
    showToast("Cambiado a " + tenantId);
    executeQuery();
  }

  function setMode(mode) {
    state.mode = mode;
    document.getElementById("btn-mode-hybrid").classList.toggle("active", mode === "standard_hybrid");
    document.getElementById("btn-mode-agentic").classList.toggle("active", mode === "deep_agentic");
  }

  async function loadDemoDossier() {
    const btn = document.getElementById("btn-demo");
    const badge = document.getElementById("file-badge");
    btn.disabled = true;
    btn.textContent = "⏳ Indexando Demo...";
    badge.textContent = "PROCESANDO";

    try {
      setTenant("bufete-lex-corp", true);
      const p1 = "Sección 1 (Objeto y Penalidades): El consorcio constructor pagará una cláusula penal por mora de 420,000 USD si supera los 180 días de ejecución.";
      const p2 = "Sección 2 (Liquidación de Pagos): Pago número uno por 150,000 USD ejecutado en enero. Pago número dos por 270,000 USD con sello notarial parcialmente [ilegible] en marzo.";

      const res = await fetch("/v1/documents/ingest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-Id": state.tenantId,
          "X-Project-Id": state.projectId
        },
        body: JSON.stringify({
          job_id: "job-demo-" + Date.now(),
          document_id: "doc-laudo-904",
          filename: "laudo_arbitral_demo.pdf",
          raw_content_text: "%PDF-1.7 " + p1 + " " + p2,
          pages: [
            { page_number: 1, digital_text: p1, block_type: "header" },
            {
              page_number: 2,
              digital_text: p2,
              has_complex_tables_or_diagrams: document.getElementById("toggle-routed").checked,
              block_type: "table"
            }
          ]
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Error al indexar demo");
      }

      const data = await res.json();
      badge.textContent = data.chunks_indexed + " CHUNKS";
      showToast("✓ Demo cargada (" + data.chunks_indexed + " chunks indexados)");
      await refreshHealth();
      await executeQuery();
    } catch (err) {
      badge.textContent = "ERROR";
      showToast("Error: " + err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = "✦ Cargar Expediente Demo (1-Clic)";
    }
  }

  function handleFileUpload(file) {
    if (!file) return;
    const label = document.getElementById("dropzone-label");
    const badge = document.getElementById("file-badge");
    const container = document.getElementById("results-area");
    const progBox = document.getElementById("progress-container");
    const progStatus = document.getElementById("progress-status");
    const progPercent = document.getElementById("progress-percent");
    const progFill = document.getElementById("progress-bar-fill");

    label.textContent = "⏳ Subiendo " + file.name + "...";
    badge.textContent = "0%";
    badge.style.color = "#93c5fd";

    progBox.style.display = "block";
    progFill.style.width = "0%";
    progFill.style.background = "linear-gradient(90deg, #3b82f6, #10b981)";
    progPercent.textContent = "0%";
    progStatus.textContent = "Iniciando carga de " + file.name + "...";

    const formData = new FormData();
    formData.append("file", file);
    formData.append("force_multimodal_route_d", document.getElementById("toggle-routed").checked);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/v1/documents/upload-file", true);
    xhr.setRequestHeader("X-Tenant-Id", state.tenantId);
    xhr.setRequestHeader("X-Project-Id", state.projectId);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        progFill.style.width = pct + "%";
        progPercent.textContent = pct + "%";
        badge.textContent = pct + "%";
        if (pct < 100) {
          progStatus.textContent = "Transmitiendo archivo (" + pct + "%)...";
        } else {
          progStatus.textContent = "Archivo recibido. Indexando páginas y extrayendo texto...";
          badge.textContent = "INDEXANDO";
        }
      }
    });

    xhr.onload = async () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          progFill.style.width = "100%";
          progPercent.textContent = "100%";
          progStatus.textContent = "✓ Completado (" + data.chunks_indexed + " chunks indexados)";
          label.textContent = "✓ " + file.name + " (" + data.total_pages + " págs)";
          badge.textContent = data.chunks_indexed + " CHUNKS";
          badge.style.color = "var(--emerald)";
          showToast("✓ Archivo indexado: " + data.chunks_indexed + " chunks");

          const queryInput = document.getElementById("query-input");
          if (queryInput.value.includes("cláusula penal")) {
            queryInput.value = "¿En qué año ocurrieron los hechos y dónde?";
          }

          container.innerHTML = `
            <div class="status-pill st-certain">
              <span>✓ DOCUMENTO INDEXADO CON ÉXITO</span>
              <span style="font-family: var(--mono); font-size: 11.5px;">${data.total_pages} págs • ${data.chunks_indexed} chunks</span>
            </div>
            <div class="answer-card" style="color: #cbd5e1; font-size: 13.5px;">
              Se indexaron <strong>${data.chunks_indexed} fragmentos</strong> de <strong>${file.name}</strong> (${data.total_pages} páginas) en el espacio <code>${state.tenantId}</code>.<br/><br/>
              Ya está listo para consultas con citas verificables. Escribe tu pregunta arriba y pulsa <strong>Consultar</strong>.
            </div>
          `;
          await refreshHealth();
        } catch (e) {
          showUploadError("Error interpretando la respuesta del servidor.");
        }
      } else {
        let errorDetail = "Error en el servidor (" + xhr.status + ")";
        try {
          const errJson = JSON.parse(xhr.responseText);
          errorDetail = errJson.detail || errorDetail;
        } catch (_) {
          if (xhr.status === 413) {
            errorDetail = "El archivo supera el límite de 32 MB permitido por el servidor.";
          } else if (xhr.status === 504 || xhr.status === 502) {
            errorDetail = "El servidor agotó el tiempo de espera procesando este documento.";
          }
        }
        showUploadError(errorDetail);
      }
    };

    xhr.onerror = () => {
      showUploadError("Fallo de conexión de red al conectar con Cloud Run.");
    };

    function showUploadError(msg) {
      progFill.style.background = "var(--rose)";
      progStatus.textContent = "⚠ Error al procesar";
      progPercent.textContent = "Error";
      label.textContent = "Subir archivo PDF o TXT";
      badge.textContent = "ERROR";
      badge.style.color = "var(--rose)";
      showToast("Error: " + msg, true);
      container.innerHTML = `
        <div class="status-pill st-abstained">
          <span>⚠ ERROR AL SUBIR O PROCESAR DOCUMENTO</span>
        </div>
        <div class="answer-card" style="border-color: rgba(244, 63, 94, 0.4); color: #fca5a5; font-size: 13.5px;">
          <strong>Detalle del error:</strong> ${msg}<br/><br/>
          <em>Si el PDF es un escaneo de imágenes sin texto digital, activa el switch <strong>'Visión Tablas (Ruta D Flash)'</strong> a la izquierda para procesarlo con visión multimodal.</em>
        </div>
      `;
    }

    xhr.send(formData);
  }

  async function executeQuery() {
    const btn = document.getElementById("btn-ask");
    const container = document.getElementById("results-area");
    let question = document.getElementById("query-input").value.trim();
    if (!question) return;

    const isExhaustive = document.getElementById("toggle-exhaustive").checked;
    if (isExhaustive && !question.toLowerCase().includes("todos")) {
      question = "Listar todos: " + question;
    }

    btn.disabled = true;
    btn.textContent = "Buscando...";
    const t0 = performance.now();

    container.innerHTML = `
      <div style="text-align: center; padding: 45px 20px; color: var(--muted);">
        <div style="font-size: 26px; margin-bottom: 8px;">🔍</div>
        <div style="font-size: 13.5px; font-weight: 600; color: #f8fafc;">Buscando evidencias para: "${question}"</div>
        <div style="font-size: 12px; color: var(--subtle); margin-top: 4px;">Recuperando y analizando fragmentos documentales...</div>
      </div>
    `;

    try {
      const res = await fetch("/v1/rag/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-Id": state.tenantId,
          "X-Project-Id": state.projectId
        },
        body: JSON.stringify({
          question: question,
          mode: state.mode,
          top_k: state.topK,
          exhaustive: isExhaustive,
          budget: {
            max_iterations: 3,
            max_subqueries: state.maxSubqueries,
            max_parallelism: 3,
            max_input_tokens: 32000,
            timeout_seconds: 30
          }
        })
      });

      const ms = Math.round(performance.now() - t0);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Error en consulta");
      }

      const data = await res.json();
      renderResponse(data, ms);
    } catch (err) {
      container.innerHTML = `<div class="status-pill st-abstained">Error: ${err.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Consultar";
    }
  }

  function renderResponse(data, ms) {
    const container = document.getElementById("results-area");
    let stClass = "st-certain";
    let stText = "✓ EVIDENCIA VERIFICADA";

    if (data.epistemic_status === "grounded_with_uncertainty") {
      stClass = "st-uncertain";
      stText = "⚠ CON INCERTIDUMBRE [ILEGIBLE]";
    } else if (data.epistemic_status === "abstained_insufficient_evidence") {
      stClass = "st-abstained";
      stText = "🛡 ABSTENCIÓN — SIN EVIDENCIA EN ESTE TENANT";
    }

    const cites = (data.citations || []).map(c => {
      const pct = Math.min(100, Math.round((c.rerank_score || 0.5) * 100));
      return `
        <div class="cite-card">
          <div class="cite-top">
            <span>${c.chunk_id} • Pág ${c.page_start}-${c.page_end}</span>
            <span>Relevancia: ${pct}% (RRF ${c.rrf_score})</span>
          </div>
          <div style="font-size: 13px; color: var(--text);">"${c.observed_excerpt}"</div>
          <div class="score-bar-bg"><div class="score-bar-fill" style="width: ${pct}%;"></div></div>
        </div>
      `;
    }).join("");

    const warnings = (data.uncertainty_warnings || []).length
      ? `<div class="cite-card" style="border-color: rgba(245, 158, 11, 0.4); color: #fde68a; font-size: 12.5px;">
          <strong>⚠ Pasajes Inciertos:</strong> ${data.uncertainty_warnings.join(" | ")}
         </div>`
      : "";

    container.innerHTML = `
      <div class="status-pill ${stClass}">
        <span>${stText}</span>
        <span style="font-family: var(--mono); font-size: 11.5px;">${ms} ms • Top-${state.topK}</span>
      </div>
      <div style="font-size: 13px; font-weight: 600; color: #93c5fd; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
        <span style="color: var(--muted); font-size: 11.5px; text-transform: uppercase;">Consulta:</span>
        <span>"${data.question}"</span>
      </div>
      <div class="answer-card">${data.synthesized_answer}</div>
      ${warnings}
      <div style="font-size: 11.5px; color: var(--muted); text-transform: uppercase; margin: 12px 0 8px;">
        Fuentes Citadas (${(data.citations || []).length})
      </div>
      ${cites}
    `;
  }

  // Bind all interactive controls safely on DOM ready
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btn-demo").addEventListener("click", loadDemoDossier);
    document.getElementById("btn-ask").addEventListener("click", executeQuery);
    document.getElementById("query-input").addEventListener("keydown", e => {
      if (e.key === "Enter") executeQuery();
    });

    document.getElementById("btn-tenant-a").addEventListener("click", () => setTenant("bufete-lex-corp", true));
    document.getElementById("btn-tenant-b").addEventListener("click", () => setTenant("auditoria-externa-z", false));
    document.getElementById("btn-mode-hybrid").addEventListener("click", () => setMode("standard_hybrid"));
    document.getElementById("btn-mode-agentic").addEventListener("click", () => setMode("deep_agentic"));

    const knobTopK = document.getElementById("knob-topk");
    knobTopK.addEventListener("input", e => {
      state.topK = parseInt(e.target.value, 10);
      document.getElementById("val-topk").textContent = state.topK;
    });

    const knobSubq = document.getElementById("knob-subq");
    knobSubq.addEventListener("input", e => {
      state.maxSubqueries = parseInt(e.target.value, 10);
      document.getElementById("val-subq").textContent = state.maxSubqueries;
    });

    const dz = document.getElementById("dropzone");
    const fi = document.getElementById("file-input");
    dz.addEventListener("click", () => fi.click());
    fi.addEventListener("change", e => handleFileUpload(e.target.files[0]));
    dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("dragover"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
    dz.addEventListener("drop", e => {
      e.preventDefault();
      dz.classList.remove("dragover");
      if (e.dataTransfer.files.length) handleFileUpload(e.dataTransfer.files[0]);
    });

    document.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        document.getElementById("query-input").value = chip.getAttribute("data-q");
        setMode(chip.getAttribute("data-m"));
        executeQuery();
      });
    });

    refreshHealth();
  });
</script>
</body>
</html>
"""
