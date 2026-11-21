<!-- auto-mas:i18n {"display_name_i18n":{"zh_CN":"SignFlow 抽卡记录","en":"SignFlow Gacha Records"},"description_i18n":{"zh_CN":"记录并展示抽卡结果，首批接入森空岛明日方舟，其他游戏按 tag 分页预留。","en":"Records and displays gacha results. Arknights via Skland first; other games are reserved behind per-game tabs."},"tags_i18n":{"zh_CN":["游戏社区","抽卡记录"],"en":["community","gacha"]}} -->

# SignFlow 抽卡记录

记录并展示抽卡结果，首批接入森空岛明日方舟，其他游戏按 tag 分页预留。

依赖核心插件「SignFlow 游戏社区」（服务名 `signflow.community`）；核心插件未启用时，本插件无法启用。

## 能力

- 读取：**只在用户点按钮时读一次**。不排定时任务、不在插件启用时预热、不在签到之后自动补拉；抽卡记录接口是风控敏感面，什么时候打由用户决定。
- 展示：按游戏、账号 UID、卡池筛选并分页，附每池累计抽数与距上次最高稀有度的抽数。
- 存档：本机 `data/signflow/gacha.json`，多游戏共用一份，靠记录自带的 `game` 字段区分。

## 刻意不做

自动刷新。读取请求会直接打在官方接口上，频繁拉取会触发风控；页面刷新一次列表只读本地存档，代价很低，交给用户手动点。

## 许可证

AGPL-3.0-or-later。第三方来源与许可见仓库根目录 [NOTICE.md](../../NOTICE.md)。
