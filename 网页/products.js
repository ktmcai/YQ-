(() => {
  const grid = document.querySelector('#products .product-grid');
  if (!grid) return;
  let categories = [];
  let loaded = false;
  let failed = false;
  let selectedSeries = 'JP';

  function create(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function render() {
    const english = document.documentElement.lang === 'en';
    grid.replaceChildren();
    if (!loaded || failed) {
      grid.append(create('p', 'product-load-state', failed
        ? english ? 'Products could not be loaded. Please refresh to try again.' : '产品目录暂时无法加载，请刷新重试。'
        : english ? 'Loading products…' : '正在加载产品…'));
      return;
    }
    categories.forEach((category, index) => {
      const card = create('article', `product-card${category.wide ? ' product-card-wide' : ''}`);
      card.dataset.productCategory = category.id;
      const head = create('div', 'card-head');
      const heading = create('div');
      heading.append(create('h3', '', category.name), create('p', '', english && category.description_en ? category.description_en : category.description));
      if (!category.series?.length) head.append(create('span', 'card-number', String(index + 1).padStart(2, '0')));
      head.append(heading);
      card.append(head);
      if (category.series?.length) {
        card.classList.add('axis-card');
        const tabs = create('div', 'axis-series-tabs');
        tabs.setAttribute('role', 'tablist');
        tabs.setAttribute('aria-label', english ? 'AXIS product series' : 'AXIS 产品系列');
        const panel = create('div', 'axis-series-panel');
        panel.id = 'axis-series-panel';
        panel.setAttribute('role', 'tabpanel');
        panel.tabIndex = 0;
        const buttons = category.series.map((series) => {
          const button = create('button', 'axis-series-tab');
          button.type = 'button';
          button.id = 'axis-tab-' + series.code;
          button.setAttribute('role', 'tab');
          button.setAttribute('aria-controls', panel.id);
          const name = create('span');
          if (english) name.textContent = series.name_en;
          else name.append(create('span', 'axis-name-part', series.name.replace('关节执行器', '')), create('span', 'axis-name-part', '关节执行器'));
          button.append(create('strong', '', series.code), name);
          button.addEventListener('click', () => select(series.code));
          tabs.append(button);
          return button;
        });
        function select(code) {
          selectedSeries = code;
          buttons.forEach((button, i) => {
            const active = category.series[i].code === code;
            button.setAttribute('aria-selected', String(active));
            button.tabIndex = active ? 0 : -1;
          });
          panel.setAttribute('aria-labelledby', 'axis-tab-' + code);
          const products = category.products.filter((product) => product.series === code);
          panel.replaceChildren(create('p', 'axis-series-caption', english ? `${code} series · ${products.length} products` : `${code} 系列 · ${products.length} 款产品`));
          if (products.length) panel.append(productItems(products, english));
          else panel.append(create('p', 'axis-empty', english ? 'No products published in this series yet.' : '该系列暂无已发布产品。'));
          const branch = category.series.find((entry) => entry.code === code);
          if (branch.guide_href) {
            const documents = create('a', 'axis-document-link', english ? `Browse ${code} documentation →` : `浏览 ${code} 系列文档 →`);
            documents.href = branch.guide_href;
            panel.append(documents);
          }
        }
        tabs.addEventListener('keydown', (event) => {
          const index = buttons.indexOf(document.activeElement);
          if (index < 0 || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
          select(category.series[next].code);
          buttons[next].focus();
        });
        select(selectedSeries);
        card.append(tabs, panel);
        const other = category.products.filter((product) => !product.series);
        if (other.length) card.append(create('p', 'axis-series-caption', english ? 'Other AXIS products' : '其他 AXIS 产品'), productItems(other, english));
      } else if (!category.products.length) {
        card.append(create('p', 'empty-card', english ? 'No products available yet' : '暂无对外产品'));
      } else {
        card.append(productItems(category.products, english));
      }
      grid.append(card);
    });
  }

  function productItems(products, english) {
    const items = create('div', 'card-items');
    products.forEach((product) => {
          const item = create(product.href ? 'a' : 'div', product.href ? '' : 'product-item unavailable');
          item.dataset.productId = product.id;
          if (product.href) {
            item.href = product.href;
            if (product.external) { item.target = '_blank'; item.rel = 'noopener noreferrer'; }
          }
          const summary = create('span', 'product-summary', english && product.description_en ? product.description_en : product.description);
          item.append(create('strong', '', product.name));
          if (product.rated_torque || product.peak_torque) {
            item.classList.add('has-torque');
            if (!product.href) item.tabIndex = 0;
            const details = create('div', 'product-details');
            const torque = create('div', 'product-torque');
            if (product.rated_torque) torque.append(create('span', '', `${english ? 'Rated torque' : '额定扭矩'}：${product.rated_torque} N·m`));
            if (product.peak_torque) torque.append(create('span', '', `${english ? 'Peak torque' : '峰值扭矩'}：${product.peak_torque} N·m`));
            details.append(summary, torque);
            item.append(details);
          } else item.append(summary);
          const status = create('b', '', product.href ? '↗' : english ? 'Soon' : '待开放');
          status.setAttribute('aria-hidden', 'true');
          item.append(status);
          items.append(item);
    });
    return items;
  }

  document.addEventListener('site-language-change', render);
  fetch('/api/products', { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) throw new Error('Products unavailable');
      return response.json();
    })
    .then((items) => {
      if (!Array.isArray(items)) throw new Error('Invalid products response');
      categories = items;
      loaded = true;
      render();
    })
    .catch(() => { failed = true; render(); });
})();
