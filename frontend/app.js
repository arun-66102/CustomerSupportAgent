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
  initParticles();
  initTabs();
  initChat();
  initEvaluation();
  checkHealth();
  loadTaxonomy();
  setInterval(checkHealth, 30000);
});

// ── Background Particles ───────────────────────────────────────────────
function initParticles() {
  const container = document.getElementById('particles');
  const orbs = [
    { size: 300, top: '10%', left: '5%', delay: '0s' },
    { size: 200, top: '60%', right: '8%', delay: '3s' },
    { size: 150, top: '30%', right: '25%', delay: '6s' },
  ];
  orbs.forEach(({ size, top, left, right, delay }) => {
    const orb = document.createElement('div');
    orb.className = 'orb';
    orb.style.cssText = `width:${size}px;height:${size}px;top:${top};${left ? `left:${left}` : `right:${right}`};background:radial-gradient(circle,rgba(59,130,246,0.3) 0%,transparent 70%);animation-delay:${delay};animation-duration:${8 + Math.random()*4}s`;
    container.appendChild(orb);
  });
}

// ── Health Check ───────────────────────────────────────────────────────
async function checkHealth() {
  const dot = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(5000) });
    if (res.ok) {
      const data = await res.json();
      dot.className = 'status-indicator online';
      text.textContent = `Online · ${data.conversations_loaded.toLocaleString()} conversations`;
    } else {
      throw new Error();
    }
  } catch {
    dot.className = 'status-indicator error';
    text.textContent = 'Backend offline — start the server';
  }
}

// ── Tabs ──────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`panel${capitalize(tab)}`).classList.add('active');
    });
  });
}

function capitalize(str) {
  const map = { chat: 'Chat', pipeline: 'Pipeline', evaluation: 'Eval', taxonomy: 'Taxonomy' };
  return map[str] || str.charAt(0).toUpperCase() + str.slice(1);
}

// ── Chat ──────────────────────────────────────────────────────────────
function initChat() {
  const input = document.getElementById('messageInput');
  const sendBtn = document.getElementById('sendBtn');
  const charCount = document.getElementById('charCount');

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

  sendBtn.addEventListener('click', sendMessage);

  document.querySelectorAll('.quick-prompt').forEach(btn => {
    btn.addEventListener('click', () => {
      input.value = btn.dataset.msg;
      charCount.textContent = input.value.length;
      autoResize(input);
      sendMessage();
    });
  });
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

async function sendMessage() {
  const input = document.getElementById('messageInput');
  const msg = input.value.trim();
  if (!msg || isLoading) return;

  isLoading = true;
  input.value = '';
  input.style.height = 'auto';
  document.getElementById('charCount').textContent = '0';
  document.getElementById('sendBtn').disabled = true;

  // Remove welcome screen
  const welcome = document.querySelector('.chat-welcome');
  if (welcome) welcome.remove();

  // Add user message
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
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
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
    document.getElementById('messageInput').focus();
  }
}

function appendMessage(role, text) {
  const chatWindow = document.getElementById('chatWindow');
  const wrapper = document.createElement('div');
  wrapper.className = `msg-wrapper msg-${role}`;
  wrapper.innerHTML = `
    <div class="msg-label">${role === 'user' ? 'You' : 'Apple Support AI'}</div>
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
      <div class="evidence-snippets-title">📚 Historical Evidence Used</div>
      ${topResults.map(r => `
        <div class="evidence-item">
          <span class="evidence-sim">${(r.similarity * 100).toFixed(0)}% similar</span> — ${escapeHtml(r.customer_message.slice(0, 80))}...
        </div>
      `).join('')}
    </div>
  ` : '';

  wrapper.innerHTML = `
    <div class="msg-label">Apple Support AI</div>
    <div class="msg-bubble">
      ${escapeHtml(reply)}
      <div class="decision-badge ${isEscalate ? 'escalate' : 'auto'}">
        ${isEscalate ? '🚨 ESCALATE TO HUMAN' : '✅ AUTO-HANDLED'}
      </div>
      ${evidenceHtml}
    </div>
    <div class="msg-meta">
      <span>🎯 ${formatIntentLabel(intent.intent)} · ${pct(intent.confidence)}</span>
      <span>⚡ ${data.total_duration_ms || '?'}ms</span>
      <span>📊 ${formatRisk(intent.risk)}</span>
      <span>🔍 ${retrieval.evidence_quality || 'N/A'} evidence</span>
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
    <div class="msg-label">System</div>
    <div class="msg-bubble" style="border-color:rgba(239,68,68,0.3);color:#ef4444;">
      ⚠️ Error: ${escapeHtml(msg)}
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
    <div class="msg-label">Apple Support AI</div>
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
  cw.scrollTop = cw.scrollHeight;
}

// ── Pipeline Trace ────────────────────────────────────────────────────
function updatePipelineTrace(data) {
  const empty = document.getElementById('pipelineEmpty');
  const trace = document.getElementById('pipelineTrace');
  empty.classList.add('hidden');
  trace.classList.remove('hidden');
  trace.innerHTML = '';

  const steps = [
    {
      num: '1', title: 'Intent Classification', icon: '🎯',
      duration: getDuration(data, 'intent_classification'),
      content: buildIntentKV(data.intent)
    },
    {
      num: '2', title: 'RAG Historical Retrieval', icon: '🔍',
      duration: getDuration(data, 'rag_retrieval'),
      content: buildRetrievalContent(data.retrieval)
    },
    {
      num: '3', title: 'Evidence Validation', icon: '🔬',
      duration: getDuration(data, 'evidence_validation'),
      content: buildEvidenceKV(data.evidence_validation)
    },
    {
      num: '4', title: 'LLM Response Generation', icon: '💬',
      duration: getDuration(data, 'response_generation'),
      content: buildResponseContent(data.generated_response)
    },
    {
      num: '5', title: 'Decision Engine', icon: '⚖️',
      duration: getDuration(data, 'decision_engine'),
      content: buildDecisionContent(data.decision)
    }
  ];

  steps.forEach(step => {
    const div = document.createElement('div');
    div.className = 'pipeline-step';
    div.innerHTML = `
      <div class="step-header">
        <div class="step-num">${step.num}</div>
        <div class="step-title">${step.icon} ${step.title}</div>
        <div class="step-duration">${step.duration}</div>
        <div class="step-status"></div>
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
  if (!intent) return '<p class="kv-key">No data</p>';
  const risk = (intent.risk || '').toUpperCase();
  return `
    <div class="step-kv">
      <div class="kv-item"><div class="kv-key">Intent</div><div class="kv-val intent-label">${intent.intent || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Confidence</div><div class="kv-val">${pct(intent.confidence)}</div></div>
      <div class="kv-item"><div class="kv-key">Risk Level</div><div class="kv-val ${risk.toLowerCase()}">${risk}</div></div>
      <div class="kv-item"><div class="kv-key">Method</div><div class="kv-val">${intent.method || '—'}</div></div>
    </div>
    ${intent.reasoning ? `<div style="margin-top:12px;font-size:12px;color:var(--text-secondary);padding:10px;background:rgba(255,255,255,0.03);border-radius:8px;">"${escapeHtml(intent.reasoning)}"</div>` : ''}
  `;
}

function buildRetrievalContent(retrieval) {
  if (!retrieval) return '<p class="kv-key">No data</p>';
  const results = retrieval.results || [];
  return `
    <div class="step-kv">
      <div class="kv-item"><div class="kv-key">Quality</div><div class="kv-val ${retrieval.evidence_quality}">${retrieval.evidence_quality || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Confidence</div><div class="kv-val">${retrieval.retrieval_confidence?.toFixed(3) || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Top Similarity</div><div class="kv-val">${retrieval.top_similarity?.toFixed(3) || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Results</div><div class="kv-val">${results.length}</div></div>
    </div>
    <div class="evidence-list" style="margin-top:12px;">
      ${results.slice(0, 3).map((r, i) => `
        <div class="evidence-card">
          <div class="evidence-card-header">
            <span class="ev-rank">Rank ${i+1}</span>
            <span class="ev-sim">${(r.similarity * 100).toFixed(0)}% similar</span>
            <span class="ev-rank" style="color:var(--text-muted);">ID: ${r.conversation_id}</span>
          </div>
          <div class="ev-q"><span class="ev-label">CUSTOMER</span>${escapeHtml(r.customer_message?.slice(0, 120) || '')}${r.customer_message?.length > 120 ? '...' : ''}</div>
          <div class="ev-a" style="margin-top:6px;"><span class="ev-label">SUPPORT</span>${escapeHtml(r.brand_response?.slice(0, 120) || '')}${r.brand_response?.length > 120 ? '...' : ''}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function buildEvidenceKV(ev) {
  if (!ev) return '<p class="kv-key">No data</p>';
  return `
    <div class="step-kv">
      <div class="kv-item"><div class="kv-key">Sufficient</div><div class="kv-val ${ev.sufficient ? 'low' : 'high'}">${ev.sufficient ? 'YES ✓' : 'NO ✗'}</div></div>
      <div class="kv-item"><div class="kv-key">Evidence Confidence</div><div class="kv-val">${ev.evidence_confidence?.toFixed(3) || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Quality</div><div class="kv-val ${ev.quality}">${ev.quality || '—'}</div></div>
    </div>
    ${ev.validation_notes ? `<div style="margin-top:10px;font-size:12px;color:var(--text-secondary);padding:8px 12px;background:rgba(255,255,255,0.03);border-radius:8px;">${escapeHtml(ev.validation_notes)}</div>` : ''}
  `;
}

function buildResponseContent(resp) {
  if (!resp) return '<p class="kv-key">No data</p>';
  return `
    <div class="step-kv" style="margin-bottom:12px;">
      <div class="kv-item"><div class="kv-key">Method</div><div class="kv-val">${resp.method || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Evidence Used</div><div class="kv-val">${(resp.evidence_used || []).length} sources</div></div>
    </div>
    ${resp.reply ? `<div style="font-size:13px;color:var(--text-primary);padding:14px;background:rgba(59,130,246,0.05);border:1px solid rgba(59,130,246,0.12);border-radius:10px;line-height:1.65;">${escapeHtml(resp.reply)}</div>` : ''}
    ${resp.confidence_note ? `<div style="margin-top:8px;font-size:11px;color:var(--text-muted);">📝 ${escapeHtml(resp.confidence_note)}</div>` : ''}
  `;
}

function buildDecisionContent(dec) {
  if (!dec) return '<p class="kv-key">No data</p>';
  const isEsc = dec.decision === 'ESCALATE';
  const cf = dec.confidence_factors || {};
  return `
    <div class="step-kv" style="margin-bottom:12px;">
      <div class="kv-item"><div class="kv-key">Decision</div><div class="kv-val ${isEsc ? 'escalate' : 'auto-handle'}" style="font-size:16px;">${isEsc ? '🚨 ESCALATE' : '✅ AUTO-HANDLE'}</div></div>
      <div class="kv-item"><div class="kv-key">Risk Level</div><div class="kv-val ${(dec.risk_level || '').toLowerCase()}">${dec.risk_level || '—'}</div></div>
      <div class="kv-item"><div class="kv-key">Intent Confidence</div><div class="kv-val">${pct(cf.intent_confidence)}</div></div>
      <div class="kv-item"><div class="kv-key">Retrieval Confidence</div><div class="kv-val">${cf.retrieval_confidence?.toFixed(3) || '—'}</div></div>
    </div>
    <div style="font-size:13px;color:var(--text-secondary);padding:12px;background:rgba(255,255,255,0.03);border-radius:8px;">
      📋 ${escapeHtml(dec.reason || '')}
    </div>
  `;
}

// ── Evaluation ────────────────────────────────────────────────────────
function initEvaluation() {
  document.getElementById('modeQuick').addEventListener('click', () => {
    evalMode = 'quick';
    document.getElementById('modeQuick').classList.add('active');
    document.getElementById('modeFull').classList.remove('active');
  });
  document.getElementById('modeFull').addEventListener('click', () => {
    evalMode = 'full';
    document.getElementById('modeFull').classList.add('active');
    document.getElementById('modeQuick').classList.remove('active');
  });

  const sampleSlider = document.getElementById('sampleSize');
  sampleSlider.addEventListener('input', () => {
    sampleSize = parseInt(sampleSlider.value);
    document.getElementById('sampleSizeVal').textContent = sampleSize;
  });

  document.getElementById('runEvalBtn').addEventListener('click', runEvaluation);
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
      const err = await res.json();
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
      ${metricCard('Intent Accuracy', pct(im.accuracy), colorScore(im.accuracy), 'Correct intent predictions')}
      ${metricCard('Intent Macro F1', pct(im.macro_f1), colorScore(im.macro_f1), 'Balanced F1 across all classes')}
      ${metricCard('Decision Accuracy', pct(dm.accuracy), colorScore(dm.accuracy), 'AUTO-HANDLE / ESCALATE decisions')}
      ${metricCard('False Auto-Handle', pct(dm.false_auto_handle_rate), colorScoreInverse(dm.false_auto_handle_rate), 'Dangerous: should-escalate but auto-handled')}
      ${metricCard('Recall@5', pct(rm.recall_at_k?.['recall@5']), colorScore(rm.recall_at_k?.['recall@5']), 'RAG retrieval recall')}
      ${metricCard('MRR', (rm.mrr || 0).toFixed(3), 'neutral', 'Mean Reciprocal Rank')}
    </div>

    <!-- Baseline Comparison -->
    ${bc.comparison_table ? `
    <div class="eval-section">
      <div class="eval-section-title">📊 System vs Baselines — Intent Classification</div>
      <div class="table-scroll">
        <table class="results-table">
          <thead><tr><th>System</th><th>Accuracy</th><th>Macro F1</th></tr></thead>
          <tbody>
            ${bc.comparison_table.map(row => `
              <tr>
                <td style="font-weight:600">${row.system}</td>
                <td><span class="badge ${row.method === 'llm' ? 'badge-blue' : 'badge-orange'}">${row.accuracy}</span></td>
                <td><span class="badge ${row.method === 'llm' ? 'badge-blue' : 'badge-orange'}">${row.macro_f1}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>` : ''}

    <!-- Decision Confusion Matrix -->
    ${dm.confusion_matrix ? `
    <div class="eval-section">
      <div class="eval-section-title">⚖️ Decision Engine — Confusion Matrix</div>
      <div class="confusion-matrix">
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">Rows = Actual, Cols = Predicted</div>
        <div class="cm-grid">
          <div class="cm-cell cm-corner"></div>
          <div class="cm-cell cm-corner cm-header">Pred: AUTO</div>
          <div class="cm-cell cm-corner cm-header">Pred: ESCALATE</div>
          <div class="cm-cell cm-corner cm-header">Actual: AUTO</div>
          <div class="cm-cell cm-tp"><div class="cm-val">${dm.confusion_matrix.tp_correct_auto}</div><div class="cm-label">✅ Correct Auto</div></div>
          <div class="cm-cell cm-fn"><div class="cm-val">${dm.confusion_matrix.fn_unnecessary_escalation}</div><div class="cm-label">⚠️ Unnecessary Esc.</div></div>
          <div class="cm-cell cm-corner cm-header">Actual: ESCALATE</div>
          <div class="cm-cell cm-fp"><div class="cm-val">${dm.confusion_matrix.fp_false_auto_handle}</div><div class="cm-label">🚨 FALSE AUTO</div></div>
          <div class="cm-cell cm-tn"><div class="cm-val">${dm.confusion_matrix.tn_correct_escalation}</div><div class="cm-label">✅ Correct Esc.</div></div>
        </div>
        <div style="margin-top:12px;font-size:12px;color:var(--accent-red);">
          🚨 False Auto-Handle Rate: <strong>${pct(dm.false_auto_handle_rate)}</strong> 
          (cases where dangerous issues were auto-handled instead of escalated)
        </div>
      </div>
    </div>` : ''}

    <!-- Per-intent breakdown -->
    ${im.per_intent ? `
    <div class="eval-section">
      <div class="eval-section-title">🎯 Intent Classification — Per-Class Results</div>
      <div class="table-scroll">
        <table class="results-table">
          <thead><tr><th>Intent</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead>
          <tbody>
            ${Object.entries(im.per_intent).map(([intent, m]) => `
              <tr>
                <td style="font-weight:600;color:var(--accent-blue)">${intent}</td>
                <td>${pct(m.precision)}</td>
                <td>${pct(m.recall)}</td>
                <td><span class="badge ${m.f1 > 0.7 ? 'badge-green' : m.f1 > 0.4 ? 'badge-orange' : 'badge-red'}">${pct(m.f1)}</span></td>
                <td>${m.support}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>` : ''}

    <!-- Retrieval metrics -->
    <div class="eval-section">
      <div class="eval-section-title">🔍 RAG Retrieval Metrics</div>
      <div style="padding:16px 20px;">
        <div class="metrics-row" style="margin-bottom:16px;">
          ${Object.entries(rm.recall_at_k || {}).map(([k, v]) => metricCard(k.toUpperCase(), pct(v), colorScore(v), '')).join('')}
          ${Object.entries(rm.precision_at_k || {}).map(([k, v]) => metricCard(k.replace('precision@', 'P@').toUpperCase(), pct(v), colorScore(v), '')).join('')}
        </div>
        <div style="font-size:13px;color:var(--text-secondary);">
          Evidence Quality: 
          🟢 Strong: ${rm.evidence_quality_distribution?.strong || 0} · 
          🟡 Moderate: ${rm.evidence_quality_distribution?.moderate || 0} · 
          🔴 Weak: ${rm.evidence_quality_distribution?.weak || 0}
        </div>
      </div>
    </div>

    <!-- Response quality if available -->
    ${resp ? `
    <div class="eval-section">
      <div class="eval-section-title">💬 Response Quality — LLM Judge Scores (1-5)</div>
      <div style="padding:20px;">
        <div style="margin-bottom:12px;font-size:14px;font-weight:700;color:var(--text-primary)">
          Overall: ${resp.average_overall}/5.0
        </div>
        ${Object.entries(resp.average_scores || {}).map(([dim, score]) => `
          <div class="score-bar-row">
            <div class="score-bar-label">${capitalize2(dim)}</div>
            <div class="score-bar-track"><div class="score-bar-fill" style="width:${(score/5)*100}%"></div></div>
            <div class="score-bar-val">${score}</div>
          </div>
        `).join('')}
      </div>
    </div>` : ''}

    <!-- Sample predictions table -->
    <div class="eval-section">
      <div class="eval-section-title">📋 Sample Predictions (first 15)</div>
      <div class="table-scroll">
        <table class="results-table">
          <thead><tr><th>Message</th><th>True Intent</th><th>Predicted</th><th>Expected Decision</th><th>Predicted Decision</th><th>✓</th></tr></thead>
          <tbody>
            ${(data.pipeline_outputs || []).slice(0,15).map(row => {
              const intentOk = row.intent?.intent === (row.true_intent || '');
              const decOk = row.decision === row.expected_decision;
              return `<tr>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(row.message?.slice(0,60))}…</td>
                <td><span class="badge badge-purple">${row.true_intent || row.intent?.intent || '—'}</span></td>
                <td><span class="badge ${row.intent?.intent === row.true_intent ? 'badge-green' : 'badge-red'}">${row.intent?.intent || '—'}</span></td>
                <td><span class="badge ${row.expected_decision === 'AUTO-HANDLE' ? 'badge-green' : 'badge-red'}">${row.expected_decision}</span></td>
                <td><span class="badge ${row.decision === 'AUTO-HANDLE' ? 'badge-green' : 'badge-red'}">${row.decision}</span></td>
                <td>${decOk ? '✅' : '❌'}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <div style="text-align:center;padding:16px;font-size:12px;color:var(--text-muted);">
      Evaluated ${data.sample_size} examples · Mode: ${data.mode} · 
      Data leakage prevented: each example excluded from its own retrieval
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

// ── Taxonomy ──────────────────────────────────────────────────────────
async function loadTaxonomy() {
  try {
    const res = await fetch(`${API_BASE}/api/taxonomy`);
    if (!res.ok) return;
    const data = await res.json();
    renderTaxonomy(data.intents);
  } catch (e) {
    document.getElementById('taxonomyGrid').innerHTML = '<p style="color:var(--text-muted)">Could not load taxonomy — is the server running?</p>';
  }
}

function renderTaxonomy(taxonomy) {
  const grid = document.getElementById('taxonomyGrid');
  grid.innerHTML = Object.entries(taxonomy).map(([key, info]) => `
    <div class="taxonomy-card risk-${info.risk}">
      <div class="tc-header">
        <span class="tc-key">${key}</span>
        <span class="tc-risk ${info.risk}">${info.risk}</span>
      </div>
      <div class="tc-label">${info.label}</div>
      <div class="tc-desc">${escapeHtml(info.description)}</div>
      <div class="tc-examples">
        <div class="tc-ex-label">Examples</div>
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

function formatRisk(risk) {
  if (!risk) return '—';
  const icons = { LOW: '🟢', MEDIUM: '🟡', HIGH: '🔴' };
  return `${icons[risk] || ''} ${risk}`;
}

function capitalize2(str) {
  return str.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
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
