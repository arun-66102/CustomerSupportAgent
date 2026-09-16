// ── Config ─────────────────────────────────────────────────────────────
const API_BASE = (window.location.protocol.startsWith('http')) 
  ? window.location.origin 
  : 'http://localhost:8000';

// ── State ──────────────────────────────────────────────────────────────
let lastPipelineResult = null;
let isLoading = false;
let evalMode = 'quick';
let sampleSize = 20;

// ── DOM Ready ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initChat();
  initEvaluation();
  checkHealth();
  loadTaxonomy();
  setInterval(checkHealth, 30000);
});

// ── Health Check ───────────────────────────────────────────────────────
async function checkHealth() {
  const dot = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(5000) });
    if (res.ok) {
      const data = await res.json();
      dot.className = 'status-dot online';
      text.textContent = `Online · ${data.conversations_loaded.toLocaleString()} records`;
    } else {
      throw new Error();
    }
  } catch {
    dot.className = 'status-dot error';
    text.textContent = 'Backend offline — run start.bat';
  }
}

// ── Unified Tab Navigation (Top Nav + Floating Dock + Footer) ─────────
function initTabs() {
  const allTabTriggers = document.querySelectorAll('[data-tab]');
  allTabTriggers.forEach(el => {
    el.addEventListener('click', (e) => {
      const tab = el.dataset.tab;
      if (tab) {
        if (el.tagName === 'A') e.preventDefault();
        switchTab(tab);
      }
    });
  });

  const floatingAction = document.getElementById('floating-action-btn');
  if (floatingAction) {
    floatingAction.addEventListener('click', () => {
      switchTab('chat');
      const input = document.getElementById('messageInput');
      if (input) {
        input.focus();
        input.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  }
}

function switchTab(tab) {
  // Update top buttons
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });

  // Update floating dock buttons
  document.querySelectorAll('.dock-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });

  // Update tab panels
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  const targetPanel = document.getElementById(`panel${capitalize(tab)}`);
  if (targetPanel) {
    targetPanel.classList.add('active');
    targetPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function capitalize(str) {
  const map = { chat: 'Chat', pipeline: 'Pipeline', evaluation: 'Eval', taxonomy: 'Taxonomy' };
  return map[str] || str.charAt(0).toUpperCase() + str.slice(1);
}

// ── Chat Controller ────────────────────────────────────────────────────
function initChat() {
  const input = document.getElementById('messageInput');
  const sendBtn = document.getElementById('sendBtn');
  const charCount = document.getElementById('charCount');

  if (input) {
    input.addEventListener('input', () => {
      charCount.textContent = input.value.length;
      autoResize(input);
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  if (sendBtn) {
    sendBtn.addEventListener('click', sendMessage);
  }

  // Quick prompt buttons
  document.querySelectorAll('.quick-prompt').forEach(btn => {
    btn.addEventListener('click', () => {
      const msg = btn.dataset.msg;
      if (msg && input) {
        input.value = msg;
        charCount.textContent = input.value.length;
        autoResize(input);
        sendMessage();
      }
    });
  });
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 130) + 'px';
}

async function sendMessage() {
  const input = document.getElementById('messageInput');
  const msg = input ? input.value.trim() : '';
  if (!msg || isLoading) return;

  isLoading = true;
  input.value = '';
  input.style.height = 'auto';
  document.getElementById('charCount').textContent = '0';
  document.getElementById('sendBtn').disabled = true;

  // Remove welcome screen if visible
  const welcome = document.querySelector('.chat-welcome');
  if (welcome) welcome.remove();

  // Append user message
  appendMessage('user', msg);

  // Show typing indicator
  const typingId = showTyping();

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, top_k: 5 })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server responded with HTTP ${res.status}`);
    }

    const data = await res.json();
    lastPipelineResult = data;

    removeTyping(typingId);
    appendAgentMessage(data);
    updatePipelineTrace(data);

  } catch (err) {
    removeTyping(typingId);
    appendErrorMessage(err.message);
  } finally {
    isLoading = false;
    document.getElementById('sendBtn').disabled = false;
    if (input) input.focus();
  }
}

function appendMessage(role, text) {
  const chatWindow = document.getElementById('chatWindow');
  const wrapper = document.createElement('div');
  wrapper.className = `msg-wrapper msg-${role}`;
  wrapper.innerHTML = `
    <div class="msg-label">
      <iconify-icon icon="${role === 'user' ? 'lucide:user' : 'lucide:apple'}"></iconify-icon>
      <span>${role === 'user' ? 'Customer' : 'Apple Support AI'}</span>
    </div>
    <div class="msg-bubble">${escapeHtml(text)}</div>
  `;
  chatWindow.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function appendAgentMessage(data) {
  const chatWindow = document.getElementById('chatWindow');
  const wrapper = document.createElement('div');
  wrapper.className = 'msg-wrapper msg-agent';

  const intent = data.intent || {};
  const decision = data.decision || {};
  const retrieval = data.retrieval || {};
  const reply = data.final_reply || data.generated_response?.reply || 'No response generated.';
  const dec = data.final_decision || decision.decision || 'UNKNOWN';
  const isEscalate = dec === 'ESCALATE';

  const topResults = (retrieval.results || []).slice(0, 2);
  const evidenceHtml = topResults.length > 0 ? `
    <div class="evidence-snippets">
      <div class="evidence-snippets-title">
        <iconify-icon icon="lucide:book-marked"></iconify-icon>
        Historical Evidence Citations
      </div>
      ${topResults.map(r => `
        <div class="evidence-item">
          <span class="evidence-sim">${(r.similarity * 100).toFixed(0)}% Match</span> — ${escapeHtml(r.customer_message.slice(0, 85))}...
        </div>
      `).join('')}
    </div>
  ` : '';

  wrapper.innerHTML = `
    <div class="msg-label">
      <iconify-icon icon="lucide:apple"></iconify-icon>
      <span>Apple Support AI · Diagnosis</span>
    </div>
    <div class="msg-bubble">
      ${escapeHtml(reply)}
      <div class="decision-badge ${isEscalate ? 'escalate' : 'auto'}">
        <iconify-icon icon="${isEscalate ? 'lucide:alert-triangle' : 'lucide:check-circle'}"></iconify-icon>
        <span>${isEscalate ? 'ESCALATE TO SENIOR ADVISOR' : 'AUTO-RESOLVED & VALIDATED'}</span>
      </div>
      ${evidenceHtml}
    </div>
    <div class="msg-meta">
      <span><iconify-icon icon="lucide:target"></iconify-icon> ${formatIntentLabel(intent.intent)} (${pct(intent.confidence)})</span>
      <span><iconify-icon icon="lucide:zap"></iconify-icon> ${data.total_duration_ms || '?'}ms</span>
      <span><iconify-icon icon="lucide:shield"></iconify-icon> Risk: ${intent.risk || 'LOW'}</span>
      <span><iconify-icon icon="lucide:file-search"></iconify-icon> Evidence: ${retrieval.evidence_quality || 'N/A'}</span>
    </div>
  `;
  chatWindow.appendChild(wrapper);
  scrollToBottom();
}

function appendErrorMessage(msg) {
  const chatWindow = document.getElementById('chatWindow');
  const wrapper = document.createElement('div');
  wrapper.className = 'msg-wrapper msg-agent';
  wrapper.innerHTML = `
    <div class="msg-label">
      <iconify-icon icon="lucide:alert-circle"></iconify-icon>
      <span>Diagnostic Engine Error</span>
    </div>
    <div class="msg-bubble" style="border-color:rgba(239,68,68,0.4); color:#f87171;">
      <strong>Inference Failure:</strong> ${escapeHtml(msg)}
    </div>
  `;
  chatWindow.appendChild(wrapper);
  scrollToBottom();
}

function showTyping() {
  const id = 'typing-' + Date.now();
  const chatWindow = document.getElementById('chatWindow');
  const el = document.createElement('div');
  el.className = 'msg-wrapper msg-agent';
  el.id = id;
  el.innerHTML = `
    <div class="msg-label">
      <iconify-icon icon="lucide:apple"></iconify-icon>
      <span>Apple Support AI</span>
    </div>
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;
  chatWindow.appendChild(el);
  scrollToBottom();
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function scrollToBottom() {
  const cw = document.getElementById('chatWindow');
  if (cw) cw.scrollTop = cw.scrollHeight;
}

// ── Pipeline Trace ────────────────────────────────────────────────────
function updatePipelineTrace(data) {
  const empty = document.getElementById('pipelineEmpty');
  const trace = document.getElementById('pipelineTrace');
  if (!empty || !trace) return;

  empty.classList.add('hidden');
  trace.classList.remove('hidden');
  trace.innerHTML = '';

  const steps = [
    {
      num: '01', title: 'Intent & Risk Classification', icon: 'lucide:target',
      duration: getDuration(data, 'intent_classification'),
      content: buildIntentKV(data.intent)
    },
    {
      num: '02', title: 'RAG Historical Retrieval', icon: 'lucide:search',
      duration: getDuration(data, 'rag_retrieval'),
      content: buildRetrievalContent(data.retrieval)
    },
    {
      num: '03', title: 'Evidence Quality Validation', icon: 'lucide:check-circle-2',
      duration: getDuration(data, 'evidence_validation'),
      content: buildEvidenceKV(data.evidence_validation)
    },
    {
      num: '04', title: 'LLM Response Generation (Groq)', icon: 'lucide:cpu',
      duration: getDuration(data, 'response_generation'),
      content: buildResponseContent(data.generated_response)
    },
    {
      num: '05', title: 'Decision & Escalation Engine', icon: 'lucide:shield-alert',
      duration: getDuration(data, 'decision_engine'),
      content: buildDecisionContent(data.decision)
    }
  ];

  steps.forEach(step => {
    const div = document.createElement('div');
    div.className = 'pipeline-step';
    div.innerHTML = `
      <div class="step-header">
        <div class="step-left">
          <span class="step-num">${step.num}</span>
          <span class="step-title">
            <iconify-icon icon="${step.icon}"></iconify-icon>
            ${step.title}
          </span>
        </div>
        <div class="step-duration">${step.duration}</div>
      </div>
      <div class="step-body">${step.content}</div>
    `;
    trace.appendChild(div);
  });
}

function getDuration(data, stepName) {
  const trace = data.pipeline_trace || [];
  const s = trace.find(t => t.step === stepName);
  return s ? `${s.duration_ms}ms` : '—';
}

function buildIntentKV(intent) {
  if (!intent) return '<p class="kv-key">No telemetry captured</p>';
  const risk = (intent.risk || '').toUpperCase();
  return `
    <div class="step-kv">
      <div class="kv-item"><div class="kv-key">Predicted Intent</div><div class="kv-val" style="color:var(--color-accent);">${intent.intent || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Classifier Confidence</div><div class="kv-val">${pct(intent.confidence)}</div></div>
      <div class="kv-item"><div class="kv-key">Assessed Risk</div><div class="kv-val ${risk.toLowerCase()}">${risk || 'LOW'}</div></div>
      <div class="kv-item"><div class="kv-key">Classification Method</div><div class="kv-val">${intent.method || 'LLM Few-Shot'}</div></div>
    </div>
    ${intent.reasoning ? `<div style="margin-top:14px; font-size:12px; color:var(--text-secondary); padding:10px 14px; background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:8px;">"${escapeHtml(intent.reasoning)}"</div>` : ''}
  `;
}

function buildRetrievalContent(retrieval) {
  if (!retrieval) return '<p class="kv-key">No telemetry captured</p>';
  const results = retrieval.results || [];
  return `
    <div class="step-kv">
      <div class="kv-item"><div class="kv-key">Evidence Quality</div><div class="kv-val" style="color:#34d399;">${retrieval.evidence_quality || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Retrieval Confidence</div><div class="kv-val">${retrieval.retrieval_confidence?.toFixed(3) || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Top Cosine Match</div><div class="kv-val">${retrieval.top_similarity?.toFixed(3) || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Candidate Pool</div><div class="kv-val">${results.length} historical tickets</div></div>
    </div>
    <div class="evidence-list" style="margin-top:14px;">
      ${results.slice(0, 3).map((r, i) => `
        <div class="evidence-card">
          <div class="evidence-card-header">
            <span>Rank 0${i+1}</span>
            <span class="ev-sim">${(r.similarity * 100).toFixed(0)}% Match</span>
            <span style="color:var(--text-faint);">Ticket #${r.conversation_id}</span>
          </div>
          <div class="ev-q"><span class="ev-label">USER</span>${escapeHtml(r.customer_message?.slice(0, 140) || '')}${r.customer_message?.length > 140 ? '...' : ''}</div>
          <div class="ev-a" style="margin-top:6px;"><span class="ev-label" style="color:var(--color-accent);">RESOL</span>${escapeHtml(r.brand_response?.slice(0, 140) || '')}${r.brand_response?.length > 140 ? '...' : ''}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function buildEvidenceKV(ev) {
  if (!ev) return '<p class="kv-key">No telemetry captured</p>';
  return `
    <div class="step-kv">
      <div class="kv-item"><div class="kv-key">Grounding Sufficient</div><div class="kv-val ${ev.sufficient ? 'low' : 'high'}">${ev.sufficient ? 'YES (PASSED)' : 'NO (INSUFFICIENT)'}</div></div>
      <div class="kv-item"><div class="kv-key">Evidence Confidence</div><div class="kv-val">${ev.evidence_confidence?.toFixed(3) || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Grounding Quality</div><div class="kv-val ${ev.quality}">${ev.quality || '—'}</div></div>
    </div>
    ${ev.validation_notes ? `<div style="margin-top:12px; font-size:12px; color:var(--text-secondary); padding:10px 14px; background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:8px;">${escapeHtml(ev.validation_notes)}</div>` : ''}
  `;
}

function buildResponseContent(resp) {
  if (!resp) return '<p class="kv-key">No telemetry captured</p>';
  return `
    <div class="step-kv" style="margin-bottom:12px;">
      <div class="kv-item"><div class="kv-key">Generator Engine</div><div class="kv-val">llama-3.3-70b-versatile</div></div>
      <div class="kv-item"><div class="kv-key">Evidence Referenced</div><div class="kv-val">${(resp.evidence_used || []).length} citations</div></div>
    </div>
    ${resp.reply ? `<div style="font-size:13px; color:var(--text-secondary); padding:14px; background:var(--bg-surface); border:1px solid var(--border-medium); border-radius:10px; line-height:1.65;">${escapeHtml(resp.reply)}</div>` : ''}
    ${resp.confidence_note ? `<div style="margin-top:8px; font-size:11px; color:var(--text-faint);">Note: ${escapeHtml(resp.confidence_note)}</div>` : ''}
  `;
}

function buildDecisionContent(dec) {
  if (!dec) return '<p class="kv-key">No telemetry captured</p>';
  const isEsc = dec.decision === 'ESCALATE';
  const cf = dec.confidence_factors || {};
  return `
    <div class="step-kv" style="margin-bottom:14px;">
      <div class="kv-item"><div class="kv-key">Final Resolution</div><div class="kv-val" style="font-size:15px; color:${isEsc ? 'var(--color-accent)' : '#34d399'}; display:inline-flex; align-items:center; gap:6px;">${isEsc ? '<iconify-icon icon="lucide:alert-triangle"></iconify-icon> ESCALATE TO SENIOR ADVISOR' : '<iconify-icon icon="lucide:check-circle-2"></iconify-icon> AUTO-HANDLE'}</div></div>
      <div class="kv-item"><div class="kv-key">Risk Evaluation</div><div class="kv-val ${(dec.risk_level || '').toLowerCase()}">${dec.risk_level || 'LOW'}</div></div>
      <div class="kv-item"><div class="kv-key">Intent Certainty</div><div class="kv-val">${pct(cf.intent_confidence)}</div></div>
      <div class="kv-item"><div class="kv-key">Grounding Score</div><div class="kv-val">${cf.retrieval_confidence?.toFixed(3) || '—'}</div></div>
    </div>
    <div style="font-size:13px; color:var(--text-muted); padding:12px 14px; background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:8px;">
      Rationale: ${escapeHtml(dec.reason || 'Decision evaluated against risk thresholds and grounding confidence.')}
    </div>
  `;
}

// ── Evaluation Controller ─────────────────────────────────────────────
function initEvaluation() {
  const modeQuick = document.getElementById('modeQuick');
  const modeFull = document.getElementById('modeFull');
  const sampleSlider = document.getElementById('sampleSize');
  const runBtn = document.getElementById('runEvalBtn');

  if (modeQuick && modeFull) {
    modeQuick.addEventListener('click', () => {
      evalMode = 'quick';
      modeQuick.classList.add('active');
      modeFull.classList.remove('active');
    });
    modeFull.addEventListener('click', () => {
      evalMode = 'full';
      modeFull.classList.add('active');
      modeQuick.classList.remove('active');
    });
  }

  if (sampleSlider) {
    sampleSlider.addEventListener('input', () => {
      sampleSize = parseInt(sampleSlider.value);
      const valPill = document.getElementById('sampleSizeVal');
      if (valPill) valPill.textContent = sampleSize;
    });
  }

  if (runBtn) {
    runBtn.addEventListener('click', runEvaluation);
  }
}

async function runEvaluation() {
  const btn = document.getElementById('runEvalBtn');
  const loading = document.getElementById('evalLoading');
  const results = document.getElementById('evalResults');

  btn.disabled = true;
  loading.classList.remove('hidden');
  results.classList.add('hidden');

  try {
    const res = await fetch(`${API_BASE}/api/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: evalMode, sample_size: sampleSize })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    renderEvalResults(data);

  } catch (err) {
    alert('Evaluation error: ' + err.message);
  } finally {
    btn.disabled = false;
    loading.classList.add('hidden');
  }
}

function renderEvalResults(data) {
  const container = document.getElementById('evalResults');
  container.classList.remove('hidden');

  const im = data.intent_metrics || {};
  const dm = data.decision_metrics || {};
  const rm = data.retrieval_metrics || {};
  const bc = data.baseline_comparison || {};
  const resp = data.response_metrics;

  container.innerHTML = `
    <!-- Top metrics row -->
    <div class="metrics-row">
      ${metricCard('Intent Accuracy', pct(im.accuracy), colorScore(im.accuracy), 'Accurate category classification')}
      ${metricCard('Intent Macro F1', pct(im.macro_f1), colorScore(im.macro_f1), 'Balanced cross-class performance')}
      ${metricCard('Decision Accuracy', pct(dm.accuracy), colorScore(dm.accuracy), 'Auto-handle vs escalate accuracy')}
      ${metricCard('False Auto-Handle', pct(dm.false_auto_handle_rate), colorScoreInverse(dm.false_auto_handle_rate), 'Critical: Dangerous issues missed')}
      ${metricCard('Recall@5', pct(rm.recall_at_k?.['recall@5']), colorScore(rm.recall_at_k?.['recall@5']), 'Historical RAG retrieval recall')}
      ${metricCard('Mean Reciprocal Rank', (rm.mrr || 0).toFixed(3), 'neutral', 'MRR of ground truth ticket')}
    </div>

    <!-- Baseline Comparison -->
    ${bc.comparison_table ? `
    <div class="eval-section">
      <div class="eval-section-title">Volume 03.1 · System vs Baselines (Intent Classification)</div>
      <div class="table-scroll">
        <table class="results-table">
          <thead><tr><th>System Architecture</th><th>Accuracy</th><th>Macro F1</th></tr></thead>
          <tbody>
            ${bc.comparison_table.map(row => `
              <tr>
                <td style="font-weight:700; color:#ffffff;">${row.system}</td>
                <td><span class="badge ${row.method === 'llm' ? 'badge-green' : 'badge-orange'}">${row.accuracy}</span></td>
                <td><span class="badge ${row.method === 'llm' ? 'badge-green' : 'badge-orange'}">${row.macro_f1}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>` : ''}

    <!-- Decision Confusion Matrix -->
    ${dm.confusion_matrix ? `
    <div class="eval-section">
      <div class="eval-section-title">Volume 03.2 · Decision Engine Confusion Matrix</div>
      <div class="confusion-matrix">
        <div style="font-size:12px; color:var(--text-muted); margin-bottom:14px;">Rows = Actual Ground Truth, Columns = Predicted Routing</div>
        <div class="cm-grid">
          <div class="cm-cell cm-corner"></div>
          <div class="cm-cell cm-corner cm-header">Pred: AUTO</div>
          <div class="cm-cell cm-corner cm-header">Pred: ESCALATE</div>
          <div class="cm-cell cm-corner cm-header">Actual: AUTO</div>
          <div class="cm-cell cm-tp"><div class="cm-val">${dm.confusion_matrix.tp_correct_auto}</div><div class="cm-label">Correct Auto</div></div>
          <div class="cm-cell cm-fn"><div class="cm-val">${dm.confusion_matrix.fn_unnecessary_escalation}</div><div class="cm-label">Safe Escalation</div></div>
          <div class="cm-cell cm-corner cm-header">Actual: ESCALATE</div>
          <div class="cm-cell cm-fp"><div class="cm-val">${dm.confusion_matrix.fp_false_auto_handle}</div><div class="cm-label">False Auto (Risk)</div></div>
          <div class="cm-cell cm-tn"><div class="cm-val">${dm.confusion_matrix.tn_correct_escalation}</div><div class="cm-label">Correct Escalate</div></div>
        </div>
        <div style="margin-top:14px; font-size:12px; color:var(--color-accent); font-weight:600;">
          False Auto-Handle Rate: <strong>${pct(dm.false_auto_handle_rate)}</strong> (Safety rate against high-risk misses)
        </div>
      </div>
    </div>` : ''}

    <!-- Retrieval metrics -->
    <div class="eval-section">
      <div class="eval-section-title">Volume 03.3 · RAG Retrieval Quality Distribution</div>
      <div style="padding:1.5rem 1.75rem;">
        <div class="metrics-row" style="margin-bottom:16px;">
          ${Object.entries(rm.recall_at_k || {}).map(([k, v]) => metricCard(k.toUpperCase(), pct(v), colorScore(v), '')).join('')}
          ${Object.entries(rm.precision_at_k || {}).map(([k, v]) => metricCard(k.replace('precision@', 'P@').toUpperCase(), pct(v), colorScore(v), '')).join('')}
        </div>
        <div style="font-size:13px; color:var(--text-muted);">
          Grounding Quality Distribution: 
          <span style="color:#34d399; font-weight:700;">Strong: ${rm.evidence_quality_distribution?.strong || 0}</span> · 
          <span style="color:#fbbf24; font-weight:700;">Moderate: ${rm.evidence_quality_distribution?.moderate || 0}</span> · 
          <span style="color:var(--color-accent); font-weight:700;">Weak: ${rm.evidence_quality_distribution?.weak || 0}</span>
        </div>
      </div>
    </div>

    <!-- Sample predictions table -->
    <div class="eval-section">
      <div class="eval-section-title">Volume 03.4 · Live Benchmark Predictions Sample</div>
      <div class="table-scroll">
        <table class="results-table">
          <thead><tr><th>Customer Inquiry</th><th>Ground Truth</th><th>Predicted</th><th>Expected Route</th><th>Predicted Route</th><th>Status</th></tr></thead>
          <tbody>
            ${(data.pipeline_outputs || []).slice(0, 15).map(row => {
              const decOk = row.decision === row.expected_decision;
              return `<tr>
                <td style="max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#ffffff;">${escapeHtml(row.message?.slice(0, 60))}…</td>
                <td><span class="badge badge-purple">${row.true_intent || row.intent?.intent || '—'}</span></td>
                <td><span class="badge ${row.intent?.intent === row.true_intent ? 'badge-green' : 'badge-red'}">${row.intent?.intent || '—'}</span></td>
                <td><span class="badge ${row.expected_decision === 'AUTO-HANDLE' ? 'badge-green' : 'badge-red'}">${row.expected_decision}</span></td>
                <td><span class="badge ${row.decision === 'AUTO-HANDLE' ? 'badge-green' : 'badge-red'}">${row.decision}</span></td>
                <td><span class="badge ${decOk ? 'badge-green' : 'badge-red'}" style="display:inline-flex; align-items:center; gap:4px;"><iconify-icon icon="${decOk ? 'lucide:check-circle-2' : 'lucide:x-circle'}"></iconify-icon> ${decOk ? 'Pass' : 'Miss'}</span></td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function metricCard(label, value, cls, sub) {
  return `
    <div class="metric-card">
      <div class="metric-label">${label}</div>
      <div class="metric-value ${cls}">${value}</div>
      ${sub ? `<div class="metric-sub">${sub}</div>` : ''}
    </div>
  `;
}

// ── Taxonomy Controller ───────────────────────────────────────────────
async function loadTaxonomy() {
  const grid = document.getElementById('taxonomyGrid');
  try {
    const res = await fetch(`${API_BASE}/api/taxonomy`);
    if (!res.ok) return;
    const data = await res.json();
    renderTaxonomy(data.intents);
  } catch (e) {
    if (grid) {
      grid.innerHTML = '<p style="color:var(--text-muted)">Could not connect to backend taxonomy endpoint. Ensure FastAPI server is running.</p>';
    }
  }
}

function renderTaxonomy(taxonomy) {
  const grid = document.getElementById('taxonomyGrid');
  if (!grid) return;

  grid.innerHTML = Object.entries(taxonomy).map(([key, info]) => `
    <div class="taxonomy-card">
      <div>
        <div class="tc-header">
          <span class="tc-key">${key}</span>
          <span class="tc-risk ${info.risk}">${info.risk} RISK</span>
        </div>
        <h3 class="tc-label">${info.label}</h3>
        <p class="tc-desc">${escapeHtml(info.description)}</p>
      </div>
      <div class="tc-examples">
        <div class="tc-ex-label">Exemplary Utterances</div>
        ${(info.examples || []).map(ex => `<div class="tc-ex-item">${escapeHtml(ex)}</div>`).join('')}
      </div>
    </div>
  `).join('');
}

// ── Helpers ───────────────────────────────────────────────────────────
function pct(val) {
  if (val === undefined || val === null) return '—';
  return (val * 100).toFixed(1) + '%';
}

function colorScore(val) {
  if (!val && val !== 0) return 'neutral';
  if (val >= 0.75) return 'good';
  if (val >= 0.50) return 'warn';
  return 'bad';
}

function colorScoreInverse(val) {
  if (!val && val !== 0) return 'neutral';
  if (val <= 0.05) return 'good';
  if (val <= 0.15) return 'warn';
  return 'bad';
}

function formatIntentLabel(intent) {
  if (!intent) return '—';
  return intent.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
