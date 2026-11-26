# -*- coding: utf-8 -*-
"""新大屏B（优爆品与市场热卖品）—— 名单与口径配置。

名单完全来自业务提供的《优爆品与市场热卖品数据.xlsx》四个 sheet，
团队归属同表；不在本文件里的名字一律不上屏。
"""

REPO = "PengyuanBruce/youpin-customer-board"
REPO_DIR = r"C:\Users\admin\Desktop\个人优爆品客户跟进"
RAW_DIR = r"D:\AWB\公司数据管理大屏Agent\project\build\compass_raw"

# Ⅰ 优爆品 · 拍档销售（21 人，Excel sheet1）
TEAMS = [
    ("野狼战队", ["汤子豪", "漆螯童", "李怡萍", "邓晓东", "牛群", "程碧瑶"]),
    ("雷霆战队", ["陈建国", "王子豪", "夏锐", "高国权", "谢承杰", "王金国", "郭龙耀", "库亚涛"]),
    ("头狼战队", ["李彬", "蒋汶桃", "张伟志", "何尧玲", "舒媛丹", "李金城", "王钢"]),
]

# Ⅱ 优爆品 · 拍档客服（11 人，Excel sheet2）
# 2026-11-25 用户要求去掉「陆晓菲」：平台 11-22 起不再返回她的行（客户已改派），
#   留在表里只会是一行 `--`，故从名单移除；Ⅳ 热卖客服沿用同一份名单。
KEFU = ["陈宇", "曹丽", "方琼", "罗洋清", "李岩", "谭美玲", "庞婷婷", "农路源", "苏梓梦", "古慧华", "汤青芬"]

# Ⅲ 市场热卖品 · 拍档销售（21 人 = Excel sheet3 的 17 人 + 业务补充的野狼 4 人）
# 2026-11-20 补：汤子豪 / 漆螯童 / 李怡萍 / 邓晓东（源表 hot-sales-sales.json 里本就有数据）
HOT_SALES_ORDER = ["汤子豪", "漆螯童", "李怡萍", "邓晓东",
                   "牛群", "程碧瑶", "陈建国", "王子豪", "夏锐", "高国权", "谢承杰",
                   "王金国", "郭龙耀", "库亚涛", "李彬", "蒋汶桃", "张伟志", "何尧玲",
                   "舒媛丹", "李金城", "王钢"] + ["王凡", "罗金填", "文一锦"]

# 不归属任何团队的销售（2026-11-26 用户要求）：只把数据并进 Ⅰ/Ⅲ 两张表，
#   团队列显示「—」，不参与任何战队的合计/排序分组，排在表尾。
EXTRA_SALES = ["王凡", "罗金填", "文一锦"]

# Ⅳ 市场热卖品 · 拍档客服（11 人，沿用客服名单）
HOT_KEFU = list(KEFU)

# 平台把个别人的「当季度累计目标」置空时的承接值（仅这些人在源表为 null 时生效）。
# 汤青芬：2026-11-20 及更早一直是 5,415，平台自 11-23 现网起回溯置空；
#   2026-11-26 用户指出「目标不对」后按最后可用值沿用，页面底部有口径说明。
CARRY_TARGETS = {"汤青芬": 5415.0}


def team_of(name):
    """团队归属；不属于任何战队的人返回「—」（2026-11-26：王凡/罗金填/文一锦）。"""
    for team, members in TEAMS:
        if name in members:
            return team
    return "—"


SALES_ORDER = [n for _, members in TEAMS for n in members] + EXTRA_SALES

# ---------------- 列映射（源文件列索引） ----------------
# youpin3-sales-full.json：29 列
YPS = {"name": 4, "count": 8, "target": 15, "pct": 16, "p4p": 23, "ds": 0}
# youpin3-kefu-full.json：30 列（多一个 partner_id）
YPK = {"name": 5, "count": 10, "target": 16, "pct": 17, "p4p": 24, "ds": 0}
# hot-sales-sales.json：19 列
HSS = {"name": 1, "target": 2, "count": 3, "pct": 4, "p4p": 15, "ds": 0}
# hot-sales-kefu.json：18 列
HSK = {"name": 1, "target": 2, "count": 3, "pct": 4, "p4p": 15, "ds": 0}

FILES = {
    "you_sales": ("youpin3-sales-full.json", YPS),
    "you_kefu": ("youpin3-kefu-full.json", YPK),
    "hot_sales": ("hot-sales-sales.json", HSS),
    "hot_kefu": ("hot-sales-kefu.json", HSK),
}
