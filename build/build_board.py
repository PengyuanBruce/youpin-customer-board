"""客户优爆品数据看板构建脚本.

读取当前目录下每位销售的 *.xlsx（拍档系统 ▸ 客户管理 ▸ 拍档客户管理 导出的
CGS 客户优爆品明细），生成：
  snapshots/customers-YYYY-MM-DD.json   每数据日一份客户级快照（用于算新增）
  board.json                            页面数据
  index.html                            自包含单文件看板（数据内联）

新增口径：
  今日新增 = 当前数据日优爆品数 - 上一个可用数据日优爆品数
  本月新增 = 当前数据日优爆品数 - 本月首个可用数据日优爆品数
  缺基准一律 None（前端显示 --），禁止用 0 或上月值兜底。
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re

import openpyxl

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(BASE, "snapshots")
HOME_SRC = r"D:\AWB\公司数据管理大屏Agent\project\build\data_cur.json"
HOME_CACHE = os.path.join(BASE, "build", "home_cache.json")

TEMPLATE = os.path.join(BASE, "build", "template.html")
OUT_HTML = os.path.join(BASE, "index.html")
OUT_JSON = os.path.join(BASE, "board.json")

# 表头文字 -> 内部字段（按名称匹配，不用列位置）
COLS = {
    "序号": "seq",
    "客户名称": "name",
    "星等级": "stars",
    "本月实收(USD)": "recv_m",
    "本季度实收(USD)": "recv_q",
    "在线品数": "online",
    "优爆品数": "you",
    "优品数": "you",
    "其中：爆品数": "boom",
    "优品占比": "you_pct",
    "准优品数": "quasi",
    "商机优品数": "chance",
    "交易优品数": "trade_you",
    "4.5分以上品数": "g45",
    "交易品数": "trade",
    "近7日动销品数": "active7",
    "商品数据": "has_goods",
    "客服": "kefu",
    "30天P4P消耗": "p4p30",
    "30天P消耗": "p4p30",
}


def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def txt(v):
    return "" if v is None else str(v).strip()


def read_workbook(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    title = txt(rows[0][0]) if rows else ""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", title)
    ds = m.group(1) if m else None

    hdr_idx = None
    for i, r in enumerate(rows[:8]):
        if txt(r[0]) == "序号":
            hdr_idx = i
            break
    if hdr_idx is None:
        raise RuntimeError(f"{os.path.basename(path)}: 找不到表头行")

    header = [txt(c) for c in rows[hdr_idx]]
    field_of = {}
    for i, h in enumerate(header):
        if h in COLS and COLS[h] not in field_of.values():
            field_of[i] = COLS[h]

    customers = []
    for r in rows[hdr_idx + 1:]:
        if len(r) <= 1 or not txt(r[1]):
            continue
        rec = {}
        for i, f in field_of.items():
            rec[f] = r[i] if i < len(r) else None
        name = txt(rec.get("name"))
        if not name:
            continue
        seq = txt(rec.get("seq"))
        if seq.endswith(".0"):
            seq = seq[:-2]
        customers.append({
            "key": f"{seq}|{name}",
            "seq": seq,
            "name": name,
            "stars": num(rec.get("stars")),
            "online": num(rec.get("online")),
            "you": num(rec.get("you")),
            "boom": num(rec.get("boom")),
            "trade": num(rec.get("trade")),
            "you_pct": num(rec.get("you_pct")),
            "kefu": txt(rec.get("kefu")),
            "has_goods": txt(rec.get("has_goods")),
            "p4p30": num(rec.get("p4p30")),
        })
    wb.close()
    return ds, title, customers


def load_snapshots():
    os.makedirs(SNAP_DIR, exist_ok=True)
    snaps = {}
    for p in sorted(glob.glob(os.path.join(SNAP_DIR, "customers-*.json"))):
        with open(p, encoding="utf-8") as fh:
            s = json.load(fh)
        if s.get("ds"):
            snaps[s["ds"]] = s
    return snaps


def write_snapshot(ds, persons, customers, captured_at):
    os.makedirs(SNAP_DIR, exist_ok=True)
    payload = {
        "ds": ds,
        "captured_at": captured_at,
        "persons": {p["name"]: {"you": p["you"], "trade": p["trade"], "customers": p["count"]}
                    for p in persons},
        "customers": {c["key"]: {"you": c["you"], "trade": c["trade"], "name": c["name"]}
                      for c in customers},
    }
    path = os.path.join(SNAP_DIR, f"customers-{ds}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    return path


def load_home():
    """首页 优爆品 + 挑战赛 数据：优先读公司大屏当日产物，失败则用本地缓存。"""
    home, src = None, None
    if os.path.exists(HOME_SRC):
        try:
            with open(HOME_SRC, encoding="utf-8") as fh:
                d = json.load(fh)
            home = {
                "goods": d.get("goods"),
                "youpin_company": d.get("youpin_company"),
                "goods_sales": d.get("goods_sales") or [],
                "goods_kefu": d.get("goods_kefu") or [],
                "goods_challenge": d.get("goods_challenge") or {},
                "update_time": d.get("update_time"),
            }
            src = HOME_SRC
            with open(HOME_CACHE, "w", encoding="utf-8") as fh:
                json.dump(home, fh, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            print("读公司大屏数据失败:", exc)
    if home is None and os.path.exists(HOME_CACHE):
        with open(HOME_CACHE, encoding="utf-8") as fh:
            home = json.load(fh)
        src = HOME_CACHE + " (cache)"
    return home, src


def main():
    now = dt.datetime.now()
    captured_at = now.strftime("%Y-%m-%d %H:%M")

    files = [f for f in sorted(glob.glob(os.path.join(BASE, "*.xlsx")))
             if not os.path.basename(f).startswith("~" + chr(36))]
    if not files:
        raise SystemExit("工作区没有 xlsx")

    persons, all_customers, ds_set = [], [], set()
    for f in files:
        ds, title, rows = read_workbook(f)
        name = os.path.splitext(os.path.basename(f))[0]
        if ds:
            ds_set.add(ds)
        you = sum(r["you"] or 0 for r in rows)
        trade = sum(r["trade"] or 0 for r in rows)
        persons.append({
            "name": name,
            "file": os.path.basename(f),
            "ds": ds,
            "title": title,
            "count": len(rows),
            "you": you,
            "trade": trade,
            "boom": sum(r["boom"] or 0 for r in rows),
            "online": sum(r["online"] or 0 for r in rows),
            "customers": rows,
        })
        all_customers.extend(rows)

    if len(ds_set) > 1:
        print("!! 工作区表格数据日期不一致:", sorted(ds_set))
    data_ds = max(ds_set) if ds_set else now.strftime("%Y-%m-%d")

    snaps = load_snapshots()
    write_snapshot(data_ds, persons, all_customers, captured_at)
    snaps = load_snapshots()

    dates = sorted(snaps)
    prev_ds = max([d for d in dates if d < data_ds], default=None)
    month = data_ds[:7]
    month_base_ds = min([d for d in dates if d[:7] == month], default=data_ds)

    def delta(key, field, base_snap):
        if not base_snap:
            return None
        cur = snaps[data_ds]["customers"].get(key)
        old = base_snap["customers"].get(key)
        if not cur or not old:
            return None
        a, b = cur.get(field), old.get(field)
        if a is None or b is None:
            return None
        return a - b

    prev_snap = snaps.get(prev_ds) if prev_ds else None
    # 本月基准就是当天时，本月新增没有独立基准 -> None（不拿 0 顶）
    month_snap = snaps.get(month_base_ds) if month_base_ds and month_base_ds != data_ds else None

    for p in persons:
        for c in p["customers"]:
            c["day_add"] = delta(c["key"], "you", prev_snap)
            c["month_add"] = delta(c["key"], "you", month_snap)

    # 汇总：任一子项缺基准即缺（宁缺勿错）
    for p in persons:
        for f in ("day_add", "month_add"):
            vals = [c[f] for c in p["customers"]]
            p[f] = None if any(v is None for v in vals) else sum(vals)

    persons.sort(key=lambda x: (-(x["you"] or 0), x["name"]))

    home, home_src = load_home()

    board = {
        "meta": {
            "data_ds": data_ds,
            "captured_at": captured_at,
            "month": month,
            "prev_ds": prev_ds,
            "month_base_ds": month_base_ds if month_snap else None,
            "snapshot_dates": dates,
            "person_count": len(persons),
            "customer_count": len(all_customers),
            "home_source": home_src,
            "home_update": (home or {}).get("update_time"),
        },
        "persons": persons,
        "home": home,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(board, fh, ensure_ascii=False, indent=1)

    with open(TEMPLATE, encoding="utf-8") as fh:
        tpl = fh.read()
    html = tpl.replace("/*__BOARD__*/null", json.dumps(board, ensure_ascii=False, separators=(",", ":")))
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"数据日 {data_ds} | 销售 {len(persons)} 人 | 客户 {len(all_customers)} 家")
    print(f"上一数据日 {prev_ds or '无'} | 本月首个数据日 {month_base_ds} | 快照 {len(dates)} 份")
    print("首页数据源:", home_src)
    for p in persons:
        print(f"  {p['name']}: 客户{p['count']} 优爆品{p['you']:.0f} 交易品{p['trade']:.0f}"
              f" 本月新增{p['month_add']} 今日新增{p['day_add']}")
    print("已生成", OUT_HTML, os.path.getsize(OUT_HTML), "B")


if __name__ == "__main__":
    main()
