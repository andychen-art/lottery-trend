// 云端收尾：给页面补 canonical + 合规免责提示，并重建 sitemap/robots（就地修改，幂等）
// 用法: node _build/finalize.js [仓库根目录]
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(process.argv[2] || process.cwd());
const OWNER = 'andychen-art';
const REPO = 'lottery-trend';
const BASE = 'https://' + OWNER + '.github.io/' + REPO;

const PAGES = ['index.html', 'ssq-trend.html', 'qlc-trend.html', 'dlt-trend.html',
               'hen22x5-trend.html', 'ssq-tail-metric.html', 'about.html'];

let changed = 0;

for (const f of PAGES) {
  const p = path.join(ROOT, f);
  if (!fs.existsSync(p)) { console.log('  ⚠️ 缺文件: ' + f); continue; }
  let html = fs.readFileSync(p, 'utf8');
  const before = html;

  // 1) canonical
  const pageUrl = f === 'index.html' ? BASE + '/' : BASE + '/' + f;
  if (!/rel=["']canonical["']/i.test(html)) {
    const tag = '<link rel="canonical" href="' + pageUrl + '">\n';
    if (/<\/title>/i.test(html)) html = html.replace(/<\/title>/i, '</title>\n' + tag);
    else if (/<head[^>]*>/i.test(html)) html = html.replace(/<head[^>]*>/i, (m) => m + '\n' + tag);
  } else {
    // 已存在但地址不对（比如旧的 COS 域名）→ 纠正
    html = html.replace(/<link\s+rel=["']canonical["']\s+href=["'][^"']*["']\s*\/?>/i,
                        '<link rel="canonical" href="' + pageUrl + '">');
  }

  // 2) 合规免责提示
  if (html.indexOf('id="compliance-footer"') === -1 && html.indexOf('理性购彩') === -1) {
    const footer = [
      '<div id="compliance-footer" style="max-width:1200px;margin:28px auto 20px;padding:14px 18px;background:#fff8e6;border:1px solid #f0d48a;border-radius:10px;font-size:13px;line-height:1.9;color:#8a6d3b;">',
      '  <div style="font-weight:600;margin-bottom:4px;">温馨提示</div>',
      '  本站所有数据与统计图表仅供参考，<b>不构成任何投注建议</b>。彩票开奖为独立随机事件，请理性购彩，量力而行。未成年人不得购彩。',
      '  <div style="margin-top:8px;font-size:12px;color:#9a7f4f;">数据来源：公开开奖数据整理 · <a href="' + BASE + '/" style="color:#9a7f4f;">首页</a> · <a href="' + BASE + '/about.html" style="color:#9a7f4f;">关于本站与免责声明</a></div>',
      '</div>'
    ].join('\n');
    if (/<\/body>/i.test(html)) html = html.replace(/<\/body>/i, footer + '\n</body>');
    else html += '\n' + footer;
  }

  // 3) 站内绝对路径 /data/ → 相对 data/（子路径部署必须）
  html = html.replace(/"\/data\/([a-z0-9_]+\.json)"/g, '"data/$1"');

  if (html !== before) {
    fs.writeFileSync(p, html, 'utf8');
    changed++;
    console.log('  ✏️  ' + f);
  } else {
    console.log('  ✓  ' + f + '（无需修改）');
  }
}

// sitemap / robots
const today = new Date().toISOString().slice(0, 10);
const urls = ['/', '/ssq-trend.html', '/qlc-trend.html', '/dlt-trend.html',
              '/hen22x5-trend.html', '/ssq-tail-metric.html', '/about.html'];
const sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
  + urls.map((u) => '  <url>\n    <loc>' + BASE + u + '</loc>\n    <lastmod>' + today + '</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>' + (u === '/' ? '1.0' : '0.8') + '</priority>\n  </url>').join('\n')
  + '\n</urlset>\n';
fs.writeFileSync(path.join(ROOT, 'sitemap.xml'), sitemap, 'utf8');
fs.writeFileSync(path.join(ROOT, 'robots.txt'), 'User-agent: *\nAllow: /\n\nSitemap: ' + BASE + '/sitemap.xml\n', 'utf8');
fs.writeFileSync(path.join(ROOT, '.nojekyll'), '', 'utf8');
console.log('  ✓  sitemap.xml / robots.txt / .nojekyll（lastmod ' + today + '）');

// 冒烟检查
const idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const trend = fs.readFileSync(path.join(ROOT, 'ssq-trend.html'), 'utf8');
const okDoctype = /^<!DOCTYPE html>/i.test(idx.trim());
const okLinks = PAGES.slice(1).filter((f) => idx.includes(f)).length;
const okData = /["'](?:\.\/)?data\/[a-z0-9_]+\.json["']/.test(trend);
const okNoAbsData = !/["']\/data\//.test(trend);
console.log('');
console.log('  冒烟检查:');
console.log('    index DOCTYPE      : ' + (okDoctype ? 'OK' : 'FAIL'));
console.log('    index 站内链接     : ' + okLinks + ' 个');
console.log('    ssq-trend 取数相对路径: ' + (okData ? 'OK' : 'FAIL'));
console.log('    ssq-trend 无绝对/data/: ' + (okNoAbsData ? 'OK' : 'FAIL'));
console.log('  改动页面数: ' + changed + '/' + PAGES.length);

if (!okDoctype || !okData || !okNoAbsData) {
  console.log('  ❌ 页面结构检查未通过');
  process.exit(1);
}
