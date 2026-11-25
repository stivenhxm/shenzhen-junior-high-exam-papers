(() => {
  'use strict';
  const {element, button, link, texText, render, difficultyInfo} = window.BankReader;
  const data = window.BankData;
  const main = document.getElementById('main');
  const offline = window.BANK_OFFLINE;
  const facetLabels = {school:'学校', term:'年级学期', year:'学年', teaching:'教学学期', knowledge:'知识点', exam:'考点', difficulty:'难度'};
  const exerciseFacets = ['knowledge','exam','difficulty'];
  const pageSize = 60;
  let catalog, papers, tags, difficulties, generation = 0;
  let filterBar, teachingFacet;

  function route() {
    const hash = location.hash.slice(1);
    if (!hash && offline) return offline.start.mode === 'paper'
      ? {mode:'papers',paper:offline.start.key} : {mode:'practice'};
    if (hash && !hash.includes('=')) return {mode:'papers',item:decodeURIComponent(hash)};
    const params = new URLSearchParams(hash);
    const state = {mode:'papers', ...Object.fromEntries(params)};
    for (const key of Object.keys(facetLabels)) {
      if (params.has(key)) {
        const values = params.getAll(key);
        state[key] = [...new Set((key==='year' ? values.map(yearKey) : values).filter(Boolean))];
      }
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
  function yearKey(value) { return value.trim().replace(/\s*[-–—－]\s*/g,'-'); }

  function facetOptions(key) {
    if (key==='difficulty') return [...difficulties.keys()].map(level=>[level,level]);
    if (key==='knowledge' || key==='exam') {
      return catalog.tags.filter(t=>t.kind===key).map(t=>[t.id,t.name]);
    }
    if (key==='year') {
      const years = [...new Set(catalog.papers.map(p=>yearKey(p.academic_year)).filter(Boolean))];
      return years.sort().reverse().map(year=>[year,year+' 学年']);
    }
    const values = catalog.papers.map(p=>key==='school' ? p.school : paperTerm(p));
    return [...new Set(values.filter(Boolean))].map(v=>[v,v]);
  }

  function facet(key,options=facetOptions(key)) {
    const label = facetLabels[key];
    const isTag = key==='knowledge' || key==='exam';
    const startsEmpty = exerciseFacets.includes(key);
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
      const noConstraint = startsEmpty ? !selected.length : selected.length===boxes.length;
      const changes = {[key]:noConstraint ? null : selected, item:null,paper:null,page:null};
      if (key==='teaching') changes.module=null;
      follow(url(route(),changes));
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
    } else {
      if (key==='difficulty') {
        const total = catalog.difficulties.reduce((sum,d)=>sum+d.count,0);
        const note = '共 '+total.toLocaleString('zh-CN')+' 个已标注的单题或小问，可与年级学期、知识点或考点一起筛选。';
        panel.append(element('p','facet-note',note));
      }
      panel.append(actions,list);
    }
    details.append(toggle,panel);
    function sync(state) {
      const selected = new Set(state[key] || (startsEmpty ? [] : options.map(([id])=>id)));
      for (const box of boxes) box.checked = selected.has(box.value);
      const names = options.filter(([id])=>selected.has(id)).map(([,name])=>name);
      value.textContent = names.length===1 ? names[0]
        : !names.length ? (startsEmpty?'选择'+label:'未选择')
        : names.length===options.length ? '全部（'+names.length+'）' : '已选 '+names.length+' 项';
    }
    return {details,sync};
  }
  function filters(s) {
    if (!filterBar || filterBar.mode!==s.mode || !filterBar.box.isConnected) {
      const box = element('div','filters');
      const keys = ['school','term'];
      if (s.mode==='papers') keys.push('year');
      if (s.mode==='tags') {
        keys.push('knowledge','exam');
        if (difficulties.size) keys.push('difficulty');
      }
      const fields = keys.map(key=>facet(key));
      box.append(...fields.map(f=>f.details));
      filterBar = {box,fields,mode:s.mode};
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
    const visible = catalog.papers.filter(p=>matchesPaper(p,s) && (!s.year || s.year.includes(yearKey(p.academic_year))));
    const grid = element('div','papers');
    for (const p of visible) {
      const card = link('',url(s,{paper:p.id}),'paper-card');
      const foot = element('div','paper-foot');
      foot.append(element('span','',p.count+' 道大题'),element('span','','查看目录 →'));
      card.append(element('small','muted',paperMeta(p)),element('h3','',p.school));
      if (p.title) card.append(element('p','paper-name',p.title));
      const distribution = difficultyInfo(p,'难度（按单题及小问计）');
      if (distribution) card.append(distribution);
      card.append(foot);
      grid.append(card);
    }
    showWithFilters(filters(s),heading('试卷目录',visible.length+' 份试卷'),grid);
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
      const difficulty = difficultyInfo(q);
      if (difficulty) row.append(difficulty);
      if (q.preview && !compact) {
        const preview = texText(q.preview.replace(/\\\((?:(?!\\\))[\s\S])*$/u,'…'),'preview');
        row.append(preview);
      }
      wrap.append(row);
    }
    if (!compact) data.math(wrap).catch(error=>wrap.append(element('p','status error',error.message)));
    return wrap;
  }
  function hasPages(s,results) { return s.mode!=='papers' && results.length>pageSize; }
  function pageOf(index) { return Math.floor(index/pageSize)+1; }
  function pageControls(page,total,change) {
    const nav=element('nav','result-pages');
    nav.setAttribute('aria-label','题目分页');
    const previous=button('上一页',()=>change(page-1));
    const next=button('下一页',()=>change(page+1));
    previous.disabled=page===1;
    next.disabled=page===total;
    nav.append(previous,element('span','','第 '+page+' / '+total+' 页'),next);
    return nav;
  }
  function pagedRows(results,s,compact=false,current=s.item) {
    if (!hasPages(s,results)) return resultRows(results,s,compact,current);
    const total=Math.ceil(results.length/pageSize);
    const index=compact ? results.findIndex(row=>row.id===current) : -1;
    const requested=Number(s.page);
    const page=index>=0 ? pageOf(index) : Math.min(total,Math.max(1,Number.isInteger(requested)?requested:1));
    const box=element('div',compact?'paged-side':'paged-results');
    function change(next) {
      if (compact) display(next);
      else {
        follow(url(s,{page:next>1?next:null}));
        window.scrollTo(0,0);
      }
    }
    function display(number) {
      const start=(number-1)*pageSize;
      const slice=results.slice(start,start+pageSize);
      const rows=resultRows(slice,{...s,page:number>1?number:null},compact,current);
      box.replaceChildren(pageControls(number,total,change),rows);
      if (!compact) box.append(pageControls(number,total,change));
    }
    display(page);
    return box;
  }
  function crumb(text,href) {
    const row = element('nav','crumb');
    row.setAttribute('aria-label','返回目录');
    row.append(link('← '+text,href));
    return row;
  }
  function tagResultsText(s) {
    return exerciseFacets.filter(key=>s[key]?.length).map(key=>{
      const ids=s[key];
      if (key==='difficulty') return ids.join(' / ');
      return ids.length===1 ? tags.get(ids[0])?.name || ids[0] : ids.length+' 个'+facetLabels[key];
    }).join(' ∩ ') || '匹配题目';
  }
  function mapNode(s,kind,node,module,css) {
    const indexed=tags.has(node.id);
    const view=indexed ? link(node.name,url(s,{[kind]:node.id,module:module.id,item:null}),css)
      : element('span',css+' map-unindexed',node.name);
    view.dataset[kind]=node.id;
    if (!indexed) view.append(element('small','map-unavailable','暂无题'));
    return view;
  }
  function moduleBranch(s,module,inTerm,searchable) {
    const contents=element('ul','map-knowledge-list');
    for (const knowledge of module.knowledge) {
      const exams=knowledge.exams.filter(inTerm);
      if (!inTerm(knowledge) && !exams.length) continue;
      const row=element('li','map-knowledge-row');
      row.append(mapNode(s,'knowledge',knowledge,module,'map-knowledge'));
      searchable.push({kind:'knowledge',node:knowledge,module});
      if (exams.length) {
        const list=element('ul','map-exams');
        for (const exam of exams) {
          const leaf=element('li');
          leaf.append(mapNode(s,'exam',exam,module,'map-exam'));
          list.append(leaf);
          searchable.push({kind:'exam',node:exam,module});
        }
        row.append(list);
      }
      contents.append(row);
    }
    if (!contents.childElementCount) return null;
    const branch=element('details','map-module');
    branch.dataset.module=module.id;
    branch.name='curriculum-modules';
    branch.open=s.module===module.id;
    const toggle=element('summary','map-module-toggle',module.name);
    branch.append(toggle,contents);
    return branch;
  }
  function curriculumMap(s,curriculum) {
    const box = element('section','sheet curriculum-map');
    const title = heading('知识点与考点图谱');
    teachingFacet ||= facet('teaching',curriculum.terms.map(term=>[term,term]));
    teachingFacet.sync(s);
    title.append(teachingFacet.details);
    const tree=element('div','map-domains');
    const searchable=[];
    const inTerm=node=>!s.teaching || s.teaching.some(term=>node.terms.includes(term));
    for (const domain of curriculum.domains) {
      const section=element('section','map-domain');
      section.dataset.domain=domain.id;
      const modules=element('div','map-branches');
      for (const module of domain.modules) {
        const branch=moduleBranch(s,module,inTerm,searchable);
        if (branch) modules.append(branch);
      }
      if (modules.childElementCount) {
        section.append(element('h3','map-domain-title',domain.name),modules);
        tree.append(section);
      }
    }
    // Keep the open branch in the URL without redrawing the map on every disclosure.
    let mapHash=location.hash;
    tree.addEventListener('toggle',()=>{
      if (!tree.isConnected || location.hash!==mapHash) return;
      const active=tree.querySelector('.map-module[open]')?.dataset.module;
      const next=url(s,{module:active});
      if (next!==mapHash) history.replaceState(history.state,'',next);
      mapHash=location.hash;
    },true);
    const tools=element('div','map-tools');
    const input = element('input','filter-entry');
    input.type = 'search'; input.setAttribute('aria-label','搜索标签名称或编号');
    input.placeholder = '搜索知识点、考点名称或编号';
    const matches = element('div','filter-tags');
    const report = element('small','muted');
    report.setAttribute('aria-live','polite');
    function search() {
      matches.replaceChildren();
      const query = input.value.trim().toLocaleLowerCase();
      report.textContent = '';
      if (!query) return;
      const found = searchable.filter(({node})=>(node.name+' '+node.id).toLocaleLowerCase().includes(query));
      report.textContent = '找到 '+found.length+' 个标签';
      for (const {kind,node,module} of found) {
        const match=mapNode(s,kind,node,module,'map-search-match');
        match.append(element('small','',facetLabels[kind]));
        matches.append(match);
      }
    }
    input.addEventListener('input',search);
    tools.append(input,element('small','muted','按北师大版教材编排，展开模块可查看知识点和考点。'),report);
    box.append(title,tools);
    if (s.teaching && !curriculum.terms.every(term=>s.teaching.includes(term))) {
      for (const term of curriculum.terms.filter(term=>s.teaching.includes(term))) {
        const note=curriculum.term_notes?.[term];
        if (note) box.append(element('p','map-term-note',term+' · '+note));
      }
    }
    box.append(matches,tree);
    if (!tree.childElementCount) box.append(element('p','empty',s.teaching?.length===0
      ? '请选择教学学期以查看图谱。' : '所选教学学期没有可显示的知识点或考点。'));
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
    side.append(bar,pagedRows(results,s,true,current));
    return side;
  }
  async function read(s,results,title,extra,turn,item) {
    item ||= await data.get('items/'+s.item);
    if (turn!==generation) return;
    const current=s.mode==='papers'?item.question_id:item.id;
    const index=results.findIndex(r=>r.id===current);
    const paged=hasPages(s,results);
    const currentPage=paged && index>=0 ? pageOf(index) : Number(s.page);
    const back=url(s,{item:null,page:currentPage>1?currentPage:null});
    const itemURL = id => {
      const target=paged ? results.findIndex(row=>row.id===id) : -1;
      const page=target>=0 ? pageOf(target) : currentPage;
      return url(s,{item:id,page:page>1?page:null});
    };
    const paperURL=s.mode!=='papers' && (!offline || Object.hasOwn(offline.data,'papers/'+item.paper_id))
      ? url({mode:'papers',paper:item.paper_id}) : null;
    const ctx = {papers,tags,itemURL,paperURL,tagURL:id=>{
      if (!tags.has(id) || (offline && !Object.hasOwn(offline.data,'tags/'+id))) return null;
      return url({mode:'tags',school:s.school,term:s.term,difficulty:s.difficulty,[tags.get(id).kind]:id});
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
    if (s.item) return read(s,p.results,'本卷目录',[],turn,direct);
    const box = element('section','sheet');
    box.append(heading(p.school,p.count+' 道大题'),element('p','paper-name',p.title),
      element('p','metadata',paperMeta(p)));
    for (const detail of [p.metadata_note,p.edition_note]) {
      if (detail) box.append(element('p','metadata',detail));
    }
    const distribution = difficultyInfo(p,'难度分布（按单题及小问计）');
    if (distribution) box.append(distribution);
    box.append(resultRows(p.results,s));
    main.replaceChildren(crumb('全部试卷',url(s,{paper:null})),box);
    document.title=p.school+' · 深圳初中数学题库';
  }
  async function tagView(s,turn) {
    const banner = filters(s);
    const groups = exerciseFacets.filter(key=>s[key]?.length);
    let results=[];
    const terms = new Set(catalog.papers.filter(p=>matchesPaper(p,s)).map(paperTerm));
    if (groups.length && terms.size) {
      // Each index has complete leaf summaries, so only the smallest union of shards is needed.
      const choices = groups.map(key=>{
        const shards = key==='difficulty' ? s[key].flatMap(level=>{
          const entry=difficulties.get(level);
          if (!entry) return [];
          return entry.shards ? entry.shards.filter(part=>terms.has(part.term)) : [entry];
        })
          : s[key].filter(id=>tags.get(id)?.kind===key).map(id=>({key:'tags/'+id,count:tags.get(id).count}));
        return {shards,count:shards.reduce((sum,shard)=>sum+shard.count,0)};
      });
      const seed = choices.sort((a,b)=>a.count-b.count)[0];
      const indexes = await Promise.all(seed.shards.map(shard=>data.get(shard.key)));
      if (turn!==generation) return;
      const byId = new Map();
      for (const index of indexes) for (const row of index.results) byId.set(row.id,row);
      results = [...byId.values()].filter(row=>matchesPaper(papers.get(row.paper_id),s) &&
        groups.every(key=>key==='difficulty' ? s.difficulty.includes(row.difficulty)
          : s[key].some(id=>row[key+'_ids'].includes(id))));
      if (indexes.length>1) results.sort((a,b)=>a.paper_id.localeCompare(b.paper_id) ||
        String(a.number).localeCompare(String(b.number),'zh',{numeric:true}) ||
        a.id.localeCompare(b.id,'zh',{numeric:true}));
    }
    if (s.item) return read(s,results,'筛选结果',[banner],turn);
    if (!groups.length) {
      const curriculum=await data.get('curriculum');
      if (turn!==generation) return;
      const restoreModule=s.module && !main.querySelector('.curriculum-map');
      const controls=teachingFacet?.details;
      const focus=controls?.contains(document.activeElement) ? document.activeElement : null;
      const map=curriculumMap(s,curriculum);
      showWithFilters(banner,map);
      if (focus) focus.focus({preventScroll:true});
      else if (restoreModule) map.querySelector('.map-module[open] > summary')?.focus();
      return;
    }
    const panel=element('section','sheet');
    panel.append(heading(tagResultsText(s),results.length+' 个结果'));
    panel.append(results.length?pagedRows(results,s):element('p','empty','当前范围没有匹配的题目或小问。'));
    const fromMap=main.querySelector('.curriculum-map')?.contains(document.activeElement);
    const back=crumb('知识点与考点图谱',url(s,{knowledge:null,exam:null,difficulty:null,item:null,page:null}));
    showWithFilters(banner,back,panel);
    if (fromMap) back.firstElementChild.focus();
  }
  async function practice(s,turn) {
    const results = (offline?.results || catalog.practice_results || [])
      .filter(row=>matchesPaper(papers.get(row.paper_id),s));
    const chosen = tags.get(offline?.start.key)?.name || '专项练习';
    if (s.item) return read(s,results,'专项练习目录',[],turn);
    const box=element('section','sheet');
    box.append(heading(chosen,results.length+' 项'),results.length?pagedRows(results,s):
      element('p','empty','当前筛选范围没有练习。'));
    showWithFilters(filters(s),box);
  }
  async function draw() {
    const turn=++generation;
    try {
      if (!catalog) {
        catalog=await data.get('catalog');
        papers=new Map(catalog.papers.map(p=>[p.id,p]));
        tags=new Map(catalog.tags.map(t=>[t.id,t]));
        difficulties=new Map((catalog.difficulties || []).map(d=>[d.level,d]));
      }
      if (turn!==generation) return;
      const s=route();
      const inPractice=offline?.start.mode==='practice';
      const paperTab=document.getElementById('paper-tab');
      const tagTab=document.getElementById('tag-tab');
      const tabFilters = {school:s.school,term:s.term,knowledge:s.knowledge,exam:s.exam,difficulty:s.difficulty};
      paperTab.href=url({mode:inPractice?'practice':'papers',...tabFilters,year:s.year});
      tagTab.href=url({mode:'tags',...tabFilters,teaching:s.teaching,module:s.module});
      if (inPractice) paperTab.textContent='专项练习目录';
      document.getElementById('home').href=offline?'#':'#mode=papers';
      if (difficulties.size) tagTab.textContent='按知识点、考点与难度找题';
      tagTab.hidden=!!offline && !tags.size && !difficulties.size;
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
