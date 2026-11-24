// Classic-script shards work both on a static host and when the entry is opened from disk.
(() => {
  'use strict';
  const values = new Map();
  const loading = new Map();
  const pdfs = new Map();
  let mathReady;

  function script(src) {
    return new Promise((resolve, reject) => {
      const el = document.createElement('script');
      el.src = src;
      el.onload = () => { el.remove(); resolve(); };
      el.onerror = () => { el.remove(); reject(new Error('未能读取 ' + src)); };
      document.head.append(el);
    });
  }
  function put(key, payload) {
    values.set(key, payload);
  }
  async function get(key) {
    if (!/^(?:catalog|curriculum|(?:papers|tags|items|answers)\/[A-Za-z\d._-]+)$/.test(key)) throw new Error('无效的题库编号');
    if (values.has(key)) return values.get(key);
    const offline = window.BANK_OFFLINE;
    if (offline) {
      if (Object.hasOwn(offline.data, key)) return offline.data[key];
      throw new Error('这份离线文件未收录该内容。');
    }
    if (!loading.has(key)) {
      const pending = script('generated/' + key + '.js').then(() => {
        if (!values.has(key)) throw new Error('数据分片缺少记录：' + key);
        return values.get(key);
      }).finally(() => loading.delete(key));
      loading.set(key, pending);
    }
    return loading.get(key);
  }
  function hasItem(id) {
    return !window.BANK_OFFLINE || Object.hasOwn(window.BANK_OFFLINE.data, 'items/' + id);
  }
  function asset(path) {
    return window.BANK_OFFLINE?.assets?.[path] || path;
  }
  function pdf(path) {
    const value = asset(path);
    if (!value || !value.startsWith('data:')) return value;
    if (!pdfs.has(path)) {
      const raw = atob(value.slice(value.indexOf(',') + 1));
      const bytes = Uint8Array.from(raw, c => c.charCodeAt(0));
      pdfs.set(path, URL.createObjectURL(new Blob([bytes], {type:'application/pdf'})));
    }
    return pdfs.get(path);
  }
  async function math(host) {
    const spans = [...host.querySelectorAll('.bank-tex[data-tex]')];
    if (!spans.length) return;
    if (!window.katex) {
      if (window.BANK_OFFLINE) throw new Error('离线文件缺少公式排版组件。');
      if (!mathReady) mathReady = script('web/vendor/katex.min.js').catch(error => { mathReady = null; throw error; });
      await mathReady;
    }
    if (!window.katex?.render) throw new Error('公式排版组件未能启动。');
    for (const node of spans) {
      window.katex.render(node.dataset.tex, node, {
        output:'mathml', displayMode:node.dataset.display === 'block', trust:false, throwOnError:false, strict:'ignore'
      });
    }
  }
  window.BankData = {put, get, hasItem, asset, pdf, math};
})();
