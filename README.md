# SignFlow

AUTO-MAS 的游戏社区插件集合。游戏社区本体能力由本仓库的核心插件承担，
签到仍由 AUTO-MAS 本体执行；本仓库提供三个附属插件做功能补充。

| 目录 | 发行包 | 插件 ID | 作用 |
| --- | --- | --- | --- |
| `packages/signflow` | `signflow` | `signflow` | 游戏社区核心插件：账号、平台协议与社区数据门面 |
| `packages/signflow-notes` | `signflow-notes` | `signflow_notes` | 日常便笺（游戏内体力、委托、派遣等完整内容） |
| `packages/signflow-gacha` | `signflow-gacha` | `signflow_gacha` | 抽卡记录（首批仅森空岛明日方舟） |
| `packages/signflow-token` | `signflow-token` | `signflow_token` | Token 获取（扫码 / 短信 / 账密），受神秘入口授权门禁 |

三个附属插件都依赖核心插件提供的服务 `signflow.community`；核心插件未启用时它们无法启用。

## 前端在哪里

AUTO-MAS 的动态前端尚未上线，插件页面仍由主程序 `frontend/src/views/gamesign` 维护并随桌面应用构建。
本仓库只持有插件后端。

## 源码联调

```powershell
python scripts/link_dev.py --auto-mas D:\GitHub\AUTO-MAS
```

脚本会在 `AUTO-MAS/plugins/` 下为四个包建立目录联接（该目录已被主仓 `.gitignore` 忽略）。
用 `--unlink` 撤销。

## 构建

```powershell
python -m build packages/signflow
```

四个包分别构建、分别发布到 PyPI；附属包通过 `signflow>=0.1.0,<0.2` 依赖核心包。

## 许可证

AGPL-3.0-or-later，见 [LICENSE](LICENSE)。第三方来源与许可见 [NOTICE.md](NOTICE.md)。
