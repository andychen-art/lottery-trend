// 双色球数据更新代理服务（本地）
// 作用：转发中福彩官网开奖接口，并添加 CORS 头，让 HTML 软件能直接 fetch
// 启动：node ssq_update_server.js   （端口 8701）
const http = require('http');
const path = require('path');
const fs = require('fs');
const https = require('https');
const PORT = 8701;
const CWL_API = 'https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice';
const WUBAI_SSQ = 'https://datachart.500.com/ssq/history/newinc/history.php?start=03001&end=26999';
const WUBAI_QLC = 'https://datachart.500.com/qlc/history/newinc/history.php?start=07001&end=26999';
const LECAI_DLT = 'https://data.17500.cn/dlt_asc.txt';
const LECAI_LIST_API = 'https://www.17500.cn/api/kaijiang/getlist';
const LECAI_WINLIST = 'https://m.17500.cn/api/m/win/list';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36';

function get(url, headers) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    mod.get(url, { headers: headers || { 'User-Agent': UA } }, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => resolve({ status: res.statusCode, body }));
    }).on('error', reject);
  });
}

function post(url, form, headers) {
  return new Promise((resolve, reject) => {
    const data = new URLSearchParams(form).toString();
    const req = https.request(url, {
      method: 'POST',
      headers: Object.assign({
        'User-Agent': UA,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(data)
      }, headers || {})
    }, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => resolve({ status: res.statusCode, body }));
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

// 解析 500.com history.php 全量历史表（ssq: 6红+1蓝；qlc: 7基本+1特别）
// 行结构: <tr class="t_tr1"><!--<td>2</td>--><td>26103</td><td class="t_cfont2">04</td>...<td class="t_cfont4">15</td>...
function parseWubaiRows(html, nred) {
  const rows = [];
  (html.match(/<tr class="t_tr1">[\s\S]*?<\/tr>/g) || []).forEach(function (tr) {
    tr = tr.replace(/<!--[\s\S]*?-->/g, ''); // 先移除行内注释（注释内也有 td）
    const tds = (tr.match(/<td[^>]*>[\s\S]*?<\/td>/g) || []).map(function (td) {
      return td.replace(/<[^>]+>/g, '').replace(/\s+/g, '').trim();
    }).filter(function (x) { return x !== ''; });
    if (tds.length < nred + 2) return;
    if (!/^\d{5}$/.test(tds[0])) return;
    const red = tds.slice(1, 1 + nred).map(Number);
    const blue = /^\d+$/.test(tds[1 + nred] || '') ? tds[1 + nred] : '';
    if (red.some(function (x) { return isNaN(x) || x < 1 || x > 35; })) return;
    rows.push({ issue: '20' + tds[0], red: red, blue: blue });
  });
  rows.sort(function (a, b) { return a.issue < b.issue ? -1 : 1; });
  return rows;
}

// 解析 500.com qlc 全量历史表（结构与 ssq 不同：号码挤在一格，特别号在 span 内）
// 行结构: <td class="t_tr1">26103</td><td class="cfont2">01 08 20 21 23 26 30<span class="cBlue"> 29</span></td>...
function parseWubaiQlc(html) {
  const rows = [];
  (html.match(/<tr class="t_tr1">[\s\S]*?<\/tr>/g) || []).forEach(function (tr) {
    tr = tr.replace(/<!--[\s\S]*?-->/g, '');
    const issueM = tr.match(/<td[^>]*>(\d{5})<\/td>/);
    const numsM = tr.match(/<td class="cfont2">([\s\S]*?)<\/td>/);
    if (!issueM || !numsM) return;
    const nums = numsM[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().split(' ').map(Number);
    if (nums.length < 7) return;
    const red = nums.slice(0, 7);
    const blue = nums.length >= 8 ? String(nums[7]) : '';
    if (red.some(function (x) { return isNaN(x) || x < 1 || x > 30; })) return;
    rows.push({ issue: '20' + issueM[1], red: red, blue: blue });
  });
  rows.sort(function (a, b) { return a.issue < b.issue ? -1 : 1; });
  return rows;
}

// 解析乐彩网 dlt_asc.txt：期号 日期 前5 后2 ...
function parseDlt(text) {
  const rows = [];
  text.split(/\n/).forEach(line => {
    const p = line.trim().split(/\s+/);
    if (p.length < 8) return;
    if (!/^\d{5}$/.test(p[0])) return; // 期号如 07001
    const red = p.slice(2, 7).map(Number);
    const blue = p.slice(7, 9).map(Number);
    if (red.some(isNaN) || blue.some(isNaN)) return;
    rows.push({ issue: '20' + p[0], red: red, blue: blue });
  });
  return rows;
}

// 解析乐彩网 getlist 返回的 HTML 表格 → [{issue, red:[5个号]}]
function parseLecaiList(html) {
  const rows = [];
  (html.match(/<tr>[\s\S]*?<\/tr>/g) || []).forEach(tr => {
    if (/<th/i.test(tr)) return; // 表头
    const tds = (tr.match(/<td[^>]*>([\s\S]*?)<\/td>/g) || []).map(td => td.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim());
    if (tds.length < 3) return;
    const issue = tds[0];
    if (!/^\d{7}$/.test(issue)) return;
    const nums = tds[2].split(/\s+/).map(Number).filter(x => !isNaN(x));
    if (nums.length < 5) return;
    rows.push({ issue: issue, red: nums.slice(0, 5) });
  });
  return rows;
}

// 解析乐彩网手机版 win/list 返回（每页 20 期，期号降序）→ [{issue, red:[5个号]}]
function parseWinList(html) {
  const rows = [];
  const re = /data-name="issue" data-v="(\d{7})"[\s\S]*?data-copy="true"[^>]*data-v="([\d ]+)"/g;
  let m;
  while ((m = re.exec(html))) {
    const nums = m[2].trim().split(/\s+/).map(Number);
    if (nums.length >= 5) rows.push({ issue: m[1], red: nums.slice(0, 5) });
  }
  return rows;
}

// 河南福彩22选5：本地全量缓存（cache/hen22x5_full.json）+ 手机版接口增量翻页补最新
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function hnCachePath() { return path.join(__dirname, 'cache', 'hen22x5_full.json'); }
function hnCacheLoad() {
  try {
    const c = JSON.parse(fs.readFileSync(hnCachePath(), 'utf8'));
    if (c && Array.isArray(c.rows) && c.rows.length > 100) return c.rows;
  } catch (e) {}
  return null;
}
function hnCacheSave(rows) {
  try {
    const dir = path.join(__dirname, 'cache');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir);
    fs.writeFileSync(hnCachePath(), JSON.stringify({ t: Date.now(), rows: rows }));
  } catch (e) {}
}
async function fetchHen22x5(count) {
  const target = Math.min(parseInt(count) || 500, 5000);
  const map = {};
  const cached = hnCacheLoad();
  if (cached) cached.forEach(function (row) { map[row.issue] = row; });
  // 1) getlist：最近几期 + 拿到最新期号作游标
  let cursor = null;
  let latestIssue = null;
  for (let attempt = 0; attempt < 3 && !cursor; attempt++) {
    try {
      const r = await post(LECAI_LIST_API, { lotid: 'hen22x5', limit: '300', year: '' }, { Referer: 'https://www.17500.cn/kj/list-hen22x5.html' });
      if (r.status !== 200) throw new Error('upstream ' + r.status);
      const rows = parseLecaiList(r.body);
      if (rows.length > 0) {
        rows.forEach(function (row) { map[row.issue] = row; });
        latestIssue = rows[0].issue; // 最新一期
        cursor = rows[rows.length - 1].issue; // 页内最旧一期 → 往前翻
        break;
      }
    } catch (e) { /* 重试 */ }
    await sleep(2000);
  }
  if (!cursor) {
    const list = Object.values(map).sort(function (a, b) { return a.issue.localeCompare(b.issue); });
    if (list.length > 0) return list.slice(-target).map(function (row) { return { code: row.issue, red: row.red.join(','), blue: '' }; });
    throw new Error('hen22x5 上游无数据');
  }
  // 2) 手机版接口往前翻页：翻到「本地缓存已覆盖」或「够数」或「到底」为止
  let guard = 0;
  let needPages = cached ? 400 : Math.ceil(target / 20);
  while (cursor && Object.keys(map).length < target && guard < needPages) {
    guard++;
    if (cached && map[cursor]) break; // 已覆盖到缓存范围 → 增量完成
    try {
      const r = await post(LECAI_WINLIST + '/hen22x5/' + cursor, {}, { Referer: 'https://m.17500.cn/kj-m/list-hen22x5.html' });
      if (r.status !== 200) { await sleep(2500); continue; }
      const rows = parseWinList(r.body);
      if (rows.length === 0) break; // 到底了
      rows.forEach(function (row) { map[row.issue] = row; });
      cursor = rows[rows.length - 1].issue; // 页内最旧一期 → 继续往前
    } catch (e) { await sleep(2500); }
    await sleep(1200); // 风控间隔
  }
  const list = Object.values(map).sort(function (a, b) { return a.issue.localeCompare(b.issue); }).slice(-target);
  hnCacheSave(list);
  return list.map(function (row) { return { code: row.issue, red: row.red.join(','), blue: '' }; });
}

// 内存 + 磁盘缓存（各玩法 TTL 不同；避免每次打开网页都慢速抓取）
const DATA_CACHE = {};
const CACHE_TTL = { ssq: 600000, qlc: 600000, dlt: 600000, hen22x5: 3600000 };
const DISK_TTL = { ssq: 1800000, qlc: 1800000, dlt: 1800000, hen22x5: 21600000 }; // 磁盘缓存有效期（hen22x5 6小时）
function diskCachePath(game) { return path.join(__dirname, 'cache', game + '_data.json'); }
(function preloadDiskCache() {
  ['ssq', 'qlc', 'dlt', 'hen22x5'].forEach(function (game) {
    try {
      const c = JSON.parse(fs.readFileSync(diskCachePath(game), 'utf8'));
      if (c && c.data && Date.now() - c.t < DISK_TTL[game]) DATA_CACHE[game] = { t: c.t, data: c.data };
    } catch (e) {}
  });
})();
function saveDiskCache(game) {
  try {
    const dir = path.join(__dirname, 'cache');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir);
    fs.writeFileSync(diskCachePath(game), JSON.stringify({ t: Date.now(), data: DATA_CACHE[game].data }));
  } catch (e) {}
}

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  const u = new URL(req.url, 'http://127.0.0.1:' + PORT);
  if (u.pathname === '/ping') {
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('ok');
    return;
  }
  if (u.pathname === '/data') {
    const game = u.searchParams.get('game') || 'ssq';
    const issueCount = u.searchParams.get('issueCount') || '100';
    const ck = game;
    if (DATA_CACHE[ck] && Date.now() - DATA_CACHE[ck].t < (CACHE_TTL[game] || 60000)) {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=UTF-8' });
      res.end(DATA_CACHE[ck].data);
      return;
    }
    (async () => {
      let out;
      if (game === 'ssq' || game === 'qlc') {
        // 500.com 全量历史（一次请求拿全部期数，历史不清除）；失败时回退中福彩官网
        const wb = await get(game === 'ssq' ? WUBAI_SSQ : WUBAI_QLC, {
          'User-Agent': UA, 'Referer': 'https://datachart.500.com/'
        });
        if (wb.status === 200) {
          const rows = game === 'ssq' ? parseWubaiRows(wb.body, 6) : parseWubaiQlc(wb.body);
          if (rows.length > 100) {
            out = JSON.stringify({
              state: 0,
              result: rows.map(function (row) { return { code: row.issue, red: row.red.join(','), blue: row.blue }; })
            });
          }
        }
        if (!out) {
          const r = await get(CWL_API + '?name=' + game + '&issueCount=' + issueCount, {
            'User-Agent': UA, 'Referer': 'https://www.cwl.gov.cn/', 'Accept': 'application/json, text/plain, */*'
          });
          out = r.body;
        }
      } else if (game === 'dlt') {
        // 乐彩网大乐透全量数据文件（本地解析，取最后 N 期）
        const r = await get(LECAI_DLT, { 'User-Agent': UA });
        if (r.status !== 200) throw new Error('dlt upstream ' + r.status);
        const rows = parseDlt(r.body);
        const n = Math.min(parseInt(issueCount) || 100, rows.length);
        const list = rows.slice(-n).map(row => ({ code: row.issue, red: row.red.join(','), blue: row.blue.join(',') }));
        out = JSON.stringify({ state: 0, result: list });
      } else if (game === 'hen22x5') {
        // 河南福彩22选5：本地全量缓存 + 乐彩网增量翻页
        const list = await fetchHen22x5(issueCount);
        out = JSON.stringify({ state: 0, result: list });
      } else {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('unknown game: ' + game);
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json; charset=UTF-8' });
      res.end(out);
      DATA_CACHE[ck] = { t: Date.now(), data: out };
      saveDiskCache(ck);
    })().catch(e => {
      res.writeHead(502, { 'Content-Type': 'application/json; charset=UTF-8' });
      res.end(JSON.stringify({ state: 1, message: 'upstream error: ' + e.message }));
    });
    return;
  }
  // 静态文件服务：走势图 HTML（局域网访问）
  const staticRoot = __dirname;
  const decPath = decodeURIComponent(u.pathname);
  if (u.pathname === '/' || u.pathname === '/index.html') {
    const files = fs.readdirSync(staticRoot).filter(function(f){ return f.endsWith('.html'); });
    const links = files.map(function(f){ return '<a href="/' + encodeURIComponent(f) + '">' + f + '</a>'; }).join('<br>\n');
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>乐透走势图</title></head><body style="font-family:Microsoft YaHei;padding:24px;background:#f5f6fa"><h2 style="color:#d33">📊 走势图列表</h2><div style="line-height:2">' + links + '</div></body></html>');
    return;
  }
  const filePath = path.join(staticRoot, decPath);
  if (decPath.startsWith('/') && decPath.indexOf('..') < 0 && fs.existsSync(filePath) && filePath.indexOf(staticRoot) === 0) {
    const ct = filePath.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': ct });
    fs.createReadStream(filePath).pipe(res);
    return;
  }
  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('not found');
});

server.listen(PORT, '0.0.0.0', () => {
  console.log('✅ 乐透数据更新代理已启动: http://0.0.0.0:' + PORT + ' （局域网可访问）');
  console.log('   接口: /data?game=ssq|qlc|dlt|hen22x5&issueCount=N');
});
