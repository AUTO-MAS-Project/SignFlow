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
"""Token 获取门面：凭据状态盘点与刷新写回。

本模块不重新实现任何上游协议：格式校验交给宿主的 validate_* 函数，刷新交给
宿主的 refresh_skland_session_credential / refresh_taygedo_credential /
derive_miyoushe_cookie_token，写回交给 Config.update_sign_flow_account。
上游改端点或改字段时，本插件跟着宿主动，不维护第二份协议实现。

凭据原文只在进程内传递：不写日志、不进异常消息、不出现在返回值里。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

__all__ = ["TokenFacade"]


def _community() -> Any:
    """取核心插件的账号门面实例。

    宿主把方法包过一层 CallGate，require 拿到的是方法本身，要再调用一次
    才得到门面实例；这一步写错会拿到一个不可调用的包装对象。
    """

    from auto_mas_core import Plugin

    return Plugin.services.require("signflow.community")()


def _validators() -> dict[str, Callable[[str], object]]:
    """平台显示名到宿主本地格式校验函数的映射。

    键取自宿主平台注册表的 log_name。未登记的平台按「暂不支持校验」处理：
    宿主将来新增平台时这里不会抛 KeyError，状态页仍能把凭据列为已配置。
    """

    from auto_mas_core.host.tools_common_community_providers import (
        cloud_genshin,
        kuro,
        miyoushe,
        skland,
        taygedo,
    )

    return {
        "森空岛": skland.validate_skland_credential,
        "米游社": miyoushe.validate_miyoushe_cookie,
        "云原神": cloud_genshin.validate_cloud_genshin_token,
        "库街区": kuro.validate_kuro_credential,
        "塔吉多": taygedo.validate_taygedo_credential,
    }


def _wanted(account_ids: Iterable[str] | None) -> set[str] | None:
    """把筛选参数收敛成 uid 集合；留空表示不筛选。"""

    if account_ids is None:
        return None
    selected = {str(item).strip() for item in account_ids if str(item).strip()}
    return selected or None


def _item(platform: str, field: str, raw: str) -> dict[str, object]:
    """生成单个平台的凭据状态条目。"""

    if not raw:
        return {
            "field": field,
            "platform": platform,
            "configured": False,
            "checked": True,
            "valid": False,
            "message": "尚未配置",
        }

    validator = _validators().get(platform)
    if validator is None:
        # 平台尚未登记校验实现：明确说没校验，不伪装成通过。
        return {
            "field": field,
            "platform": platform,
            "configured": True,
            "checked": False,
            "valid": False,
            "message": "该平台暂不支持本地校验",
        }

    try:
        validator(raw)
    except ValueError as error:
        return {
            "field": field,
            "platform": platform,
            "configured": True,
            "checked": True,
            "valid": False,
            "message": str(error),
        }

    return {
        "field": field,
        "platform": platform,
        "configured": True,
        "checked": True,
        "valid": True,
        "message": "凭据格式有效",
    }


async def _refresh_skland(raw: str, proxy: str | None) -> str:
    """用宿主实现刷新森空岛凭据：只换 token，cred 与 userId 不变。"""

    from auto_mas_core.host.tools_common_community_providers import skland

    from app.tools.common.community.http import create_community_client

    credential = skland.parse_skland_credential(raw)
    device_id = await skland.get_cached_device_id(proxy)
    async with create_community_client(proxy) as client:
        updated = await skland.refresh_skland_session_credential(
            client, credential, device_id
        )
    return skland.serialize_skland_credential(updated)


async def _refresh_taygedo(raw: str, proxy: str | None) -> str:
    """用宿主实现刷新塔吉多凭据；refreshToken 成对轮换由宿主保证。"""

    from auto_mas_core.host.tools_common_community_providers import taygedo

    updated = await taygedo.refresh_taygedo_credential(raw, proxy=proxy)
    return taygedo.serialize_taygedo_credential(updated)


async def _refresh_miyoushe(raw: str, proxy: str | None) -> str:
    """用 stoken 派生新的 cookie_token，再合并回原 Cookie 串。"""

    from auto_mas_core.host.tools_common_community_providers import miyoushe

    session = miyoushe.prepare_miyoushe_session(raw)
    stoken = str(
        session.cookies.get("stoken_v2") or session.cookies.get("stoken") or ""
    ).strip()
    mid = str(session.cookies.get("mid") or "").strip()
    if not stoken or not mid:
        raise ValueError("米游社凭据缺少 stoken 或 mid，无法自动刷新")
    cookie_token, _ = await miyoushe.derive_miyoushe_cookie_token(
        stoken, mid, session.uid, proxy
    )
    # 合并而不是重建：全量 Cookie 可能带服务端兼容字段，重建会裁掉它们。
    return miyoushe.merge_miyoushe_cookie_update(raw, f"cookie_token={cookie_token}")


async def _refresh_one(platform: str, raw: str, proxy: str | None) -> str:
    """按平台分派刷新实现；没接通刷新的平台明确报错，不返回原值。"""

    if platform == "森空岛":
        return await _refresh_skland(raw, proxy)
    if platform == "米游社":
        return await _refresh_miyoushe(raw, proxy)
    if platform == "塔吉多":
        return await _refresh_taygedo(raw, proxy)
    raise ValueError(f"{platform}凭据暂不支持自动刷新，请在帐号管理中重新获取")


async def _persist(account_uid: str, field: str, raw: str) -> None:
    """把新凭据写回账号组，走宿主唯一的账号写入口。"""

    from auto_mas_core.host.core import Config

    await Config.update_sign_flow_account(
        account_uid, {"SignFlowAccount": {field: raw}}
    )


class TokenFacade:
    """凭据状态与刷新的唯一入口，由 Token 插件暴露为服务。"""

    __slots__ = ()

    def status(
        self, account_ids: Iterable[str] | None = None
    ) -> tuple[dict[str, object], ...]:
        """按账号组盘点各平台凭据的配置与格式状态。"""

        community = _community()
        platforms = dict(community.platforms())
        wanted = _wanted(account_ids)
        fields = community.token_fields()

        rows: list[dict[str, object]] = []
        for account in community.accounts():
            if wanted is not None and account.uid not in wanted:
                continue
            rows.append(
                {
                    "uid": account.uid,
                    "name": account.name,
                    "enabled": account.enabled,
                    "items": [
                        _item(
                            platforms.get(field, ""),
                            field,
                            account.tokens.get(field, ""),
                        )
                        for field in fields
                    ],
                }
            )
        return tuple(rows)

    async def refresh(
        self, account_uid: str, fields: Iterable[str] | None = None
    ) -> dict[str, object]:
        """刷新指定账号的凭据并写回；单个平台失败不影响其他平台。"""

        community = _community()
        account = community.account(account_uid)
        if account is None:
            raise ValueError("请选择一个已保存的社区账号")

        configured = [
            item for item in community.token_fields() if account.tokens.get(item)
        ]
        requested = list(fields) if fields else configured
        targets = [item for item in requested if account.tokens.get(item)]
        if not targets:
            raise ValueError("该账号还没有可刷新的凭据")

        platforms = dict(community.platforms())
        proxy = community.proxy()
        items: list[dict[str, object]] = []
        for field in targets:
            platform = platforms.get(field, "")
            try:
                updated = await _refresh_one(platform, account.tokens[field], proxy)
            except ValueError as error:
                items.append(
                    {
                        "field": field,
                        "platform": platform,
                        "refreshed": False,
                        "message": str(error),
                    }
                )
                continue

            if updated == account.tokens[field]:
                items.append(
                    {
                        "field": field,
                        "platform": platform,
                        "refreshed": True,
                        "message": "凭据仍然有效",
                    }
                )
                continue

            try:
                await _persist(account.uid, field, updated)
            except Exception:
                # 写回失败不能让用户以为已经好了；上游已消费旧凭据时尤其如此。
                items.append(
                    {
                        "field": field,
                        "platform": platform,
                        "refreshed": False,
                        "message": "刷新成功但写回失败，请重试",
                    }
                )
                continue

            items.append(
                {
                    "field": field,
                    "platform": platform,
                    "refreshed": True,
                    "message": "凭据已更新",
                }
            )

        return {"uid": account.uid, "items": items}
