(() => {
  const section = document.querySelector('#documents');
  if (!section || window.location.protocol === 'file:') return;
  const status = document.createElement('p');
  status.className = 'document-status';
  status.setAttribute('role', 'status');
  status.hidden = true;
  section.append(status);
  let documents = [];
  let failed = false;

  function render() {
    const english = document.documentElement.lang === 'en';
    section.querySelectorAll('[data-pdf-document]').forEach((card) => card.remove());
    status.hidden = !failed;
    status.textContent = english ? 'Documents could not be loaded. Please refresh to try again.' : '资料暂时无法加载，请刷新重试。';
    documents.forEach((document) => {
      const card = window.document.createElement('article');
      card.className = 'product-card pdf-document-card';
      card.dataset.pdfDocument = document.id;
      const head = window.document.createElement('div');
      head.className = 'card-head';
      const title = window.document.createElement('h3');
      title.textContent = document.title;
      const metadata = window.document.createElement('p');
      const size = document.byte_size >= 1048576
        ? `${(document.byte_size / 1048576).toFixed(1)} MB`
        : `${Math.max(1, Math.ceil(document.byte_size / 1024))} KB`;
      const linked = document.source_type === 'url';
      metadata.textContent = linked ? (english ? 'Web document' : '网页资料')
        : `PDF · ${document.page_count} ${english ? 'pages' : '页'} · ${size}`;
      const heading = window.document.createElement('div');
      heading.append(title, metadata);
      head.append(heading);
      const actions = window.document.createElement('div');
      actions.className = 'document-actions';
      const view = window.document.createElement('a');
      view.className = 'document-link primary';
      view.href = linked ? document.external_url : `document.html?id=${document.id}`;
      view.textContent = linked ? (english ? 'Open link ↗' : '打开链接 ↗') : (english ? 'View online' : '在线查看');
      if (linked) {
        view.target = '_blank';
        view.rel = 'noopener noreferrer';
      }
      actions.append(view);
      if (!linked) {
        const download = window.document.createElement('a');
        download.className = 'document-link';
        download.href = `/documents/${document.id}/download`;
        download.download = document.original_name;
        download.textContent = english ? 'Download PDF' : '下载 PDF';
        actions.append(download);
      }
      card.append(head, actions);
      section.append(card);
    });
  }

  document.addEventListener('site-language-change', render);
  fetch('/api/documents', { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) throw new Error('Documents unavailable');
      return response.json();
    })
    .then((items) => {
      if (!Array.isArray(items)) throw new Error('Invalid documents response');
      documents = items;
      render();
    })
    .catch(() => { failed = true; render(); });
})();
