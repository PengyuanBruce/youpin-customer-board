# 客户优爆品数据看板

CGS 客户级优爆品跟进看板：首页放公司口径的「优爆品总览 + 优爆品挑战赛」，顶部导航按销售分页，逐客户看**当前优爆品数 / 总交易品数 / 本月新增 / 今日新增**。

线上地址：https://pengyuanbruce.github.io/youpin-customer-board/

## 数据来源与口径

| 项目 | 来源 | 口径 |
|---|---|---|
| 子页（销售分页） | 工作区每位销售的 `姓名.xlsx`（拍档系统 ▸ 客户管理 ▸ 拍档客户管理，CGS 客户优爆品明细） | 当前优爆品数 = 表格「优爆品数」（含其中爆品）；总交易品数 = 表格「交易品数」 |
| 今日新增 | 快照做差 | 当前数据日 − 上一数据日（同客户） |
| 本月新增 | 快照做差 | 当前数据日 − 本月首个数据日（同客户） |
| 首页优爆品 / 挑战赛 | 公司大屏同源 `data_cur.json`（平台口径） | 与子页的 CGS 口径不同，不要跨页相加 |

- **缺基准一律显示 `--`**，不用 0 或上月值顶替。
- 客户唯一键 = `序号|客户名称`（同名不同账号的客户不会被合并）。

## 目录

```
index.html                        自包含看板（数据内联，双击即开）
board.json                        页面数据（构建产物）
snapshots/customers-YYYY-MM-DD.json  每数据日一份客户级快照，用于算新增
build/build_board.py              解析 xlsx → 快照 → board.json → index.html
build/template.html               页面骨架（CSS/JS，占位符 /*__BOARD__*/null）
build/push_github.py              推送 index.html / board.json / snapshots 到本仓库
build/home_cache.json             首页数据缓存（读不到公司大屏时兜底）
```

## 每日更新

1. 把当天导出的 `姓名.xlsx` 覆盖到工作目录（文件名保持人名不变）；
2. 构建：

```powershell
cd C:\Users\admin\Desktop\个人优爆品客户跟进
python build\build_board.py
```

3. 推送（只发有变化的文件）：

```powershell
python build\push_github.py
```

推送后 GitHub Pages 约 10 分钟（`Cache-Control: max-age=600`）内刷新；要看是否已生效，用提交 SHA 取 raw 内容核对，不要只看首页缓存。
