const $ = id => document.getElementById(id);
let runId = localStorage.getItem('research-run'), seq = 0, timer, reportLoaded = false;
const stages = {created:'已创建',planning:'整理范围',research:'搜索与阅读',review:'证据核验',gaps:'检查信息缺口',writing:'撰写报告',completed:'研究完成',failed:'任务失败',interrupted:'任务中断'};
async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) { let detail = await response.json(); throw new Error(typeof detail.detail === 'string' ? detail.detail : '输入不符合要求，请检查问题与预算。'); }
  return response;
}
function showError(message) { $('error').textContent = message; $('error').hidden = false; }
function node(tag, text, className) { const el=document.createElement(tag); el.textContent=text; if(className) el.className=className; return el; }
function renderSources(state) {
  $('sources').replaceChildren(); $('evidence').replaceChildren();
  for (const source of state.sources) {
    const details=node('details',''); details.append(node('summary',source.title));
    const link=node('a',source.url,'source-link'); link.href=source.url; link.target='_blank'; link.rel='noopener noreferrer'; details.append(link);
    details.append(node('p',`发布日期：${source.published_at || '未知'} · 版本：${source.version || '未知'} · ${source.source_type}`,'help'));
    details.append(node('div',source.text,'source-text')); $('sources').append(details);
  }
  for(const e of state.evidence) {
    const item=node('div','','evidence-item'); item.append(node('p',`${e.verdict} · ${e.claim}`)); item.append(node('blockquote',e.quote)); item.append(node('p',e.reason,'help')); $('evidence').append(item);
  }
}
async function poll() {
  clearTimeout(timer);
  if(!runId) return;
  try {
    const state=await (await api(`/api/research/${runId}`)).json();
    $('status').textContent=stages[state.status==='completed'?'completed':state.status==='failed'?'failed':state.status==='interrupted'?'interrupted':state.stage] || state.stage;
    $('metric-round').textContent=state.round; $('metric-calls').textContent=`${state.calls}/${state.request.max_calls}`; $('metric-sources').textContent=state.sources.length;
    $('notice').textContent=state.error || state.warnings.join('；') || '研究正在进行，关键证据会逐步显示。';
    renderSources(state);
    const events=await (await api(`/api/research/${runId}/events?after_seq=${seq}`)).json();
    for(const event of events.events) { $('events').append(node('li',`${stages[event.stage] || event.stage} · ${JSON.stringify(event.detail)}`)); seq=event.seq; }
    const complete=state.status==='completed', failed=['failed','interrupted'].includes(state.status);
    $('resume').hidden=!failed; $('submit').disabled=state.status==='running' || state.status==='created';
    for(const [id,format] of [['download-md','markdown'],['download-json','json']]) { $(id).hidden=!complete; $(id).href=`/api/research/${runId}/report?format=${format}`; }
    if(complete && !reportLoaded) { $('report').textContent=await (await api(`/api/research/${runId}/report?format=markdown`)).text(); $('report').hidden=false; $('empty').hidden=true; reportLoaded=true; }
    if(!complete && !failed) timer=setTimeout(poll,1000);
  } catch(error) { showError(error.message); $('submit').disabled=false; }
}
$('research-form').addEventListener('submit',async event=>{
  event.preventDefault(); $('error').hidden=true; $('submit').disabled=true;
  const constraints={};
  for(const line of $('constraints').value.split('\n').filter(x=>x.trim())) {
    const match=line.match(/^([^:：]+)[:：](.+)$/);
    if(!match){showError('每条约束请用“名称：要求”的格式。'); $('submit').disabled=false; return;}
    constraints[match[1].trim()]=match[2].trim();
  }
  try{
    const result=await(await api('/api/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:$('topic').value,constraints,as_of:$('as-of').value,max_rounds:Number($('rounds').value),max_calls:Number($('calls').value)})})).json();
    runId=result.run_id; localStorage.setItem('research-run',runId); seq=0; reportLoaded=false; $('events').replaceChildren(); $('report').hidden=true; $('empty').hidden=false; poll();
  }catch(error){showError(error.message); $('submit').disabled=false;}
});
$('resume').addEventListener('click',async()=>{try{await api(`/api/research/${runId}/resume`,{method:'POST'}); $('resume').hidden=true; poll();}catch(error){showError(error.message);}});
$('example').addEventListener('click',()=>{$('topic').value='中文 PDF 企业知识库应该采用向量检索还是混合检索？是否需要 Reranker？'; $('constraints').value='预算：有限\n数据：中文 PDF\n更新：每周增量';});
for(const button of document.querySelectorAll('[role="tab"]')) button.addEventListener('click',()=>{for(const other of document.querySelectorAll('[role="tab"]')){other.setAttribute('aria-selected',String(other===button)); $(other.dataset.panel).hidden=other!==button;}});
api('/api/health').then(r=>r.json()).then(health=>{$('mode').textContent=health.mode==='replay'?'离线回放 · 人工构造素材':'联网研究 · 核对证据'; $('as-of').value=health.default_as_of; $('notice').textContent=health.notice; if(runId) poll();}).catch(error=>showError(error.message));
