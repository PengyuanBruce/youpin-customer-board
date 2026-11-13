"""看板数据核心：读表 → 取平台指标 → 快照 → 做差。

表结构（2026-11-08 起）：每人一个 xlsx，至少含「客户名称 / 客户类型标签 / 客服」；
旧版 18 列明细（含 序号/优爆品数/交易品数）仍兼容。
指标：平台「全量客户盘点」采集件的某个 stat_date 分区，按 (拍档销售, 客户名) 匹配；
同名多账号用候选分配，优先用上一期快照或表格自带数值做锚。
"""

import copy
import datetime as dt
import glob
import json
import os
import re

import openpyxl

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(BASE, "snapshots")
RAW_DIR = r"D:\AWB\公司数据管理大屏Agent\project\build\compass_raw"
INV_CURRENT = os.path.join(RAW_DIR, "audit-full-customers.json")
HOME_SRC = r"D:\AWB\公司数据管理大屏Agent\project\build\data_cur.json"
HOME_CACHE = os.path.join(BASE, "build", "home_cache.json")


def norm(s):
    s = str(s or "").strip().replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", s)


def txt(v):
    return "" if v is None else str(v).strip()


def num(v):
    if v is None or v == "" or v == "-":
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def read_table(path):
    """返回 {'name','customers':[{name,ctype,kefu,key}],'title'}；兼容 3 列与旧 18 列。"""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    title = txt(rows[0][0]) if rows and rows[0] else ""
    hi = None
    for i, r in enumerate(rows[:8]):
        if "客户名称" in [txt(c) for c in r]:
            hi = i
            break
    if hi is None:
        raise ValueError(f"{os.path.basename(path)}: 找不到「客户名称」表头")
    hdr = [txt(c) for c in rows[hi]]

    def col(*names):
        for n in names:
            if n in hdr:
                return hdr.index(n)
        return -1

    c_name = col("客户名称")
    c_type = col("客户类型标签", "客户类型")
    c_kefu = col("客服", "拍档客服")
    occ = {}
    customers = []
    for r in rows[hi + 1:]:
        if not r or c_name < 0 or not r[c_name]:
            continue
        name = txt(r[c_name])
        occ[name] = occ.get(name, 0) + 1
        customers.append({
            "name": name,
            "ctype": txt(r[c_type]) if c_type >= 0 else "",
            "kefu": txt(r[c_kefu]) if c_kefu >= 0 else "",
            "key": f"{name}#{occ[name]}",
        })
    return {"name": os.path.splitext(os.path.basename(path))[0],
            "title": title, "customers": customers}


def load_inventory(path):
    """返回 (stat_date_iso, {(销售, 客户): [候选...]}, 行数)。"""
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    rows = []
    for item in d.get("rawResponses") or []:
        body = item.get("data") or {}
        if isinstance(body.get("data"), list):
            rows.extend(body["data"])
    stats = sorted({txt(r.get("stat_date")) for r in rows if r.get("stat_date")})
    ds = stats[-1] if stats else ""
    table = {}
    for r in rows:
        if txt(r.get("stat_date")) != ds:
            continue
        sales = norm(r.get("partner_user_sales_name"))
        name = norm(r.get("cust_name_cn"))
        item = {
            "ali_id": txt(r.get("ali_id")),
            "you": num(r.get("youbaopin_prd_cnt")),
            "trade": num(r.get("jiaoyi_prd_cnt")),
            "sales": txt(r.get("partner_user_sales_name")),
        }
        table.setdefault((sales, name), []).append(item)
        # 兜底索引：客户换销售后仍能按名字找到（表里记的是老销售）
        table.setdefault(("*", name), []).append(item)
    iso = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}" if len(ds) == 8 else ds
    return iso, table, len(rows)


def partitions():
    """所有可用盘点分区（含历史备份），按数据日升序 [(iso, path)]。"""
    out = {}
    for p in glob.glob(os.path.join(RAW_DIR, "_prev", "*", "audit-full-customers.json")) + [INV_CURRENT]:
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            stat = ""
            for item in d.get("rawResponses") or []:
                body = item.get("data") or {}
                lst = body.get("data")
                if isinstance(lst, list) and lst:
                    stat = txt(lst[0].get("stat_date"))
                    break
            if len(stat) == 8:
                iso = f"{stat[:4]}-{stat[4:6]}-{stat[6:8]}"
                out[iso] = p
        except Exception:
            continue
    return sorted(out.items())


def load_first_year_anchor():
    """客群/首次年.xlsx：客户名 → 11-01 的优爆品数，用作同名多账号分配时的稳定锚。"""
    path = os.path.join(BASE, "客群", "首次年.xlsx")
    if not os.path.exists(path):
        return {}
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [txt(c) for c in rows[0]]
    if "客户名称" not in hdr or "优爆品数" not in hdr:
        return {}
    ni, ui = hdr.index("客户名称"), hdr.index("优爆品数")
    out = {}
    for r in rows[1:]:
        if not r or not r[ni]:
            continue
        v = num(r[ui])
        out.setdefault(norm(r[ni]), []).append(v)
    return out


def _dist(row, hit, prior):
    if hit.get("you") is None:
        return 10 ** 6
    old = ((prior or {}).get("customers") or {}).get(row["key"]) or {}
    a = old.get("you")
    if a is None:
        a = row.get("xlsx_you")
        b = row.get("xlsx_trade") or 0
    else:
        b = old.get("trade") or 0
    if a is None:
        return 10 ** 6
    return abs(hit["you"] - a) + abs((hit.get("trade") or 0) - b)


def _assign(rows, cands, prior):
    """把候选账号分给同名的若干行；返回 [(row, hit or None)]。"""
    if not cands:
        return [(r, None) for r in rows]
    if len(cands) == 1:
        return [(r, cands[0]) for r in rows]
    if len(rows) == 1:
        return [(rows[0], min(cands, key=lambda h: _dist(rows[0], h, prior)))]
    from itertools import permutations
    best, best_cost = None, None
    for perm in permutations(cands, len(rows)) if len(cands) >= len(rows) else []:
        cost = sum(_dist(r, h, prior) for r, h in zip(rows, perm))
        if best_cost is None or cost < best_cost:
            best, best_cost = perm, cost
    if best is None:  # 候选比行少，按序分配
        best = tuple(cands[i % len(cands)] for i in range(len(rows)))
    return list(zip(rows, best))


def assign(persons, table, prior=None):
    matched = total = 0
    for p in persons:
        groups = {}
        for c in p["customers"]:
            c.setdefault("xlsx_you", c.get("you"))
            c.setdefault("xlsx_trade", c.get("trade"))
            groups.setdefault(c["name"], []).append(c)
        for name, rows in groups.items():
            cands = table.get((norm(p["name"]), norm(name))) or []
            fallback = False
            if not cands:
                # 客户可能只是换了销售（表里仍记着老销售），按名字兜底找一次
                cands = table.get(("*", norm(name))) or []
                fallback = bool(cands)
            total += len(rows)
            if len(rows) == 1 and len(cands) > 1:
                # 一个客户名对应平台多个账号（同公司多店）：合并计，稳定且不猜
                c = rows[0]
                matched += 1
                ys = [h["you"] for h in cands if h.get("you") is not None]
                ts = [h["trade"] for h in cands if h.get("trade") is not None]
                c["you"] = sum(ys) if ys else None
                c["trade"] = sum(ts) if ts else None
                c["ali_id"] = "+".join(h["ali_id"] for h in cands if h["ali_id"])
                c["agg"] = len(cands)
                c["src"] = "inv" if c["you"] is not None else "noval"
                if fallback:
                    c["owner"] = cands[0].get("sales") or ""
                continue
            for c, hit in _assign(rows, cands, prior):
                if hit is None:
                    c["src"] = "missing"
                    continue
                matched += 1
                if hit.get("you") is None:
                    c["src"] = "noval"
                    continue
                c["src"] = "inv"
                c["ali_id"] = hit["ali_id"]
                c["you"] = hit["you"]
                c["trade"] = hit["trade"]
                if fallback:
                    c["owner"] = hit.get("sales") or ""
                if len(cands) > 1:
                    c["ambig"] = True
        p["you"] = sum(c.get("you") or 0 for c in p["customers"])
        p["trade"] = sum(c.get("trade") or 0 for c in p["customers"])
        p["count"] = len(p["customers"])
    return {"matched": matched, "total": total}


def write_snapshot(ds, persons, captured_at, source="inventory"):
    cust = {}
    ppl = {}
    for p in persons:
        ppl[p["name"]] = {"you": p.get("you"), "trade": p.get("trade"), "count": p["count"]}
        for c in p["customers"]:
            cust[c["key"]] = {"name": c["name"], "you": c.get("you"),
                              "trade": c.get("trade"), "ali_id": c.get("ali_id")}
    payload = {"ds": ds, "captured_at": captured_at, "source": source,
               "persons": ppl, "customers": cust}
    os.makedirs(SNAP_DIR, exist_ok=True)
    path = os.path.join(SNAP_DIR, f"customers-{ds}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    return path


def load_snapshots():
    out = {}
    for p in sorted(glob.glob(os.path.join(SNAP_DIR, "customers-*.json"))):
        ds = os.path.basename(p)[len("customers-"):-len(".json")]
        try:
            with open(p, encoding="utf-8") as fh:
                out[ds] = json.load(fh)
        except Exception:
            continue
    return out


def load_members():
    persons = []
    for path in sorted(glob.glob(os.path.join(BASE, "*.xlsx"))):
        if os.path.basename(path).startswith("~" + chr(36)):
            continue
        persons.append(read_table(path))
    return persons


def load_home():
    home = {}
    # BOARD_HOME_SOURCE=cache：忽略上游 data_cur（例如挑战赛基线被上游跑坏时），
    # 直接用上一版缓存，避免把残缺首页发上线。
    if os.environ.get("BOARD_HOME_SOURCE") == "cache":
        if os.path.exists(HOME_CACHE):
            with open(HOME_CACHE, encoding="utf-8") as fh:
                return json.load(fh)
        return {}
    if os.path.exists(HOME_SRC):
        with open(HOME_SRC, encoding="utf-8") as fh:
            d = json.load(fh)
        # 首页只保留「优爆品总览」；挑战赛板块已整体下线，相关数据不再随页面下发
        home = {k: d.get(k) for k in ("goods",)}
        home["update"] = d.get("update_time")
        with open(HOME_CACHE, "w", encoding="utf-8") as fh:
            json.dump(home, fh, ensure_ascii=False)
        return home
    if os.path.exists(HOME_CACHE):
        with open(HOME_CACHE, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def main():
    persons = load_members()
    anchors = load_first_year_anchor()
    for p in persons:
        for c in p['customers']:
            vs = anchors.get(norm(c['name'])) or []
            if len(vs) == 1:
                c['xlsx_you'] = vs[0]
    prior = load_snapshots()
    parts = partitions()
    if not parts:
        raise SystemExit("没有可用的盘点分区")

    # 逐分区算覆盖，挑「最新且覆盖达标」的分区做当期数据日
    evaluated = []
    base_anchor_ds = None
    for iso, path in parts:
        dsm, table, rows = load_inventory(path)
        ds = dsm or iso
        # 固定锚：始终用本表结构下最早那期快照，避免每天换锚导致同名多账号来回漂
        anchor = prior.get(base_anchor_ds) if base_anchor_ds else None
        if anchor is None:
            # 最早的分区没有「本期之前」的固定锚：退到磁盘上离它最近的一份更早快照。
            # 否则同名多账号会全成本并列 10**6、按候选顺序瞎分（序号 #1/#2 隔天对调）。
            earlier = [d for d in sorted(prior) if d < ds]
            if earlier:
                anchor = prior[earlier[-1]]
        ps = copy.deepcopy(persons)
        st = assign(ps, table, anchor)
        if base_anchor_ds is None:
            base_anchor_ds = ds
        cov = st["matched"] / max(1, st["total"])
        evaluated.append({"ds": ds, "path": path, "table": table, "rows": rows,
                          "persons": ps, "stat": st, "cov": cov})

    good = [e for e in evaluated if e["cov"] >= 0.95]
    chosen = good[-1] if good else max(evaluated, key=lambda e: e["cov"])
    stale = [e for e in evaluated if e["ds"] > chosen["ds"]]

    # 用选中的成员/分配结果重建该分区及各历史分区快照
    persons = chosen["persons"]
    for e in evaluated:
        # 覆盖不足的分区不落快照：否则明天会拿它当「昨天」算差，把残缺数带进来
        if e is not chosen and e["cov"] < 0.95:
            continue
        captures = prior.get(e["ds"], {}).get("captured_at") or ""
        write_snapshot(e["ds"], e["persons"], captures or "", "inventory")

    snaps = load_snapshots()
    data_ds = chosen["ds"]
    all_ds = sorted(snaps)
    prev_ds = max([d for d in all_ds if d < data_ds], default=None)
    prev_snap = snaps.get(prev_ds)
    month = data_ds[:7]
    month_bases = [d for d in all_ds if d.startswith(month)]
    # 本月基准：优先取覆盖当前清单 ≥90% 的最早一份（新清单首日之前的老快照对这批客户没有基准）
    cur_keys = {c["key"] for p in persons for c in p["customers"]}
    month_base_ds = month_bases[0] if month_bases else None
    for d in month_bases:
        have = {k for k in (snaps[d].get("customers") or {}) if k in cur_keys}
        if len(have) / max(1, len(cur_keys)) >= 0.9:
            month_base_ds = d
            break
    month_snap = snaps.get(month_base_ds)
    day_gap = None
    if prev_ds:
        day_gap = (dt.date.fromisoformat(data_ds) - dt.date.fromisoformat(prev_ds)).days

    for p in persons:
        for c in p["customers"]:
            known = c.get("src") == "inv"
            if known and c.get("ambig") and prev_snap:
                old = (prev_snap.get("customers") or {}).get(c["key"]) or {}
                known = old.get("ali_id") == c.get("ali_id")
            old_day = ((prev_snap or {}).get("customers") or {}).get(c["key"]) or {}
            old_mon = ((month_snap or {}).get("customers") or {}).get(c["key"]) or {}
            c["day_add"] = (None if not known or old_day.get("you") is None
                            else c["you"] - old_day["you"])
            c["month_add"] = (None if not known or old_mon.get("you") is None
                              else c["you"] - old_mon["you"])
        for f in ("day_add", "month_add"):
            vals = [c[f] for c in p["customers"] if c[f] is not None]
            p[f] = sum(vals) if vals else None
            p[f + "_excluded"] = p["count"] - len(vals)

    captured_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    board = {
        "meta": {
            "data_ds": data_ds,
            "prev_ds": prev_ds,
            "day_gap": day_gap,
            "month_base_ds": month_base_ds,
            "snapshot_dates": all_ds,
            "captured_at": captured_at,
            "person_count": len(persons),
            "customer_count": sum(p["count"] for p in persons),
            "inventory": {
                "used": True,
                "ds": data_ds.replace("-", ""),
                "matched": chosen["stat"]["matched"],
                "total": chosen["stat"]["total"],
                "coverage": round(chosen["cov"], 4),
                "rows": chosen["rows"],
                "stale_partitions": [{"ds": e["ds"], "rows": e["rows"],
                                      "coverage": round(e["cov"], 4)} for e in stale],
            },
        },
        "persons": sorted(persons, key=lambda p: -(p.get("you") or 0)),
        "home": load_home(),
    }
    with open(os.path.join(BASE, "board.json"), "w", encoding="utf-8") as fh:
        json.dump(board, fh, ensure_ascii=False, indent=1)

    tpl = os.path.join(BASE, "build", "template.html")
    with open(tpl, encoding="utf-8") as fh:
        html = fh.read().replace("/*__BOARD__*/null", json.dumps(board, ensure_ascii=False))
    with open(os.path.join(BASE, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"数据日 {data_ds} | 上期 {prev_ds}（间隔 {day_gap} 天）| 本月基准 {month_base_ds}")
    print(f"销售 {len(persons)} 人 | 客户 {board['meta']['customer_count']} 家 | "
          f"匹配 {chosen['stat']['matched']}/{chosen['stat']['total']} ({chosen['cov']:.1%})")
    print(f"优爆品 {sum(p['you'] or 0 for p in persons):.0f} | 交易品 {sum(p['trade'] or 0 for p in persons):.0f}")
    if stale:
        print("被跳过的分区（覆盖不足）：", [(e["ds"], e["rows"], round(e["cov"], 3)) for e in stale])


if __name__ == "__main__":
    main()
