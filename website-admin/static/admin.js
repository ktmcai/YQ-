document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

document.querySelectorAll('form[data-upload]').forEach((form) => {
  const input = form.querySelector('input[type="file"]');
  const type = form.querySelector('[name="source_type"]');
  function updateFields() {
    form.querySelectorAll('[data-source-field]').forEach((field) => {
      const active = field.dataset.sourceField === type.value;
      field.hidden = !active;
      field.querySelectorAll('input').forEach((control) => {
        control.disabled = !active;
        control.required = active && (control.type !== 'file' || form.dataset.existingPdf !== 'true');
      });
    });
  }
  type.addEventListener('change', updateFields);
  updateFields();
  input.addEventListener('change', () => {
    const file = input.files[0];
    const error = file && (!file.name.toLowerCase().endsWith('.pdf')
      ? '请选择 PDF 格式的文件。'
      : file.size > 30 * 1024 * 1024 ? 'PDF 文件不能超过 30 MB。' : '');
    input.setCustomValidity(error || '');
    if (error) input.reportValidity();
  });
  form.addEventListener('submit', () => {
    const status = form.querySelector('.upload-status');
    status.textContent = '正在保存资料，请稍候，不要关闭此页面。';
    status.hidden = false;
    // Wait until the browser has included the clicked submit button's action.
    window.setTimeout(() => {
      form.querySelectorAll('button[type="submit"]').forEach((button) => { button.disabled = true; });
    }, 0);
  });
});

document.querySelectorAll('form[data-product-editor]').forEach((form) => {
  const type = form.querySelector('[name="link_type"]');
  function updateFields() {
    form.querySelectorAll('[data-link-field]').forEach((field) => {
      const active = field.dataset.linkField === type.value;
      field.hidden = !active;
      field.querySelectorAll('input,select').forEach((input) => {
        input.disabled = !active;
        input.required = active;
      });
    });
  }
  type.addEventListener('change', updateFields);
  updateFields();
});
