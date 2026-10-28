'use strict';

// Replay is reduced from the selected event prefix. Snapshot rows supply bodies,
// never future approval, lifecycle, cost, or ownership state.
let trace = null, cursor = 0, timer = null, follow = true, view = null;
let selectedAgent = '', selectedTask = '', lastRenderedSeq = null, boardSignature = '', snapshotSignature = '', dialogBoardSignature = '';
const $ = id => document.getElementById(id);
const money = value => '$' + ((value || 0) / 1e6).toFixed(6);
const list = value => {
  if (Array.isArray(value)) return value;
  try { const parsed = JSON.parse(value || '[]'); return Array.isArray(parsed) ? parsed : []; } catch { return []; }
};
const labels = {
  peer_joined: 'Joined the team', peer_retired: 'Retired from the team', peer_state: 'Agent state changed',
  task_proposed: 'Proposed shared work', task_claimed: 'Claimed a task', claim_released: 'Released a claim',
  claim_expired: 'Claim expired', artifact_published: 'Published an artifact', artifact_reviewed: 'Reviewed an artifact',
  finding_published: 'Shared an evidence finding', helper_proposed: 'Requested a temporary helper',
  helper_reviewed: 'Reviewed a helper request', scope_proposed: 'Proposed the required scope',
  scope_reviewed: 'Reviewed the scope', semantic_call_started: 'Started a semantic call',
  semantic_call_finished: 'Received a semantic result', outcome_checked: 'Checked the final outcome',
  run_finished: 'Run finished', shutdown_started: 'Team shutting down', action_rejected: 'Action needs repair',
};
function describe(e) {
  const p = e.payload || {};
  return (labels[e.type] || e.type.replaceAll('_', ' ')) +
    (p.reason ? ' · ' + p.reason : p.state ? ' · ' + p.state : p.key ? ' · ' + p.key : '');
}
function reduce(events, source = trace || {}) {
  const state = {peers: {}, tasks: {}, artifacts: {}, board: [], helpers: {}, scopes: {}, leaves: {},
    reservations: {}, callRecords: {}, settled: 0, calls: 0, scope: 0, status: 'running',
    memo_artifact_id: null, issues: []};
  const bodies = new Map((source.artifacts || []).map(a => [a.id, a]));
  const post = (e, category, title, content, extra = {}) => state.board.push({seq: e.seq, time: e.time,
    actor: e.actor, category, title, content: content || '', evidence: [], ...extra});
  for (const e of events) {
    const p = e.payload || {}, peer = state.peers[e.actor], task = state.tasks[p.task_id];
    if (peer && labels[e.type] && e.type !== 'peer_state') peer.last = describe(e);
    switch (e.type) {
      case 'peer_joined': {
        const request = state.helpers[p.proposal_id] || {};
        state.peers[e.actor] = {state: 'ready', family: p.family, model_key: p.model_key,
          bootstrap: p.bootstrap !== false, capability: request.capability || 'general',
          reason: p.reason || 'Bootstrap generalist', settled: 0, calls: 0, input_tokens: 0,
          output_tokens: 0, last: 'Joined the team'};
        post(e, 'coordination', p.bootstrap === false ? 'A temporary helper joined' : 'Bootstrap peer joined',
          p.reason || 'Generalist peer ready to claim and independently review shared work.');
        break;
      }
      case 'peer_state': if (peer) peer.state = p.state; break;
      case 'peer_retired':
        if (peer) Object.assign(peer, {state: 'retired', reason: p.reason});
        post(e, 'coordination', 'Retired from the team', p.reason);
        break;
      case 'task_proposed':
        state.tasks[p.task_id] = {id: p.task_id, key: p.key, spec: p.spec || {}, final: !!p.spec?.final,
          state: 'open', holder: null, artifact_id: null, dependencies: p.spec?.dependencies || []};
        post(e, 'coordination', 'Shared task · ' + p.key, p.spec?.objective, {task_id: p.task_id});
        break;
      case 'task_claimed':
        if (task) Object.assign(task, {state: 'claimed', holder: e.actor});
        post(e, 'coordination', 'Claimed · ' + (task?.key || p.task_id), 'Took responsibility for this task.', {task_id: p.task_id});
        break;
      case 'claim_released': case 'claim_expired':
        if (task) Object.assign(task, {state: 'open', holder: null});
        break;
      case 'finding_published':
        post(e, 'finding', 'Evidence finding', p.content, {evidence: list(p.evidence)});
        break;
      case 'artifact_published': {
        const body = bodies.get(p.artifact_id);
        state.artifacts[p.artifact_id] = {id: p.artifact_id, task: p.task_id, author: e.actor,
          content: body?.content || 'Artifact body is unavailable in this snapshot.',
          evidence: list(body?.evidence || p.evidence), version: p.version || body?.version || 1, approved: false};
        if (task) {
          Object.assign(task, {state: 'review', holder: null, artifact_id: p.artifact_id});
          if (task.final) state.memo_artifact_id = p.artifact_id;
        }
        const a = state.artifacts[p.artifact_id];
        post(e, 'artifact', 'Published · ' + (task?.key || 'artifact'), a.content,
          {evidence: a.evidence, artifact_id: a.id, task_id: p.task_id});
        break;
      }
      case 'final_memo_published':
        // Single-agent comparison exports use this event instead of a final task.
        if (state.artifacts[p.artifact_id]) state.memo_artifact_id = p.artifact_id;
        break;
      case 'artifact_reviewed': {
        const a = state.artifacts[p.artifact_id];
        if (!a) break;
        a.approved = p.approved; a.reviewer = e.actor; a.review_reason = p.reason;
        const t = state.tasks[a.task];
        if (t && t.artifact_id === a.id) t.state = p.approved ? 'done' : 'open';
        post(e, 'review', (p.approved ? 'Approved · ' : 'Repair requested · ') + (t?.key || 'artifact'), p.reason,
          {artifact_id: a.id, task_id: a.task, evidence: a.evidence, approved: p.approved});
        break;
      }
      case 'scope_proposed':
        state.scopes[p.proposal_id] = {...p, state: 'pending'};
        post(e, 'coordination', 'Proposed the required scope', (p.required || []).map(id => state.tasks[id]?.key || id).join(' · '));
        break;
      case 'scope_reviewed':
        if (p.approved) {
          state.scope = p.scope_version;
          for (const scope of Object.values(state.scopes)) scope.state = 'superseded';
          for (const t of Object.values(state.tasks)) if (t.final) {
            if (t.artifact_id && state.artifacts[t.artifact_id]) state.artifacts[t.artifact_id].approved = false;
            t.state = 'open'; t.holder = null;
            t.dependencies = state.scopes[p.proposal_id]?.required || t.dependencies;
          }
        }
        if (state.scopes[p.proposal_id]) state.scopes[p.proposal_id].state = p.approved ? 'accepted' : 'rejected';
        post(e, 'review', p.approved ? 'Approved the scope independently' : 'Scope needs revision', p.reason);
        break;
      case 'helper_proposed':
        state.helpers[p.proposal_id] = p;
        post(e, 'coordination', 'Requested a helper · ' + p.capability, p.reason,
          {evidence: list(p.evidence), task_ids: p.task_ids || [], requested_model: p.model_key,
            requested_budget_micro: p.budget_micro});
        break;
      case 'helper_reviewed': {
        const request = state.helpers[p.proposal_id] || {};
        post(e, 'review', p.approved ? 'Helper admitted independently' : 'Helper request declined',
          (p.peer_id ? p.peer_id + ' · ' : '') + (request.reason || 'Independent admission decision recorded.'));
        break;
      }
      case 'semantic_call_started':
        state.leaves[p.identity] = {owner: e.actor, state: 'Analyzing supplied evidence', model_key: p.model_key};
        break;
      case 'semantic_call_finished':
        if (state.leaves[p.identity]) state.leaves[p.identity].state = 'Returned a stored result';
        break;
      case 'call_reserved':
        state.reservations[p.call_id] = p.reserved_micro;
        state.callRecords[p.call_id] = {owner: e.actor, reserved: p.reserved_micro, purpose: p.purpose};
        state.calls++;
        if (peer) peer.calls++;
        break;
      case 'call_settled': {
        state.settled += p.settled_micro;
        delete state.reservations[p.call_id];
        const record = state.callRecords[p.call_id];
        if (record) {
          record.settled = p.settled_micro;
          const owner = state.peers[record.owner];
          if (owner) { owner.settled += p.settled_micro; owner.input_tokens += p.usage?.input_tokens || 0; owner.output_tokens += p.usage?.output_tokens || 0; }
        }
        break;
      }
      case 'outcome_checked':
        post(e, 'review', p.approved ? 'Final outcome independently checked' : 'Final outcome needs work',
          p.approved ? 'The original rubric and required artifacts passed the outcome check.' : (p.issues || []).join('\n'));
        break;
      case 'action_rejected':
        post(e, 'coordination', 'Action needs repair', p.error || p.reason);
        break;
      case 'run_finished': state.status = p.status; state.issues = p.issues || []; break;
    }
  }
  return state;
}

function node(tag, text = '', cls = '') {
  const el = document.createElement(tag); el.textContent = String(text); if (cls) el.className = cls; return el;
}
function svg(tag, attrs = {}, text) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  if (text !== undefined) el.textContent = String(text);
  return el;
}
function empty(parent, title, detail) {
  const el = node('div', '', 'empty'); el.append(node('strong', title), node('span', detail)); parent.append(el);
}
function families() { return [...new Set(Object.values(view.peers).map(p => p.family))]; }
function familyIndex(peer) { return Math.max(0, families().indexOf(peer?.family)); }
function familyLabel(family) { return family?.startsWith('scripted-family-') ? 'Scripted family ' + (family.endsWith('one') ? '1' : '2') : family || 'Unknown family'; }
function modelSpec(peer) {
  const start = trace.events.find(e => e.type === 'run_started');
  return (trace.model_configuration?.models || start?.payload?.configuration?.models || {})[peer.model_key] || {};
}
function modelLabel(peer) {
  const spec = modelSpec(peer);
  return spec.id ? spec.id.split('/').pop() : peer.model_key === 'one' ? 'Scripted model 1' : peer.model_key === 'two' ? 'Scripted model 2' : peer.model_key || familyLabel(peer.family);
}
function refs(parent, evidence) {
  if (!evidence?.length) return;
  const wrap = node('div', '', 'evidence'); for (const ref of evidence) wrap.append(node('span', typeof ref === 'string' ? ref : JSON.stringify(ref))); parent.append(wrap);
}
function heldTasks(id) { return Object.values(view.tasks).filter(t => t.holder === id).map(t => t.key).join(', ') || 'No held task'; }
function taskAvailability(task) {
  if (task.final && (!view.scope || Object.values(view.scopes).some(s => ['pending', 'rejected'].includes(s.state)))) return 'Waiting for scope approval';
  if (task.dependencies.some(id => view.tasks[id]?.state !== 'done')) return 'Waiting for reviewed dependencies';
  return 'Available to claim';
}
function renderGraph(visible, animate) {
  const graph = $('graph'); graph.replaceChildren();
  const peers = Object.entries(view.peers), cx = 330, cy = 208, positions = {};
  graph.append(svg('ellipse', {cx, cy, rx: 218, ry: 153, class: 'graph-orbit'}));
  peers.forEach(([id], i) => {
    const angle = -Math.PI / 2 + i * 2 * Math.PI / Math.max(peers.length, 3);
    positions[id] = [cx + Math.cos(angle) * 236, cy + Math.sin(angle) * 139];
    graph.append(svg('line', {x1: cx, y1: cy, x2: positions[id][0], y2: positions[id][1], class: 'spoke'}));
  });
  const hub = svg('g', {id: 'shared-board-hub', class: 'hub-control', role: 'button', tabindex: '0',
    'aria-label': 'Open shared board contents', 'data-focus-key': 'shared-board-hub'});
  hub.onclick = openBoard;
  hub.onkeydown = e => { if (['Enter', ' '].includes(e.key)) { e.preventDefault(); openBoard(); } };
  hub.append(svg('title', {}, 'Click to read the shared board'), svg('circle', {cx, cy, r: 67, class: 'hub-outer'}), svg('circle', {cx, cy, r: 56, class: 'hub-inner'}),
    svg('text', {x: cx, y: cy - 8, class: 'hub-title'}, 'Shared board'),
    svg('text', {x: cx, y: cy + 11, class: 'hub-label'}, view.board.length + ' posts · scope v' + view.scope),
    svg('text', {x: cx, y: cy + 27, class: 'hub-label'}, 'click to read posts'));
  graph.append(hub);
  for (const [id, p] of peers) {
    const [x, y] = positions[id], g = svg('g', {class: 'agent-node ' + p.state, role: 'button', tabindex: '0',
      'aria-label': `${id}, ${modelLabel(p)}, ${p.state}. Open agent details.`, 'data-focus-key': 'agent:' + id});
    g.classList.add('family-' + (familyIndex(p) % 3));
    g.append(svg('title', {}, `${id} · ${modelLabel(p)} · ${p.state}`));
    if (['working', 'reviewing'].includes(p.state)) g.append(svg('circle', {cx: x, cy: y, r: 34, class: 'agent-ring'}));
    g.append(svg('circle', {cx: x, cy: y, r: 28, class: 'agent-body'}), svg('text', {x, y: y + 5, class: 'agent-id'}, id),
      svg('text', {x, y: y + 48, class: 'agent-model'}, modelLabel(p)), svg('text', {x, y: y + 64, class: 'agent-state'}, p.state));
    if (!p.bootstrap) g.append(svg('text', {x, y: y - 39, class: 'helper-label'}, 'TEMPORARY HELPER'));
    g.onclick = () => openAgent(id);
    g.onkeydown = e => { if (['Enter', ' '].includes(e.key)) { e.preventDefault(); openAgent(id); } };
    graph.append(g);
  }
  if (!peers.length) graph.append(svg('text', {x: cx, y: 405, class: 'hub-label'}, 'Agents appear when they join the ledger.'));
  const current = visible.at(-1), record = current && view.callRecords[current.payload?.call_id];
  const actor = positions[current?.actor] ? current.actor : record?.owner;
  if (animate && positions[actor] && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const [x, y] = positions[actor];
    const dot = svg('circle', {r: 4.5, class: 'signal' + (current.type.includes('review') ? ' review' : '')});
    dot.append(svg('animateMotion', {dur: '.8s', repeatCount: '1', fill: 'freeze', path: `M ${x} ${y} L ${cx} ${cy}`}));
    dot.append(svg('animate', {attributeName: 'opacity', values: '1;1;0', dur: '.8s', fill: 'freeze'})); graph.append(dot);
  }
  $('graph-legend').replaceChildren();
  families().forEach((family, i) => { const item = node('span', '', 'legend-item'); item.append(node('i', '', 'legend-dot family-' + i), node('span', familyLabel(family))); $('graph-legend').append(item); });
  const helper = node('span', '', 'legend-item'); helper.append(node('i', '', 'legend-dot helper'), node('span', 'Temporary helper')); $('graph-legend').append(helper);
  $('active-count').textContent = peers.filter(([, p]) => !['retired', 'failed'].includes(p.state)).length + ' active';
  const action = $('current-action'); action.replaceChildren();
  if (current) action.append(node('strong', '#' + current.seq + ' · ' + current.actor + '  '), node('span', describe(current)));
  else action.textContent = 'The team is about to join. Press Play events to follow the run.';
}
function renderTasks() {
  $('tasks').replaceChildren(); const tasks = Object.values(view.tasks);
  $('task-count').textContent = tasks.length + ' tasks';
  for (const [key, title] of [['open', 'OPEN'], ['claimed', 'CLAIMED'], ['review', 'IN REVIEW'], ['done', 'DONE']]) {
    const rows = tasks.filter(t => t.state === key), lane = node('div', '', 'task-lane ' + key), h = node('div', '', 'lane-heading');
    h.append(node('span', title), node('span', rows.length)); lane.append(h);
    for (const task of rows) {
      const b = node('button', '', 'task-card'); b.append(node('strong', task.key + (task.final ? ' · final' : '')),
        node('small', task.holder || (key === 'review' ? 'Waiting for independent review' : key === 'done' ? 'Independently approved' : taskAvailability(task))));
      b.dataset.focusKey = 'task:' + task.id; b.onclick = () => openTask(task.id); lane.append(b);
    }
    if (!rows.length) lane.append(node('p', 'No tasks', 'lane-empty'));
    $('tasks').append(lane);
  }
}
function renderBoard() {
  const agent = $('agent-filter').value, category = $('type-filter').value;
  const signature = view.board.map(m => m.seq).join(',') + ':' + agent + ':' + category;
  if (signature === boardSignature) return;
  boardSignature = signature;
  const board = $('board'), scroll = board.scrollTop, opened = new Set([...board.querySelectorAll('details[open]')].map(d => d.dataset.seq));
  board.replaceChildren(); const rows = view.board.filter(m => (!agent || m.actor === agent) && (!category || m.category === category));
  $('board-count').textContent = rows.length + ' / ' + view.board.length + ' posts';
  for (const m of rows.slice().reverse()) {
    const post = node('article', '', 'post ' + m.category), peer = view.peers[m.actor], avatar = node('span', m.actor === 'system' ? 'sys' : m.actor, 'avatar family-' + familyIndex(peer));
    const head = node('div', '', 'post-header'), author = node('button', m.actor, 'post-author');
    author.dataset.focusKey = 'post-author:' + m.seq;
    author.onclick = () => peer && openAgent(m.actor); author.disabled = !peer;
    head.append(author, node('span', m.category, 'post-tag'), node('span', '#' + m.seq, 'post-seq'));
    post.append(avatar, head, node('h3', m.title));
    if (m.content.length > 320) {
      post.append(node('p', m.content.slice(0, 240) + '…'));
      const detail = node('details'); detail.dataset.seq = m.seq; detail.open = opened.has(String(m.seq));
      const summary = node('summary', 'Read full ' + (m.category === 'artifact' ? 'artifact' : 'message'));
      summary.dataset.focusKey = 'post-content:' + m.seq;
      detail.append(summary, node('pre', m.content)); post.append(detail);
    } else post.append(node('p', m.content));
    if (m.requested_model !== undefined) {
      post.append(node('p', 'Requested model: ' + m.requested_model + '\nRequested budget: ' + money(m.requested_budget_micro) +
        '\nTasks: ' + (m.task_ids.map(id => view.tasks[id]?.key || id).join(', ') || 'None recorded')));
    }
    refs(post, m.evidence); board.append(post);
  }
  if (!rows.length) empty(board, view.board.length ? 'No posts match these filters' : 'The shared board is waiting',
    view.board.length ? 'Choose another author or message type.' : 'Findings, claims, proposals, and reviews appear as agents publish them.');
  board.scrollTop = scroll;
}
function updateFilters() {
  const select = $('agent-filter'), value = select.value, ids = Object.keys(view.peers);
  if (select.dataset.ids !== ids.join(',')) {
    select.replaceChildren(node('option', 'All agents')); select.firstChild.value = '';
    for (const id of ids) { const option = node('option', id + ' · ' + modelLabel(view.peers[id])); option.value = id; select.append(option); }
    select.value = ids.includes(value) ? value : ''; select.dataset.ids = ids.join(',');
  }
}
function openBoard() {
  renderBoardDialog();
  if (!$('board-dialog').open) $('board-dialog').showModal();
}
function renderBoardDialog() {
  const author = $('board-dialog-agent'), previous = author.value, ids = [...new Set(view.board.map(m => m.actor))];
  if (author.dataset.ids !== ids.join(',')) {
    author.replaceChildren(node('option', 'All authors')); author.firstChild.value = '';
    for (const id of ids) { const option = node('option', id); option.value = id; author.append(option); }
    author.value = ids.includes(previous) ? previous : ''; author.dataset.ids = ids.join(',');
  }
  const category = $('board-dialog-type').value, query = $('board-dialog-search').value.trim().toLowerCase(), order = $('board-dialog-order').value;
  const signature = view.board.map(m => m.seq).join(',') + ':' + JSON.stringify([author.value, category, query, order]);
  if (signature === dialogBoardSignature) return;
  dialogBoardSignature = signature;
  const rows = view.board.filter(m => (!author.value || m.actor === author.value) && (!category || m.category === category) &&
    (!query || [m.actor, m.title, m.category, m.content, ...m.evidence, m.requested_model, ...(m.task_ids || []).map(id => view.tasks[id]?.key || id)].join(' ').toLowerCase().includes(query)));
  if (order === 'desc') rows.reverse();
  $('board-dialog-count').textContent = rows.length + ' / ' + view.board.length + ' posts';
  const target = $('board-dialog-list'), scroll = target.scrollTop; target.replaceChildren();
  for (const m of rows) {
    const article = node('article', '', 'post ' + m.category), head = node('div', '', 'post-header');
    head.append(node('strong', m.actor, 'post-author'), node('span', m.category, 'post-tag'), node('span', '#' + m.seq, 'post-seq'));
    article.append(node('span', m.actor === 'system' ? 'sys' : m.actor, 'avatar family-' + familyIndex(view.peers[m.actor])),
      head, node('h3', m.title), node('pre', m.content));
    if (m.requested_model !== undefined) article.append(node('p', 'Requested model: ' + m.requested_model + '\nRequested budget: ' + money(m.requested_budget_micro) +
      '\nTasks: ' + (m.task_ids.map(id => view.tasks[id]?.key || id).join(', ') || 'None recorded')));
    refs(article, m.evidence); target.append(article);
  }
  if (!rows.length) empty(target, view.board.length ? 'No posts match these filters' : 'No posts at this point in the run',
    view.board.length ? 'Change the filters or search text.' : 'Step forward or play the events to watch the common board fill.');
  target.scrollTop = scroll;
}
function renderPeers() {
  $('peers').replaceChildren();
  for (const [id, p] of Object.entries(view.peers)) {
    const card = node('button', '', 'peer-card ' + p.state), top = node('div', '', 'peer-top');
    top.append(node('strong', id), node('span', p.state, 'state-pill')); card.append(top,
      node('small', modelLabel(p) + (p.bootstrap ? ' · bootstrap' : ' · helper')),
      node('small', heldTasks(id)), node('small', p.calls + ' calls · ' + money(p.settled)),
      node('small', p.last)); card.dataset.focusKey = 'peer-card:' + id; card.onclick = () => openAgent(id); $('peers').append(card);
  }
  if (!Object.keys(view.peers).length) empty($('peers'), 'No agents have joined yet', 'Play or step forward to watch the team assemble.');
}
function renderLeaves() {
  $('leaves').replaceChildren(); const leaves = Object.entries(view.leaves);
  $('leaf-count').textContent = leaves.length + ' calls';
  for (const [id, leaf] of leaves) { const el = node('div', '', 'leaf'); el.append(node('strong', leaf.owner + ' → ' + (leaf.model_key || 'semantic leaf')), node('small', leaf.state)); el.title = id; $('leaves').append(el); }
  if (!leaves.length) $('leaves').append(node('p', 'No semantic calls in the displayed events.', 'panel-hint'));
}
function render() {
  if (!trace) return;
  const focusKey = document.activeElement?.dataset?.focusKey;
  const visible = trace.events.slice(0, cursor); view = reduce(visible, trace);
  const seq = visible.at(-1)?.seq ?? 0, animate = lastRenderedSeq !== null && seq > lastRenderedSeq;
  const synthetic = ['scripted', 'offline_fake'].includes(trace.mode), unresolved = Object.values(view.reservations).reduce((a, b) => a + b, 0);
  $('mode').textContent = trace.mode === 'scripted' ? 'SCRIPTED REPLAY' : trace.mode === 'offline_fake' ? 'FAKE PROVIDERS · REAL RUNTIME' : trace.mode === 'live' ? 'LIVE MODEL RUN' : 'RECORDED RUN · MODE UNKNOWN';
  $('mode').classList.toggle('live', trace.mode === 'live');
  $('mode-note').textContent = trace.mode === 'scripted' ? 'Recorded ledger transitions. Synthetic model usage.' : trace.mode === 'offline_fake' ? 'Real runtime with test models. Synthetic usage.' : trace.mode === 'live' ? 'Actual provider activity. Costs are usage estimates.' : 'Only recorded activity is shown.';
  $('cursor').max = trace.events.length; $('cursor').value = cursor;
  $('position').textContent = `${cursor} / ${trace.events.length} events`;
  $('metrics').replaceChildren();
  for (const [value, label] of [[view.status.replaceAll('_', ' '), 'Run status'], [Object.values(view.peers).filter(p => !['retired', 'failed'].includes(p.state)).length + ' / ' + Object.keys(view.peers).length, 'Active / total peers'], [view.calls, 'Model calls'], [money(view.settled), synthetic ? 'Synthetic settled cost' : 'Settled cost estimate'], [money(unresolved), 'Reserved / unresolved']]) {
    const el = node('div', '', 'metric'); el.append(node('strong', value), node('span', label)); $('metrics').append(el);
  }
  updateFilters(); renderGraph(visible, animate); renderTasks(); renderBoard(); renderPeers(); renderLeaves();
  if ($('board-dialog').open) renderBoardDialog();
  const artifact = view.artifacts[view.memo_artifact_id];
  $('memo').textContent = artifact?.content || '';
  $('memo-status').textContent = !artifact ? 'Not published' : artifact.approved ? 'Independently approved' : 'Awaiting review';
  $('memo-note').textContent = `Scope v${view.scope} · ` + (!artifact ? 'The final memo appears only after publication.' : 'Published by ' + artifact.author + ' · version ' + artifact.version);
  $('brief').textContent = trace.brief || 'The original brief is not recorded in this snapshot. It will appear in the completed trace.';
  $('run-issues').textContent = view.issues.join('\n');
  $('events').replaceChildren();
  for (const e of visible.slice(-80).reverse()) { const li = node('li'); li.append(node('span', '#' + e.seq, 'event-seq'), node('span', e.actor, 'event-actor'), node('span', describe(e))); $('events').append(li); }
  if ($('detail-dialog').open) {
    if (selectedAgent && view.peers[selectedAgent]) renderAgentDetail(selectedAgent);
    else if (selectedTask && view.tasks[selectedTask]) renderTaskDetail(selectedTask);
    else $('detail-dialog').close();
  }
  lastRenderedSeq = seq;
  if (focusKey) [...document.querySelectorAll('[data-focus-key]')].find(el => el.dataset.focusKey === focusKey)?.focus({preventScroll: true});
}
function detailRows(rows) {
  const dl = node('dl', '', 'detail-grid'); for (const [label, value] of rows) dl.append(node('dt', label), node('dd', value)); return dl;
}
function detailSection(title, content) { const el = node('section', '', 'detail-section'); el.append(node('h3', title), node('p', content)); return el; }
function renderAgentDetail(id) {
  const p = view.peers[id], spec = modelSpec(p), body = $('detail-body'), scroll = body.parentElement.scrollTop;
  $('detail-kind').textContent = p.bootstrap ? 'BOOTSTRAP PEER' : 'TEMPORARY HELPER'; $('detail-title').textContent = id + ' · ' + modelLabel(p);
  body.replaceChildren(detailRows([['State', p.state], ['Model', spec.id || modelLabel(p)], ['Provider', spec.provider || (trace.mode === 'scripted' ? 'Scripted test model' : 'Not recorded')],
    ['Family', familyLabel(p.family)], ['Capability', p.capability], ['Held work', heldTasks(id)], ['Model calls', p.calls], ['Settled estimate', money(p.settled)],
    ['Input / output tokens', p.input_tokens + ' / ' + p.output_tokens]]), detailSection('Why this agent is here', p.reason), detailSection('Last recorded action', p.last));
  const section = detailSection('Posts on the common board', 'These are public ledger records, not the agent’s private context or internal reasoning.');
  const filter = node('button', 'Show this agent’s board posts'); filter.dataset.focusKey = 'agent-post-filter'; filter.onclick = () => { $('agent-filter').value = id; $('type-filter').value = ''; $('detail-dialog').close(); renderBoard(); $('board').scrollIntoView({block: 'center'}); }; section.append(filter);
  for (const m of view.board.filter(m => m.actor === id).slice(-8).reverse()) { const item = node('div', '', 'detail-message'); item.append(node('strong', '#' + m.seq + ' · ' + m.title), node('p', m.content)); section.append(item); }
  body.append(section); body.parentElement.scrollTop = scroll;
}
function renderTaskDetail(id) {
  const t = view.tasks[id], body = $('detail-body'), artifact = view.artifacts[t.artifact_id];
  $('detail-kind').textContent = 'SHARED TASK'; $('detail-title').textContent = t.key;
  body.replaceChildren(detailRows([['State', t.state], ['Holder', t.holder || 'No held claim'], ['Final deliverable', t.final ? 'Yes' : 'No']]),
    detailSection('Objective', t.spec.objective || 'Not recorded'), detailSection('Acceptance criteria', (t.spec.acceptance_criteria || []).join('\n')),
    detailSection('Dependencies', t.dependencies.map(dep => view.tasks[dep]?.key || dep).join(', ') || (t.final && !view.scope ? 'Waiting for independently approved scope.' : 'No dependencies.')));
  if (artifact) { body.append(detailSection('Published artifact · version ' + artifact.version, artifact.content)); refs(body, artifact.evidence);
    if (artifact.reviewer) body.append(detailSection('Review by ' + artifact.reviewer, artifact.review_reason));
  } else body.append(detailSection('Artifact', 'No artifact has been published at this point in the run.'));
}
function openAgent(id) { selectedAgent = id; selectedTask = ''; renderAgentDetail(id); if (!$('detail-dialog').open) $('detail-dialog').showModal(); }
function openTask(id) { selectedTask = id; selectedAgent = ''; renderTaskDetail(id); if (!$('detail-dialog').open) $('detail-dialog').showModal(); }
function stopPlayback() { if (timer !== null) clearInterval(timer); timer = null; $('play').textContent = 'Play events'; }
function stepForward() {
  // Keep accounting events in the reduction but pause the presentation on actions.
  do { cursor = Math.min(cursor + 1, trace.events.length); }
  while (cursor < trace.events.length && ['call_reserved', 'call_submitted', 'call_settled'].includes(trace.events[cursor - 1]?.type));
  render();
}
function startPlayback() {
  stopPlayback(); follow = false; if (cursor >= trace.events.length) cursor = 0;
  $('play').textContent = 'Pause';
  timer = setInterval(() => { stepForward(); if (cursor >= trace.events.length) stopPlayback(); }, Number($('speed').value));
}
async function refresh() {
  try {
    const response = await fetch('/api/snapshot', {cache: 'no-store'});
    if (!response.ok) throw new Error('Run unavailable · retrying');
    const data = await response.json(); if (!Array.isArray(data.events)) throw new Error('Invalid run snapshot');
    const signature = JSON.stringify(data), changed = signature !== snapshotSignature;
    snapshotSignature = signature;
    const first = trace === null; trace = data;
    if (follow) cursor = trace.events.length;
    cursor = Math.min(cursor, trace.events.length);
    for (const id of ['play', 'step', 'start', 'end', 'cursor']) $(id).disabled = false;
    $('connection').textContent = trace.status === 'running' ? 'Following ledger' : 'Recorded ledger connected'; $('connection').classList.remove('error');
    if (first && trace.mode === 'scripted') { cursor = 0; render(); startPlayback(); } else if (changed) render();
  } catch (error) {
    $('connection').textContent = error.message || 'Connection lost · retrying'; $('connection').classList.add('error');
  }
}
function init() {
  $('play').onclick = () => timer !== null ? stopPlayback() : startPlayback();
  $('step').onclick = () => { stopPlayback(); follow = false; stepForward(); };
  $('start').onclick = () => { stopPlayback(); follow = false; cursor = 0; render(); };
  $('end').onclick = () => { stopPlayback(); follow = true; cursor = trace.events.length; render(); };
  $('cursor').oninput = () => { stopPlayback(); follow = false; cursor = Number($('cursor').value); render(); };
  $('speed').onchange = () => { if (timer !== null) startPlayback(); };
  $('agent-filter').onchange = renderBoard; $('type-filter').onchange = renderBoard;
  $('clear-filter').onclick = () => { $('agent-filter').value = ''; $('type-filter').value = ''; renderBoard(); };
  $('close-detail').onclick = () => $('detail-dialog').close();
  $('open-board').onclick = openBoard;
  $('board-dialog-close').onclick = () => $('board-dialog').close();
  $('board-dialog').onclose = () => $('shared-board-hub')?.focus({preventScroll: true});
  for (const id of ['board-dialog-agent', 'board-dialog-type', 'board-dialog-order']) $(id).onchange = renderBoardDialog;
  $('board-dialog-search').oninput = renderBoardDialog;
  $('board-dialog-clear').onclick = () => { $('board-dialog-agent').value = ''; $('board-dialog-type').value = ''; $('board-dialog-search').value = ''; renderBoardDialog(); };
  $('board-dialog').onclick = e => { if (e.target === $('board-dialog') && (e.clientX < e.target.getBoundingClientRect().left || e.clientX > e.target.getBoundingClientRect().right || e.clientY < e.target.getBoundingClientRect().top || e.clientY > e.target.getBoundingClientRect().bottom)) e.target.close(); };
  $('detail-dialog').onclick = e => { if (e.target === $('detail-dialog') && (e.clientX < e.target.getBoundingClientRect().left || e.clientX > e.target.getBoundingClientRect().right || e.clientY < e.target.getBoundingClientRect().top || e.clientY > e.target.getBoundingClientRect().bottom)) e.target.close(); };
  refresh(); setInterval(refresh, 2000);
}
if (typeof module !== 'undefined' && module.exports) module.exports = {reduce};
else init();
