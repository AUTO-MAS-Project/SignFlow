# Changelog

本仓库遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-11-20

### Added

- 新增 `signflow` 核心插件骨架，提供账号与社区数据门面服务 `signflow.community`。
- 新增 `signflow-notes` 日常便笺、`signflow-gacha` 抽卡记录、`signflow-token` Token 获取三个附属插件骨架，均依赖核心插件服务。
- 核心插件新增 `signflow.activity` 服务与 `POST /api/plugin/signflow/notes/query` 代发端点。
- `signflow-notes` 日常便笺插件接通核心插件，输出与前端 `ActivitySnapshot` 一致的驼峰投影。
