(() => {
  const form = document.querySelector('#guide-form');
  if (!form) return;
  const save = document.querySelector('#save-guide');
  const saveStatus = document.querySelector('#save-status');
  const uploadStatus = document.querySelector('#upload-status');
  if (!window.Jodit) { saveStatus.textContent = '编辑器加载失败，请刷新后重试。'; return; }
  const buttons = ['undo', 'redo', '|', 'paragraph', 'bold', 'italic', 'underline', '|', 'ul', 'ol', 'link', 'table', '|', 'eraser', 'fullsize'];
  const editor = Jodit.make('#guide-content', {
    language: 'zh_cn', height: 620, minHeight: 400, toolbarSticky: false,
    buttons, buttonsMD: buttons, buttonsSM: buttons, buttonsXS: buttons,
    showCharsCounter: false, showWordsCounter: false, showXPathInStatusbar: false,
    askBeforePasteHTML: false, askBeforePasteFromWord: false,
    defaultActionOnPaste: 'insert_clear_html',
    disablePlugins: ['image', 'file', 'video', 'iframe', 'drag-and-drop', 'drag-and-drop-element'],
    cleanHTML: { removeEmptyElements: false, removeTrailingBr: false },
    resizer: { forImageChangeAttributes: true },
    controls: { paragraph: { list: { p: '正文', h2: '一级标题', h3: '二级标题', h4: '三级标题', pre: '代码块', blockquote: '引用' } } },
  });
  let dirty = false;
  let pending = false;
  let submitted = false;
  let selection;
  save.disabled = false;
  saveStatus.textContent = '尚未修改';
  function changed() { dirty = true; saveStatus.textContent = '有未保存的修改'; }
  editor.events.on('change', changed);
  form.querySelectorAll('input[name="title"],input[name="label"]').forEach((input) => input.addEventListener('input', changed));
  window.addEventListener('beforeunload', (event) => {
    if ((dirty || pending) && !submitted) { event.preventDefault(); event.returnValue = ''; }
  });

  async function upload(file, image) {
    if (!file) return;
    if (file.size > (image ? 10 : 150) * 1048576) { uploadStatus.textContent = image ? '图片不能超过 10 MB。' : '附件不能超过 150 MB。'; return; }
    pending = true;
    save.disabled = true;
    document.querySelectorAll('#insert-image,#insert-file').forEach((button) => { button.disabled = true; });
    editor.setReadOnly(true);
    uploadStatus.textContent = `正在上传 ${file.name}…`;
    try {
      const data = new FormData();
      data.append('file', file);
      data.append('csrf_token', form.elements.csrf_token.value);
      const response = await fetch(form.dataset.uploadUrl, { method: 'POST', body: data });
      const result = await response.json().catch(() => { throw new Error('上传失败，请检查文件大小和登录状态。'); });
      if (!response.ok) throw new Error(result.error || '上传失败，请重试。');
      editor.setReadOnly(false);
      if (selection) editor.s.restore();
      const fragment = document.createElement('p');
      if (result.image) {
        const img = document.createElement('img');
        img.src = result.url; img.alt = result.name; img.width = result.width; img.height = result.height;
        fragment.append(img);
      } else {
        const link = document.createElement('a');
        link.href = result.view_url; link.textContent = result.name;
        if (result.view_url === result.url) link.download = result.name;
        fragment.append(link);
        if (result.view_url !== result.url) {
          const download = document.createElement('a');
          download.href = result.download_url; download.textContent = '下载 PDF'; download.className = 'attachment-download'; download.download = result.name;
          fragment.append(' ', download);
        }
      }
      editor.s.insertHTML(fragment.outerHTML);
      changed();
      uploadStatus.textContent = '已插入正文，点击“保存并更新官网”后生效。';
    } catch (error) { uploadStatus.textContent = error.message; }
    finally {
      pending = false; save.disabled = false; editor.setReadOnly(false);
      document.querySelectorAll('#insert-image,#insert-file').forEach((button) => { button.disabled = false; });
    }
  }
  for (const [buttonId, inputId, image] of [['insert-image', 'image-upload', true], ['insert-file', 'file-upload', false]]) {
    const input = document.getElementById(inputId);
    document.getElementById(buttonId).addEventListener('click', () => { selection = editor.s.save(); input.value = ''; input.click(); });
    input.addEventListener('change', () => upload(input.files[0], image));
  }
  editor.editor.addEventListener('paste', (event) => {
    const file = Array.from(event.clipboardData?.files || []).find((item) => item.type.startsWith('image/'));
    if (file) { event.preventDefault(); event.stopImmediatePropagation(); selection = editor.s.save(); upload(file, true); }
  }, true);
  form.addEventListener('submit', (event) => {
    if (pending) { event.preventDefault(); return; }
    form.elements.content_html.value = editor.value;
    submitted = true;
    save.disabled = true;
    saveStatus.textContent = '正在保存…';
  });
})();
