# -*- coding: utf-8 -*-
"""
双色球近50期 尾数指标统计 → 单文件 HTML（重做版，覆盖旧版）

结构：顶部 4 个位组一级选项卡（123位 / 234位 / 345位 / 456位），点击切换；
每个位组面板内部再设 2 个二级选项卡——「码差三码和」「码合三码和」，点击二级选项卡只显示对应那一张表（另一张隐藏）。
每张表每行=一期（期号从小到大：最旧期在首行/顶部、最新期在末行/底部）：
  期号 | 数值落列·遗漏走势（只保留偶数列，单数列不显示）：
        · 对每个偶数值 v 从窗口最旧一期起逐期连续累计遗漏（初值 0）
        · 当期数值==v → 该格高亮显示该数值，计数归 0
        · 当期数值≠v → 计数+1，该格显示真实累计遗漏值
          = 距上次开出 v 的期数；窗口内尚未开出过 → 自窗口首期累计；1、2、3…递增，不取个位、不封顶
        · 两次开出之间、首次开出之前、最近一次开出之后均连续累计显示 → 整列无空白格
        · 折线：相邻两期的「数值落点」（高亮格）之间以醒目彩色折线相连（SVG 叠加在表格上、随表格横向滚动）
       | 数值属性 12 列分列（每个取值一列、落点标记）：大小（大/小）、单双（单/双）、质合（质/合）
         各 2 列 + 012路（0路/1路/2路）、升平降（升/平/降）各 3 列——每期在当期属性取值对应列落点（●高亮）；
         其中 012路、升平降 相邻两期落点之间以折线相连；大小/单双/质合 只落点、暂不加连线
       | 遗漏值个位落列：0~9 共 10 列；该期所开数值本次开出前连续累计遗漏 S（与数值落列同一连续累计口径）
         取个位 d，在 d 对应的列落点高亮（其余列本行留空）；相邻两期个位落点之间以折线相连
       | 个位属性 12 列分列（同数值属性规则）：大小/单双/质合 各 2 列、012路/升平降 各 3 列；
         012路、升平降 同样加相邻两期落点折线连线

指标口径：
- 码差三码和 = |a-b| + |a-c| + |b-c|，原值相加不取个位，恒为偶数，范围 0~18
- 码合三码和 = (a+b)%10 + (a+c)%10 + (b+c)%10，两两和取个位后相加，最后不取个位，恒为偶数，范围 0~26
- 属性（对数值 n）：大小 大=n≥5 / 小=n<5；单双 按奇偶（数值恒偶故恒显"双"）；
  质合 质=n∈{1,2,3,5,7,11,13,17,19,23}，合=其余；012路 n%3（0路/1路/2路 三列落点走势）；
  升平降=本期 vs 上期同列数值（升/平/降 三列落点走势），首期无上期可比 → 无落点
- 数值落列遗漏（连续累计，不取个位、不封顶）：对每个偶数值 v 从窗口最旧一期起逐期累计——
  当期数值==v → 本格高亮、计数归 0；≠v → 计数+1 并显示（=距上次开出 v 的期数；尚未开出过则自首期累计）；
  列内无空白格。
- 遗漏值个位 = 该期所开数值 v 本次开出前连续累计遗漏 S（=本次开出前已连续未出期数，与数值落列同一连续
  累计计数；上期同值开出 → S=0）取个位 %10，显示 0-9 并对该个位标注上述属性。
- 显示排序：期号从小到大（最旧期=首期在首行/顶部，最新期=末期在末行/底部）；各偶数列遗漏走势随行自上而下 1、2、3… 正序递增
- 期号展示：数据期号为 5 位数字（如 26054），展示与 title 一律补全为完整期号（2026054，加 "20" 前缀）
"""
import json
import os
import sys
import shutil
import datetime

BASE = os.environ.get("LOTTERY_BASE") or r"C:\Users\pc\.openclaw\workspace"
DATA = os.environ.get("LOTTERY_SSQ_DATA") or os.path.join(BASE, "lottery_data", "ssq.json")
OUT = os.path.join(BASE, "tools", "ssq", "双色球尾数指标统计.html")
DESKTOP = r"C:\Users\pc\Desktop\双色球尾数指标统计.html"

# 可选命令行参数：期数上限 + 输出路径（如 python build_tail_metric_table.py 100 out.html）
# 默认最近500期（打开快）；参数 all = 全量历史；参数数字 = 最近N期
_LIMIT = 500
_CUSTOM_OUT = None
if len(sys.argv) > 1:
    if sys.argv[1] == "all":
        _LIMIT = None
    elif sys.argv[1].isdigit():
        _LIMIT = int(sys.argv[1])
    if len(sys.argv) > 2:
        _CUSTOM_OUT = sys.argv[2]
if _CUSTOM_OUT:
    OUT = _CUSTOM_OUT

raw = json.load(open(DATA, encoding="utf-8"))
raw.sort(key=lambda r: r[0])
if _LIMIT and len(raw) > _LIMIT:
    raw = raw[-_LIMIT:]
N = len(raw)  # 不限制期数，使用全量历史数据


def fmt_issue(n):
    """数据期号为5位数字(如 26054) → 完整期号 2026054（加 '20' 前缀）"""
    s = str(n)
    return "20" + s if len(s) == 5 else s

# 位组定义: (名称, 红球升序下标[0..5], 位次说明)
GROUPS = [
    ("123位", [0, 1, 2], "红球第1/2/3位（升序第1~3个）"),
    ("234位", [1, 2, 3], "红球第2/3/4位（升序第2~4个）"),
    ("345位", [2, 3, 4], "红球第3/4/5位（升序第3~5个）"),
    ("456位", [3, 4, 5], "红球第4/5/6位（升序第4~6个）"),
]
# 指标定义: (key, 名称, 偶数列列表, css配色族, 公式, 说明)
METRICS = [
    ("cha", "码差三码和", list(range(0, 20, 2)),
     ("m-cha", "#e8871a", "#ffe0be", "#b3541e"),
     "|a−b| + |a−c| + |b−c|",
     "两两尾数差绝对值之和，原值相加、不取个位；恒为偶数，范围 0~18"),
    ("he", "码合三码和", list(range(0, 28, 2)),
     ("m-he", "#2d6cdf", "#d9e7ff", "#174ea6"),
     "(a+b)%10 + (a+c)%10 + (b+c)%10",
     "三个两两和分别取个位后再相加，最后不取个位；恒为偶数，范围 0~26"),
]

PRIME = {1, 2, 3, 5, 7, 11, 13, 17, 19, 23}  # 质


# ---- 逐期解析：期号升序存储（时间序） ----
rows = []
for rec in raw:
    issue = rec[0]
    reds = rec[1]["value"] if isinstance(rec[1], dict) else rec[1]
    rows.append({"issue": issue, "reds": reds})

# ---- 每 (位组, 指标) 的时间序列计算 ----
# data[(gi,mi)] = {cols, kind..., arr:[{v, tail_txt, parts_txt, miss, digit, spv, dspv}]}
data = {}
for gi, (gn, pos, gdesc) in enumerate(GROUPS):
    for mi, (mk, kindname, cols, colors, formula, note) in enumerate(METRICS):
        key = (gi, mi)
        vals = []
        details = []
        tailtxt = []
        for r in rows:
            tails = [r["reds"][p] % 10 for p in pos]
            a, b, c = tails
            if mk == "cha":
                p1, p2, p3 = abs(a - b), abs(a - c), abs(b - c)
                v = p1 + p2 + p3
                dtxt = "|%d−%d|+|%d−%d|+|%d−%d| = %d+%d+%d = %d" % (a, b, a, c, b, c, p1, p2, p3, v)
            else:
                s1, s2, s3 = (a + b) % 10, (a + c) % 10, (b + c) % 10
                v = s1 + s2 + s3
                dtxt = "(%d+%d)%%10+(%d+%d)%%10+(%d+%d)%%10 = %d+%d+%d = %d" % (a, b, a, c, b, c, s1, s2, s3, v)
            assert v % 2 == 0 and 0 <= v <= cols[-1], (issue, gn, kindname, v)
            vals.append(v)
            details.append(dtxt)
            tailtxt.append("%d %d %d" % (a, b, c))
        # 遗漏值个位口径：S = 该期数值 v 本次开出前连续累计遗漏（= 连续累计计数器在开出当格归0前已达到的值）
        last = {}
        miss = []
        for i, v in enumerate(vals):
            if v in last:
                miss.append(i - 1 - last[v])   # 距上次出现：中间隔 (i-1-L) 期；上期同值 → 0
            else:
                miss.append(i)                 # 窗口内首次出现：自首期累计到本期前
            last[v] = i
        digits = [m % 10 for m in miss]
        # 升平降（与上一期同列比较；时间序首期 i=0 记 None → "-"）
        spv = [None] * N
        for i in range(1, N):
            spv[i] = 1 if vals[i] > vals[i - 1] else (-1 if vals[i] < vals[i - 1] else 0)
        dspv = [None] * N
        for i in range(1, N):
            dspv[i] = 1 if digits[i] > digits[i - 1] else (-1 if digits[i] < digits[i - 1] else 0)
        arr = [{"v": vals[i], "tt": tailtxt[i], "dt": details[i],
                "miss": miss[i], "digit": digits[i], "spv": spv[i], "dspv": dspv[i]}
               for i in range(N)]
        data[key] = {"cols": cols, "colors": colors, "kindname": kindname,
                     "formula": formula, "note": note, "arr": arr}


# ================= 构建 HTML =================

def six_pair_cells(n, om, big_thr=5):
    """属性 12 列分列中的前 6 列（每个取值一列、落点标记）：大小（大/小）、单双（单/双）、质合（质/合）。
    每期在当期取值对应列落点 ●（td.mk + 取值色类），其余列留空；大小/单双/质合 只落点、相邻两期间暂不加连线"""
    pre = "个位" if om else "数值"
    sym = "d" if om else "n"
    big = n >= big_thr
    odd = n % 2 == 1
    prime = n in PRIME
    groups = [
        (0 if big else 1, "大小", ("大", "小"), ("big", "small"),
         ("「大」(%s=%d≥%d)" % (sym, n, big_thr)) if big else ("「小」(%s=%d<%d)" % (sym, n, big_thr))),
        (0 if odd else 1, "单双", ("单", "双"), ("odd", "even"),
         ("「单」(%s=%d为奇数)" % (sym, n)) if odd else ("「双」(%s=%d为偶数)" % (sym, n))),
        (0 if prime else 1, "质合", ("质", "合"), ("prime", "comp"),
         ("「质」(%s∈质数集{1,2,3,5,7,11,13,17,19,23})" % sym) if prime else ("「合」(%s为其余情况)" % sym)),
    ]
    out = []
    for matched, aname, names, clses, txt in groups:
        for k in range(2):
            if k == matched:
                out.append('<td class="mk r3 %s" title="%s属性·%s（分列：%s/%s 每个取值一列、显示实际取值）：'
                           '本行%s取值 = %s → 在「%s」列显示实际取值「%s」；'
                           '大小/单双/质合 只落点、相邻两期间暂不加连线">%s</td>'
                           % (clses[k], pre, aname, names[0], names[1], pre, txt, names[k], names[k], names[k]))
            else:
                out.append('<td class="r3" title="%s属性·%s（分列：%s/%s 每个取值一列）：'
                           '本行%s取值 = %s，落点在「%s」列，本列（%s）留空"></td>'
                           % (pre, aname, names[0], names[1], pre, txt, names[matched], names[k]))
    return out


def attr_h2_cells(om, big_thr=5):
    """属性 12 列分列的表头（大小/单双/质合 每取值一列 + 012路/升平降 各 3 列）"""
    pre = "个位" if om else "数值"
    sym = "d" if om else "n"
    cls = "at omat r3" if om else "at r3"
    cells = []
    for col, crit in (("大", "%s≥%d" % (sym, big_thr)), ("小", "%s<%d" % (sym, big_thr)),
                      ("单", "%s 为奇数" % sym), ("双", "%s 为偶数" % sym),
                      ("质", "%s∈质数集{1,2,3,5,7,11,13,17,19,23}" % sym),
                      ("合", "%s 为其余(合数)" % sym)):
        cells.append('<th class="%s" title="%s属性 · 12 列分列中的「%s」列（%s → 本列）：本行取值=「%s」'
                     '→ 本列显示实际取值「%s」；大小/单双/质合 只落点、相邻两期间暂不加连线">%s</th>'
                     % (cls, pre, col, crit, col, col, col))
    for t in ("0路", "1路", "2路"):
        cells.append('<th class="%s" title="%s 012路 落点列 %s：本行%s值 %s%%3 = %d → 在本列落点（●），'
                     '其余行本列留空；相邻两期落点折线相连">%s</th>'
                     % (cls, pre, t, sym, sym, int(t[0]), t))
    for t in ("升", "平", "降"):
        cells.append('<th class="%s" title="%s升平降 落点列 %s：本期%s相对上期为「%s」→ 在本列落点（●）；'
                     '首期无上期可比→本行无落点">%s</th>' % (cls, pre, t, pre, t, t))
    return cells


def lu3_cells(rv, om):
    """012路 拆 3 列（0路/1路/2路）：本行 rv = n%3（n=数值 v 或个位 d）→ 在 rv 对应列落点（●），其余两列留空"""
    pre = "个位" if om else "数值"
    nv = "d" if om else "v"
    out = []
    for k in range(3):
        if k == rv:
            out.append('<td class="mk r3 lu%d" title="%s012路：本行%s值 n%%3 = %d → '
                       '在 %d路 列显示实际取值「%d」；相邻两期落点间以折线相连">%d</td>' % (rv, pre, nv, rv, rv, rv, rv))
        else:
            out.append('<td class="r3" title="%s012路：本行 n%%3 = %d（落点在 %d路 列），本列（%d路）留空"></td>'
                       % (pre, rv, rv, k))
    return out


def sp3_cells(sv, om):
    """升平降 拆 3 列（升/平/降）：本行 sv=1升/0平/-1降 → 对应列落点（●）；sv=None（首期）三列均留空"""
    pre = "个位" if om else "数值"
    if sv is None:
        return ['<td class="r3" title="%s升平降：首期（无上期可比）→ 三列均无落点，折线自第 2 期起"></td>' % pre] * 3
    col = 1 - sv                      # 升→列0、平→列1、降→列2
    names = ("升", "平", "降")
    cls = ("up", "flat", "down")[col]
    mark = names[col]
    cmp_txt = "与上一期遗漏个位比较" if om else "与上一期数值比较"
    out = []
    for k in range(3):
        if k == col:
            out.append('<td class="mk r3 %s" title="%s升平降：%s → %s（在 %s 列显示实际取值「%s」）；'
                       '相邻两期落点间以折线相连">%s</td>' % (cls, pre, cmp_txt, mark, mark, mark, mark))
        else:
            out.append('<td class="r3" title="%s升平降：本行为 %s（落点在 %s 列），本列（%s）留空"></td>'
                       % (pre, mark, mark, names[k]))
    return out


def build_table(gi, mi):
    """单张指标表 html（含 thead/tbody）"""
    gn, pos, gdesc = GROUPS[gi]
    md = data[(gi, mi)]
    cols, colors = md["cols"], md["colors"]
    mc, acolor, abg, atxt = colors
    kindname = md["kindname"]
    arr = md["arr"]
    nc = len(cols)          # 落列偶数个数
    big_thr = 10 if mi == 0 else 14   # 大小阈值：码差三码和(大≥10)、码合三码和(大≥14)
    DGT = list(range(10))   # 遗漏值个位落列 0~9
    total = 1 + nc + 12 + 10 + 12  # 期号1 + 偶数列 + 数值属性12列分列 + 个位落列10 + 个位属性12列分列

    # ---- 表头（2 行）----
    h1 = ['<th class="issue" rowspan="2">期号</th>']
    h1.append('<th class="blk sep mblk" colspan="%d" style="color:%s;background:%s22" '
              'title="数值落列·遗漏走势：对每个偶数值 v 从窗口最旧一期起逐期连续累计遗漏（初值0）：'
              '当期该%s的数值==v → 本格高亮显示该数值、计数归 0；≠v → 计数+1、本格显示真实累计遗漏值'
              '（=距上次开出 v 的期数；窗口内尚未开出过则自窗口首期起累计；不取个位、不封顶）。'
              '整列无空白格；数值恒为偶数，单数列不显示。'
              '折线：相邻两期的数值落点（高亮格）之间以醒目彩色折线相连（SVG 叠加，随表格横向滚动）">'
              '数值落列 · 遗漏走势 · %s（偶数列 %s~%s，落点间折线相连）</th>'
              % (nc, atxt, acolor, kindname, kindname, cols[0], cols[-1]))
    h1.append('<th class="blk sep" colspan="12" title="本期数值的属性：共 12 列分列（每个取值一列、落点标记）——'
              '大小（大/小）、单双（单/双）、质合（质/合）每取值各 1 列，012路（0路/1路/2路）、升平降（升/平/降）各 3 列；'
              '每期在当期属性取值对应的列落点（●高亮）；其中 012路、升平降 相邻两期落点以折线相连，'
              '大小/单双/质合 只落点、暂不加连线">数值属性（12 列分列：大/小 · 单/双 · 质/合 + 0/1/2路 + 升/平/降；'
              '012路·升平降 落点折线相连）</th>')
    h1.append('<th class="blk sep omblk2" colspan="10" '
              'title="遗漏值个位落列（0~9）：每期取该期所开数值 v 本次开出前连续累计遗漏 S'
              '（=本次开出前已连续未出期数，与数值落列同一连续累计计数；上期同值开出→S=0），'
              '取个位 d（S 除以 10 的余数，0~9）→ 在 d 对应的列落点高亮显示 d，其余个位列本行留空；'
              '相邻两期落点间以折线相连">'
              '遗漏值个位落列（个位 0~9，落点折线相连）</th>')
    h1.append('<th class="blk sep" colspan="12" title="遗漏值个位 d 的属性：共 12 列分列（同数值属性规则）——'
              '大小（大/小）、单双（单/双）、质合（质/合）每取值各 1 列，012路（d%3）、升平降（与上一期个位比较）各 3 列；'
              '每期在当期取值对应列落点（●高亮）；其中 012路、升平降 相邻两期落点以折线相连，'
              '大小/单双/质合 只落点、暂不加连线">个位属性（12 列分列：大/小 · 单/双 · 质/合 + 0/1/2路 + 升/平/降；'
              '012路·升平降 落点折线相连）</th>')
    assert len(h1) == 5

    h2 = []
    for c in cols:
        h2.append('<th class="vl" title="偶数列 %d：当期数值=%d → 本格高亮显示该值、计数归 0；'
                  '≠ → 本格显示连续累计遗漏（自上次开出 %d 或窗口内尚未开出过则自窗口首期起，逐期累加的真实值，'
                  '1、2、3…递增，不取个位、不封顶），整列无空白格">%d</th>' % (c, c, c, c))
    h2 += attr_h2_cells(False, big_thr)   # 数值属性 12 列分列：大/小 单/双 质/合 + 0/1/2路 + 升/平/降
    for d in DGT:
        h2.append('<th class="om dg" title="个位落列 %d：该期遗漏值个位 d（S 除以 10 的余数，与数值落列同口径）'
                  '等于 %d 时在本列落点高亮显示 d，其余个位列本行留空">%d</th>' % (d, d, d))
    h2 += attr_h2_cells(True)    # 个位属性 12 列分列（同上）
    assert len(h2) == total - 1

    # 数值落列·遗漏走势：对每个偶数值 v 按时间序（旧→新）逐期连续累计遗漏
    # trend_seq[c][i] = ("hit",) 或 ("run", miss, last_open_i)
    #   miss = 该期未开出 v 时的真实累计遗漏值（1、2、3…，不取个位、不封顶）
    #   last_open_i = v 最近一次开出期的时间序下标；None = 窗口内尚未开出过（自窗口首期累计）
    trend_seq = {}
    for c in cols:
        seq = []
        miss = 0
        last_open = None
        for i in range(N):
            if arr[i]["v"] == c:
                seq.append(("hit",))
                miss = 0
                last_open = i
            else:
                miss += 1
                seq.append(("run", miss, last_open))
        trend_seq[c] = seq

    # ---- 表体：期号从小到大（最旧期=首期在首行，最新期=末期在末行）----
    tb = []
    for i in range(N):
        r = rows[i]
        e = arr[i]
        tds = ['<td class="issue" title="%s期（红球 %s）">%s</td>'
               % (fmt_issue(r["issue"]), " ".join("%02d" % x for x in r["reds"]), fmt_issue(r["issue"]))]
        for c in cols:
            st = trend_seq[c][i]
            if st[0] == "hit":
                tds.append('<td class="hit %s" title="%s位尾数 %s → %s = %d\n%s\n（本列遗漏计数归 0）">%d</td>'
                           % (mc, gn, e["tt"], kindname, e["v"], e["dt"], e["v"]))
            else:
                k, li = st[1], st[2]
                if li is None:
                    tip = "值%d遗漏走势：该期未开出；窗口内自首期起尚未开出过值%d，已连续累计遗漏 %d 期（真实值，不取个位、不封顶）" % (c, c, k)
                else:
                    tip = "值%d遗漏走势：该期未开出，自上次开出值%d（%s期）起已连续累计遗漏 %d 期（真实值，不取个位、不封顶）" % (c, c, fmt_issue(rows[li]["issue"]), k)
                tds.append('<td class="vl tr" title="%s">%d</td>' % (tip, k))
        tds += six_pair_cells(e["v"], False, big_thr)  # 数值 大小/单双/质合 分列（每取值一列、只落点）
        tds += lu3_cells(e["v"] % 3, False)   # 数值 012路 拆 3 列落点
        tds += sp3_cells(e["spv"], False)     # 数值 升平降 拆 3 列落点
        # ---- 遗漏值个位落列（0~9 共 10 列）：当期 S 的个位 d 在 d 列落点高亮，其余列本行留空 ----
        for d in DGT:
            if d == e["digit"]:
                if e["miss"] == 0:
                    tds.append('<td class="hit dgh0" title="%s位·%s：上期同值开出 → 连续累计遗漏归 0，'
                               '遗漏个位 d=0 → 在本列（0）落点（红底，与数值落列同口径）">0</td>' % (gn, kindname))
                else:
                    tds.append('<td class="hit dgh" title="%s位·%s 值 %d：本次开出前连续累计遗漏已达 %d 期'
                               '（与数值落列同一计数、同一口径），取个位 d=%d → 在本列（%d）落点高亮">%d</td>'
                               % (gn, kindname, e["v"], e["miss"], e["digit"], d, d))
            else:
                cls = 'vl dg' + (" oml" if d == 0 else "")
                tds.append('<td class="%s" title="%s位·%s：本行遗漏个位为 %d，不在个位列 %d（本列本行留空）"></td>'
                           % (cls, gn, kindname, e["digit"], d))
        tds += six_pair_cells(e["digit"], True)  # 个位 大小/单双/质合 分列（每取值一列、只落点）
        tds += lu3_cells(e["digit"] % 3, True)  # 个位 012路 拆 3 列落点
        tds += sp3_cells(e["dspv"], True)       # 个位 升平降 拆 3 列落点
        assert len(tds) == total, (gi, mi, len(tds))
        tb.append("<tr>" + "".join(tds) + "</tr>")

    head = ("<thead><tr>%s</tr><tr>%s</tr></thead>" % ("".join(h1), "".join(h2)))
    return '<div class="mtitle"><b style="color:%s">%s</b>　<span class="fm">＝ %s</span>　<span class="nt">%s</span></div>\n' \
           '<div class="scrollwrap"><table class="zs">%s<tbody>\n%s\n</tbody></table></div>' \
           % (atxt, kindname, md["formula"], md["note"], head, "\n".join(tb))


def build_panel(gi):
    """位组一级面板：ptitle + 二级选项卡（码差三码和/码合三码和）+ 两个 msec（点击只显示对应一张表）"""
    gn, pos, gdesc = GROUPS[gi]
    parts = ['<div class="ptitle"><span class="gn">%s</span>　%s：红球第 %s 个红球的尾数 a、b、c（红球按升序排列，尾数=号码个位，如 11→1、20→0）</div>'
             % (gn, gdesc, "、".join(str(p + 1) for p in pos))]
    parts.append('<div class="mtabs">')
    for mi in range(2):
        mk, kindname, cols, colors, formula, note = METRICS[mi]
        parts.append('<span class="mtab%s %s" title="%s位组内二级选项卡：点击显示「%s」表（另一张隐藏）">%s</span>'
                     % (" on" if mi == 0 else "", colors[0], gn, kindname, kindname))
    parts.append('</div>')
    for mi in range(2):
        mk, kindname = METRICS[mi][0], METRICS[mi][1]
        parts.append('<div class="msec%s" id="p%d-m%d">%s</div>'
                     % (" on" if mi == 0 else "", gi, mi, build_table(gi, mi)))
    return "\n".join(parts)


TABS = []
PANELS = []
for gi, (gn, pos, gdesc) in enumerate(GROUPS):
    TABS.append('<span class="tab%s" data-i="%d" title="%s红球尾数">%s</span>'
                % (" on" if gi == 0 else "", gi, gdesc, gn))
    PANELS.append('<div class="panel%s" id="p%d">%s</div>'
                  % (" on" if gi == 0 else "", gi, build_panel(gi)))

CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f5f6fa; color:#333; padding:12px; }
h1 { font-size:19px; color:#d33; margin-bottom:2px; }
.sub { color:#888; font-size:12px; margin-bottom:10px; line-height:1.7; }
/* 说明折叠按钮与隐藏态 */
.info-toggle { margin-left:auto; align-self:center; background:#fff; border:1px solid #ccc; color:#555;
  border-radius:5px; padding:4px 14px; font-size:12px; cursor:pointer; user-select:none; white-space:nowrap; }
.info-toggle:hover { color:#d33; border-color:#d33; }
.hidden { display:none !important; }
/* 选项卡 */
.tabs { display:flex; gap:6px; margin:10px 0; }
.tab { background:#fff; border:1px solid #ccc; color:#555; border-radius:6px 6px 0 0;
  padding:7px 26px; font-size:14px; font-weight:bold; cursor:pointer; user-select:none; }
.tab:hover { color:#d33; border-color:#d33; }
.tab.on { background:#d33; color:#fff; border-color:#d33; }
.panel { display:none; }
.panel.on { display:block; }
/* 二级选项卡（位组面板内：码差三码和 / 码合三码和，互斥显示） */
.mtabs { display:flex; gap:4px; margin:0 0 8px; }
.mtab { background:#fff; border:1px solid #ccc; color:#777; border-radius:5px 5px 0 0;
  padding:4px 16px; font-size:13px; font-weight:bold; cursor:pointer; user-select:none; }
.mtab:hover { color:#b3541e; border-color:#b3541e; }
.mtab.on.m-cha { background:#e8871a; color:#fff; border-color:#e8871a; }
.mtab.on.m-he { background:#2d6cdf; color:#fff; border-color:#2d6cdf; }
.msec { display:none; }
.msec.on { display:block; }
/* 图例 */
.legend { display:flex; flex-wrap:wrap; gap:4px 16px; align-items:center; background:#fff;
  border:1px solid #eee; border-radius:6px; padding:7px 12px; margin-bottom:6px; font-size:12px; color:#555; }
.legend .lg { display:inline-flex; align-items:center; gap:4px; white-space:nowrap; }
.legend .sw { display:inline-block; min-width:18px; text-align:center; border-radius:3px;
  font-weight:bold; font-size:11px; padding:0 2px; }
/* 位组标题 & 指标标题 */
.ptitle { background:#fff; border:1px solid #e6e6e6; border-left:4px solid #d33; border-radius:4px;
  padding:7px 10px; margin:4px 0 10px; font-size:13px; color:#444; }
.ptitle .gn { color:#d33; font-size:15px; font-weight:bold; }
.mtitle { font-size:12px; padding:4px 2px 6px; color:#333; }
.mtitle .fm { color:#555; font-family:Consolas,monospace; }
.mtitle .nt { color:#999; }
/* 滚动容器 & 表格 */
.scrollwrap { overflow:auto; max-height:70vh; border:1px solid #dcdcdc; border-radius:6px;
  background:#fff; margin-bottom:14px; }
table.zs { border-collapse:collapse; font-size:11px; white-space:nowrap; }
table.zs th, table.zs td { border:1px solid #e3e3e3; padding:2px 4px; text-align:center; height:24px; }
table.zs thead th { position:sticky; top:0; z-index:20; background:#f0f0f0; color:#333;
  font-weight:bold; border-bottom:1px solid #ccc; }
table.zs thead tr:first-child th { top:0; height:28px; font-size:12px; }
table.zs thead tr:last-child th { top:30px; height:22px; font-size:10px; font-weight:normal; color:#555; background:#fafafa; }
table.zs thead th.sep, table.zs td.sep { border-left:2px solid #9aa5b5; }
table.zs thead th.issue { background:#e8e8e8; }
table.zs thead th.blk.omblk { background:#e8f1fb; color:#2d6cdf; }
table.zs thead th.blk.omblk2 { background:#f1e7fb; color:#7b1fa2; }
table.zs thead th.om, table.zs tbody td.oml { border-left:2px solid #9aa5b5; }
thead th.vl { background:#fdf6ec; }
thead th.at { background:#f7f7f7; }
thead th.omat { background:#eef4fc; }
thead th.dg { background:#fbf7fe; color:#6a4fa3; font-weight:bold; min-width:20px; }
/* 行内单元格 */
td.issue { font-weight:bold; color:#333; background:#f5f5f5; min-width:58px; }
td.vl { background:#fff; min-width:32px; }
td.vl.tr { color:#8c8c8c; }
td.hit { font-weight:bold; font-size:12px; min-width:32px; }
td.hit.m-cha { background:#ffe0be; color:#b3541e; }
td.hit.m-he { background:#d9e7ff; color:#174ea6; }
tbody tr:nth-child(even) td { background:#f7f9fc; }
tbody tr:nth-child(even) td.issue { background:#eff1f4; }
tbody tr:nth-child(even) td.hit.m-cha { background:#ffe0be; }
tbody tr:nth-child(even) td.hit.m-he { background:#d9e7ff; }
td.dg { background:#fff; min-width:20px; }
td.hit.dgh { background:#f1dffb; color:#7b1fa2; font-size:12px; }
td.hit.dgh0 { background:#ffecec; color:#e4393c; font-size:12px; }
tbody tr:nth-child(even) td.dg { background:#f7f9fc; }
tbody tr:nth-child(even) td.dg.oml { background:#f7f9fc; }
tbody tr:nth-child(even) td.hit.dgh { background:#f1dffb; }
tbody tr:nth-child(even) td.hit.dgh0 { background:#ffecec; }
td.a { font-weight:bold; font-size:11px; min-width:32px; }
td.a.big { color:#e4393c; }
td.a.small { color:#2d6cdf; }
td.a.odd { background:#ffe3e3; color:#c0392b; }
td.a.even { background:#e3ecff; color:#2d6cdf; }
tbody tr:nth-child(even) td.a.odd { background:#ffe3e3; }
tbody tr:nth-child(even) td.a.even { background:#e3ecff; }
td.a.prime { color:#2e8b57; }
td.a.comp { color:#b3541e; }
td.a.lu0 { color:#e4393c; }
td.a.lu1 { color:#2d6cdf; }
td.a.lu2 { color:#2e8b57; }
td.a.up { color:#e4393c; }
td.a.flat { color:#999; }
td.a.down { color:#2e8b57; }
td.a.dash { color:#bbb; font-weight:normal; }
/* 图例色块 */
.lg .big{color:#e4393c;font-weight:bold}.lg .small{color:#2d6cdf;font-weight:bold}
.lg .odd{background:#ffe3e3;color:#c0392b}.lg .even{background:#e3ecff;color:#2d6cdf}
.lg .prime{color:#2e8b57;font-weight:bold}.lg .comp{color:#b3541e;font-weight:bold}
.lg .lu0{color:#e4393c;font-weight:bold}.lg .lu1{color:#2d6cdf;font-weight:bold}.lg .lu2{color:#2e8b57;font-weight:bold}
.lg .up{color:#e4393c;font-weight:bold}.lg .flat{color:#999}.lg .down{color:#2e8b57;font-weight:bold}.lg .dash{color:#bbb}
.lg .tr{color:#8c8c8c;font-weight:bold}
.lg .hit-cha{background:#ffe0be;color:#b3541e}.lg .hit-he{background:#d9e7ff;color:#174ea6}
.lg .mo{background:#ffecec;color:#e4393c;font-weight:bold}
/* 图例色块：大小/单双/质合 分列取值（对应 td.mk.* 落点底色） */
.lg .sw.big{background:#ffe1e0;color:#e4393c;font-weight:bold}
.lg .sw.small{background:#dbe8ff;color:#2d6cdf;font-weight:bold}
.lg .sw.odd{background:#ffe3e3;color:#c0392b;font-weight:bold}
.lg .sw.even{background:#e3ecff;color:#2d6cdf;font-weight:bold}
.lg .sw.prime{background:#d5f0e0;color:#2e8b57;font-weight:bold}
.lg .sw.comp{background:#fdf1e2;color:#b3541e;font-weight:bold}
footer { color:#aaa; font-size:11px; margin-top:12px; line-height:1.8; }
footer b { color:#888; }
/* 连线叠加：SVG 位于表格上方、随滚动容器内容滚动 */
.scrollwrap { position:relative; }
svg.ovl { position:absolute; left:0; top:0; pointer-events:none; z-index:6; }
svg.ovl path { fill:none; stroke-linecap:round; stroke-linejoin:round; }
.lg .dgh{background:#f1dffb;color:#7b1fa2;font-weight:bold}
.lg .dgh0{background:#ffecec;color:#e4393c;font-weight:bold}
.lg .ln{color:#c2410c;font-weight:bold}
.lg .lnh{color:#1a56c2;font-weight:bold}
.lg .lnv{color:#8a93a6;font-weight:bold}
.lg .lnd{color:#7b1fa2;font-weight:bold}
/* 012路/升平降 三列落点：mk=落点（●）列，r3=三列通用窄列；相邻两期落点折线由 SVG 叠加绘制 */
th.r3 { min-width:20px; font-size:10px; }
td.r3 { min-width:20px; padding:0 1px; }
td.mk { font-size:10px; padding:0 1px; color:#7a7f8a; }
td.mk.lu0 { background:#ffe1e0; color:#e4393c; }
td.mk.lu1 { background:#dbe8ff; color:#2d6cdf; }
td.mk.lu2 { background:#d5f0e0; color:#2e8b57; }
td.mk.up { background:#ffe1e0; color:#e4393c; }
td.mk.flat { background:#f0f0f0; color:#7a7f8a; }
td.mk.down { background:#d5f0e0; color:#2e8b57; }
/* 属性 12 列分列：大小/单双/质合 落点 ●（只落点、不加连线） */
td.mk.big { background:#ffe1e0; color:#e4393c; }
td.mk.small { background:#dbe8ff; color:#2d6cdf; }
td.mk.odd { background:#ffe3e3; color:#c0392b; }
td.mk.even { background:#e3ecff; color:#2d6cdf; }
td.mk.prime { background:#d5f0e0; color:#2e8b57; }
td.mk.comp { background:#fdf1e2; color:#b3541e; }
"""

LEGEND = """
<div class="legend">
  <span class="lg"><b>数值落列·遗漏走势</b>：每行=一期；对每个偶数值从窗口最旧一期起逐期连续累计——当期数值=该偶数列 → 本格高亮显示该值（计数归0）；未开出 → 本格显示真实累计遗漏（自上次开出或自窗口首期起 1、2、3…递增，不取个位、不封顶；首次开出前与最近开出后均连续显示，整列无空白；数值恒偶，单数列不显示）</span>
  <span class="lg"><i class="sw hit-cha">10</i>码差开出格</span>
  <span class="lg"><i class="sw hit-he">16</i>码合开出格</span>
  <span class="lg"><i class="sw tr">3</i>遗漏走势值（灰字，实际值）</span>
  <span class="lg"><b>数值属性 / 个位属性（各 12 列分列，每期在当期取值对应列落点●）</b></span>
  <span class="lg">大小（2 列）：<i class="sw big">大</i>n≥5 / <i class="sw small">小</i>n&lt;5</span>
  <span class="lg">单双（2 列）：<i class="sw odd">单</i>奇数 / <i class="sw even">双</i>偶数</span>
  <span class="lg">质合（2 列）：<i class="sw prime">质</i>质集{1,2,3,5,7,11,13,17,19,23} / <i class="sw comp">合</i>其余</span>
  <span class="lg">012路（3 列）：<i class="lu0">0</i><i class="lu1">1</i><i class="lu2">2</i> = n%3（相邻两期落点折线相连）</span>
  <span class="lg">升平降（3 列）：<i class="up">升</i><i class="flat">平</i><i class="down">降</i> = 本期 vs 上期（相邻两期落点折线相连；首期无上期可比 → 无落点，折线自第 2 期起）</span>
  <span class="lg"><b>连线：</b>012路、升平降 加折线连线（数值组、个位组各 2 组，共 4 组）；大小/单双/质合 只落点、暂不加连线</span>
  <span class="lg"><i class="sw dgh">6</i>遗漏个位落列：0~9 每期在其个位列落点（紫底），相邻两期落点间折线相连</span>
  <span class="lg"><i class="sw dgh0">0</i>红底 0 = S=0（上期同值开出，连续累计遗漏归 0）</span>
  <span class="lg"><i class="ln">━━</i>码差数值落点折线 <i class="lnh">━━</i>码合数值落点折线 <i class="lnd">━━</i>遗漏个位落点折线 <i class="lnv">━━</i>012路/升平降 落点折线（灰）</span>
</div>
"""

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
issue_first, issue_last = rows[0]["issue"], rows[-1]["issue"]

JS = """
<script>
(function () {
  var SVGNS = 'http://www.w3.org/2000/svg';
  function el(tag, attrs) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  /* 绘制所有可见面板内表格的连线叠加层（数值落点折线 + 遗漏个位落点折线 + 012路/升平降 三列落点折线） */
  function drawAll() {
    var wraps = document.querySelectorAll('.scrollwrap');
    for (var w = 0; w < wraps.length; w++) {
      var h = wraps[w], tbl = h.querySelector('table.zs');
      if (!tbl) continue;
      var panel = h.closest('.panel');
      if (panel && panel.className.indexOf(' on') < 0) continue; // 仅可见一级面板
      var sec = h.closest('.msec');
      if (sec && sec.className.indexOf(' on') < 0) continue; // 仅可见二级面板（码差/码合互斥显示）
      drawTable(h, tbl);
    }
  }
  function drawTable(h, tbl) {
    var olds = h.querySelectorAll('svg.ovl');
    for (var o = 0; o < olds.length; o++) olds[o].parentNode.removeChild(olds[o]);
    if (!tbl.tHead || tbl.tHead.rows.length < 2) return;
    var rows = tbl.tBodies[0].rows;
    if (!rows.length) return;
    var svg = el('svg', { 'class': 'ovl' });
    svg.setAttribute('width', h.scrollWidth);
    svg.setAttribute('height', h.scrollHeight);
    h.appendChild(svg);
    var hb = h.getBoundingClientRect();
    function pt(el_, yoff) {
      var r = el_.getBoundingClientRect();
      return [r.left - hb.left - h.clientLeft + h.scrollLeft + r.width / 2,
              r.top - hb.top - h.clientTop + h.scrollTop + r.height / 2 + (yoff || 0)];
    }
    /* 1) 数值落点折线：每行唯一的高亮落点格（td.hit），相邻两期连线 */
    var hitColor = null, pts = [];
    for (var i = 0; i < rows.length; i++) {
      var hit = rows[i].querySelector('td.hit');
      if (!hit) continue;
      if (!hitColor) hitColor = (hit.className.indexOf('m-he') >= 0) ? '#1a56c2' : '#c2410c';
      pts.push(pt(hit));
    }
    if (pts.length >= 2) {
      var d = 'M' + pts[0][0] + ' ' + pts[0][1];
      for (var k = 1; k < pts.length; k++) d += ' L' + pts[k][0] + ' ' + pts[k][1];
      svg.appendChild(el('path', { d: d, stroke: hitColor, 'stroke-width': 1.6, opacity: 0.85 }));
    }
    /* 1b) 遗漏值个位落列（0~9）折线：每行的个位落点（td.hit.dgh / td.hit.dgh0）相邻两期相连 */
    var dpPrev = null;
    for (var di = 0; di < rows.length; di++) {
      var dcell = rows[di].querySelector('td.hit.dgh, td.hit.dgh0');
      if (!dcell) { dpPrev = null; continue; }
      var dp = pt(dcell);
      if (dpPrev) {
        svg.appendChild(el('path', { d: 'M' + dpPrev[0] + ' ' + dpPrev[1] + ' L' + dp[0] + ' ' + dp[1],
          stroke: '#7b1fa2', 'stroke-width': 1.4, opacity: 0.85 }));
      }
      dpPrev = dp;
    }
    /* 2) 012路（0路/1路/2路）与 升平降（升/平/降）三列落点折线：数值属性组 + 个位属性组各 2 组，共 4 组。
          每组连续 3 列；每行在其对应列有落点格（class mk，●），相邻两期落点以折线相连 */
    var hcells = tbl.tHead.rows[1].cells;
    var LUCOL2 = { '0': '#e4393c', '1': '#2d6cdf', '2': '#2e8b57' };
    var groups = [];
    for (var ci = 0; ci < hcells.length; ci++) {
      var nm = hcells[ci].textContent.replace(/\\s/g, '');
      if (nm === '0路' || nm === '升') { groups.push({ a: ci, b: ci + 2 }); ci += 2; }
    }
    for (var g = 0; g < groups.length; g++) {
      var gg = groups[g], prev = null;
      for (var ri = 0; ri < rows.length; ri++) {
        var p = null, cell = null;
        for (var c2 = gg.a; c2 <= gg.b; c2++) {
          var cc = rows[ri].cells[c2 + 1];
          if (cc && /(?:^| )mk(?: |$)/.test(cc.className)) { p = pt(cc); cell = cc; break; }
        }
        if (!p) { prev = null; continue; } // 首期升平降等无落点行：断开折线
        var m2 = /(?:^| )lu([012])(?: |$)/.exec(cell.className), fill;
        if (m2) { fill = LUCOL2[m2[1]]; }
        else if (/up/.test(cell.className)) { fill = '#e4393c'; }
        else if (/down/.test(cell.className)) { fill = '#2e8b57'; }
        else { fill = '#7a7f8a'; }
        if (prev) {
          svg.appendChild(el('path', { d: 'M' + prev[0] + ' ' + prev[1] + ' L' + p[0] + ' ' + p[1],
            stroke: '#aab2c2', 'stroke-width': 1.1, opacity: 0.9 }));
        }
        prev = p;
      }
    }
  }
  /* 一级选项卡切换（位组 123/234/345/456） */
  var tabs = document.querySelectorAll('.tab');
  var panels = document.querySelectorAll('.panel');
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].onclick = (function (idx) {
      return function () {
        for (var j = 0; j < tabs.length; j++) {
          tabs[j].classList.toggle('on', j === idx);
          panels[j].classList.toggle('on', j === idx);
        }
        drawAll();
      };
    })(i);
  }
  /* 二级选项卡切换（每个位组面板内：码差三码和 / 码合三码和，互斥显示） */
  var mtabs = document.querySelectorAll('.mtab');
  for (var i = 0; i < mtabs.length; i++) {
    mtabs[i].onclick = (function (me) {
      return function () {
        var pnl = me.closest('.panel');
        if (!pnl) return;
        var tbs = pnl.querySelectorAll('.mtab');
        var secs = pnl.querySelectorAll('.msec');
        var idx = 0;
        for (var j = 0; j < tbs.length; j++) { if (tbs[j] === me) { idx = j; break; } }
        for (var j = 0; j < tbs.length; j++) {
          tbs[j].classList.toggle('on', j === idx);
          if (secs[j]) secs[j].classList.toggle('on', j === idx);
        }
        drawAll();
      };
    })(mtabs[i]);
  }
  drawAll();
  window.addEventListener('resize', drawAll);
  /* 说明折叠开关：默认隐藏上方说明/图例与下方口径说明，让图表最大化显示 */
  var it = document.getElementById('infoToggle');
  if (it) {
    it.onclick = function () {
      var targets = [document.querySelector('.sub'), document.getElementById('legendWrap'),
                     document.getElementById('footerWrap')];
      var isHidden = targets.some(function (el) { return el && el.classList.contains('hidden'); });
      targets.forEach(function (el) { if (el) el.classList.toggle('hidden', !isHidden); });
      it.textContent = isHidden ? '隐藏说明' : '显示说明';
    };
  }
})();
</script>
"""

TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>双色球 · 尾数指标统计（码差/码合三码和）</title>
<style>__CSS__</style>
</head>
<body>
<h1>双色球 · 尾数指标统计（码差三码和 / 码合三码和）</h1>
<div class="sub hidden">数据源：lottery_data/ssq.json · 期号 __FIRST__（最旧，首行）~ __LAST__（最新，末行）· 共 __N__ 期，期号从小到大排列（最旧期在上、最新期在下，各列遗漏走势自上而下正序递增）· 红球尾数 = 号码个位 · 生成时间 __NOW__</div>
<div class="tabs">__TABS__<span id="infoToggle" class="info-toggle">显示说明</span></div>
<div id="legendWrap" class="hidden">__LEGEND__</div>
__PANELS__
<footer id="footerWrap" class="hidden">
<b>口径说明：</b><br>
① 位组：123位=红球（升序）第1/2/3个、234位=第2/3/4个、345位=第3/4/5个、456位=第4/5/6个；a、b、c 为该位组三个红球的尾数。<br>
② 码差三码和 = |a−b| + |a−c| + |b−c|，两两差绝对值之和按原值相加、不取个位；恒为偶数，范围 0~18。<br>
③ 码合三码和 = (a+b)取个位 + (a+c)取个位 + (b+c)取个位，三个两两和先各取个位再相加、最后不取个位；恒为偶数，范围 0~26。<br>
④ 属性定义与展示：对数值 n 或个位 d —— 大小 = 大(≥5)/小(&lt;5)；单双按奇偶（指标值恒为偶数 → 数值组恒落「双」列、「单」列恒空，个位组按 d 奇偶落列）；质合 = 质 n∈{1,2,3,5,7,11,13,17,19,23}，合=其余；012路 = n%3；升平降 = 与上一期同列比较，升/平/降，首期无上期可比 → 无落点。展示：数值属性、个位属性均为 <b>12 列分列</b>（每个取值一列、落点标记）——大小（大/小）、单双（单/双）、质合（质/合）各 2 列，012路（0路/1路/2路）、升平降（升/平/降）各 3 列，每期在当期属性取值对应的列落点（●高亮）。<br>
⑤ 数值落列·遗漏（连续累计、真实值不取个位、不封顶）：对每个偶数值 v 从窗口最旧一期起逐期维护计数——当期未开出 v → 计数+1，该列本格显示真实累计遗漏（= 距上次开出 v 的期数；窗口内尚未开出过 → 自窗口首期累计；两次开出之间、首次开出之前、最近一次开出之后均连续显示，整列无空白格）；当期开出 v → 该格高亮显示数值并归 0。<br>
⑥ 遗漏值个位落列：每期取该期所开数值 v 在本次开出前连续累计已达到的遗漏值 S（= 本次开出前已连续未出期数；上期同值开出 → S=0；与⑤为同一连续累计计数、同一口径）取个位后的数字 d（0~9），在 0~9 共 10 列中 d 对应的列落点高亮显示 d，其余个位列本行留空；并对该个位 d 同样标注上述属性（属性口径同④）。<br>
⑦ 折线走势：相邻两期的「数值落点」（高亮格）之间以醒目彩色折线相连（SVG 叠加于表格之上、随表格横向滚动）；「遗漏个位落列」（0~9）同样把相邻两期落点以折线相连。属性 12 列分列中：012路、升平降 每期在取值对应列落点（●高亮），相邻两期落点间以折线相连（数值组、个位组各两处，共 4 组折线）；大小/单双/质合 只落点（●）、相邻两期间暂不加连线。<br>
⑧ 本表仅作数据统计展示，开奖为独立随机事件，请理性参考。
</footer>
__JS__
</body>
</html>"""

html = (TPL
        .replace("__CSS__", CSS)
        .replace("__FIRST__", fmt_issue(issue_first))
        .replace("__LAST__", fmt_issue(issue_last))
        .replace("__N__", str(N))
        .replace("__NOW__", now)
        .replace("__TABS__", "".join(TABS))
        .replace("__LEGEND__", LEGEND)
        .replace("__PANELS__", "".join(PANELS))
        .replace("__MOD10__", "10")
        .replace("__JS__", JS))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
# 删除所有单元格悬停提示 title 属性，大幅减小文件体积（全量历史数据下单元格极多）
import re as _re
html = _re.sub(r' title="[^"]*"', '', html)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK written:", OUT)
print("size:", os.path.getsize(OUT), "bytes")
print("tables:", html.count('<table class="zs">'), "| panels:", len(PANELS))
print("期号范围: %s ~ %s" % (fmt_issue(issue_first), fmt_issue(issue_last)))
if _CUSTOM_OUT:
    print("[note] 自定义输出，跳过桌面同步")
elif os.path.isdir(DESKTOP):
    print("[skip] 桌面路径被同名文件夹占用，跳过复制（不覆盖桌面项目）:", DESKTOP)
elif os.path.exists(DESKTOP) and not os.path.isfile(DESKTOP):
    print("[skip] 桌面路径非普通文件，跳过复制:", DESKTOP)
else:
    try:
        shutil.copyfile(OUT, DESKTOP)
        print("OK copied:", DESKTOP)
    except Exception as e:
        print("[warn] 桌面复制失败（不影响主文件）:", e)
