# Changelog

本仓库遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Changed

- 日常便笺采集（平台协议、角色发现、并发查询、串行锁与 300s / 30s 两级缓存）从 AUTO-MAS 本体迁入 `signflow-notes`，插件不再向宿主转发，不依赖 `signflow.activity`。
- 核心插件下线 `signflow.activity` 服务与对应实现，只保留 `signflow.community`；便笺插件改为依赖账号与凭据门面。
- 签到执行从 AUTO-MAS 本体迁入 `signflow-sign`：宿主只留触发、串行锁与结果写盘，插件负责账号遍历、平台调用、凭据回写与完成日期标记。
- 核心插件的账号门面新增凭据写回与完成日期标记，签到插件经 `signflow.community` 复用，不再让宿主反向调用插件。

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
- `signflow-token` 新增库街区短信登录：自带极验（滑块本地识别、图标可选云码）、发码与换凭据，登录结果直接写回账号组。
- 核心插件新增 `POST /api/plugin/signflow/token/login/open`、`/send`、`/submit` 三个代发端点。
