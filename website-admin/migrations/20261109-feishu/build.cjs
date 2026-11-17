const fs=require('node:fs'),path=require('node:path');const MarkdownIt=require('markdown-it');
const root=path.resolve(__dirname,'../../..'), exportsDir=__dirname;
const output=path.join(root,'网页','guides'),archive=path.join(root,'website-admin','migrations','20261109-feishu');
const jobs=[
 {slug:'selection',label:'快速选型 · 电机参数表',category:'选型资料',source:'wiki/C7SKwVeB8iJ2gTkeQE4cymV6nxv'},
 {slug:'jp57-08',label:'JP57-08 G1',category:'YONIQ AXIS',source:'docx/GSSXdAIAJocehkxhpbEcmxKVnRe',productId:1},
 {slug:'jp57-40',label:'JP57-40 G1',category:'YONIQ AXIS',source:'docx/LW2ydbYwzoUKVmxVDAccMcdBntd',productId:2},
 {slug:'db1-v24',label:'DB1-V24',category:'YONIQ DRIVE',source:'docx/HQ30dgSqYoW9Z7xkozjcHs82nTc',productId:4},
 {slug:'db1-v36',label:'DB1-V36',category:'YONIQ DRIVE',source:'docx/T5YIdDLvJoelNlx2KaycLtdHnxd',productId:5},
 {slug:'db1-v48',label:'DB1-V48',category:'YONIQ DRIVE',source:'docx/B8zbdrASeoaAxyxKYDPcAwAanfe',productId:6},
 {slug:'cf-1',label:'CF-1',category:'YONIQ LINK',source:'docx/YEefdI5cMohwyXxAVggcyat1nag',productId:7},
 {slug:'studio',label:'YONIQ STUDIO',category:'YONIQ STUDIO',source:'wiki/EQ0ewITm0i3sYFkNSYecxgqtnhb',productId:8},
 {slug:'serial-protocol',label:'串口协议手册',category:'协议手册',source:'docx/ZsBddgkFwodVhEx4PxAcgpUDnVc'}
];
const sourceMap=new Map(jobs.map(j=>[j.source.split('/').pop(),j.slug]));sourceMap.set('It0kd7CAqot1Lbxy7cQcyNMhnIe','studio');
const crossSections={LJD0dl9Wqo3EZ6x5TCAchc9BnVg:'电机状态1',A4DNdaOoSoeqDCxn2YVcEQxznvF:'电机状态2',ItZ0ddMShoAkZExrt3vcChZDn3r:'电机状态3',Cp3WddHDHoXdhZx5DeYcAwupnBd:'电机状态4',GcNHdbMLjo0JdSx7dQIcahQHnYg:'电机执行结果ACK',DjZfdkDuZo5UoVxjFZZcd0C5nDP:'电机 MAVLIN_ID信息',ELG1ddRkdoBDRsxcuJ2ckiwfnGd:'电机 CAN ID 信息',N8NldQTjEoQfYdxfkyRce4APncf:'电机控制参数表',VotUdOELdo5K3zx8WkbcVVOknfb:'电机保护参数表',QyMwdAKsGoBmQcxwBafct71Rn4f:'电机限制参数表'};
const md=new MarkdownIt({html:false,linkify:true,breaks:true});
md.inline.ruler.before('html_inline','export_break',(state,silent)=>{const match=state.src.slice(state.pos).match(/^<br\s*\/?>/i);if(!match)return false;if(!silent)state.push('hardbreak','br',0);state.pos+=match[0].length;return true;});
md.inline.ruler.before('emphasis','export_bold',(state,silent)=>{
 if(!state.src.startsWith('**',state.pos))return false;
 const end=state.src.indexOf('**',state.pos+2);if(end<0)return false;
 const inner=state.src.slice(state.pos+2,end);if(!inner.trim()||inner.includes('\n'))return false;
 if(!silent){state.push('strong_open','strong',1);const children=[];state.md.inline.parse(inner.trim(),state.md,state.env,children);state.tokens.push(...children);state.push('strong_close','strong',-1);}
 state.pos=end+2;return true;
});
const dimensions=JSON.parse(fs.readFileSync(path.join(exportsDir,'image-dimensions.json'),'utf8'));
const escape=md.utils.escapeHtml;
const cleanText=t=>t.filter(c=>['text','code_inline'].includes(c.type)).map(c=>c.content).join('');
const tables=JSON.parse(fs.readFileSync(path.join(exportsDir,'selection-tables.json'),'utf8').replace(/^\uFEFF/,''));
fs.mkdirSync(archive,{recursive:true});fs.mkdirSync(output,{recursive:true});
fs.writeFileSync(path.join(archive,'selection-tables.json'),JSON.stringify(tables,null,2));
const entries=[];
for(const job of jobs){
 const original=fs.readFileSync(path.join(archive,job.slug+'.md'),'utf8');
 fs.writeFileSync(path.join(archive,job.slug+'.md'),original);
 const target=path.join(output,job.slug);fs.mkdirSync(target,{recursive:true});

 // Feishu escapes punctuation even in standalone URLs. Restore those URLs before linkification.
 let source=original.replace(/^https?:\/\/[^\r\n]+$/gm,s=>s.replace(/\\([\W_])/g,'$1'));
 // Empty bold spans and whitespace inside bold delimiters are export artifacts.
 source=source.replace(/\*{4}/g,'');
 const tokens=md.parse(source,{}),headingIds=new Map();
 let title='',counter=0;
 for(let i=0;i<tokens.length;i++)if(tokens[i].type==='heading_open'){
  const text=cleanText(tokens[i+1].children||[]);
  if(!text){tokens.splice(i,3);i--;continue;}
  if(!title){title=text;tokens.splice(i,3);i--;continue;}
  const level=Math.min(6,Number(tokens[i].tag.slice(1))+1);tokens[i].tag=tokens[i+2].tag='h'+level;
  const id='section-'+(++counter);tokens[i].attrSet('id',id);if(!headingIds.has(text))headingIds.set(text,id);
 }
 const rewrite=href=>{
  if(href.startsWith('https://tcnyx5kk9u7c.feishu.cn/')){
   const u=new URL(href),key=u.pathname.split('/').pop();
   if(key==='FwE7w2rONiH1RrkPrmHcXLnVnDg'){
    const heading=crossSections[u.hash.replace('#share-','')],id=headingIds.get(heading);
    if(job.slug!=='serial-protocol'||!id)throw Error('Unmapped chapter: '+href);
    return '#'+id;
   }
   const slug=sourceMap.get(key);if(!slug)throw Error('Unmapped document: '+href);
   return '/guides.html?doc='+slug;
  }
  if(/^(https?:|mailto:|#)/.test(href))return href;
  const relative=decodeURIComponent(href);
  if(!fs.existsSync(path.join(target,relative)))throw Error('Missing attachment: '+job.slug+'/'+relative);
  return '/guides/'+job.slug+'/'+href;
 };
 for(const token of tokens)for(const child of token.children||[]){
  if(child.type==='image'){child.attrSet('src',rewrite(child.attrGet('src')));child.attrSet('loading','lazy');child.attrSet('decoding','async');const size=dimensions.find(d=>d.src===child.attrGet('src'));if(!size)throw Error('Image dimensions missing');child.attrSet('width',String(size.width));child.attrSet('height',String(size.height));}
  if(child.type==='link_open'){
   const href=rewrite(child.attrGet('href'));child.attrSet('href',href);
   if(href.startsWith('http')){child.attrSet('target','_blank');child.attrSet('rel','noopener noreferrer');}
   else if(href.startsWith('/guides/'))child.attrSet('download','');
  }
 }
 let html=md.renderer.render(tokens,md.options,{});
 if(job.slug==='selection'){
  if(tables.length!==3)throw Error('Expected all three parameter tables');
  const headings=[...html.matchAll(/<h3 id="([^"]+)">([\s\S]*?)<\/h3>/g)];
  if(headings.length!==3)throw Error('Selection heading mismatch');
  for(let i=2;i>=0;i--){
   const table='<table><caption>'+escape(headings[i][2].replace(/<[^>]+>/g,''))+'</caption><tbody>'+tables[i].rows.map(row=>'<tr>'+row.map((cell,col)=>{const tag=col===row.length-1?'td':'th';return '<'+tag+(cell.rowspan>1?' rowspan="'+cell.rowspan+'"':'')+(cell.colspan>1?' colspan="'+cell.colspan+'"':'')+(tag==='th'?' scope="'+(cell.rowspan>1?'rowgroup':'row')+'"':'')+'>'+escape(cell.text).replace(/\r?\n/g,'<br>')+'</'+tag+'>';}).join('')+'</tr>').join('')+'</tbody></table>';
   const at=i===2?html.length:html.indexOf(headings[i+1][0]);html=html.slice(0,at)+table+html.slice(at);
  }
 }
 html=html.replace(/<table>/g,'<div class="table-scroll" tabindex="0" role="region" aria-label="数据表格"><table>').replace(/<\/table>/g,'</table></div>');
 html=html.replace(/<a href="(\/guides\/[^"?]+\.pdf)" download="">([\s\S]*?)<\/a>/g,(_,asset,label)=>'<a href="/vendor/pdfjs-6.4.299-legacy/web/viewer.html?file='+encodeURIComponent(asset)+'#zoom=page-fit">'+label+'</a><a class="attachment-download" href="'+asset+'" download>下载 PDF</a>');
 fs.writeFileSync(path.join(target,'content.html'),html);
 const text=tokens.filter(t=>t.type==='inline'||t.type==='fence'||t.type==='code_block').map(t=>t.children?cleanText(t.children):t.content).join(' ')+(job.slug==='selection'?tables.map(t=>t.text).join(' '):'');
 entries.push({slug:job.slug,label:job.label,category:job.category,title,text:text.replace(/\s+/g,' ')});
 console.log(job.slug,'headings',counter,'bytes',Buffer.byteLength(html));
}
fs.writeFileSync(path.join(output,'catalog.json'),JSON.stringify(entries));
fs.writeFileSync(path.join(archive,'sources.json'),JSON.stringify(jobs.map(j=>({...j,source:'https://tcnyx5kk9u7c.feishu.cn/'+j.source})),null,2));


