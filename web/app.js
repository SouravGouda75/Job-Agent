/**
 * web/app.js
 * Vanilla JavaScript Frontend Controller for the Autonomous Job Hunting Agent Dashboard.
 * Manages Server-Sent Events (SSE), StateGraph animation, HITL approvals, and ATS Studio.
 */

// Global State
let currentThreadId = null;
let currentSessionStatus = 'idle';
let sseSource = null;

// --------------------------------------------------------------------------
// Initialization
// --------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  initSSE();
  fetchHealthStatus();
  fetchDailyStats();
  fetchResumesList();
  loadCheckpointThreads();

  // Periodic poll for health & stats every 25s
  setInterval(() => {
    fetchHealthStatus();
    fetchDailyStats();
  }, 25000);
});

// --------------------------------------------------------------------------
// Navigation Tabs
// --------------------------------------------------------------------------
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

  const activeBtn = document.getElementById(`tab-btn-${tabId}`);
  const activePane = document.getElementById(`pane-${tabId}`);

  if (activeBtn) activeBtn.classList.add('active');
  if (activePane) activePane.classList.add('active');

  if (tabId === 'checkpoints') {
    loadCheckpointThreads();
  }
}

// --------------------------------------------------------------------------
// Server-Sent Events (SSE) Live Stream
// --------------------------------------------------------------------------
function initSSE() {
  if (sseSource) {
    sseSource.close();
  }

  sseSource = new EventSource('/api/events');

  sseSource.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data);
      handleLiveEvent(payload.event, payload.data);
    } catch (err) {
      console.warn('SSE parse warning:', err);
    }
  };

  sseSource.onerror = () => {
    console.log('SSE reconnecting...');
  };
}

function handleLiveEvent(eventType, data) {
  if (eventType === 'connected') {
    if (data.status) updateSessionStatus(data.status);
    if (data.thread_id) currentThreadId = data.thread_id;
  } else if (eventType === 'log') {
    appendTerminalLine(data.message, data.status === 'error' ? 'error' : 'info');
    if (data.node) {
      highlightActiveNode(data.node);
    }
  } else if (eventType === 'hitl_approval_required') {
    handleHitlApprovalEvent(data);
  } else if (eventType === 'session_completed') {
    handleSessionCompletedEvent(data);
  }
}

// --------------------------------------------------------------------------
// StateGraph Visualizer Controller
// --------------------------------------------------------------------------
const GRAPH_NODES = [
  'health_check',
  'scrape_jobs',
  'jd_prescreen',
  'ats_scorer',
  'resume_tailor',
  'safety_check',
  'apply_job',
  'log_result'
];

function highlightActiveNode(activeNodeId) {
  const cleanId = activeNodeId.toLowerCase().replace(/_node$/, '');
  const activeIdx = GRAPH_NODES.indexOf(cleanId);

  GRAPH_NODES.forEach((nodeId, idx) => {
    const el = document.getElementById(`node-${nodeId}`);
    if (!el) return;

    el.classList.remove('active', 'hitl-waiting');

    if (idx < activeIdx) {
      el.classList.add('done');
    } else if (idx === activeIdx) {
      el.classList.add('active');
      el.classList.remove('done');
    } else {
      el.classList.remove('done');
    }
  });

  updateSessionStatus('running');
}

function resetGraphNodes() {
  GRAPH_NODES.forEach(nodeId => {
    const el = document.getElementById(`node-${nodeId}`);
    if (el) el.classList.remove('active', 'done', 'hitl-waiting');
  });
}

// --------------------------------------------------------------------------
// Health & Daily Stats
// --------------------------------------------------------------------------
async function fetchHealthStatus() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();

    // Ollama Pill
    const pOllama = document.getElementById('pill-ollama');
    const dotOllama = pOllama.querySelector('.pill-dot');
    const valOllama = document.getElementById('val-ollama');
    if (data.ollama_alive) {
      dotOllama.className = 'pill-dot online';
      valOllama.textContent = 'ONLINE';
    } else {
      dotOllama.className = 'pill-dot offline';
      valOllama.textContent = 'OFFLINE';
    }

    // Gemini Pill
    const pGemini = document.getElementById('pill-gemini');
    const dotGemini = pGemini.querySelector('.pill-dot');
    const valGemini = document.getElementById('val-gemini');
    if (data.gemini_alive) {
      dotGemini.className = 'pill-dot online';
      valGemini.textContent = 'ONLINE';
    } else {
      dotGemini.className = 'pill-dot offline';
      valGemini.textContent = 'OFFLINE';
    }

    // Browser Pill
    const pBrowser = document.getElementById('pill-browser');
    const dotBrowser = pBrowser.querySelector('.pill-dot');
    const valBrowser = document.getElementById('val-browser');
    if (data.browser_ready) {
      dotBrowser.className = 'pill-dot online';
      valBrowser.textContent = 'READY';
    } else {
      dotBrowser.className = 'pill-dot offline';
      valBrowser.textContent = 'FAILED';
    }
  } catch (err) {
    console.warn('Health check error:', err);
  }
}

async function fetchDailyStats() {
  try {
    const res = await fetch('/api/stats/daily');
    const data = await res.json();
    const liCount = data.stats.linkedin_count || 0;
    const maxLi = data.limits.daily_max_linkedin || 40;

    // Update gauge text
    document.getElementById('gauge-li-val').textContent = liCount;
    document.getElementById('gauge-li-max').textContent = `/ ${maxLi}`;

    // Update circular SVG gauge
    const circumference = 289; // 2 * pi * 46
    const pct = Math.min(liCount / maxLi, 1);
    const offset = circumference - (pct * circumference);
    const ring = document.getElementById('ring-linkedin');
    if (ring) ring.style.strokeDashoffset = offset;

    // Delay range
    document.getElementById('disp-delay-range').textContent = `${data.limits.min_delay_seconds || 45} – ${data.limits.max_delay_seconds || 90}s`;
  } catch (err) {
    console.warn('Daily stats error:', err);
  }
}

function updateSessionStatus(status) {
  currentSessionStatus = status;
  const valEl = document.getElementById('val-session-status');
  const tagJob = document.getElementById('tag-job-status');

  if (valEl) valEl.textContent = status.toUpperCase();

  if (tagJob) {
    tagJob.textContent = status.toUpperCase();
    tagJob.className = 'status-tag ' + (
      status === 'running' ? 'tag-running' :
      status === 'waiting_approval' ? 'tag-hitl' :
      status === 'completed' ? 'tag-safe' : 'tag-idle'
    );
  }
}

// --------------------------------------------------------------------------
// Human-in-the-Loop (HITL) Workflow
// --------------------------------------------------------------------------
function handleHitlApprovalEvent(data) {
  currentThreadId = data.thread_id;
  updateSessionStatus('waiting_approval');

  // Highlight apply node in purple
  const applyNode = document.getElementById('node-apply_job');
  if (applyNode) {
    applyNode.classList.remove('active');
    applyNode.classList.add('hitl-waiting');
  }

  // Populate Active Job Card
  const emptyState = document.getElementById('job-empty-state');
  const detailsContent = document.getElementById('job-details-content');
  const hitlBanner = document.getElementById('hitl-banner');

  if (emptyState) emptyState.classList.add('hidden');
  if (detailsContent) detailsContent.classList.remove('hidden');
  if (hitlBanner) hitlBanner.classList.remove('hidden');

  const job = data.current_job || {};
  let title = job.title || data.title || 'Target Job';
  // Deduplicate repeated title halves (e.g. "Software Engineer 1 Software Engineer 1")
  const half = Math.floor(title.length / 2);
  if (half > 3 && title.slice(0, half).trim() === title.slice(half).trim()) {
    title = title.slice(0, half).trim();
  }
  const titleWords = title.split(/\s+/);
  if (titleWords.length >= 4 && titleWords.length % 2 === 0) {
    const mid = titleWords.length / 2;
    if (titleWords.slice(0, mid).join(' ') === titleWords.slice(mid).join(' ')) {
      title = titleWords.slice(0, mid).join(' ');
    }
  }
  document.getElementById('disp-job-title').textContent = title;

  let company = job.company || data.company || '';
  if (!company || company.toLowerCase() === 'company') {
    company = 'Company Unspecified';
  } else {
    const cHalf = Math.floor(company.length / 2);
    if (cHalf > 2 && company.slice(0, cHalf).trim() === company.slice(cHalf).trim()) {
      company = company.slice(0, cHalf).trim();
    }
  }
  const location = job.location || data.location || 'Remote';
  document.getElementById('disp-job-company').textContent = `${company} • ${location}`;
  document.getElementById('disp-score-num').textContent = `${data.ats_score || 0}%`;

  // Apply type badge
  const applyTypeBadge = document.getElementById('disp-apply-type');
  const applyType = data.apply_type || job.apply_type || 'easy_apply';
  if (applyTypeBadge) {
    if (applyType === 'external') {
      applyTypeBadge.textContent = '🔗 External Portal';
      applyTypeBadge.className = 'apply-type-badge external';
    } else {
      applyTypeBadge.textContent = '🟢 Easy Apply';
      applyTypeBadge.className = 'apply-type-badge easy-apply';
    }
  }

  // Experience badge
  const expBadge = document.getElementById('disp-experience');
  const expRequired = data.experience_required ?? job.experience_required ?? 0;
  if (expBadge) {
    if (expRequired === 0) {
      expBadge.textContent = '✅ 0-1 yr / Entry level';
    } else if (expRequired === 1) {
      expBadge.textContent = '✅ 1-2 yrs required';
    } else {
      expBadge.textContent = `✅ ${expRequired} yr(s) required`;
    }
  }

  // Job profile link
  const jobLink = document.getElementById('disp-job-link');
  const jobUrl = data.job_url || job.job_url || job.url || '';
  if (jobLink) {
    if (jobUrl) {
      jobLink.href = jobUrl;
      jobLink.classList.remove('hidden');
    } else {
      jobLink.classList.add('hidden');
    }
  }

  // JD Summary
  const summaryText = document.getElementById('disp-jd-summary');
  const jdSummary = data.jd_summary || job.jd_summary || '';
  if (summaryText) {
    if (jdSummary) {
      summaryText.textContent = jdSummary;
    } else if (title && company !== 'Company Unspecified') {
      summaryText.textContent = `Role: ${title} at ${company}. View full job description on LinkedIn.`;
    } else {
      summaryText.textContent = 'Summary unavailable for this listing.';
    }
  }

  // External portal link (show for external jobs)
  const extLinksDiv = document.getElementById('hitl-external-links');
  const extLink = document.getElementById('disp-external-link');
  const externalUrl = data.external_url || job.external_url || '';
  if (extLinksDiv && extLink) {
    if (applyType === 'external' && externalUrl) {
      extLink.href = externalUrl;
      extLinksDiv.classList.remove('hidden');
    } else {
      extLinksDiv.classList.add('hidden');
    }
  }

  // Update buttons: for external jobs, show "Save to Apply Later" instead of "Approve & Submit"
  const approveBtn = document.getElementById('btn-approve-submit');
  if (approveBtn) {
    if (applyType === 'external') {
      approveBtn.textContent = '📌 Save to Apply Later';
    } else {
      approveBtn.textContent = '✅ Approve & Submit';
    }
  }

  // Matched chips
  const matchedBox = document.getElementById('disp-matched-chips');
  matchedBox.innerHTML = '';
  (data.matched_keywords || []).slice(0, 10).forEach(kw => {
    const chip = document.createElement('span');
    chip.className = 'chip matched';
    chip.textContent = kw;
    matchedBox.appendChild(chip);
  });

  // Missing chips
  const missingBox = document.getElementById('disp-missing-chips');
  missingBox.innerHTML = '';
  (data.missing_keywords || []).slice(0, 10).forEach(kw => {
    const chip = document.createElement('span');
    chip.className = 'chip missing';
    chip.textContent = kw;
    missingBox.appendChild(chip);
  });

  appendTerminalLine(`🧑 HITL Approval Paused: Reviewing application for "${job.title}" at "${job.company}" (ATS: ${data.ats_score}%) [${applyType}]`, 'warn');
}

async function submitApproval(action) {
  if (!currentThreadId) {
    alert('No active thread to approve.');
    return;
  }

  let resolvedAction = action;
  if (action === true) resolvedAction = 'approve';
  if (action === false) resolvedAction = 'skip';

  const hitlBanner = document.getElementById('hitl-banner');
  if (hitlBanner) hitlBanner.classList.add('hidden');

  let logMsg = '✅ Submitting approval to agent...';
  if (resolvedAction === 'whatsapp') {
    logMsg = '📲 Dispatching job card to WhatsApp group & moving to next...';
  } else if (resolvedAction === 'both') {
    logMsg = '🚀 Dispatching to WhatsApp group and submitting application...';
  } else if (resolvedAction === 'skip') {
    logMsg = '⏭️ Skipping current job...';
  }
  appendTerminalLine(logMsg, 'info');

  try {
    const res = await fetch('/api/session/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: currentThreadId, action: resolvedAction })
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`Approval error: ${err.detail || 'Failed'}`);
    }
  } catch (err) {
    console.error('Submit approval error:', err);
  }
}

function handleSessionCompletedEvent(data) {
  updateSessionStatus('completed');
  appendTerminalLine(`🎉 Session completed! Submitted ${data.applied_count} application(s).`, 'success');
  fetchDailyStats();
  loadCheckpointThreads();

  // Mark all nodes as done
  GRAPH_NODES.forEach(nodeId => {
    const el = document.getElementById(`node-${nodeId}`);
    if (el) {
      el.classList.remove('active', 'hitl-waiting');
      el.classList.add('done');
    }
  });

  const hitlBanner = document.getElementById('hitl-banner');
  if (hitlBanner) hitlBanner.classList.add('hidden');
}

// --------------------------------------------------------------------------
// Start Session Modal & Actions
// --------------------------------------------------------------------------
function openStartModal() {
  document.getElementById('modal-start-session').classList.remove('hidden');
}

function closeStartModal() {
  document.getElementById('modal-start-session').classList.add('hidden');
}

async function confirmStartSession() {
  const role = document.getElementById('inp-modal-role').value.trim() || 'Software Engineer';
  const location = document.getElementById('inp-modal-loc').value.trim() || 'India';
  const maxApps = parseInt(document.getElementById('inp-modal-max').value, 10) || 3;
  const mode = document.getElementById('inp-modal-mode').value;

  const workTypes = [];
  if (document.getElementById('chk-wt-remote')?.checked) workTypes.push('Remote');
  if (document.getElementById('chk-wt-hybrid')?.checked) workTypes.push('Hybrid');
  if (document.getElementById('chk-wt-onsite')?.checked) workTypes.push('On-site');
  if (workTypes.length === 0) workTypes.push('Remote', 'Hybrid', 'On-site');

  const datePosted = document.getElementById('inp-modal-date')?.value || 'past_week';

  closeStartModal();
  resetGraphNodes();
  highlightActiveNode('health_check');

  appendTerminalLine(`🚀 Launching ${mode.toUpperCase()} batch for "${role}" in "${location}" [${workTypes.join(', ')} | Date: ${datePosted}]...`, 'info');

  try {
    const res = await fetch('/api/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_role: role,
        target_location: location,
        work_types: workTypes,
        date_posted: datePosted,
        max_applications: maxApps,
        mode: mode
      })
    });
    const data = await res.json();
    if (res.ok) {
      currentThreadId = data.thread_id;
      appendTerminalLine(`Session started with Thread ID: ${data.thread_id}`, 'info');
    } else {
      appendTerminalLine(`Error starting session: ${data.detail || 'Failed'}`, 'error');
    }
  } catch (err) {
    appendTerminalLine(`Network error: ${err}`, 'error');
  }
}

// --------------------------------------------------------------------------
// Activity Console Terminal
// --------------------------------------------------------------------------
function appendTerminalLine(text, level = 'info') {
  const body = document.getElementById('terminal-body');
  if (!body) return;

  const line = document.createElement('div');
  line.className = `terminal-line ${level}`;
  line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}

function clearTerminal() {
  const body = document.getElementById('terminal-body');
  if (body) {
    body.innerHTML = '<div class="terminal-line system">[SYSTEM] Terminal logs cleared. Live stream active.</div>';
  }
}

// --------------------------------------------------------------------------
// ATS Studio Tab
// --------------------------------------------------------------------------
async function fetchResumesList() {
  try {
    const res = await fetch('/api/resumes');
    const data = await res.json();
    const select = document.getElementById('ats-resume-select');
    if (!select) return;

    select.innerHTML = '<option value="">Auto-detect from resumes/ folder</option>';
    (data.candidate_resumes || []).forEach(r => {
      const opt = document.createElement('option');
      opt.value = r;
      opt.textContent = r;
      select.appendChild(opt);
    });
  } catch (err) {
    console.warn('Fetch resumes error:', err);
  }
}

function loadSampleJd() {
  const sample = `# Senior Software Engineer (AI & Full Stack)

Responsibilities:
- Build, optimize, and deploy scalable microservices using Python, FastAPI, and Docker.
- Design resilient LangChain and LangGraph agentic workflows with LLMs (Gemini, Llama3, Ollama).
- Develop responsive, accessible web frontends using modern JavaScript, HTML5, and CSS3.
- Integrate vector databases, SQLite checkpointer storage, and REST APIs.
- Lead code reviews, mentor junior developers, and enforce automated testing.

Required Skills:
- 4+ years of Python engineering experience.
- Deep expertise in RAG architectures, prompt engineering, and agent state machines.
- Hands-on experience with Playwright or browser automation.
- Cloud platforms (GCP, AWS) and container orchestration.`;

  document.getElementById('ats-jd-text').value = sample;
}

async function runAtsStudioMatch(tailor = false) {
  const resumeSelect = document.getElementById('ats-resume-select').value;
  const jdText = document.getElementById('ats-jd-text').value.trim();

  if (!jdText) {
    alert('Please paste a Job Description text or click "Load Sample JD" first.');
    return;
  }

  const btn = tailor ? document.getElementById('btn-run-tailor') : document.getElementById('btn-run-ats');
  const origText = btn.textContent;
  btn.textContent = tailor ? '⏳ Tailoring with AI Brain...' : '⏳ Analyzing ATS Tokens...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/ats/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_path: resumeSelect || null,
        jd_text: jdText,
        tailor: tailor
      })
    });

    const data = await res.json();
    if (!res.ok) {
      alert(`Error: ${data.detail || 'Could not calculate ATS match.'}`);
      return;
    }

    // Display Results
    document.getElementById('ats-empty-state').classList.add('hidden');
    document.getElementById('ats-output-content').classList.remove('hidden');

    const score = data.ats_score || 0;
    document.getElementById('ats-res-score').textContent = `${score}%`;
    document.getElementById('ats-res-status').textContent = score >= 60 ? 'Strong Match' : (score >= 40 ? 'Moderate Match' : 'Keyword Gap Detected');
    document.getElementById('ats-res-summary').textContent = `Evaluated against ${data.resume_name}`;

    // Matched list
    const matchedBox = document.getElementById('ats-matched-list');
    matchedBox.innerHTML = '';
    document.getElementById('ats-matched-count').textContent = (data.matched_keywords || []).length;
    (data.matched_keywords || []).forEach(kw => {
      const chip = document.createElement('span');
      chip.className = 'chip matched';
      chip.textContent = kw;
      matchedBox.appendChild(chip);
    });

    // Missing list
    const missingBox = document.getElementById('ats-missing-list');
    missingBox.innerHTML = '';
    document.getElementById('ats-missing-count').textContent = (data.missing_keywords || []).length;
    (data.missing_keywords || []).forEach(kw => {
      const chip = document.createElement('span');
      chip.className = 'chip missing';
      chip.textContent = kw;
      missingBox.appendChild(chip);
    });

    // Tailored download buttons
    const tailorBlock = document.getElementById('tailored-actions-block');
    if (data.tailored_pdf) {
      tailorBlock.classList.remove('hidden');
      document.getElementById('btn-view-pdf').href = `/api/resumes/download/${data.tailored_pdf}`;
      document.getElementById('btn-view-md').href = `/api/resumes/download/${data.tailored_md}`;
    } else {
      tailorBlock.classList.add('hidden');
    }

  } catch (err) {
    alert(`Request error: ${err}`);
  } finally {
    btn.textContent = origText;
    btn.disabled = false;
  }
}

// --------------------------------------------------------------------------
// Checkpoint Threads Tab
// --------------------------------------------------------------------------
async function loadCheckpointThreads() {
  const tbody = document.getElementById('tbody-threads');
  if (!tbody) return;

  try {
    const res = await fetch('/api/checkpoints');
    const data = await res.json();
    const threads = data.threads || [];

    if (threads.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center">No checkpoints recorded yet. Run a session to generate checkpoints!</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    threads.forEach(t => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong style="font-family: var(--font-mono); color: var(--cyan-primary);">${t.thread_id}</strong></td>
        <td>${t.target_role}</td>
        <td><span class="status-tag ${t.next_node === 'Completed' ? 'tag-safe' : 'tag-hitl'}">${t.next_node}</span></td>
        <td><strong>${t.ats_score}%</strong></td>
        <td>${t.applied_count}</td>
        <td>${t.mode}</td>
        <td>
          <button class="btn-ghost" onclick="resumeSavedThread('${t.thread_id}')">Resume</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.warn('Checkpoints fetch error:', err);
  }
}

function resumeSavedThread(threadId) {
  currentThreadId = threadId;
  switchTab('pipeline');
  appendTerminalLine(`Loaded checkpoint thread: ${threadId}. Monitoring live...`, 'info');
}

// --------------------------------------------------------------------------
// Apply Later / External Queue
// --------------------------------------------------------------------------
async function fetchExternalQueue() {
  try {
    const res = await fetch('/api/external-queue');
    const data = await res.json();
    const tbody = document.getElementById('tbody-external-queue');
    if (!tbody) return;

    const queue = data.queue || [];
    if (queue.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center">No external jobs queued yet. Run a session to discover external portal jobs.</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    queue.forEach(item => {
      const tr = document.createElement('tr');
      const savedDate = item.saved_at ? new Date(item.saved_at).toLocaleDateString() : '—';
      const summary = (item.jd_summary || '').substring(0, 80);
      tr.innerHTML = `
        <td><strong>${item.title || 'Unknown'}</strong></td>
        <td>${item.company || 'Unknown'}</td>
        <td><strong>${item.ats_score || 0}%</strong></td>
        <td class="text-muted" title="${item.jd_summary || ''}">${summary}${summary.length >= 80 ? '...' : ''}</td>
        <td>${item.job_url ? `<a href="${item.job_url}" target="_blank" class="link-external">\ud83d\udd17 LinkedIn</a>` : '—'}</td>
        <td>${item.external_url ? `<a href="${item.external_url}" target="_blank" class="link-external">\ud83d\udd17 Portal</a>` : '—'}</td>
        <td>${savedDate}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.warn('External queue fetch error:', err);
  }
}
