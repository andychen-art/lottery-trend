// 用仓库里已有的 data/hen22x5.json 预热数据服务的本地缓存，
// 让云端只抓「新增的几期」，不必从零翻 25 页接口（否则会超时）
const fs = require('fs');
const path = require('path');

const ROOT = process.argv[2] || process.cwd();
const SRC = path.join(ROOT, 'data', 'hen22x5.json');
const DIR = path.join(ROOT, '_build', 'cache');
const OUT = path.join(DIR, 'hen22x5_full.json');

if (!fs.existsSync(SRC)) { console.log('无 data/hen22x5.json，跳过预热'); process.exit(0); }

const d = JSON.parse(fs.readFileSync(SRC, 'utf8'));
const rows = (d.result || []).map((r) => ({
  issue: String(r.code),
  red: String(r.red).split(',').map((x) => Number(x))
})).filter((r) => r.issue && r.red.length >= 5 && r.red.every((n) => !isNaN(n)));

if (rows.length < 100) { console.log('现有数据仅 ' + rows.length + ' 期，跳过预热'); process.exit(0); }

fs.mkdirSync(DIR, { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ t: Date.now(), rows }), 'utf8');
console.log('已预热 hen22x5 缓存: ' + rows.length + ' 期（' + rows[0].issue + ' ~ ' + rows[rows.length - 1].issue + '）');
console.log('缓存文件: ' + OUT + '  ' + (fs.statSync(OUT).size / 1024).toFixed(1) + ' KB');
