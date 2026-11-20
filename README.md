# 优爆品 & 市场热卖品 · 拍档大屏

四个板块，一块一表，名单与列口径按业务方《优爆品与市场热卖品数据.xlsx》：

| 板块 | 内容 | 名单 | 源数据 |
|---|---|---|---|
| Ⅰ | 优爆品 · 拍档销售 | 21 人 / 3 个战队 | 优品3.0「拍档销售」 |
| Ⅱ | 优爆品 · 拍档客服 | 12 人 | 优品3.0「拍档客服」 |
| Ⅲ | 市场热卖品 · 拍档销售 | 17 人 | 市场热卖定招「拍档销售」 |
| Ⅳ | 市场热卖品 · 拍档客服 | 12 人 | 市场热卖定招「拍档客服」 |

## 每日更新

```powershell
cd C:\Users\admin\Desktop\个人优爆品客户跟进
python build\nb_build.py      # 读大屏A 的 compass_raw → board.json + index.html
python build\nb_push.py       # 推到 GitHub Pages
```

依赖大屏A 每日采集（`D:\AWB\公司数据管理大屏Agent\project\build\compass_raw`）：
`youpin3-sales-full.json`、`youpin3-kefu-full.json`、`hot-sales-sales.json`、`hot-sales-kefu.json`。

## 口径

- **优爆品目标 / 数 / 完成率 / 推P**：直接取优品3.0 对应维度表，不跨维度借用。
- **热卖品数** = 当季度定招品数；**热卖推P** = 曾经是市场热卖、当前是定招品且在 p4p 推广中的商品数。
- **周增长** = 上周一~周五净增（按数据日回溯，与 A 屏同口径），基线是本项目自有日更历史
  `build/nb_history.json`。两端快照缺一即显示 `--`，不做任何替代口径。
- 名单外的人不上屏；名单内但源文件缺数据的人显示 `未取到` 且各列 `--`。
