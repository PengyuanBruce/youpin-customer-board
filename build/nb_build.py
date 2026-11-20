# -*- coding: utf-8 -*-
"""新大屏B：优爆品 & 市场热卖品（四板块）

数据源（均由大屏A 每日采集落在 compass_raw）：
  优爆品-销售  youpin3-sales-full.json
  优爆品-客服  youpin3-kefu-full.json
  热卖品-销售  hot-sales-sales.json
  热卖品-客服  hot-sales-kefu.json

产出：build/nb_board.json + index.html（四板块，一个 sheet 一个板块）。
周增长：按「上周一~周五净增」口径，用本项目自有的日更历史（nb_history.json）计算；
        基线缺失时显示 --，绝不用别的口径顶替。
"""

import json
import os
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nb_config as C  # noqa: E402

HISTORY = os.path.join(HERE, "nb_history.json")


# ---------------- 基础工具 ----------------
def norm(s):
    return (s or "").replace("\u3000", "").strip()


def num(v):
    if v is None or v == "" or v == "null":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pct_of(count, target):
    if count is None or not target:
        return None
    return count / target * 100


def load_value(fname):
    p = os.path.join(C.RAW_DIR, fname)
    if not os.path.exists(p):
        return None, {}
    with open(p, "r", encoding="utf-8") as f:
        d = json.load(f)
    v = d["response"]["data"]["value"]
    return d, v


def parse_section(key):
    """返回 (ds, {name: {count,target,pct,p4p}})。pct 统一换算成百分数。"""
    fname, idx = C.FILES[key]
    d, v = load_value(fname)
    if not v:
        return None, {}
    rows = v.get("values") or []
    out = {}
    ds = None
    for r in rows:
        name = norm(r[idx["name"]].get("v"))
        if not name:
            continue
        pct = num(r[idx["pct"]].get("v"))
        if pct is not None and pct <= 1.5:
            pct *= 100
        out[name] = {
            "count": num(r[idx["count"]].get("v")),
            "target": num(r[idx["target"]].get("v")),
            "pct": pct,
            "p4p": num(r[idx["p4p"]].get("v")),
        }
        if ds is None:
            ds = (r[idx["ds"]].get("v") if "ds" in idx else (v.get("params") or {}).get("ds"))
    if ds is None:
        ds = (d.get("meta") or {}).get("ds")
    if isinstance(ds, str):
        ds = ds.strip().split(" ")[0].replace("-", "").replace("/", "")
        if len(ds) >= 8 and ds[:8].isdigit():
            ds = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
    return ds, out


# ---------------- 历史（周增长基线） ----------------
def load_history():
    if not os.path.exists(HISTORY):
        return {}
    with open(HISTORY, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(h):
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def record(h, ds, key, data):
    if not ds:
        return
    slot = h.setdefault(ds, {}).setdefault(key, {})
    for name, m in data.items():
        slot[name] = {"count": m["count"], "p4p": m["p4p"]}


def last_week_window(ds):
    """上周一~周五 与基线（上周日）。ds 为字符串 YYYY-MM-DD。"""
    d = datetime.strptime(ds, "%Y-%m-%d").date()
    this_monday = d - timedelta(days=d.weekday())
    mon = this_monday - timedelta(days=7)
    fri = mon + timedelta(days=4)
    base = mon - timedelta(days=1)
    return mon, fri, base


def week_delta(h, ds, key, field):
    """返回 ({name: delta}, meta)。基线缺失返回 ({}, meta with short_by=None)。"""
    if not ds:
        return {}, {"mon": None, "fri": None, "base": None, "short_by": None}
    mon, fri, base = last_week_window(ds)
    hb = h.get(base.isoformat(), {}).get(key)
    if not hb:
        return {}, {"mon": mon.isoformat(), "fri": fri.isoformat(),
                    "base": base.isoformat(), "short_by": None, "status": "基线缺失"}
    # 末端：优先周五，缺则回退到窗口内更早的可用日
    end = None
    short = 0
    for back in range(0, 5):
        cand = fri - timedelta(days=back)
        if cand < mon:
            break
        if h.get(cand.isoformat(), {}).get(key):
            end = cand
            short = back
            break
    if end is None:
        return {}, {"mon": mon.isoformat(), "fri": fri.isoformat(),
                    "base": base.isoformat(), "short_by": None, "status": "末端缺失"}
    he = h[end.isoformat()][key]
    out = {}
    for name, cur in he.items():
        b = (hb.get(name) or {}).get(field)
        c = (cur or {}).get(field)
        if b is None or c is None:
            continue
        out[name] = c - b
    return out, {"mon": mon.isoformat(), "fri": fri.isoformat(),
                 "base": base.isoformat(), "end": end.isoformat(),
                 "short_by": short, "status": "ok"}


# ---------------- 组装 ----------------
def person_row(name, m, delta_c, delta_p):
    m = m or {}
    return {
        "name": name,
        "count": m.get("count"),
        "target": m.get("target"),
        "pct": m.get("pct") if m.get("pct") is not None else pct_of(m.get("count"), m.get("target")),
        "p4p": m.get("p4p"),
        "week": delta_c.get(name) if delta_c else None,
        "p4p_week": delta_p.get(name) if delta_p else None,
        "missing": not m,
    }


def team_rollup(members, rows):
    tgt = cnt = p4p = 0.0
    have = 0
    weeks = []
    pweeks = []
    for r in rows:
        if r["target"] is not None:
            tgt += r["target"]
        if r["count"] is not None:
            cnt += r["count"]
            have += 1
        if r["p4p"] is not None:
            p4p += r["p4p"]
        weeks.append(r["week"])
        pweeks.append(r["p4p_week"])
    return {
        "team": "",
        "members": len(members),
        "target": tgt if tgt else None,
        "count": cnt if have else None,
        "pct": pct_of(cnt, tgt) if tgt else None,
        "p4p": p4p if p4p else None,
        "week": sum(weeks) if weeks and all(w is not None for w in weeks) else None,
        "p4p_week": sum(pweeks) if pweeks and all(w is not None for w in pweeks) else None,
    }


def build_section(no, sid, title, ds, roster, data, order, delta_c, delta_p, win, note):
    rows = [person_row(n, data.get(n), delta_c, delta_p) for n in order]
    return {
        "no": no,
        "id": sid,
        "title": title,
        "ds": ds,
        "note": note,
        "rows": rows,
        "week_window": win,
    }


def main():
    h = load_history()
    warnings = []

    you_s_ds, you_s = parse_section("you_sales")
    you_k_ds, you_k = parse_section("you_kefu")
    hot_s_ds, hot_s = parse_section("hot_sales")
    hot_k_ds, hot_k = parse_section("hot_kefu")

    for key, data in (("you_sales", you_s), ("you_kefu", you_k),
                      ("hot_sales", hot_s), ("hot_kefu", hot_k)):
        ds = {"you_sales": you_s_ds, "you_kefu": you_k_ds,
              "hot_sales": hot_s_ds, "hot_kefu": hot_k_ds}[key]
        record(h, ds, key, data)

    def deltas(key, ds):
        c, w1 = week_delta(h, ds, key, "count")
        p, w2 = week_delta(h, ds, key, "p4p")
        return c, p, w1

    yc, yp, yw = deltas("you_sales", you_s_ds)
    kc, kp, kw = deltas("you_kefu", you_k_ds)
    sc, sp, sw = deltas("hot_sales", hot_s_ds)
    kkc, kkp, kw2 = deltas("hot_kefu", hot_k_ds)

    # ---- Ⅰ 优爆品 · 拍档销售 ----
    s1_rows = []
    team_blocks = []
    for team, members in C.TEAMS:
        tro = []
        for n in members:
            r = person_row(n, you_s.get(n), yc, yp)
            r["team"] = team
            s1_rows.append(r)
            tro.append(r)
            if r["missing"]:
                warnings.append(f"优爆品-销售：{n} 在源文件中没有数据")
        sub = team_rollup(members, tro)
        sub["team"] = team
        team_blocks.append(sub)

    sec1 = {
        "no": "Ⅰ", "id": "you-sales", "title": "优爆品 · 拍档销售",
        "ds": you_s_ds, "week_window": yw, "rows": s1_rows, "teams": team_blocks,
        "note": "优爆品目标/数/完成率/推P 取自优品3.0「拍档销售」表；周增长 = 上周一~周五净增。",
    }

    # ---- Ⅱ 优爆品 · 拍档客服 ----
    s2_rows = []
    for n in C.KEFU:
        r = person_row(n, you_k.get(n), kc, kp)
        r["team"] = "拍档客服"
        s2_rows.append(r)
        if r["missing"]:
            warnings.append(f"优爆品-客服：{n} 在源文件中没有数据")
    sec2 = {
        "no": "Ⅱ", "id": "you-kefu", "title": "优爆品 · 拍档客服",
        "ds": you_k_ds, "week_window": kw, "rows": s2_rows,
        "teams": [dict(team_rollup(C.KEFU, s2_rows), team="客服合计")],
        "note": "取自优品3.0「拍档客服」表；季度目标与完成率同表。",
    }

    # ---- Ⅲ 市场热卖品 · 拍档销售 ----
    s3_rows = []
    for n in C.HOT_SALES_ORDER:
        r = person_row(n, hot_s.get(n), sc, sp)
        r["team"] = C.team_of(n)
        s3_rows.append(r)
        if r["missing"]:
            warnings.append(f"市场热卖-销售：{n} 在源文件中没有数据")
    blocks3 = []
    for team, members in C.TEAMS:
        sub_rows = [r for r in s3_rows if r["team"] == team]
        if not sub_rows:
            continue
        sub = team_rollup([r["name"] for r in sub_rows], sub_rows)
        sub["team"] = team
        blocks3.append(sub)
    sec3 = {
        "no": "Ⅲ", "id": "hot-sales", "title": "市场热卖品 · 拍档销售",
        "ds": hot_s_ds, "week_window": sw, "rows": s3_rows, "teams": blocks3,
        "note": "热卖品数 = 当季度定招品数；推P = 曾经是市场热卖且当前是定招品且在 p4p 推广中的商品数。",
    }

    # ---- Ⅳ 市场热卖品 · 拍档客服 ----
    s4_rows = []
    for n in C.HOT_KEFU:
        r = person_row(n, hot_k.get(n), kkc, kkp)
        r["team"] = "拍档客服"
        s4_rows.append(r)
        if r["missing"]:
            warnings.append(f"市场热卖-客服：{n} 在源文件中没有数据")
    sec4 = {
        "no": "Ⅳ", "id": "hot-kefu", "title": "市场热卖品 · 拍档客服",
        "ds": hot_k_ds, "week_window": kw2, "rows": s4_rows,
        "teams": [dict(team_rollup(C.HOT_KEFU, s4_rows), team="客服合计")],
        "note": "取数口径同 Ⅲ，维度为拍档客服。",
    }

    board = {
        "meta": {
            "title": "优爆品 & 市场热卖品",
            "subtitle": "拍档销售 · 拍档客服",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "you_ds": you_s_ds,
            "hot_sales_ds": hot_s_ds,
            "hot_kefu_ds": hot_k_ds,
            "week_rule": "周增长 = 上周一~周五净增（按数据日回溯；两端快照缺一即 --）",
            "sources": [
                "优品3.0 · 拍档销售", "优品3.0 · 拍档客服",
                "市场热卖定招 · 拍档销售", "市场热卖定招 · 拍档客服",
            ],
            "warnings": sorted(set(warnings)),
        },
        "sections": [sec1, sec2, sec3, sec4],
    }

    save_history(h)

    out_json = os.path.join(C.REPO_DIR, "board.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(board, f, ensure_ascii=False, separators=(",", ":"))

    # 汇总（供自检/汇报）
    def total(rows, k):
        vals = [r[k] for r in rows if r.get(k) is not None]
        return sum(vals) if vals else None

    print(f"优爆品 ds={you_s_ds}  热卖-销售 ds={hot_s_ds}  热卖-客服 ds={hot_k_ds}")
    print(f"Ⅰ 优爆品-销售：{len(s1_rows)} 人  数合计 {total(s1_rows,'count')}  目标合计 {total(s1_rows,'target')}")
    print(f"Ⅱ 优爆品-客服：{len(s2_rows)} 人  数合计 {total(s2_rows,'count')}  目标合计 {total(s2_rows,'target')}")
    print(f"Ⅲ 热卖-销售：{len(s3_rows)} 人  数合计 {total(s3_rows,'count')}  目标合计 {total(s3_rows,'target')}")
    print(f"Ⅳ 热卖-客服：{len(s4_rows)} 人  数合计 {total(s4_rows,'count')}  目标合计 {total(s4_rows,'target')}")
    print("周增长基线：", "有" if yc else "无（显示 --）")
    if warnings:
        print("告警：", "；".join(sorted(set(warnings))))

    return board


if __name__ == "__main__":
    b = main()
    # 渲染页面
    import nb_render
    html = nb_render.render(b)
    with open(os.path.join(C.REPO_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成 board.json 与 index.html")
