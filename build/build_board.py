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
import sys

import openpyxl

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(BASE, "snapshots")
INVENTORY_SRC = (r"D:\AWB\公司数据管理大屏Agent\project\build"
                 r"\compass_raw\audit-full-customers.json")
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


def norm_key(s):
    """客户名/销售名比对用：去空白、全角括号转半角。不做「去掉深圳市」这类激进归并。"""
    s = str(s or "").strip().replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", s)


def load_inventory(path):
    """读平台「全量客户盘点」采集件，返回 (数据日, {(销售, 客户): 指标})。

    采集件形如 {meta, rawResponses:[{data:{data:[...]}}]}，只取最大 stat_date 分区。
    """
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    rows = []
    for item in d.get("rawResponses") or []:
        body = item.get("data") or {}
        if isinstance(body.get("data"), list):
            rows.extend(body["data"])
    if not rows:
        return None, {}, 0

    ds_all = sorted({str(r.get("stat_date")) for r in rows if r.get("stat_date")})
    ds = ds_all[-1]
    table = {}
    kept = 0
    for r in rows:
        if str(r.get("stat_date")) != ds:
            continue
        kept += 1
        k = (norm_key(r.get("partner_user_sales_name")), norm_key(r.get("cust_name_cn")))
        table[k] = {
            "you": num(r.get("youbaopin_prd_cnt")),
            "trade": num(r.get("jiaoyi_prd_cnt")),
            "online": num(r.get("prd_cnt")),
            "boom": num(r.get("baopin_prd_cnt")),
            "kefu": txt(r.get("partner_user_kefu_name")),
            "cgs": str(r.get("is_cgs_service") or "").upper(),
        }
    return ds, table, kept


def apply_inventory(persons, inv_path):
    """用平台盘点件刷新每位在册客户的指标（客户清单仍以工作区 xlsx 为准）。"""
    if not inv_path or not os.path.exists(inv_path):
        return {"used": False, "reason": "未找到盘点采集件", "matched": 0, "total": 0}
    ds, table, kept = load_inventory(inv_path)
    if not ds:
        return {"used": False, "reason": "盘点件无数据行", "matched": 0, "total": 0}

    matched = total = 0
    for p in persons:
        for c in p["customers"]:
            total += 1
            hit = table.get((norm_key(p["name"]), norm_key(c["name"])))
            if hit is None:
                c["src"] = "xlsx"
                continue
            matched += 1
            # 平台该客户没有商品数据（you 为空）时保留 xlsx 值，但客户已匹配
            c["src"] = "inventory" if hit.get("you") is not None else "xlsx"
            if hit.get("you") is not None:
                c["you"] = hit["you"]
            if hit.get("trade") is not None:
                c["trade"] = hit["trade"]
            if hit.get("online") is not None:
                c["online"] = hit["online"]
            if hit.get("boom") is not None:
                c["boom"] = hit["boom"]
            if hit.get("kefu"):
                c["kefu"] = hit["kefu"]
    return {"used": True, "ds": ds, "matched": matched, "total": total, "rows": kept}


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
    member_ds = max(ds_set) if ds_set else now.strftime("%Y-%m-%d")

    # 指标刷新：客户清单（谁在跟进）来自 xlsx，指标（优爆品/交易品）优先取平台盘点件
    inv_path = None
    if "--no-inventory" not in sys.argv:
        for i, a in enumerate(sys.argv):
            if a == "--inventory" and i + 1 < len(sys.argv):
                inv_path = sys.argv[i + 1]
        inv_path = inv_path or INVENTORY_SRC
    inv = apply_inventory(persons, inv_path)

    if inv.get("used") and inv.get("matched"):
        d = inv["ds"]
        inv["ds_iso"] = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        # 指标日以平台盘点分区为准（客户清单日可能更早，但不能拿旧日期给新指标贴标签）
        data_ds = max(member_ds, inv["ds_iso"])
    else:
        data_ds = member_ds

    # 指标被刷新后重算每人合计
    for p in persons:
        p["you"] = sum(c["you"] or 0 for c in p["customers"])
        p["trade"] = sum(c["trade"] or 0 for c in p["customers"])
        p["boom"] = sum(c["boom"] or 0 for c in p["customers"])
        p["online"] = sum(c["online"] or 0 for c in p["customers"])

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
    day_gap = None
    if prev_ds:
        day_gap = (dt.date.fromisoformat(data_ds) - dt.date.fromisoformat(prev_ds)).days
    # 本月基准就是当天时，本月新增没有独立基准 -> None（不拿 0 顶）
    month_snap = snaps.get(month_base_ds) if month_base_ds and month_base_ds != data_ds else None

    for p in persons:
        for c in p["customers"]:
            # 平台无商品数据的客户（指标仍沿用旧件）不参与新增，避免拿 0 冒充「没变化」
            known = (not inv.get("used")) or c.get("src") == "inventory"
            c["day_add"] = delta(c["key"], "you", prev_snap) if known else None
            c["month_add"] = delta(c["key"], "you", month_snap) if known else None

    # 汇总：只对有值项求和；有客户缺数时打 partial 标（前端加 * 并说明）
    for p in persons:
        for f in ("day_add", "month_add"):
            vals = [c[f] for c in p["customers"] if c[f] is not None]
            p[f] = sum(vals) if vals else None
            p[f + "_partial"] = len(vals) < len(p["customers"])

    persons.sort(key=lambda x: (-(x["you"] or 0), x["name"]))

    home, home_src = load_home()

    board = {
        "meta": {
            "data_ds": data_ds,
            "member_ds": member_ds,
            "inventory": inv,
            "captured_at": captured_at,
            "month": month,
            "prev_ds": prev_ds,
            "day_gap": day_gap,
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
    print(f"上一数据日 {prev_ds or '无'}（间隔 {day_gap} 天）| 本月首个数据日 {month_base_ds}"
          f" | 快照 {len(dates)} 份")
    print("客户清单来自 xlsx 数据日", member_ds,
          "| 指标刷新：", inv.get("ds"), f"{inv.get('matched')}/{inv.get('total')}" if inv.get("used") else inv.get("reason"))
    print("首页数据源:", home_src)
    for p in persons:
        print(f"  {p['name']}: 客户{p['count']} 优爆品{p['you']:.0f} 交易品{p['trade']:.0f}"
              f" 本月新增{p['month_add']} 今日新增{p['day_add']}")
    print("已生成", OUT_HTML, os.path.getsize(OUT_HTML), "B")


if __name__ == "__main__":
    main()
