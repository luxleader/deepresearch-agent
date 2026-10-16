// Source/model text is always textContent. Only ledger URLs become external links.
window.ResearchView = (() => {
  const labels = {fact: '事实', recommendation: '建议', uncertainty: '未知 / 局限'};
  const verdicts = {supported: '模型判断支持', contradicted: '存在冲突', uncertain: '尚不确定'};
  const timeLabels = {within_cutoff: '站点日期未晚于截止日', after_cutoff: '发布或修改晚于截止日', unknown: '时间适用性未知'};
  const element = (tag, text = '', className = '') => {
    const el = document.createElement(tag);
    el.textContent = text;
    if (className) el.className = className;
    return el;
  };
  const key = (type, id) => type + '-' + encodeURIComponent(id);
  function jump(id, showTab) {
    showTab('tab-sources');
    const target = document.getElementById(id);
    if (!target) return;
    if (target.tagName === 'DETAILS') target.open = true;
    target.focus();
    target.scrollIntoView({block: 'center', behavior: 'auto'});
  }
  function action(text, callback, className = 'evidence-link') {
    const button = element('button', text, className);
    button.type = 'button';
    button.addEventListener('click', callback);
    return button;
  }
  function sourceLink(source) {
    const link = element('a', source.url, 'source-link');
    try {
      const url = new URL(source.url);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return element('span', '来源地址无效');
      link.href = url.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    } catch { return element('span', '来源地址无效'); }
    return link;
  }
  function renderSources(state, showTab) {
    const sources = document.getElementById('sources');
    const evidence = document.getElementById('evidence');
    const open = new Set([...sources.querySelectorAll('details[open]')].map(el => el.id));
    sources.replaceChildren();
    evidence.replaceChildren();
    const sourceMap = new Map(state.sources.map(s => [s.id, s]));
    sources.append(element('h3', `来源原文（${state.sources.length}）`));
    if (!state.sources.length) sources.append(element('p', '尚未保存来源正文。', 'help'));
    for (const [index, source] of state.sources.entries()) {
      const details = element('details');
      details.id = key('source', source.id);
      details.tabIndex = -1;
      details.open = open.has(details.id);
      details.append(element('summary', `${index + 1}. ${source.title}`));
      details.append(sourceLink(source));
      details.append(element('p', `发布：${source.published_at || '未知'}　修改：${source.modified_at || '未知'}　版本：${source.version || '未知'}`, 'source-meta'));
      details.append(element('p', `${timeLabels[source.time_status] || '时间适用性未知'}；抓取：${source.retrieved_at || '未知'}`, 'source-meta'));
      if (source.date_basis) details.append(element('p', `日期依据：${source.date_basis}（站点声明）`, 'source-meta'));
      for (const warning of source.metadata_warnings || []) details.append(element('p', warning, 'help'));
      details.append(element('div', source.text, 'source-text'));
      sources.append(details);
    }
    evidence.append(element('h3', `证据片段（${state.evidence.length}）`));
    if (!state.evidence.length) evidence.append(element('p', '尚未保存可核对的证据片段。', 'help'));
    for (const [index, item] of state.evidence.entries()) {
      const card = element('article', '', 'evidence-item');
      card.id = key('evidence', item.id);
      card.tabIndex = -1;
      card.append(element('h4', `证据 ${index + 1} · ${verdicts[item.verdict] || '尚不确定'}`));
      card.append(element('p', item.claim));
      card.append(element('blockquote', item.quote));
      card.append(element('p', item.reason, 'help'));
      const source = sourceMap.get(item.source_id);
      if (source) {
        card.append(element('p', source.title, 'source-meta'));
        card.append(action('查看这份来源的完整原文', () => jump(key('source', source.id), showTab)));
      }
      card.append(action('返回研究报告', () => { showTab('tab-report'); document.getElementById('report').focus(); }, 'back-to-report'));
      evidence.append(card);
    }
  }
  function renderReport(payload, showTab) {
    const root = document.getElementById('report');
    root.replaceChildren();
    root.tabIndex = -1;
    const claims = new Map(payload.claims.map(c => [c.id, c]));
    const evidenceIndex = new Map(payload.evidence.map((e, i) => [e.id, i + 1]));
    function claim(id) {
      const item = claims.get(id);
      const row = element('div', '', 'report-claim');
      if (!item) { row.append(element('p', '此命题未通过核对，暂不展示。')); return row; }
      row.append(element('span', labels[item.kind] || '待核对', 'claim-kind ' + item.kind));
      row.append(element('span', item.text, 'claim-text'));
      const refs = element('div', '', 'claim-evidence');
      for (const eid of item.evidence_ids) {
        if (!evidenceIndex.has(eid)) continue;
        refs.append(action(`查看证据 ${evidenceIndex.get(eid)}`, () => jump(key('evidence', eid), showTab)));
      }
      row.append(refs);
      return row;
    }
    function section(title, ids) {
      if (!ids.length) return;
      const body = element('section', '', 'report-section');
      body.append(element('h3', title));
      for (const id of ids) body.append(claim(id));
      root.append(body);
    }
    if (payload.mode === 'replay') root.append(element('p', '人工构造回放，仅用于检查流程，不能作为技术选型结论。', 'notice'));
    const scope = element('section', '', 'report-scope');
    scope.append(element('h3', '研究范围'));
    scope.append(element('p', payload.request.topic));
    scope.append(element('p', `资料截止 ${payload.request.as_of}　·　${payload.rounds} 轮　·　${payload.outer_calls} 次研究调用`, 'source-meta'));
    const constraints = element('dl', '', 'constraints-list');
    for (const [name, value] of Object.entries(payload.request.constraints)) constraints.append(element('dt', name), element('dd', value));
    scope.append(constraints);
    if (payload.plan?.required_dimensions?.length) scope.append(element('p', '研究维度：' + payload.plan.required_dimensions.join('、'), 'source-meta'));
    root.append(scope);
    section('结论摘要', payload.summary_claim_ids);
    if (payload.comparison.length) {
      const comparison = element('section', '', 'report-section');
      comparison.append(element('h3', '方案对比'));
      for (const row of payload.comparison) {
        const candidate = element('div', '', 'comparison-candidate');
        candidate.append(claim(row.label));
        for (const [dimension, ids] of Object.entries(row.aspects)) {
          const aspect = element('div', '', 'comparison-aspect');
          aspect.append(claim(dimension));
          for (const id of ids) aspect.append(claim(id));
          candidate.append(aspect);
        }
        comparison.append(candidate);
      }
      root.append(comparison);
    }
    section('关键事实与建议', payload.claims.filter(c => !payload.limitation_claim_ids.includes(c.id)).map(c => c.id));
    section('局限与未知项', payload.limitation_claim_ids);
    root.append(element('p', '点击证据按钮核对片段与来源。片段存在与模型判断均不代表事实已经过人工确认。', 'help'));
  }
  return {renderReport, renderSources};
})();
