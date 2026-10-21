document.querySelectorAll('.product-list a[href^="manuals/"]').forEach((link) => {
  link.addEventListener('click', (event) => {
    event.preventDefault();
    window.alert('该产品手册链接已预留，文件接入后即可打开。');
  });
});
