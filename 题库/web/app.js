(() => {
  'use strict';
  const {element, button, link, texText, render} = window.BankReader;
  const data = window.BankData;
  const main = document.getElementById('main');
  const offline = window.BANK_OFFLINE;
  const facetLabels = {school:'学校', term:'年级学期', knowledge:'知识点', exam:'考点'};
  let catalog, papers, tags, generation = 0;
  let filterBar;

  function route() {
    const hash = location.hash.slice(1);
    if (!hash && offline) return offline.start.mode === 'paper'
      ? {mode:'papers',paper:offline.start.key} : {mode:'practice'};
    if (hash && !hash.includes('=')) return {mode:'papers',item:decodeURIComponent(hash)};
    const params = new URLSearchParams(hash);
    const state = {mode:'papers', ...Object.fromEntries(params)};
    for (const key of Object.keys(facetLabels)) {
      if (params.has(key)) state[key] = [...new Set(params.getAll(key).filter(Boolean))];
    }
    // Older bookmarks addressed grade and semester separately, sometimes specifying just one.
    if (!params.has('term') && (state.grade || state.semester)) {
      state.term = [...new Set(catalog.papers.filter(p =>
        (!state.grade || state.grade===p.grade) && (!state.semester || state.semester===p.semester)
      ).map(paperTerm))];
    }
    delete state.grade;
    delete state.semester;
    return state;
  }
  function url(base, changes = {}) {
    const params = new URLSearchParams();
    for (const [key,value] of Object.entries({...base,...changes})) {
      if (Array.isArray(value)) {
        for (const option of value.length ? value : ['']) params.append(key,option);
      } else if (value) params.set(key,value);
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
  function paperTerm(p) { return [p.grade,p.semester].filter(Boolean).join(''); }

  function facet(key) {
    const label = facetLabels[key];
    const isTag = key==='knowledge' || key==='exam';
    const options = isTag ? catalog.tags.filter(t=>t.kind===key).map(t=>[t.id,t.name])
      : [...new Set(catalog.papers.map(p=>key==='school'?p.school:paperTerm(p)).filter(Boolean))].map(v=>[v,v]);
    const details = element('details','facet');
    details.dataset.facet = key;
    details.setAttribute('name','bank-filters');
    const toggle = element('summary','facet-toggle');
    const value = element('span','facet-value');
    toggle.append(element('span','facet-title',label),value);
    const panel = element('div','facet-panel');
    const actions = element('div','facet-actions');
    const list = element('div','facet-options');
    list.setAttribute('role','group');
    list.setAttribute('aria-label',label);
    const boxes = [];
    function update() {
      const selected = boxes.filter(b=>b.checked).map(b=>b.value);
      const noConstraint = isTag ? !selected.length : selected.length===boxes.length;
      follow(url(route(),{[key]:noConstraint ? null : selected, item:null,paper:null}));
    }
    function checkAll(checked) {
      for (const box of boxes) box.checked = checked;
      update();
    }
    const all = button('全选',()=>checkAll(true));
    const none = button('取消全选',()=>checkAll(false));
    all.title = '勾选本组所有'+label;
    none.title = '清除本组所有'+label+'的勾选';
    actions.append(all,none);
    for (const [id,name] of options) {
      const row = element('label','facet-option');
      const box = element('input');
      box.type = 'checkbox';
      box.name = key; box.value = id;
      box.addEventListener('change',update);
      boxes.push(box);
      row.append(box,element('span','',name)); list.append(row);
    }
    if (isTag) {
      const search = element('input','facet-search');
      search.type = 'search';
      search.placeholder = '搜索'+label+'名称或编号';
      search.setAttribute('aria-label',search.placeholder);
      const empty = element('p','muted','没有匹配的'+label);
      empty.hidden = true;
      search.addEventListener('input',()=>{
        const query=search.value.trim().toLowerCase();
        for (const [i,[id,name]] of options.entries()) {
          boxes[i].parentElement.hidden = !(id+' '+name).toLowerCase().includes(query);
        }
        empty.hidden = boxes.some(box=>!box.parentElement.hidden);
      });
      panel.append(search,actions,list,empty);
    } else panel.append(actions,list);
    details.append(toggle,panel);
    function sync(state) {
      const selected = new Set(state[key] || (isTag ? [] : options.map(([id])=>id)));
      for (const box of boxes) box.checked = selected.has(box.value);
      const names = options.filter(([id])=>selected.has(id)).map(([,name])=>name);
      value.textContent = names.length===1 ? names[0]
        : !names.length ? (isTag?'选择'+label:'未选择')
        : names.length===options.length ? '全部（'+names.length+'）' : '已选 '+names.length+' 项';
    }
    return {details,sync};
  }
  function filters(s,withTags) {
    if (!filterBar || filterBar.withTags!==withTags || !filterBar.box.isConnected) {
      const box = element('div','filters');
      const fields = (withTags?Object.keys(facetLabels):['school','term']).map(facet);
      box.append(...fields.map(f=>f.details));
      filterBar = {box,fields,withTags};
    }
    for (const f of filterBar.fields) f.sync(s);
    return filterBar.box;
  }
  // Keep open checklists mounted while results change so keyboard focus, the search
  // query and the scroll position survive a sequence of selections.
  function showWithFilters(bar,...content) {
    if (main.firstElementChild!==bar) {main.replaceChildren(bar,...content); return;}
    while (main.lastChild!==bar) main.lastChild.remove();
    main.append(...content);
  }
  function closeOutside(event) {
    for (const open of main.querySelectorAll('.facet[open]')) {
      if (!open.contains(event.target)) open.open=false;
    }
  }
  document.addEventListener('pointerdown',closeOutside);
  document.addEventListener('focusin',closeOutside);
  document.addEventListener('keydown',event=>{
    const open=event.target.closest('.facet[open]');
    if (event.key==='Escape' && open) {
      event.preventDefault();
      open.open=false;
      open.querySelector('summary').focus();
    }
  });
  function matchesPaper(p,s) {
    return p && (!s.school || s.school.includes(p.school)) && (!s.term || s.term.includes(paperTerm(p)));
  }
  function paperMeta(p) {
    return [p.academic_year ? p.academic_year+' 学年' : '',paperTerm(p),p.exam_type].filter(Boolean).join(' · ');
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
    showWithFilters(filters(s,false),heading('试卷目录',visible.length+' 份试卷'),grid);
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
    return ['knowledge','exam'].filter(key=>s[key]?.length).map(key=>{
      const ids=s[key];
      return ids.length===1 ? tags.get(ids[0])?.name || ids[0] : ids.length+' 个'+facetLabels[key];
    }).join(' ∩ ') || '匹配题目';
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
    if (extra.length) showWithFilters(extra[0],crumb(title,back),layout);
    else main.replaceChildren(crumb(title,back),layout);
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
    const groups = ['knowledge','exam'].filter(key=>s[key]?.length);
    let results=[];
    if (groups.length && catalog.papers.some(p=>matchesPaper(p,s))) {
      // A summary contains both sets of tags. Load the cheaper union, then apply the
      // other group to those summaries without fetching more indexes or question bodies.
      const cost = key => s[key].reduce((sum,id)=>sum+(tags.get(id)?.count || 0),0);
      const [seed] = [...groups].sort((a,b)=>cost(a)-cost(b));
      const ids = s[seed].filter(id=>tags.get(id)?.kind===seed);
      const indexes = await Promise.all(ids.map(id=>data.get('tags/'+id)));
      if (turn!==generation) return;
      const byId = new Map();
      for (const index of indexes) for (const row of index.results) byId.set(row.id,row);
      results = [...byId.values()].filter(row=>matchesPaper(papers.get(row.paper_id),s) &&
        groups.every(key=>s[key].some(id=>row[key+'_ids'].includes(id))));
      if (indexes.length>1) results.sort((a,b)=>a.paper_id.localeCompare(b.paper_id) ||
        String(a.number).localeCompare(String(b.number),'zh',{numeric:true}) ||
        a.id.localeCompare(b.id,'zh',{numeric:true}));
    }
    if (s.item) return read(s,results,'筛选结果',url(s,{item:null}),[banner],turn);
    if (!groups.length) { showWithFilters(banner,tagSearch(s)); return; }
    const panel=element('section','sheet');
    panel.append(heading(tagResultsText(s),results.length+' 个结果'));
    panel.append(results.length?resultRows(results,s):element('p','empty','当前范围没有匹配的题目或小问。'));
    showWithFilters(banner,panel);
  }
  async function practice(s,turn) {
    const results = (offline?.results || catalog.practice_results || [])
      .filter(row=>matchesPaper(papers.get(row.paper_id),s));
    const chosen = tags.get(offline?.start.key)?.name || '专项练习';
    if (s.item) return read(s,results,'专项练习目录',url(s,{item:null}),[],turn);
    const box=element('section','sheet');
    box.append(heading(chosen,results.length+' 项'),results.length?resultRows(results,s):
      element('p','empty','当前筛选范围没有练习。'));
    showWithFilters(filters(s,false),box);
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
      const tabFilters = {school:s.school,term:s.term,knowledge:s.knowledge,exam:s.exam};
      paperTab.href=url({mode:inPractice?'practice':'papers',...tabFilters});
      tagTab.href=url({mode:'tags',...tabFilters});
      if (inPractice) paperTab.textContent='专项练习目录';
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
