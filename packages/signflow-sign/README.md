<!-- auto-mas:i18n {"display_name_i18n":{"zh_CN":"SignFlow 签到","en":"SignFlow Sign-in"},"description_i18n":{"zh_CN":"承担游戏社区每日签到的执行：账号遍历、平台调用、凭据回写与完成日期标记。","en":"Runs the daily community sign-in: account iteration, platform calls, credential write-back and completion date."},"tags_i18n":{"zh_CN":["游戏社区","签到"],"en":["community","sign-in"]}} -->

# SignFlow 签到

承担游戏社区每日签到的执行：账号遍历、平台调用、凭据回写与完成日期标记。

依赖核心插件「SignFlow 游戏社区」提供的服务 `signflow.community`（账号投影、凭据字段名与代理地址）；核心插件未启用时，本插件无法启用。
签到触发仍由宿主调度决定（定时、启动、MAS 任务与手动按钮），本插件只负责把已配置的平台跑完，不自己起定时器。
平台协议实现与平台注册表留在宿主：本包不复制第二份平台名单或凭据字段清单，用户新增平台时本插件无需改动。
本插件自己不开 HTTP 端点，签到结果由宿主写盘并推送。

## 许可证

AGPL-3.0-or-later。第三方来源与许可见仓库根目录 [NOTICE.md](../../NOTICE.md)。
