#   SignFlow: AUTO-MAS 游戏社区核心插件
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of SignFlow.

#   SignFlow is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   SignFlow is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#   GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with SignFlow. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com

"""账号组与凭据门面：附属插件唯一的账号读取入口。

宿主把账号字段、凭据字段与平台注册表集中在 `GameSignAccountFields` 与
`_COMMUNITY_SIGN_PROVIDERS`，本模块只做只读投影，不复制第二份字段清单。
凭据原文只在本对象内传递，调用方不得写入日志、异常消息或前端响应。
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["CommunityAccount", "CommunityFacade"]


@dataclass(frozen=True)
class CommunityAccount:
    """一个游戏社区账号组的只读投影。

    ``tokens`` 是按宿主凭据字段名索引的原文映射；只允许在进程内交给
    平台协议实现，禁止序列化、打印或写入任何持久化载体。
    """

    uid: str
    name: str
    enabled: bool
    tokens: dict[str, str] = field(repr=False)

    def has_token(self, token_field: str) -> bool:
        """判断某个平台凭据是否已配置。"""

        return bool(self.tokens.get(token_field, ""))


class CommunityFacade:
    """附属插件共用的账号、平台与代理读取入口。

    实例由核心插件在 `provides_services` 中暴露为 `signflow.community`，
    附属插件通过 `requires` 依赖该服务名后再取用。
    """

    __slots__ = ()

    def token_fields(self) -> tuple[str, ...]:
        """返回宿主登记的全部凭据字段名，顺序与平台注册表一致。"""

        from app.tools.common.community import sign as _sign

        return tuple(
            provider.token_field for provider in _sign.get_community_sign_providers()
        )

    def token_field(self, platform: str) -> str:
        """返回某个社区平台对应的凭据字段名。

        平台名未登记时由宿主抛出 `ValueError`，这里不做二次判定。
        """

        from app.tools.common.community import sign as _sign

        return _sign.get_community_token_field(platform)

    def platforms(self) -> tuple[tuple[str, str], ...]:
        """返回（凭据字段名，平台显示名）的对照，顺序与平台注册表一致。

        附属插件需要把字段名翻成用户看得懂的平台名时走这里，不要自己写
        第二份对照表：宿主新增平台时这份对照自动跟着变。
        """

        from app.tools.common.community import sign as _sign

        return tuple(
            (provider.token_field, provider.log_name)
            for provider in _sign.get_community_sign_providers()
        )

    def accounts(self) -> tuple[CommunityAccount, ...]:
        """按账号组顺序返回全部社区账号的只读投影。"""

        from auto_mas_core.host.core import Config

        fields = self.token_fields()
        projected: list[CommunityAccount] = []
        for raw_uid, entry in Config.ToolsConfig.GameSign_Accounts.items():
            group = entry.GameSignAccount
            projected.append(
                CommunityAccount(
                    uid=str(raw_uid),
                    name=str(group.Name),
                    enabled=bool(group.Enabled),
                    tokens={
                        name: str(getattr(group, name, "") or "") for name in fields
                    },
                )
            )
        return tuple(projected)

    def account(self, account_uid: str) -> CommunityAccount | None:
        """按账号组 uid 取单个投影；不存在时返回 `None`。"""

        target = str(account_uid).strip()
        if not target:
            return None
        for item in self.accounts():
            if item.uid == target:
                return item
        return None

    def proxy(self) -> str | None:
        """返回宿主当前配置的网络代理，未配置时为 `None`。"""

        from auto_mas_core.host.core import Config

        return Config.proxy
