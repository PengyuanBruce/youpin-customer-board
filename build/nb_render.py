# -*- coding: utf-8 -*-
"""新大屏B 的 HTML 渲染（自包含，无外部依赖）。"""

import json

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>优爆品 & 市场热卖品 · 拍档数据大屏</title>
<style>
:root{
  --bg:#0a1220; --bg2:#0e1a2c; --panel:#111e33; --panel2:#16263d;
  --line:#22344f; --line2:#2c4463;
  --ink:#e8eef8; --ink2:#a9bcd6; --ink3:#6f86a4;
  --gold:#d9b06a; --cyan:#5ad2e6; --green:#3ecf8e; --red:#f2647a; --violet:#9a8cf0;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:
    radial-gradient(1200px 600px at 12% -10%, #16304e 0%, transparent 60%),
    radial-gradient(900px 500px at 100% 0%, #1b2547 0%, transparent 55%),
    var(--bg);
  color:var(--ink);
  font-family:"HarmonyOS Sans SC","PingFang SC","Microsoft YaHei",sans-serif;
  font-size:14px; line-height:1.55;
  -webkit-font-smoothing:antialiased;
  padding-bottom:60px;
}
.wrap{max-width:1280px;margin:0 auto;padding:0 20px}
header{padding:34px 0 18px}
.eyebrow{letter-spacing:.32em;font-size:11px;color:var(--gold);text-transform:uppercase}
h1{
  font-family:"Source Han Serif SC","Songti SC",serif;
  font-size:34px;font-weight:600;margin:8px 0 6px;letter-spacing:.02em;
}
h1 span{color:var(--gold)}
.sub{color:var(--ink2);font-size:13px}
.meta{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:14px;font-size:12px;color:var(--ink3)}
.meta b{color:var(--ink2);font-weight:500}
nav{position:sticky;top:0;z-index:20;background:rgba(10,18,32,.92);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line);margin:18px 0 6px}
nav .wrap{display:flex;gap:6px;overflow-x:auto;padding:0 20px}
nav a{color:var(--ink2);text-decoration:none;font-size:13px;padding:12px 14px;white-space:nowrap;
  border-bottom:2px solid transparent;transition:.18s}
nav a:hover{color:var(--ink);border-bottom-color:var(--line2)}
nav a.on{color:var(--gold);border-bottom-color:var(--gold)}
section{margin:34px 0 0;scroll-margin-top:56px}
.sechead{display:flex;align-items:flex-end;gap:14px;flex-wrap:wrap;margin-bottom:12px}
.secno{font-family:"Source Han Serif SC","Songti SC",serif;font-size:30px;color:var(--gold);line-height:1}
.sectitle{font-size:19px;font-weight:600;letter-spacing:.02em}
.secsub{font-size:12px;color:var(--ink3);margin-left:auto}
.card{background:linear-gradient(180deg,var(--panel) 0%,var(--bg2) 100%);border:1px solid var(--line);
  border-radius:12px;overflow:hidden;box-shadow:0 10px 30px -18px #000}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;min-width:720px}
th,td{padding:10px 12px;text-align:right;white-space:nowrap;font-size:13.5px}
th{position:sticky;top:0;background:#16273f;color:var(--ink2);font-weight:500;font-size:12px;
  letter-spacing:.06em;border-bottom:1px solid var(--line2);z-index:2}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--panel);z-index:3}
th:first-child{background:#16273f;z-index:4}
th.l,td.l{text-align:left}
tbody tr{border-bottom:1px solid #1a2a42}
tbody tr:nth-child(even) td{background:#101c2e}
tbody tr:nth-child(even) td:first-child{background:#101c2e}
tbody tr:hover td{background:#182a44}
tbody tr:hover td:first-child{background:#182a44}
.team{color:var(--ink3);font-size:12px}
.name{font-weight:500}
.dim{color:#43597a}
.num{letter-spacing:.01em}
.pct{display:inline-flex;align-items:center;gap:8px;justify-content:flex-end}
.bar{width:56px;height:5px;border-radius:3px;background:#1e2f47;overflow:hidden}
.bar i{display:block;height:100%;border-radius:3px}
.up{color:var(--green)} .down{color:var(--red)} .flat{color:var(--ink3)}
.roll{background:#0f1b2d}
.roll td{background:#0f1b2d !important;font-weight:600;border-top:1px solid var(--line2)}
.roll td:first-child{background:#0f1b2d !important}
.cap{font-size:12px;color:var(--ink3);padding:10px 14px;border-top:1px solid var(--line);background:#0d1728}
.split{height:8px}
footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--line);color:var(--ink3);font-size:12px;
  display:flex;flex-wrap:wrap;gap:6px 22px}
.warn{color:var(--gold)}
@media (max-width:640px){
  h1{font-size:24px}
  .wrap{padding:0 12px}
  nav .wrap{padding:6px 12px;flex-wrap:wrap;overflow:visible;row-gap:2px}
  nav a{padding:7px 9px;font-size:12px}
  th,td{padding:9px 10px;font-size:12.5px}
  .bar{width:38px}
  .secsub{width:100%;margin-left:0}
}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">PARTNER DATA BOARD</div>
    <h1>优爆品 &amp; 市场热卖品<span> · </span>拍档大屏</h1>
    <div class="sub">四个板块 = 优爆品/市场热卖品 × 拍档销售/拍档客服，名单与口径按业务表</div>
    <div class="meta" id="meta"></div>
  </header>
</div>
<nav><div class="wrap" id="nav"></div></nav>
<div class="wrap" id="app"></div>
<div class="wrap"><footer id="foot"></footer></div>

<script id="board" type="application/json">__DATA__</script>
<script>
const B = JSON.parse(document.getElementById('board').textContent);

const fmtInt = v => (v===null||v===undefined) ? '<span class="dim">--</span>'
  : Math.round(v).toLocaleString('en-US');
const fmtPct = v => (v===null||v===undefined) ? '<span class="dim">--</span>' : v.toFixed(1)+'%';
const fmtDelta = v => (v===null||v===undefined) ? '<span class="dim">--</span>'
  : (v>0? '<span class="up">+'+Math.round(v)+'</span>'
    : v<0? '<span class="down">'+Math.round(v)+'</span>'
    : '<span class="flat">0</span>');
function bar(p){
  if(p===null||p===undefined) return '';
  const w=Math.max(0,Math.min(100,p));
  const c = p>=100? 'var(--green)' : p>=70? 'var(--cyan)' : p>=40? 'var(--gold)' : 'var(--red)';
  return `<span class="bar"><i style="width:${w}%;background:${c}"></i></span>`;
}
const dshort = d => d ? d.slice(5) : '--';

/* 顶部元信息 */
document.getElementById('meta').innerHTML = [
  `<span>更新时间 <b>${B.meta.updated_at}</b></span>`,
  `<span>优爆品数据日 <b>${B.meta.you_ds||'--'}</b></span>`,
  `<span>热卖品数据日 <b>${B.meta.hot_sales_ds||'--'} / ${B.meta.hot_kefu_ds||'--'}</b></span>`,
  `<span>${B.meta.week_rule}</span>`,
].join('');

/* 导航 */
document.getElementById('nav').innerHTML = B.sections
  .map(s=>`<a href="#${s.id}">${s.no} ${s.title}</a>`).join('');

function colHead(kind){
  if(kind==='you-sales') return ['团队','拍档销售','优爆品目标','优爆品数','优爆品季度完成率','优爆品推P数','优爆品周增长','优爆品推P周增长'];
  if(kind==='you-kefu') return ['拍档客服','季度目标','优爆品数','季度完成率','优爆品推P数','优爆品周增长','优爆品推P周增长'];
   // 2026-11-26 修：热卖两块的表头顺序原来与取值顺序（target/count/pct/p4p/week/p4p_week）
   //   不一致 → 推P 被挤到「市场热卖品周增长」列，真正的周增长被挤到「推P」列且恒为 --。
   //   统一成与优爆品两块一致：推P → 周增长 → 推P 周增长。
   if(kind==='hot-sales') return ['拍档销售','季度目标','热卖品数','季度目标完成率','市场热卖推P','市场热卖品周增长','推P 周增长'];
   return ['拍档客服','季度目标','热卖品数','季度目标完成率','热卖推P','市场热卖品周增长','推P 周增长'];
}

function rowCells(s, r, withTeam){
  const c0 = withTeam ? `<td class="l team">${r.team||''}</td>` : '';
  const nm = `<td class="l"><span class="name">${r.name}</span>${r.missing?' <span class="dim">未取到</span>':''}</td>`;
  return `<tr>${c0}${nm}
    <td class="num">${fmtInt(r.target)}</td>
    <td class="num">${fmtInt(r.count)}</td>
    <td class="num"><span class="pct">${fmtPct(r.pct)}${bar(r.pct)}</span></td>
    <td class="num">${fmtInt(r.p4p)}</td>
    <td class="num">${fmtDelta(r.week)}</td>
    <td class="num">${fmtDelta(r.p4p_week)}</td>
  </tr>`;
}

function rollCells(t){
  return `<tr class="roll"><td class="l">${t.team} · 合计</td>
    <td class="num">${fmtInt(t.target)}</td>
    <td class="num">${fmtInt(t.count)}</td>
    <td class="num"><span class="pct">${fmtPct(t.pct)}${bar(t.pct)}</span></td>
    <td class="num">${fmtInt(t.p4p)}</td>
    <td class="num">${fmtDelta(t.week)}</td>
    <td class="num">${fmtDelta(t.p4p_week)}</td></tr>`;
}

const app = document.getElementById('app');
app.innerHTML = B.sections.map(s=>{
  const withTeam = s.id==='you-sales';
  const heads = colHead(s.id);
  const win = s.week_window || {};
  const winTxt = win.status==='ok'
    ? `周增长窗口 ${dshort(win.mon)}~${dshort(win.end)}${win.short_by?`（末端退 ${win.short_by} 天）`:''}，基线 ${dshort(win.base)}`
    : `周增长：基线不足，暂显示 --（${win.status||'待累积'}）`;
  return `<section id="${s.id}">
    <div class="sechead">
      <div class="secno">${s.no}</div>
      <div class="sectitle">${s.title}</div>
      <div class="secsub">数据日 ${s.ds||'--'} · ${winTxt}</div>
    </div>
    <div class="card"><div class="scroll"><table>
      <thead><tr>${heads.map((h,i)=>`<th class="${i===0||(withTeam&&i===1)?'l':''}">${h}</th>`).join('')}</tr></thead>
      <tbody>${s.rows.map(r=>rowCells(s,r,withTeam)).join('')}
      ${(s.teams||[]).map(t=>`<tr><td colspan="${heads.length}" style="height:8px;border:0;background:transparent"></td></tr>`).join('')}
      ${(s.teams||[]).map(t=>rollCells(t,(withTeam?1:0))).join('')}
      </tbody></table></div>
      <div class="cap">${s.note}　数据日 ${s.ds||'--'}</div>
    </div>
  </section>`;
}).join('');

const w = B.meta.warnings || [];
document.getElementById('foot').innerHTML = [
  `<span>来源：${B.meta.sources.join(' · ')}</span>`,
  `<span>${B.meta.week_rule}</span>`,
  w.length? `<span class="warn">告警 ${w.length} 条：${w.slice(0,4).join('；')}${w.length>4?'…':''}</span>`:'',
  `<span>每日自动更新</span>`,
].join('');

/* 导航高亮 */
const links=[...document.querySelectorAll('nav a')];
const io=new IntersectionObserver(es=>{
  es.forEach(e=>{ if(e.isIntersecting){ links.forEach(a=>a.classList.toggle('on', a.getAttribute('href')==='#'+e.target.id)); }});
},{rootMargin:'-40% 0px -55% 0px'});
document.querySelectorAll('section').forEach(s=>io.observe(s));
</script>
</body>
</html>
"""


def render(board):
    data = json.dumps(board, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", data)
