<!-- auto-mas:i18n {"display_name_i18n":{"zh_CN":"SignFlow Token 获取","en":"SignFlow Token Access"},"description_i18n":{"zh_CN":"通过扫码、短信或账密获取各游戏社区 Token，凭据仅保存在本机。","en":"Obtains game community tokens via QR code, SMS or credentials. Credentials stay on this machine."},"tags_i18n":{"zh_CN":["游戏社区","Token 获取"],"en":["community","token"]}} -->

# SignFlow Token 获取

通过扫码、短信或账密获取各游戏社区 Token，凭据仅保存在本机。

依赖核心插件「SignFlow 游戏社区」（服务名 `signflow.community`）；核心插件未启用时，本插件无法启用。

## 能力

- 盘点账号组里各平台凭据的配置与格式状态（不输出凭据原文）。
- 刷新并写回凭据：森空岛（换 token）、米游社（派生 cookie_token 后合并回原 Cookie）、塔吉多（refreshToken 轮换）。
- 库街区、云原神暂不支持自动刷新，会如实提示去重新获取。
- 库街区短信登录：本插件自己完成极验、发码、换凭据并写回账号组，是全仓唯一一处需要人机验证的登录。

森空岛与米游社扫码、塔吉多账密仍沿用主程序「帐号管理」页已有的入口，本插件不重复实现。

## 极验与云码

库街区登录前必须过极验。两种走法：

- 人工验证（默认）：前端把验证材料交给 `POST /api/plugin/signflow/token/login/send` 的 `verification`。
- 自动验证：在插件配置里把 `Captcha.Mode` 设为 `yunma` 并填 `Captcha.YunmaToken`，由本插件跑极验的滑块或图标识别。
  滑块识别用 numpy / opencv 本地算，不联网；图标识别会把验证图转发给云码，只在填了密钥时启用。

## 分发

本插件受主程序的受控插件名单约束：只有解锁「神秘入口」后才能在插件市场看到并安装，
且**不通过官方插件源分发**，需要用户自行从本仓库构建或安装。

## 许可证

AGPL-3.0-or-later。第三方来源与许可见仓库根目录 [NOTICE.md](../../NOTICE.md)。