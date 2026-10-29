# -*- coding: utf-8 -*-
"""站点刷新：统一生成线上站点的数据与尾数页（供 lottery_update.py 每日调用）
做的事：
  1) 从本地 8701 实时服务取 4 个彩种全量数据 → SITE/data/*.json（规范化 blue：单个数字/数组/空）
  2) 重新生成线上版尾数页（300 期，约 2.7MB）→ SITE/ssq-tail-metric.html
     （生成后自动补：SEO meta + 本地打开防呆提示）
  3) 写 hen22x5_full.json 底座（供 worker.js 等备用）
用法：python refresh_site.py
"""
import json, os, sys, io, urllib.request, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = os.environ.get("LOTTERY_BASE") or r"C:\Users\pc\.openclaw\workspace"
SITE = os.environ.get("LOTTERY_SITE") or os.path.join(BASE, "money-plan", "lottery-site")
DATA = os.path.join(SITE, "data")
TOOLS = os.environ.get("LOTTERY_TOOLS") or os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
BASE_URL = "https://ottery-trend-6688-1518943552.cos-website.ap-guangzhou.myqcloud.com"
SERVICE = "http://127.0.0.1:8701/data?game=%s&issueCount=9999"
GAMES = ["ssq", "qlc", "dlt", "hen22x5"]

os.makedirs(DATA, exist_ok=True)


def norm_blue(b):
    if b is None or b == "":
        return ""
    if isinstance(b, (int, float)):
        return int(b)
    s = str(b).strip()
    if s in ("", "[]"):
        return ""
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [int(float(x)) for x in inner.split(",")] if inner else ""
    if "," in s:
        return [int(float(x)) for x in s.split(",")]
    try:
        return int(float(s))
    except ValueError:
        return s


def fetch(game):
    with urllib.request.urlopen(SERVICE % game, timeout=90) as r:
        j = json.loads(r.read().decode("utf-8"))
    rows = []
    for d in j.get("result", []):
        red = d.get("red")
        if isinstance(red, str):
            red = [int(x) for x in red.replace(" ", "").split(",") if x != ""]
        else:
            red = [int(x) for x in red]
        if len(red) < 4:
            continue
        rows.append({"code": str(d.get("code") or d.get("issue")), "red": sorted(red), "blue": norm_blue(d.get("blue"))})
    rows.sort(key=lambda x: x["code"])
    return rows


def inject_page(html):
    """给生成的尾数页补 SEO meta 与本地打开提示"""
    guard = ('\n<script>(function(){try{if(location.protocol!=="file:"){return;}'
             'var b=document.createElement("div");'
             'b.style.cssText="position:fixed;left:0;right:0;top:0;z-index:2147483000;background:#c62828;color:#fff;padding:10px 14px;font:13px/1.7 -apple-system,\\"Microsoft YaHei\\",sans-serif";'
             'b.innerHTML="⚠️ 你打开的是<strong>本地文件</strong>，站内链接会失效。请用线上地址：<br><a href=\\"' + BASE_URL + '/\\" style=\\"color:#ffe082\\">' + BASE_URL + '/</a>";'
             'document.addEventListener("DOMContentLoaded",function(){document.body.insertBefore(b,document.body.firstChild);});'
             '}catch(e){}})();</script>\n')
    if "ONLINE-GUARD" not in html:
        m = None
        for tag in ("<body>", "<body "):
            i = html.find(tag)
            if i >= 0:
                if tag == "<body>":
                    html = html[:i + 6] + guard + html[i + 6:]
                else:
                    j = html.find(">", i)
                    html = html[:j + 1] + guard + html[j + 1:]
                m = True
                break
    title = "双色球尾数指标统计 - 码差/码合三码和专项指标"
    desc = "双色球尾数指标统计：码差三码和、码合三码和专项指标，位组数值落列遗漏走势、012路、升平降、遗漏个位，含折线连线与近300期速览。"
    import re
    html = re.sub(r"<title>[\s\S]*?</title>", "<title>" + title + "</title>", html, count=1)
    if 'name="description"' not in html:
        html = html.replace('<meta charset="UTF-8">',
                            '<meta charset="UTF-8">\n<meta name="description" content="' + desc + '">\n'
                            '<meta name="keywords" content="双色球尾数,码差三码和,码合三码和,双色球指标统计">', 1)
    return html


def main():
    print("=== 1. 拉取实时数据 ===")
    all_rows = {}
    for g in GAMES:
        rows = fetch(g)
        all_rows[g] = rows
        out = {"state": 0, "result": [{"code": r["code"], "red": ",".join(str(x) for x in r["red"]), "blue": r["blue"]} for r in rows]}
        with open(os.path.join(DATA, g + ".json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        print("  %-8s %5d 期  %s ~ %s" % (g, len(rows), rows[0]["code"], rows[-1]["code"]))
        if g == "hen22x5" and not os.environ.get("LOTTERY_SKIP_HENFULL"):
            with open(os.path.join(SITE, "hen22x5_full.json"), "w", encoding="utf-8") as f:
                json.dump({"rows": [{"issue": r["code"], "red": r["red"]} for r in rows]}, f, ensure_ascii=False)

    # 云端：给尾数页生成器准备 [期号(5位), [红球...], 蓝球] 行数据
    rows_path = os.environ.get("LOTTERY_SSQ_ROWS")
    if rows_path:
        ssq_rows = []
        for r in all_rows.get("ssq", []):
            code = str(r["code"])
            short = code[2:] if len(code) == 7 else code
            ssq_rows.append([int(short) if short.isdigit() else short, r["red"], r["blue"]])
        with open(rows_path, "w", encoding="utf-8") as f:
            json.dump(ssq_rows, f, ensure_ascii=False)
        os.environ["LOTTERY_SSQ_DATA"] = rows_path
        print("  尾数页输入已生成: %s（%d 期）" % (rows_path, len(ssq_rows)))

    print("=== 2. 重新生成线上版尾数页（300期）===")
    tail = os.path.join(SITE, "ssq-tail-metric.html")
    r = subprocess.run([PY, os.path.join(TOOLS, "build_tail_metric_table.py"), "300", tail],
                       cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print("  build exit=%d %s" % (r.returncode, (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""))
    if os.path.exists(tail):
        html = open(tail, encoding="utf-8").read()
        html = inject_page(html)
        open(tail, "w", encoding="utf-8").write(html)
        print("  尾数页 %.2f MB（已补 SEO + 防呆提示）" % (os.path.getsize(tail) / 1024.0 / 1024.0))
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
