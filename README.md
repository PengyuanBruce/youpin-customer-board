# 客户优爆品数据看板

首页 = 公司口径「优爆品总览 + 优爆品挑战赛」；顶部导航 = 工作区每份销售表的文件名（当前 23 位销售）；子页 = 该销售名下客户的 **客户类型 / 当前优爆品数 / 总交易品数 / 本月新增 / 今日新增**。

线上地址：https://pengyuanbruce.github.io/youpin-customer-board/

## 数据来源

| 部分 | 来源 | 说明 |
|---|---|---|
| 导航与客户清单 | 工作区各销售的 `姓名.xlsx` | 至少含 `客户名称 / 客户类型标签 / 客服`；旧版 18 列明细也兼容。新增或删除表文件后重跑即自动增删导航 |
| 客户类型标签 | 同上，取「客户类型标签」列 | 当前三档：自选 / 首次年 / 优质货盘P（不同颜色胶囊） |
| 客户指标 | 平台「全量客户盘点」`inventory/list.json` 采集件，取某个 `stat_date` 分区 | 当前优爆品数 = `youbaopin_prd_cnt`（含其中爆品）；总交易品数 = `jiaoyi_prd_cnt` |
| 今日新增 | 快照做差 | 当前数据日 − 上一可用数据日（同客户） |
| 本月新增 | 快照做差 | 当前数据日 − 本轮清单首个可用数据日 |
| 首页优爆品 / 挑战赛 | 公司大屏同源 `data_cur.json` | 平台口径，与子页客户口径不同，不要跨页相加 |

采集件默认路径：`D:\AWB\公司数据管理大屏Agent\project\build\compass_raw\audit-full-customers.json`；
历史分区备份在 `compass_raw\_prev\<采集日>\`（脚本会自动扫，用于补历史快照与算差值）。

## 三条硬规则

1. **分区完整性守门**：某天分区若只返回部分客户（匹配覆盖 < 95%），自动回退到上一份完整分区，页脚用金色说明当前用的是哪一份。例：11-07 分区只返回 7,073 行（覆盖 82.5%），本页沿用 11-06。
2. **同名多账号**：同一销售名下同名客户对应平台多个国际站账号时，只有一个客户行就**按合计**计（稳定、不猜）；表里出现多行同名时才按上期值分配账号，并把 `ali_id` 写进快照固定下来。
3. **缺基准一律 `--`**：新加入清单的客户、平台无商品数据的客户，相关单元格显示 `--`，不拿 0 或旧值顶替。

## 每日更新

```powershell
cd C:\Users\admin\Desktop\个人优爆品客户跟进
python build\build_board.py      # 读表 + 取最新完整分区 + 写快照 + 生成 index.html
python build\push_github.py      # 只推有变化的文件
```

表有变化时，直接替换/新增同目录下的 `姓名.xlsx` 即可；导航按文件名自动生成。

## 目录

```
index.html                     自包含看板（数据内联，双击可开）
board.json                     页面数据
snapshots/customers-YYYY-MM-DD.json   每数据日客户级快照（含 ali_id）
build/build_board.py           构建脚本（core.py + core2.py + core3.py 拼装）
build/template.html            页面模板（占位符 /*__BOARD__*/null）
build/push_github.py           推送脚本（按 blob sha 只传变化文件）
build/backfill_snapshots.py    用 _prev 历史分区重建历史快照
_备份_精简前/                  改造前的 18 列明细备份（含平台序号）
客群/                          客群源表（首次年 / 优质货盘推P）
```
