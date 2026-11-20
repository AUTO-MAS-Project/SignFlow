<!-- auto-mas:i18n { "display_name_i18n": { "zh_CN": "SignFlow 游戏社区", "en": "SignFlow Community" }, "description_i18n": { "zh_CN": "游戏社区核心插件：统一提供账号、平台协议与社区数据门面，供签到、日常便笺、抽卡记录与 Token 插件复用。", "en": "Core plugin for game communities: accounts, platform protocols and the community data facade reused by sign-in, daily notes, gacha records and token plugins." }, "tags_i18n": { "zh_CN": ["游戏社区", "核心", "账号"], "en": ["community", "core", "accounts"] } } -->

# SignFlow 游戏社区（核心插件）

SignFlow 是 AUTO-MAS 的游戏社区核心插件。它把账号、平台协议与社区数据访问收拢到一处，
供下面三个附属插件复用：

| 附属插件 | 发行包 | 作用 |
| --- | --- | --- |
| 日常便笺 | `signflow-notes` | 游戏内日常便笺（体力、委托、派遣等） |
| 抽卡记录 | `signflow-gacha` | 抽卡记录（首批仅明日方舟） |
| Token 获取 | `signflow-token` | 扫码 / 短信 / 账密获取社区 Token |

三个附属插件都通过服务名 `signflow.community` 依赖本插件；未启用本插件时它们无法启用。

## 安装

插件由 AUTO-MAS 插件市场安装，不需要手工拷贝文件。源码联调时把本仓库里的
包目录链接到 `AUTO-MAS/plugins/` 下即可：

```powershell
python scripts/link_dev.py --auto-mas D:\GitHub\AUTO-MAS
```

## 许可证

AGPL-3.0-or-later。第三方来源与许可见 [NOTICE.md](NOTICE.md)。
