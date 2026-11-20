<!-- auto-mas:i18n {"display_name_i18n":{"zh_CN":"SignFlow 日常便笺","en":"SignFlow Daily Notes"},"description_i18n":{"zh_CN":"在游戏社区页面补充展示各游戏日常便笺的完整内容，不干扰 AUTO-MAS 自带的活动展示。","en":"Shows the full in-game daily note content on the community page without interfering with AUTO-MAS activity feeds."},"tags_i18n":{"zh_CN":["游戏社区","日常便笺"],"en":["community","daily-note"]}} -->

# SignFlow 日常便笺

在游戏社区页面补充展示各游戏日常便笺的完整内容，不干扰 AUTO-MAS 自带的活动展示。

依赖核心插件「SignFlow 游戏社区」提供的服务 `signflow.activity`；核心插件未启用时，本插件无法启用。
本插件自己不开 HTTP 端点，查询由核心插件代发 `POST /api/plugin/signflow/notes/query`。

## 许可证

AGPL-3.0-or-later。第三方来源与许可见仓库根目录 [NOTICE.md](../../NOTICE.md)。
