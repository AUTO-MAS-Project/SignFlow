<!-- auto-mas:i18n {"display_name_i18n":{"zh_CN":"SignFlow Token 获取","en":"SignFlow Token Access"},"description_i18n":{"zh_CN":"通过扫码、短信或账密获取各游戏社区 Token，凭据仅保存在本机。","en":"Obtains game community tokens via QR code, SMS or credentials. Credentials stay on this machine."},"tags_i18n":{"zh_CN":["游戏社区","Token 获取"],"en":["community","token"]}} -->

# SignFlow Token 获取

通过扫码、短信或账密获取各游戏社区 Token，凭据仅保存在本机。

依赖核心插件「SignFlow 游戏社区」（服务名 `signflow.community`）；核心插件未启用时，本插件无法启用。

## 能力

- 盘点账号组里各平台凭据的配置与格式状态（不输出凭据原文）。
- 刷新并写回凭据：森空岛（换 token）、米游社（派生 cookie_token 后合并回原 Cookie）、塔吉多（refreshToken 轮换）。
- 库街区、云原神暂不支持自动刷新，会如实提示去帐号管理中重新获取。

登录入口沿用主程序「帐号管理」页：森空岛与米游社扫码、塔吉多账密都在那里完成，本插件只负责后续的状态与续期。

## 许可证

AGPL-3.0-or-later。第三方来源与许可见仓库根目录 [NOTICE.md](../../NOTICE.md)。