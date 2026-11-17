(() => {
  let english = false;
  try { english = localStorage.getItem('yoniq-language') === 'en'; } catch {}
  if (english) {
    document.documentElement.lang = 'en';
    document.querySelectorAll('[data-en]').forEach((element) => { element.textContent = element.dataset.en; });
  }
  const title = document.querySelector('#document-title');
  const status = document.querySelector('#document-status');
  const identifier = new URLSearchParams(window.location.search).get('id');
  function unavailable() {
    title.textContent = english ? 'Document unavailable' : '文档暂时不可用';
    status.textContent = english ? 'This document may have been unpublished or deleted. Please return to product documentation.' : '这份文档可能已下架或删除，请返回产品资料页查看其他文档。';
  }
  if (!/^[1-9]\d*$/.test(identifier || '')) { unavailable(); return; }
  fetch(`/api/documents/${identifier}`, { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) throw new Error('Document unavailable');
      return response.json();
    })
    .then((item) => {
      title.textContent = item.title;
      document.title = `${item.title} · YONIQ`;
      if (item.source_type === 'url') {
        document.querySelector('#document-meta').textContent = english ? 'Web document' : '网页资料';
        const link = document.querySelector('#document-download');
        link.href = item.external_url;
        link.textContent = english ? 'Open link ↗' : '打开链接 ↗';
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.hidden = false;
        status.textContent = english ? 'Use the button to open this web document in a new tab.' : '这份资料为网页链接，点击按钮可在新标签页查看。';
        return;
      }
      document.querySelector('#document-meta').textContent = `PDF · ${item.page_count} ${english ? 'pages' : '页'} · ${(item.byte_size / 1048576).toFixed(2)} MB`;
      const download = document.querySelector('#document-download');
      download.href = `/documents/${identifier}/download`;
      download.download = item.original_name;
      download.hidden = false;
      const frame = document.querySelector('#pdf-viewer');
      frame.title = item.title;
      frame.hidden = false;
      document.addEventListener('webviewerloaded', (event) => {
        const viewer = event.detail.source;
        const options = viewer.PDFViewerApplicationOptions;
        options.set('disablePreferences', true);
        options.set('defaultZoomValue', 'page-fit');
        options.set('viewOnLoad', 1);
        options.set('annotationEditorMode', -1);
        options.set('localeProperties', { lang: english ? 'en-US' : 'zh-CN' });
        const stylesheet = viewer.document.createElement('link');
        stylesheet.rel = 'stylesheet';
        stylesheet.href = '/pdf-viewer.css?v=20261021';
        viewer.document.head.append(stylesheet);
      }, { once: true });
      requestAnimationFrame(() => {
        frame.src = `/vendor/pdfjs-6.4.299-legacy/web/viewer.html?file=${encodeURIComponent(`/documents/${identifier}/view`)}#page=1&zoom=page-fit`;
      });
    })
    .catch(unavailable);
})();
