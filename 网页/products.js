(() => {
  const grid = document.querySelector('#products .product-grid');
  if (!grid) return;
  let categories = [];
  let loaded = false;
  let failed = false;

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
      head.append(create('span', 'card-number', String(index + 1).padStart(2, '0')), heading);
      card.append(head);
      if (!category.products.length) {
        card.append(create('p', 'empty-card', english ? 'No products available yet' : '暂无对外产品'));
      } else {
        const items = create('div', 'card-items');
        category.products.forEach((product) => {
          const item = create(product.href ? 'a' : 'div', product.href ? '' : 'product-item unavailable');
          item.dataset.productId = product.id;
          if (product.href) {
            item.href = product.href;
            if (product.external) { item.target = '_blank'; item.rel = 'noopener noreferrer'; }
          }
          item.append(create('strong', '', product.name), create('span', '', english && product.description_en ? product.description_en : product.description));
          const status = create('b', '', product.href ? '↗' : english ? 'Soon' : '待开放');
          status.setAttribute('aria-hidden', 'true');
          item.append(status);
          items.append(item);
        });
        card.append(items);
      }
      grid.append(card);
    });
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
