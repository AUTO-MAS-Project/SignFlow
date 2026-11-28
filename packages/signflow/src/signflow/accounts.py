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

宿主把账号字段、凭据字段与平台注册表集中在 `SignFlowAccountFields` 与
`_COMMUNITY_SIGN_PROVIDERS`，本模块只做只读投影，不复制第二份字段清单。
凭据原文只在本对象内传递，调用方不得写入日志、异常消息或前端响应。

写回也走这里：附属插件（签到）不读宿主配置，凭据轮换与完成日期都经
`save_credential` / `mark_signed` 落到宿主账号组上。
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["CommunityAccount", "CommunityFacade"]


def _safe_text(group: object, name: str) -> str:
    """读取单个文本字段，读不到时退回空串。

    设备字段只在《绝区零》便笺里用到，解密失败不应该让整个账号组的
    便笺查询一起失败，所以这里降级而不是抛错。
    """

    try:
        return str(getattr(group, name, "") or "").strip()
    except Exception:
        return ""


def _safe_last_signed_on(group: object) -> str:
    """读取最近签到日期，读不到时退回空串。

    签到插件只把它当"今天签过没有"的判据，格式化成空串等价于"没签过"，
    比让整个账号投影一起失败更合适。
    """

    try:
        return getattr(group, "LastSignDate").strftime("%Y-%m-%d")
    except Exception:
        return ""


@dataclass(frozen=True)
class CommunityAccount:
    """一个游戏社区账号组的只读投影。

    ``tokens`` 是按宿主凭据字段名索引的原文映射；只允许在进程内交给
    平台协议实现，禁止序列化、打印或写入任何持久化载体。

    设备字段只在米游社《绝区零》便笺签名时使用，其它场景一律留空。
    """

    uid: str
    name: str
    enabled: bool
    tokens: dict[str, str] = field(repr=False)
    device_id: str = field(default="", repr=False)
    device_fp: str = field(default="", repr=False)
    # 最近一次签到日期（本地时区的 YYYY-MM-DD）。签到插件据此跳过今日已签的账号，
    # 与宿主 `LastSignDate.strftime("%Y-%m-%d")` 的判据保持同一形态。
    last_signed_on: str = ""

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
        for raw_uid, entry in Config.ToolsConfig.SignFlow_Accounts.items():
            group = entry.SignFlowAccount
            projected.append(
                CommunityAccount(
                    uid=str(raw_uid),
                    name=str(group.Name),
                    enabled=bool(group.Enabled),
                    tokens={
                        name: str(getattr(group, name, "") or "") for name in fields
                    },
                    device_id=_safe_text(group, "MiyousheDeviceId"),
                    device_fp=_safe_text(group, "MiyousheDeviceFp"),
                    last_signed_on=_safe_last_signed_on(group),
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

    def _entry(self, account_uid: str) -> object | None:
        """按账号组 uid 取宿主配置项；不存在时返回 `None`。

        写回必须落在账号组本体上而不是投影上：投影是一次性快照，改它不会
        经过配置框架的事务与信号。
        """

        from auto_mas_core.host.core import Config

        target = str(account_uid).strip()
        if not target:
            return None
        for raw_uid, entry in Config.ToolsConfig.SignFlow_Accounts.items():
            if str(raw_uid) == target:
                return entry
        return None

    async def save_credential(self, account_uid: str, field: str, value: str) -> None:
        """把轮换后的凭据写回账号组，不重置最近签到日期。

        与宿主 `update_sign_flow_account` 的区别只在这一点：签到执行期间刷新
        出来的 token 不是用户换的凭据，不该把当天已经记下的签到日期清掉。
        """

        entry = self._entry(account_uid)
        if entry is None:
            return
        await entry.update(  # type: ignore[attr-defined]
            type(entry).model_validate({"SignFlowAccount": {field: str(value)}}),
            check_visibility=False,
        )

    async def mark_signed(self, account_uid: str) -> None:
        """记录账号组最近一次签到日期为当前 UTC+8 时间。"""

        from datetime import datetime

        from auto_mas_core.host.utils import UTC8

        entry = self._entry(account_uid)
        if entry is None:
            return
        await entry.update(  # type: ignore[attr-defined]
            type(entry).model_validate(
                {"SignFlowAccount": {"LastSignDate": datetime.now(tz=UTC8)}}
            ),
            check_visibility=False,
        )
