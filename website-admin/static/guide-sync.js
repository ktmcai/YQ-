(() => {
  const forms = Array.from(document.querySelectorAll('[data-guide-sync]'));
  const notice = document.querySelector('#sync-notice');
  if (!notice || !forms.length) return;
  let timer;
  let watching = !notice.hidden;
  let submitting = false;
  function show(message, error = false) {
    notice.hidden = false;
    notice.className = error ? 'notice error' : 'notice';
    notice.textContent = message;
  }
  async function poll() {
    if (submitting) return;
    try {
      const response = await fetch('/admin/guides/sync-status', { cache: 'no-store' });
      if (!response.ok || response.redirected) throw new Error('请刷新页面并重新登录以查看同步结果。');
      const { jobs } = await response.json();
      if (submitting) return;
      const running = jobs.some((job) => job.status === 'running');
      for (const job of jobs) {
        const element = document.querySelector(`[data-sync-status="${job.slug}"]`);
        if (element) element.textContent = job.message;
      }
      if (watching && !running) { location.reload(); return; }
      if (running) {
        watching = true;
        forms.forEach((form) => { form.querySelector('button').disabled = true; });
        show('正在同步，关闭页面不影响任务。完成后页面将自动刷新。');
      }
      timer = setTimeout(poll, running ? 2000 : 10000);
    } catch (error) { show(error.message || '暂时无法获取同步状态，请刷新查看。', true); }
  }
  forms.forEach((form) => form.addEventListener('submit', async (event) => {
    event.preventDefault();
    submitting = true;
    clearTimeout(timer);
    forms.forEach((item) => { item.querySelector('button').disabled = true; });
    show(form.hasAttribute('data-guide-import') ? '正在检查飞书链接和读取权限…' : '正在启动同步…');
    try {
      const response = await fetch(form.action, { method: 'POST', body: new FormData(form) });
      const result = await response.json().catch(() => { throw new Error('页面已过期，请刷新并重新登录。'); });
      if (!response.ok) {
        show(result.error || '同步未能启动，请刷新后重试。', true);
        if (result.existing_url) {
          const link = document.createElement('a');
          link.href = result.existing_url;
          link.textContent = ' 查看已有资料';
          notice.append(link);
        }
        forms.forEach((item) => { item.querySelector('button').disabled = false; });
        timer = setTimeout(poll, 2000);
        return;
      }
      if (result.location) { location.assign(result.location); return; }
      submitting = false;
      watching = true;
      await poll();
    } catch (error) {
      show(error.message, true);
      forms.forEach((item) => { item.querySelector('button').disabled = false; });
      timer = setTimeout(poll, 2000);
    } finally { submitting = false; }
  }));
  poll();
})();
