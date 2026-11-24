(() => {
  'use strict';
  const data = window.BankData;
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }
  function button(text, action, className) {
    const node = element('button', className, text);
    node.type = 'button';
    node.addEventListener('click', action);
    return node;
  }
  function link(text, href, className) {
    const node = element('a', className, text);
    node.href = href;
    return node;
  }
  const byId = id => document.getElementById(id);
  const narrow = window.matchMedia('(max-width:780px)');
  const dialog = byId('lightbox');
  function zoom(on) {
    byId('image-scroll').classList.toggle('zoom', on);
    byId('zoom').textContent = on ? '适应宽度' : '放大';
    byId('zoom').setAttribute('aria-pressed', String(on));
  }
  function openImage(path, label) {
    byId('image-title').textContent = label;
    byId('large-image').src = data.asset(path);
    byId('large-image').alt = label;
    zoom(narrow.matches);
    dialog.showModal();
    byId('image-scroll').scrollTo(0,0);
  }
  byId('zoom').addEventListener('click', () => zoom(!byId('image-scroll').classList.contains('zoom')));
  byId('close-image').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });

  function section(title, load, cls) {
    const details = element('details', 'section '+(cls || ''));
    const body = element('div','section-body');
    details.append(element('summary','',title), body);
    // Defer crop URLs, larger solution shards and PDFs until the user asks for them.
    let ready;
    function populate() {
      body.replaceChildren(element('p','muted','正在加载…'));
      ready = Promise.resolve().then(() => load(body)).catch(error => {
        body.replaceChildren(element('p','status error',error.message),button('重试', populate));
      });
    }
    details.addEventListener('toggle', () => { if (details.open && !ready) populate(); });
    return details;
  }
  function pdfLinks(path, pages, kind) {
    const wrap = element('div','page-ref');
    if (!path) return wrap;
    for (const page of pages || []) {
      const node = link(kind+'第 '+page+' 页 ↗', '#');
      node.target = '_blank';
      node.rel = 'noopener';
      if (!window.BANK_OFFLINE) node.href = data.pdf(path)+'#page='+page;
      else node.addEventListener('click', () => { node.href = data.pdf(path)+'#page='+page; });
      wrap.append(node);
    }
    return wrap;
  }
  function cuts(paths, pages, name) {
    const wrap = document.createDocumentFragment();
    (paths || []).forEach((path,i) => {
      const label = name+'第 '+pages[i]+' 页';
      const div = element('div','cut');
      const img = element('img');
      img.src = data.asset(path);
      img.alt = label+'题目区域';
      img.loading = 'lazy';
      const control = button('',() => openImage(path,label));
      control.setAttribute('aria-label','放大'+label);
      control.append(img);
      div.append(control,element('small','page-note',label));
      wrap.append(div);
    });
    return wrap;
  }
  function prepareStem(html) {
    const template = document.createElement('template');
    template.innerHTML = html; // Escaped and typeset by the repository's static builder.
    for (const img of template.content.querySelectorAll('img')) {
      const path = img.getAttribute('src');
      const label = img.alt || '题图';
      const wrap = button('',() => openImage(path,label),'diagram-button');
      wrap.setAttribute('aria-label','放大'+label);
      img.setAttribute('src',data.asset(path));
      img.replaceWith(wrap);
      wrap.append(img);
    }
    for (const table of template.content.querySelectorAll('table')) {
      if (table.parentElement?.matches('.source-table,.table-wrap,.table-scroll')) continue;
      const box = element('div','table-scroll');
      table.replaceWith(box); box.append(table);
    }
    const wrap = element('div','readable');
    wrap.append(template.content);
    return wrap;
  }
  function texText(str,cls,figures) {
    const wrap = element('div','math-text '+(cls||''));
    const pattern = /\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]|〔图(\d+)〕/g;
    let from = 0;
    const text = String(str || '');
    for (const match of text.matchAll(pattern)) {
      wrap.append(document.createTextNode(text.slice(from,match.index)));
      from = match.index+match[0].length;
      if (match[3]) {
        const path = figures?.[match[3]];
        if (path) {
          const label = '解析图 '+match[3];
          const img = element('img');
          img.alt = label; img.src = data.asset(path);
          const view = button('',()=>openImage(path,label),'diagram-button solution-figure');
          view.setAttribute('aria-label','放大'+label);
          view.append(img); wrap.append(view);
        } else wrap.append(document.createTextNode(match[0]));
        continue;
      }
      const tex = match[1] ?? match[2];
      const span = element('span','bank-tex',tex);
      span.dataset.tex = tex;
      if (match[2] != null) span.dataset.display = 'block';
      wrap.append(span);
    }
    wrap.append(document.createTextNode(text.slice(from)));
    return wrap;
  }
  function note(str) {
    const wrap = element('aside','review-note');
    wrap.append(element('strong','','校勘与补充'),document.createTextNode(str));
    return wrap;
  }
  function answerSections(item) {
    return section('答案与参考解答', async body => {
      const a = await data.get('answers/'+item.id);
      const origins = {source_checked_with_correction:'依据题干校正，可展开下方原解析对照', source_transcribed:'据配套解析转录',
        source_solution_summary:'答案从配套解题过程归纳', editorial_solution:'资料提供答案，解法由题库补写',
        source_answer_only:'资料只提供答案',source_facsimile:'参考原件影像'};
      body.replaceChildren(element('p','muted', origins[a.solution_origin] || '依据配套解析整理'));
      body.append(texText(a.answer,'ref-answer',a.figure_refs));
      for (const step of a.solution_steps || []) body.append(texText(step,'step',a.figure_refs));
      const inlineFigures = new Set([a.answer,...(a.solution_steps || [])].flatMap(s=>
        [...s.matchAll(/〔图(\d+)〕/g)].map(m=>a.figure_refs?.[m[1]])));
      for (const [index,path] of (a.solution_figures || []).entries()) {
        if (inlineFigures.has(path)) continue;
        const label = '参考解答图 '+(index+1);
        const img = element('img');
        img.alt = label; img.src = data.asset(path); img.loading = 'lazy';
        const control = button('',()=>openImage(path,label),'solution-figure diagram-button');
        control.setAttribute('aria-label','放大'+label);
        control.append(img); body.append(control);
      }
      if (a.review_note) body.append(note(a.review_note));
      body.append(section('资料原答案与原解析', async source => {
        source.replaceChildren();
        if (a.given_answer) source.append(element('h3','','资料原答案'),texText(a.given_answer,'',a.figure_refs));
        source.append(pdfLinks(a.source.solution_pdf,a.source.solution_pages,'解析版'));
        if (a.source.solution_images?.length) source.append(cuts(a.source.solution_images,a.source.solution_pages,'解析版'));
        else if (a.given_solution) source.append(texText(a.given_solution));
        await data.math(source);
      }));
      await data.math(body);
    },'answer');
  }
  function tagLinks(tags, ctx) {
    const wrap = element('div','tag-links');
    for (const id of tags || []) {
      const tag = ctx.tags.get(id);
      const name = tag?.name || id;
      const url = ctx.tagURL(id);
      if (url) wrap.append(link(name,url));
      else wrap.append(element('span','muted',name));
    }
    return wrap;
  }
  function render(item,ctx) {
    const source = item.source;
    const paper = ctx.papers.get(item.paper_id);
    const r = element('article','reader');
    const top = element('div','reader-top');
    top.append(element('div','metadata', (paper?.school || '')+' · 第 '+item.number+' 题'+(item.label?' · 小问 '+item.label:'')+(item.type?' · '+item.type:'')));
    const pager = element('div','pager');
    const prev = button('上一题',()=>ctx.step(-1)), next = button('下一题',()=>ctx.step(1));
    prev.disabled = !ctx.previous;
    next.disabled = !ctx.next;
    pager.append(prev,next); top.append(pager); r.append(top);
    r.append(element('h2','',item.title));
    if (paper) r.append(element('p','metadata',paper.academic_year+' 学年 · '+paper.grade+paper.semester+' · '+paper.exam_type));
    const returns = element('div','meta-links');
    if (item.label && data.hasItem(item.question_id)) returns.append(link('查看所属整题',ctx.itemURL(item.question_id)));
    if (ctx.paperURL) returns.append(link('查看本卷目录',ctx.paperURL));
    if (returns.children.length) r.append(returns);
    if (item.parts?.length) {
      const siblings = element('div','unit-links');
      siblings.append(element('span','muted','单独练习'));
      for (const p of item.parts) if (data.hasItem(p.id)) siblings.append(link('小问 '+p.label,ctx.itemURL(p.id)));
      if (siblings.children.length>1) r.append(siblings);
    }
    const stem = prepareStem(item.html);
    r.append(stem);
    data.math(stem).catch(error => { stem.append(element('p','status error',error.message)); });
    r.append(pdfLinks(source.paper_pdf,source.question_pages,'原卷'));
    r.append(section('对照原卷 / 放大原题',body => {
      body.replaceChildren(cuts(source.question_images,source.question_pages,'原卷'));
    }));
    r.append(answerSections(item));
    r.append(section('知识点与考点',body => {
      body.replaceChildren();
      if (item.coverage) {
        const c = element('div','coverage '+(item.coverage==='完整匹配'?'':'gap'));
        c.append(element('strong','',item.coverage),document.createTextNode(item.tag_note || '')); body.append(c);
      }
      if (item.tag_reason) body.append(element('p','step',item.tag_reason));
      if (item.knowledge_ids?.length) body.append(element('h3','','知识点'),tagLinks(item.knowledge_ids,ctx));
      if (item.exam_ids?.length) body.append(element('h3','','考点'),tagLinks(item.exam_ids,ctx));
    }));
    return r;
  }
  window.BankReader = {element,button,link,texText,render};
})();
