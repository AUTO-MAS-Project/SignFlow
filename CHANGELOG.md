# Changelog

本仓库遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-11-20

### Added

- 新增 `signflow` 核心插件骨架，提供账号与社区数据门面服务 `signflow.community`。
- 新增 `signflow-notes` 日常便笺、`signflow-gacha` 抽卡记录、`signflow-token` Token 获取三个附属插件骨架，均依赖核心插件服务。
- 核心插件新增 `signflow.activity` 服务与 `POST /api/plugin/signflow/notes/query` 代发端点。
- `signflow-notes` 日常便笺插件接通核心插件，输出与前端 `ActivitySnapshot` 一致的驼峰投影。
- `signflow-gacha` 抽卡记录插件落框架：记录模型、本地存档、森空岛明日方舟寻访协议与保底统计。
- 核心插件新增 `GET /api/plugin/signflow/gacha/games`、`POST /api/plugin/signflow/gacha/query`、`POST /api/plugin/signflow/gacha/fetch` 三个代发端点。
- `signflow-gacha` 抽卡记录读取只由用户手动触发，不排定时任务、不在启用时预热，避免频繁请求触发风控。
- `signflow-token` Token 获取插件落地：凭据状态盘点与刷新写回，森空岛 / 米游社 / 塔吉多可自动续期，其余平台如实报告暂不支持。
- 核心插件新增 `POST /api/plugin/signflow/token/status`、`POST /api/plugin/signflow/token/refresh` 两个代发端点。
