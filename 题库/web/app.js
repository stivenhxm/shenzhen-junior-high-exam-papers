(() => {
  'use strict';
  const {element, button, link, texText, render} = window.BankReader;
  const data = window.BankData;
  const main = document.getElementById('main');
  const offline = window.BANK_OFFLINE;
  const facets = [['school','学校'], ['grade','年级'], ['semester','学期']];
  let catalog, papers, tags, generation = 0;

  function route() {
    const hash = location.hash.slice(1);
    if (!hash && offline) return offline.start.mode === 'paper'
      ? {mode:'papers',paper:offline.start.key} : {mode:'practice'};
    if (hash && !hash.includes('=')) return {mode:'papers',item:decodeURIComponent(hash)};
    return {mode:'papers', ...Object.fromEntries(new URLSearchParams(hash))};
  }
  function url(base, changes = {}) {
    const params = new URLSearchParams();
    for (const [key,value] of Object.entries({...base,...changes})) {
      if (value) params.set(key,value);
    }
    return '#' + params;
  }
  function follow(href) {
    if (href === location.hash) return;
    location.hash = href;
  }
  function heading(title, count) {
    const row = element('div','topline');
    row.append(element('h2','',title));
    if (count) row.append(element('small','',count));
    return row;
  }
  function selectField(label, key, options, current, change, long) {
    const wrap = element('label',long?'long':'');
    wrap.append(document.createTextNode(label));
    const field = element('select');
    field.name = key;
    field.setAttribute('aria-label',label);
    for (const [value,text] of [['','全部'+label],...options]) field.add(new Option(text,value));
    field.value = current || '';
    field.addEventListener('change',() => change(field.value));
    wrap.append(field);
    return wrap;
  }
  function filters(s, withTags) {
    const box = element('div','filters');
    const onChange = (key,value) => follow(url(s,{[key]:value,item:null,paper:null}));
    for (const [key,label] of facets) {
      const values = [...new Set(catalog.papers.map(p=>p[key]).filter(Boolean))];
      box.append(selectField(label,key,values.map(v=>[v,v]),s[key],v=>onChange(key,v)));
    }
    if (withTags) {
      for (const [key,label] of [['knowledge','知识点'],['exam','考点']]) {
        const values = catalog.tags.filter(t=>t.kind===key).map(t=>[t.id,t.name]);
        box.append(selectField(label,key,values,s[key],v=>onChange(key,v),true));
      }
    }
    return box;
  }
  function matchesPaper(p,s) {
    return p && facets.every(([key])=>!s[key] || s[key]===p[key]);
  }
  function paperMeta(p) {
    return [p.academic_year ? p.academic_year+' 学年' : '',p.grade,p.semester,p.exam_type].filter(Boolean).join(' · ');
  }
  function label(item) {
    return '第 '+item.number+' 题'+(item.label?' · 小问 '+item.label:'');
  }
  function cardList(s) {
    const visible = catalog.papers.filter(p=>matchesPaper(p,s));
    const grid = element('div','papers');
    for (const p of visible) {
      const card = link('',url(s,{paper:p.id}),'paper-card');
      const foot = element('div','paper-foot');
      foot.append(element('span','',p.count+' 道大题'),element('span','','查看目录 →'));
      card.append(element('small','muted',paperMeta(p)),element('h3','',p.school));
      if (p.title) card.append(element('p','paper-name',p.title));
      card.append(foot);
      grid.append(card);
    }
    main.replaceChildren(filters(s,false),heading('试卷目录',visible.length+' 份试卷'),grid);
    if (!visible.length) grid.append(element('p','empty','当前筛选范围没有试卷。'));
  }
  function resultRows(results,s,compact=false,current=s.item) {
    const wrap = element('div',compact?'side-list':'result-list');
    for (const q of results) {
      const row = link('',url(s,{item:q.id}),'result-row');
      if (q.id===current) row.setAttribute('aria-current','true');
      const school = papers.get(q.paper_id)?.school || '';
      row.append(element('small','', [s.mode==='papers'?'':school,label(q)].filter(Boolean).join(' · ')),
        element('strong','',q.title || label(q)));
      if (q.preview && !compact) {
        const preview = texText(q.preview.replace(/\\\((?:(?!\\\))[\s\S])*$/u,'…'),'preview');
        row.append(preview);
      }
      wrap.append(row);
    }
    if (!compact) data.math(wrap).catch(error=>wrap.append(element('p','status error',error.message)));
    return wrap;
  }
  function crumb(text,href) {
    const row = element('nav','crumb');
    row.setAttribute('aria-label','返回目录');
    row.append(link('← '+text,href));
    return row;
  }
  function tagResultsText(s) {
    return [s.knowledge,s.exam].map(id=>tags.get(id)?.name).filter(Boolean).join(' ∩ ') || '匹配题目';
  }
  function tagSearch(s) {
    const box = element('section','sheet');
    const title = heading('查找知识点或考点');
    const input = element('input','filter-entry');
    input.type = 'search'; input.setAttribute('aria-label','搜索标签名称或编号');
    input.placeholder = '输入标签名称或编号';
    const matches = element('div','filter-tags');
    const report = element('small','muted');
    report.setAttribute('aria-live','polite');
    function search() {
      matches.replaceChildren();
      const query = input.value.trim().toLocaleLowerCase();
      report.textContent = '';
      if (!query) return;
      const found = catalog.tags.filter(t=>(t.name+' '+t.id).toLocaleLowerCase().includes(query));
      report.textContent = '找到 '+found.length+' 个标签';
      for (const tag of found) matches.append(button(tag.name+' · '+(tag.kind==='exam'?'考点':'知识点'),
        ()=>follow(url(s,{[tag.kind]:tag.id,item:null}))));
    }
    input.addEventListener('input',search);
    box.append(title,input,matches,report);
    return box;
  }
  function sideList(s,results,title,current) {
    const side = element('aside','side');
    const bar = element('div','side-bar');
    bar.append(element('h2','',title+' · '+results.length));
    const toggle = button('展开目录',() => {
      const open = side.classList.toggle('expanded');
      toggle.textContent=open?'收起目录':'展开目录';
      toggle.setAttribute('aria-expanded',String(open));
    },'side-toggle');
    toggle.setAttribute('aria-expanded','false');
    bar.append(toggle);
    side.append(bar,resultRows(results,s,true,current));
    return side;
  }
  async function read(s,results,title,back,extra,turn,item) {
    item ||= await data.get('items/'+s.item);
    if (turn!==generation) return;
    const current=s.mode==='papers'?item.question_id:item.id;
    const index=results.findIndex(r=>r.id===current);
    const itemURL = id => url(s,{item:id});
    const paperURL=s.mode!=='papers' && (!offline || Object.hasOwn(offline.data,'papers/'+item.paper_id))
      ? url({mode:'papers',paper:item.paper_id}) : null;
    const ctx = {papers,tags,itemURL,paperURL,tagURL:id=>{
      if (!tags.has(id) || (offline && !Object.hasOwn(offline.data,'tags/'+id))) return null;
      return url({mode:'tags',[tags.get(id).kind]:id});
    }, previous:index>0, next:index>=0 && index+1<results.length,
    step:delta=>{ const q=results[index+delta]; if(q) follow(itemURL(q.id)); }};
    const layout=element('div','workspace');
    layout.append(sideList(s,results,title,current),render(item,ctx));
    main.replaceChildren(...extra,crumb(title,back),layout);
    document.title=item.title+' · 深圳初中数学题库';
    window.scrollTo(0,0);
  }
  async function paperView(s,turn) {
    let direct;
    if (s.item && !s.paper) {
      direct = await data.get('items/'+s.item);
      s.paper=direct.paper_id;
    }
    if (turn!==generation) return;
    if (!s.paper) { cardList(s); return; }
    const p = await data.get('papers/'+s.paper);
    if (turn!==generation) return;
    if (s.item) return read(s,p.results,'本卷目录',url(s,{item:null}),[],turn,direct);
    const box = element('section','sheet');
    box.append(heading(p.school,p.count+' 道大题'),element('p','paper-name',p.title),
      element('p','metadata',paperMeta(p)),resultRows(p.results,s));
    main.replaceChildren(crumb('全部试卷',url(s,{paper:null})),box);
    document.title=p.school+' · 深圳初中数学题库';
  }
  async function tagView(s,turn) {
    const banner = filters(s,true);
    const ids = [s.knowledge,s.exam].filter(Boolean);
    let results=[];
    if (ids.length) {
      const indexes = await Promise.all(ids.map(id=>data.get('tags/'+id)));
      if (turn!==generation) return;
      results = indexes[0].results;
      if (indexes.length>1) {
        const overlap = new Set(indexes[1].results.map(q=>q.id));
        results = results.filter(q=>overlap.has(q.id));
      }
      results = results.filter(q=>matchesPaper(papers.get(q.paper_id),s));
    }
    if (s.item) return read(s,results,'筛选结果',url(s,{item:null}),[banner],turn);
    if (!ids.length) { main.replaceChildren(banner,tagSearch(s)); return; }
    const panel=element('section','sheet');
    panel.append(heading(tagResultsText(s),results.length+' 个结果'));
    panel.append(results.length?resultRows(results,s):element('p','empty','当前范围没有匹配的题目或小问。'));
    main.replaceChildren(banner,panel);
  }
  async function practice(s,turn) {
    const results = offline?.results || catalog.practice_results || [];
    const chosen = tags.get(offline?.start.key)?.name || '专项练习';
    if (s.item) return read(s,results,'专项练习目录',url(s,{item:null}),[],turn);
    const box=element('section','sheet');
    box.append(heading(chosen,results.length+' 项'),resultRows(results,s));
    main.replaceChildren(box);
  }
  async function draw() {
    const turn=++generation;
    try {
      if (!catalog) {
        catalog=await data.get('catalog');
        papers=new Map(catalog.papers.map(p=>[p.id,p]));
        tags=new Map(catalog.tags.map(t=>[t.id,t]));
      }
      if (turn!==generation) return;
      const s=route();
      const inPractice=offline?.start.mode==='practice';
      const paperTab=document.getElementById('paper-tab');
      const tagTab=document.getElementById('tag-tab');
      if (inPractice) { paperTab.href='#mode=practice'; paperTab.textContent='专项练习目录'; }
      document.getElementById('home').href=offline?'#':'#mode=papers';
      tagTab.hidden=!!offline && !Object.keys(offline.data).some(k=>k.startsWith('tags/'));
      for (const [tab,current] of [[paperTab,s.mode!=='tags'],[tagTab,s.mode==='tags']]) {
        if (current) tab.setAttribute('aria-current','page'); else tab.removeAttribute('aria-current');
      }
      document.getElementById('collection-count').textContent=offline
        ? '离线'+(inPractice?'专项练习':'试卷')
        : catalog.papers.length+' 份试卷 · '+catalog.papers.reduce((sum,p)=>sum+p.count,0)+' 道大题';
      document.title='深圳初中数学题库';
      if (s.mode==='tags') await tagView(s,turn);
      else if (s.mode==='practice' && offline) await practice(s,turn);
      else await paperView(s,turn);
    } catch (error) {
      if (turn!==generation) return;
      main.replaceChildren(element('p','status error',error.message),button('重新读取',draw),link('返回首页','#','parent-link'));
    }
  }
  window.addEventListener('hashchange',draw);
  draw();
})();
