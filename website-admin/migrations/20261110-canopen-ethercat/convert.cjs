// Run with NODE_PATH pointing to the temporary tools containing mammoth 1.11.0.
const fs = require('fs');
const path = require('path');
const mammoth = require('mammoth');

(async () => {
  const source = path.resolve(__dirname, '../../../协议文档');
  const name = 'YONIQ_AXIS_CANopen_EtherCAT用户手册';
  const result = await mammoth.convertToHtml({path: path.join(source, name + '.docx')}, {
    styleMap: [
      "p[style-name='Title'] => !",
      "p[style-name='Subtitle'] => p:fresh",
      "p[style-name='toc 1'] => !",
      "p[style-name='toc 2'] => !",
      "p[style-name='heading 1'] => h2:fresh",
      "p[style-name='heading 2'] => h3:fresh",
      "p[style-name='Table Text'] => p:fresh",
      "p[style-name='List Bullet'] => ul > li:fresh",
    ],
  });
  if (result.messages.length) throw new Error(JSON.stringify(result.messages));
  const pdf = '/guides/canopen-ethercat/assets/YONIQ_AXIS_CANopen_EtherCAT.pdf';
  const links = `<p><a href="/vendor/pdfjs-6.4.299-legacy/web/viewer.html?file=${encodeURIComponent(pdf)}">在线查看原版 PDF</a> · <a href="${pdf}?download=1" download>下载 PDF</a></p>`;
  fs.writeFileSync(path.join(__dirname, 'content.html'), links + result.value);
  fs.copyFileSync(path.join(source, name + '.pdf'), path.join(__dirname, 'YONIQ_AXIS_CANopen_EtherCAT.pdf'));
  console.log('Converted combined manual without warnings.');
})().catch(error => { console.error(error); process.exit(1); });
