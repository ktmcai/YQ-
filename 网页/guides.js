(() => {
  let english = false;
  try { english = localStorage.getItem('yoniq-language') === 'en'; } catch {}
  if (english) {
    document.documentElement.lang = 'en';
    document.querySelectorAll('[data-en]').forEach((element) => { element.textContent = element.dataset.en; });
    document.querySelector('#document-search').placeholder = 'Model or keyword';
  }
  const list = document.querySelector('#document-list');
  const search = document.querySelector('#document-search');
  const sidebar = document.querySelector('#document-sidebar');
  const toggle = document.querySelector('#menu-toggle');
  const outlinePanel = document.querySelector('#page-outline');
  const outlineToggle = document.querySelector('#outline-toggle');
  const layout = document.querySelector('.docs-layout');
  const outlineDocked = window.matchMedia('(min-width: 1101px)');
  const documentsDocked = window.matchMedia('(min-width: 761px)');
  const status = document.querySelector('#document-status');
  const body = document.querySelector('#document-body');
  const slug = new URLSearchParams(location.search).get('doc') || 'selection';
  let documents = [];
  let axisSeries = [];
  let refreshOutline = () => {};

  function updateToggles() {
    [[toggle, sidebar, documentsDocked.matches, 'documents-collapsed', '文档目录'],
      [outlineToggle, outlinePanel, outlineDocked.matches, 'outline-collapsed', '本页目录']].forEach(([button, panel, docked, collapsed, label]) => {
      const expanded = !panel.hidden && (docked ? !layout.classList.contains(collapsed) : panel.classList.contains('open'));
      const action = english ? `${expanded ? 'Hide' : 'Show'} ${button === outlineToggle ? 'page outline' : 'documents'}` : `${expanded ? '收起' : '展开'}${label}`;
      button.setAttribute('aria-expanded', String(expanded));
      button.setAttribute('aria-label', action);
    });
  }
  function closeMenu() {
    sidebar.classList.remove('open');
    updateToggles();
  }
  function closeOutline() {
    outlinePanel.classList.remove('open');
    updateToggles();
  }
  toggle.addEventListener('click', () => {
    if (documentsDocked.matches) {
      layout.classList.toggle('documents-collapsed');
      updateToggles();
      refreshOutline();
      return;
    }
    closeOutline();
    const open = sidebar.classList.toggle('open');
    updateToggles();
    if (open) search.focus();
  });
  outlineToggle.addEventListener('click', () => {
    if (outlineDocked.matches) {
      layout.classList.toggle('outline-collapsed');
      updateToggles();
      refreshOutline();
      return;
    }
    closeMenu();
    const open = outlinePanel.classList.toggle('open');
    updateToggles();
    if (open) (outlinePanel.querySelector('[aria-current=location]') || outlinePanel.querySelector('a'))?.focus();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('open')) { closeMenu(); toggle.focus(); }
    if (event.key === 'Escape' && outlinePanel.classList.contains('open')) { closeOutline(); outlineToggle.focus(); }
  });
  document.querySelector('main').addEventListener('click', () => { closeMenu(); closeOutline(); });
  window.addEventListener('resize', () => { closeMenu(); closeOutline(); });
  updateToggles();

  function renderList() {
    const query = search.value.trim().toLocaleLowerCase();
    const matches = documents.filter((item) => {
      const series = axisSeries.find((branch) => branch.code === item.series);
      return `${item.category} ${item.series || ''} ${series?.name || ''} ${series?.name_en || ''} ${item.title} ${item.label} ${item.text}`.toLocaleLowerCase().includes(query);
    });
    list.replaceChildren();
    function documentLink(item) {
      const link = document.createElement('a');
      link.href = `/guides.html?doc=${encodeURIComponent(item.slug)}`;
      link.textContent = item.label;
      if (item.slug === slug) link.setAttribute('aria-current', 'page');
      if (query) {
        const excerpt = document.createElement('span');
        excerpt.className = 'search-excerpt';
        const start = Math.max(0, item.text.toLocaleLowerCase().indexOf(query) - 18);
        excerpt.textContent = `${start ? '…' : ''}${item.text.slice(start, start + 90)}…`;
        link.append(excerpt);
      }
      return link;
    }
    function group(title, description, opened, nested = false) {
      const details = document.createElement('details');
      details.className = nested ? 'document-tree-series' : 'document-tree-group';
      details.open = opened;
      const summary = document.createElement('summary');
      const arrow = document.createElement('span');
      arrow.className = 'tree-arrow';
      arrow.textContent = '›';
      arrow.setAttribute('aria-hidden', 'true');
      const label = document.createElement('span');
      const name = document.createElement('strong');
      name.textContent = title;
      label.append(name);
      if (description) {
        const subtitle = document.createElement('small');
        subtitle.textContent = description;
        label.append(subtitle);
      }
      summary.append(arrow, label);
      const content = document.createElement('div');
      content.className = 'document-tree-content';
      details.append(summary, content);
      return { details, content };
    }
    const groups = new Map();
    matches.forEach((item) => {
      if (!groups.has(item.category)) groups.set(item.category, []);
      groups.get(item.category).push(item);
    });
    if (!query && !groups.has('YONIQ AXIS')) groups.set('YONIQ AXIS', []);
    groups.forEach((items, category) => {
      const axis = category === 'YONIQ AXIS';
      const parent = group(category, axis ? (english ? 'Integrated joint actuators' : '一体化关节执行器') : '', Boolean(query) || axis || items.some((item) => item.slug === slug));
      if (axis) {
        items.filter((item) => !item.series).forEach((item) => parent.content.append(documentLink(item)));
        axisSeries.forEach((series) => {
          const children = items.filter((item) => item.series === series.code);
          if (query && !children.length) return;
          const branch = group(series.code, english ? series.name_en : series.name, Boolean(query) || children.some((item) => item.slug === slug) || (series.code === 'JP' && !items.some((item) => item.slug === slug)), true);
          branch.details.dataset.series = series.code;
          children.forEach((item) => branch.content.append(documentLink(item)));
          if (!children.length) {
            const empty = document.createElement('p');
            empty.className = 'document-tree-empty';
            empty.textContent = english ? 'No documents yet' : '暂无资料';
            branch.content.append(empty);
          }
          parent.content.append(branch.details);
        });
      } else items.forEach((item) => parent.content.append(documentLink(item)));
      list.append(parent.details);
    });
    document.querySelector('#search-status').textContent = query
      ? (english ? `${matches.length} matching documents` : `找到 ${matches.length} 份相关文档`)
      : (english ? `${documents.length} documents` : `共 ${documents.length} 份文档`);
  }
  search.addEventListener('input', renderList);

  Promise.all(['/guides/catalog.json', '/api/axis-series'].map((url) => fetch(url, { cache: 'no-cache' }).then((response) => {
    if (!response.ok) throw new Error('Catalog unavailable');
    return response.json();
  })))
    .then(async ([items, series]) => {
      documents = items;
      axisSeries = series;
      renderList();
      const item = documents.find((entry) => entry.slug === slug);
      if (!item) {
        status.textContent = english ? 'Document not found. Choose a document from the menu.' : '未找到这份文档，请从文档目录选择其他资料。';
        return;
      }
      const response = await fetch(`/guides/${encodeURIComponent(item.slug)}/content.html`, { cache: 'no-cache' });
      if (!response.ok) throw new Error('Document unavailable');
      body.innerHTML = await response.text();
      body.querySelectorAll('table').forEach((table) => {
        if (table.parentElement.classList.contains('table-scroll')) return;
        const wrapper = document.createElement('div');
        wrapper.className = 'table-scroll';
        wrapper.tabIndex = 0;
        wrapper.setAttribute('role', 'region');
        wrapper.setAttribute('aria-label', english ? 'Scrollable table' : '可横向滚动的表格');
        table.before(wrapper);
        wrapper.append(table);
      });
      document.title = `${item.title} · YONIQ`;
      document.querySelector('#document-title').textContent = item.title;
      const branch = axisSeries.find((entry) => entry.code === item.series);
      document.querySelector('#document-category').textContent = item.category + (branch ? ` / ${branch.code} · ${english ? branch.name_en : branch.name}` : '');
      document.querySelector('#document-heading').hidden = false;
      const outline = document.querySelector('#document-outline');
      const headings = Array.from(body.querySelectorAll('h2,h3,h4,h5,h6'));
      headings.forEach((heading) => {
        const link = document.createElement('a');
        link.href = `#${heading.id}`;
        link.textContent = heading.textContent;
        if (heading.tagName !== 'H2') link.className = 'nested';
        link.addEventListener('click', (event) => {
          if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
          closeOutline();
          heading.tabIndex = -1;
          heading.focus({ preventScroll: true });
        });
        outline.append(link);
      });
      outlinePanel.hidden = outlineToggle.hidden = !headings.length;
      updateToggles();
      let currentLink;
      let scheduled = false;
      function updateOutline() {
        scheduled = false;
        if (!headings.length) return;
        let active = 0;
        const controls = document.querySelector('.sidebar-controls');
        const offset = Math.max(document.querySelector('.docs-header').getBoundingClientRect().bottom, controls.offsetHeight ? controls.getBoundingClientRect().bottom : 0) + 32;
        headings.forEach((heading, index) => { if (heading.getBoundingClientRect().top <= offset) active = index; });
        if (window.scrollY > 0 && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) active = headings.length - 1;
        const link = outline.children[active];
        if (link === currentLink) return;
        currentLink?.removeAttribute('aria-current');
        link.setAttribute('aria-current', 'location');
        currentLink = link;
        if (outline.clientHeight && !outline.matches(':hover,:focus-within')) {
          const bounds = outline.getBoundingClientRect();
          const target = link.getBoundingClientRect();
          if (target.top < bounds.top || target.bottom > bounds.bottom) outline.scrollTop += target.top - bounds.top - outline.clientHeight / 2;
        }
      }
      function scheduleOutline() {
        if (!scheduled) { scheduled = true; requestAnimationFrame(updateOutline); }
      }
      refreshOutline = scheduleOutline;
      window.addEventListener('scroll', scheduleOutline, { passive: true });
      window.addEventListener('resize', scheduleOutline);
      body.addEventListener('load', scheduleOutline, true);
      document.querySelector('#document-footer').hidden = false;
      status.hidden = true;
      if (location.hash) {
        try { document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView(); } catch {}
      }
      scheduleOutline();
    })
    .catch(() => {
      status.textContent = english ? 'Documents could not be loaded. Please refresh to try again.' : '文档暂时无法加载，请刷新重试。';
    });
})();
