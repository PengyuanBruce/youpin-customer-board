"""用公司大屏保留的历史盘点件重建快照（修历史串号问题）。

背景：2026-11-05 之前构建时，同一销售下同名多账号客户被合并到同一个账号，
历史快照里那些行的值是错的。平台盘点件按天留了备份
（`compass_raw/_prev/<日期>/audit-full-customers.json`），可以按账号重新分配值，
把 11-02 / 11-03 / 11-04 的快照修正为账号级正确值。

用法：python build\\backfill_snapshots.py [--apply]
不带 --apply 只打印将要重写的快照与差异。
"""

import copy
import glob
import json
import os
import sys

import build_board as bb

BASE = bb.BASE
PREV_ROOTS = os.path.join(os.path.dirname(bb.INVENTORY_SRC), "_prev")
APPLY = "--apply" in sys.argv


def load_members():
    files = [f for f in sorted(glob.glob(os.path.join(BASE, "*.xlsx")))
             if not os.path.basename(f).startswith("~" + chr(36))]
    persons = []
    for f in files:
        ds, title, rows = bb.read_workbook(f)
        persons.append({
            "name": os.path.splitext(os.path.basename(f))[0],
            "file": os.path.basename(f),
            "ds": ds,
            "title": title,
            "count": len(rows),
            "you": sum(r["you"] or 0 for r in rows),
            "trade": sum(r["trade"] or 0 for r in rows),
            "boom": sum(r["boom"] or 0 for r in rows),
            "online": sum(r["online"] or 0 for r in rows),
            "customers": rows,
        })
    return persons


def main():
    persons = load_members()
    paths = sorted(glob.glob(os.path.join(PREV_ROOTS, "*", "audit-full-customers.json")))
    if not paths:
        raise SystemExit("没找到历史盘点件")
    for path in paths:
        ps = copy.deepcopy(persons)
        inv = bb.apply_inventory(ps, path, None)
        if not inv.get("used"):
            print("跳过", path, inv)
            continue
        d = inv["ds"]
        ds_iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        for p in ps:
            p["you"] = sum(c["you"] or 0 for c in p["customers"])
            p["trade"] = sum(c["trade"] or 0 for c in p["customers"])
            p["boom"] = sum(c["boom"] or 0 for c in p["customers"])
            p["online"] = sum(c["online"] or 0 for c in p["customers"])
        customers = [c for p in ps for c in p["customers"]]

        old_path = os.path.join(bb.SNAP_DIR, f"customers-{ds_iso}.json")
        old_sum = None
        if os.path.exists(old_path):
            old = json.load(open(old_path, encoding="utf-8"))
            old_sum = sum((v.get("you") or 0) for v in old["customers"].values())
        new_sum = sum(c["you"] or 0 for c in customers)
        print(f"{ds_iso}  matched {inv['matched']}/{inv['total']}  优爆品合计 "
              f"{old_sum if old_sum is not None else '-'} -> {new_sum}")
        if APPLY:
            bb.write_snapshot(ds_iso, ps, customers, "backfill " + inv["ds"], "inventory")
    if not APPLY:
        print("\n（预览模式，未写盘；加 --apply 生效）")


if __name__ == "__main__":
    main()
