const $ = id => document.getElementById(id);
let runId = localStorage.getItem('research-run'), seq = 0, timer, reportLoaded = false, restoreForm = true;
const stages = {created:'已创建',planning:'整理范围',research:'搜索与阅读',review:'证据核验',gaps:'检查信息缺口',writing:'撰写报告',completed:'研究完成',failed:'任务失败',interrupted:'任务中断'};
const tabs = [...document.querySelectorAll('[role="tab"]')];
async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail;
    try { detail = await response.json(); } catch { detail = {}; }
    const error = new Error(typeof detail.detail === 'string' ? detail.detail : `请求未成功（${response.status}），请稍后重试。`);
    error.status = response.status;
    throw error;
  }
  return response;
}
function showError(message, retry = false) { $('error').textContent = message; $('error').hidden = false; $('retry').hidden = !retry; }
function clearError() { $('error').hidden = true; $('retry').hidden = true; }
function node(tag, text) { const el = document.createElement(tag); el.textContent = text; return el; }
function showTab(id) {
  for (const tab of tabs) {
    const selected = tab.id === id;
    tab.setAttribute('aria-selected', String(selected));
    tab.setAttribute('aria-controls', tab.dataset.panel);
    tab.tabIndex = selected ? 0 : -1;
    $(tab.dataset.panel).hidden = !selected;
  }
}
function eventText(event) {
  const data = event.detail;
  if (event.stage === 'step_started') return '开始研究：' + data.question;
  if (event.stage === 'step_completed') return `已保存研究资料（${data.sources} 个来源）`;
  if (event.stage === 'error') return '执行失败：' + data.message;
  return stages[event.stage] || '研究进度已更新';
}
async function poll() {
  clearTimeout(timer);
  const currentRun = runId;
  if (!currentRun) return;
  try {
    const state = await (await api(`/api/research/${currentRun}`)).json();
    if (currentRun !== runId) return;
    clearError();
    if (restoreForm) {
      $('topic').value = state.request.topic;
      $('constraints').value = Object.entries(state.request.constraints).map(([k,v]) => `${k}：${v}`).join('\n');
      $('as-of').value = state.request.as_of; $('rounds').value = state.request.max_rounds; $('calls').value = state.request.max_calls;
      restoreForm = false;
    }
    $('status').textContent = stages[['completed','failed','interrupted'].includes(state.status) ? state.status : state.stage] || '研究中';
    $('metric-round').textContent = state.round; $('metric-calls').textContent = `${state.calls}/${state.request.max_calls}`; $('metric-sources').textContent = state.sources.length;
    $('notice').textContent = state.error || state.warnings.join('；') || '研究正在进行，关键证据会逐步显示。';
    ResearchView.renderSources(state, showTab);
    const events = await (await api(`/api/research/${currentRun}/events?after_seq=${seq}`)).json();
    if (currentRun !== runId) return;
    for (const event of events.events) { $('events').append(node('li', eventText(event))); seq = event.seq; }
    const complete = state.status === 'completed', failed = ['failed','interrupted'].includes(state.status);
    $('resume').hidden = !failed; $('submit').disabled = ['running','created'].includes(state.status);
    for (const [id,format] of [['download-md','markdown'],['download-json','json']]) {
      $(id).hidden = !complete; $(id).href = `/api/research/${currentRun}/report?format=${format}`; $(id).download = `research-${currentRun}.${format === 'json' ? 'json' : 'md'}`;
    }
    if (complete && !reportLoaded) {
      const report = await (await api(`/api/research/${currentRun}/report?format=json`)).json();
      if (currentRun !== runId) return;
      ResearchView.renderReport(report, showTab); $('report').hidden = false; $('empty').hidden = true; reportLoaded = true;
    }
    if (!complete && !failed) timer = setTimeout(poll, 1000);
  } catch (error) {
    if (currentRun !== runId) return;
    if (error.status === 404) {
      localStorage.removeItem('research-run'); runId = null;
      showError('上次任务不在当前数据库中，可以提交一个新问题。');
    } else showError('获取进度失败：' + error.message, true);
    $('submit').disabled = false;
  }
}
$('research-form').addEventListener('submit', async event => {
  event.preventDefault(); clearError(); $('submit').disabled = true;
  const constraints = {};
  for (const line of $('constraints').value.split('\n').filter(x => x.trim())) {
    const match = line.match(/^([^:：]+)[:：](.+)$/);
    if (!match || !match[1].trim() || !match[2].trim()) { showError('每条约束请用“名称：要求”的格式，名称和要求均不能为空。'); $('submit').disabled = false; return; }
    constraints[match[1].trim()] = match[2].trim();
  }
  try {
    const result = await (await api('/api/research', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:$('topic').value,constraints,as_of:$('as-of').value,max_rounds:Number($('rounds').value),max_calls:Number($('calls').value)})})).json();
    clearTimeout(timer); runId = result.run_id; localStorage.setItem('research-run', runId);
    seq = 0; reportLoaded = false; restoreForm = false;
    $('events').replaceChildren(); $('sources').replaceChildren(); $('evidence').replaceChildren();
    $('report').hidden = true; $('empty').hidden = false; $('download-md').hidden = true; $('download-json').hidden = true; $('resume').hidden = true;
    showTab('tab-report'); poll();
  } catch (error) { showError(error.message); $('submit').disabled = false; }
});
$('resume').addEventListener('click', async () => {
  $('resume').disabled = true;
  try { await api(`/api/research/${runId}/resume`, {method:'POST'}); clearError(); $('resume').hidden = true; poll(); }
  catch (error) { showError(error.message); }
  finally { $('resume').disabled = false; }
});
$('retry').addEventListener('click', () => { clearError(); poll(); });
$('example').addEventListener('click', () => { $('topic').value = '中文 PDF 企业知识库应该采用向量检索还是混合检索？是否需要 Reranker？'; $('constraints').value = '预算：有限\n数据：中文 PDF\n更新：每周增量'; });
for (const tab of tabs) {
  tab.addEventListener('click', () => showTab(tab.id));
  tab.addEventListener('keydown', event => {
    const index = tabs.indexOf(tab);
    const next = {ArrowRight:(index+1)%tabs.length,ArrowLeft:(index+tabs.length-1)%tabs.length,Home:0,End:tabs.length-1}[event.key];
    if (next === undefined) return;
    event.preventDefault(); showTab(tabs[next].id); tabs[next].focus();
  });
}
showTab('tab-report');
api('/api/health').then(r => r.json()).then(health => {
  $('mode').textContent = health.mode === 'replay' ? '离线回放 · 人工构造素材' : '联网研究 · 核对证据';
  $('as-of').value = health.default_as_of; $('notice').textContent = health.notice; if (runId) poll();
}).catch(error => showError('无法连接研究服务，请确认本机服务已启动：' + error.message));
