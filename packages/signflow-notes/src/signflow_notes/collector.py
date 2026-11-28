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

"""游戏社区日常便笺采集：账号组到活动快照的消费层。

本模块由 AUTO-MAS 本体的 app/core/community/activity.py 整块迁移而来。迁移
只换了两处来源：账号投影、凭据字段名与代理统一走核心插件暴露的
`signflow.community` 门面；宿主配置变动信号由本插件自行订阅。缓存时长、
串行锁与失败降级语义与原实现保持一致，用户看不到行为差异。
"""

from __future__ import annotations

import asyncio
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from typing import Any

import httpx
from auto_mas_core.utils import UTC8, format_exception_reason, get_logger

from .contracts import ActivityState, CommunityActivitySnapshot
from .provider import CommunityActivityProvider
from .roles import (
    ACTIVITY_COMMUNITY_DEFINITIONS,
    CommunityActivityProviderDefinition,
    CommunityActivityRole,
)
from .transport import CommunityActivityTransportError, collect_community_activity

__all__ = ["ActivityCollector"]

logger = get_logger("游戏社区活动")

_ACTIVITY_CACHE_SECONDS = 300.0
_ACTIVITY_RETRY_SECONDS = 30.0
type _ActivityCacheKey = tuple[int, str]


@dataclass(frozen=True)
class _ActivityCacheEntry:
    """单个账号组的便笺缓存条目。"""

    snapshots: tuple[CommunityActivitySnapshot, ...]
    expires_at: float


def _community() -> Any:
    """取核心插件的账号门面实例。

    宿主把方法包过一层 CallGate，require 拿到的是方法本身，要再调用一次
    才得到门面实例；这一步写错会拿到一个不可调用的包装对象。
    """

    from auto_mas_core import Plugin

    return Plugin.services.require("signflow.community")()


def _raw_token(account: Any, token_field: str) -> str:
    """读取账号投影里的凭据原文，缺字段时退回空串。

    与宿主 read_community_token 同语义：凭据原文只在进程内交给平台协议实现，
    不写日志、不进异常消息、不出现在返回值里。
    """

    tokens = getattr(account, "tokens", None)
    if not isinstance(tokens, dict):
        return ""
    return str(tokens.get(token_field, "") or "").strip()


class ActivityCollector:
    """游戏社区日常便笺的唯一采集入口，由便笺插件持有。

    对外只有 query / collect / failures 三个方法：query 带缓存与串行锁，是
    前端唯一入口；collect 真正发上游请求；failures 在整体失败时造出可展示的
    失败快照，避免接口把异常直接抛给前端。
    """

    __slots__ = ("_cache", "_invalidate", "_lock", "_revision", "_subscriptions")

    def __init__(self) -> None:
        self._cache: dict[_ActivityCacheKey, _ActivityCacheEntry] = {}
        self._revision = 0
        self._subscriptions: list[tuple[Any, dict[str, str]]] = []
        self._lock = asyncio.Lock()

        def invalidate(sender: object, event: object) -> None:
            """配置变动后清除快照，并作废尚未完成的旧查询。"""

            self._revision += 1
            self._cache.clear()

        # 信号机制在接收函数上记录订阅元数据；保留稳定函数，避免绑定方法不能写属性
        self._invalidate = invalidate

    # ──────────────── 配置信号 ────────────────

    def attach(self) -> None:
        """订阅宿主配置变动信号，用于失效便笺缓存。

        插件没有宿主那样的配置钩子，只能自己订阅：账号组成员、账号组集合、
        便笺开关与代理地址四处任一变动都要清缓存。重复启用时先解订再订阅，
        否则宿主会以「重复订阅同一 (phase, kind, group, field, sender)」拒绝。
        """

        from auto_mas_core.host.core import Config

        self.detach()
        tools_config = Config.ToolsConfig
        plans: list[tuple[Any, dict[str, str]]] = [
            (tools_config.SignFlow_Accounts, {"phase": "runtime"}),
            (
                tools_config,
                {"phase": "runtime", "group": "SignFlow", "field": "ActivityEnabled"},
            ),
            (
                Config.setting,
                {"phase": "runtime", "group": "Update", "field": "ProxyAddress"},
            ),
        ]
        # 账号组成员在配置里是集合成员，只能从集合的类型表里取到成员 Entry 类
        account_type = tools_config.SignFlow_Accounts.entry_types.get(
            "SignFlowAccountGroup"
        )
        if account_type is not None:
            plans.append(
                (account_type, {"phase": "runtime", "group": "SignFlowAccount"})
            )
        for node, options in plans:
            try:
                node.connect(self._invalidate, **options)
            except Exception as error:
                # 订阅失败只让缓存退化为按 TTL 过期，不能让便笺插件起不来
                logger.warning(f"便笺缓存订阅失败: {error}")
                continue
            self._subscriptions.append((node, options))
        self._invalidate(None, None)

    def detach(self) -> None:
        """解除全部配置信号订阅；未订阅时直接返回。"""

        for node, options in self._subscriptions:
            try:
                node.disconnect(self._invalidate, **options)
            except Exception as error:
                logger.warning(f"便笺缓存解订失败: {error}")
        self._subscriptions.clear()

    # ──────────────── 查询 ────────────────

    async def query(
        self,
        account_ids: Sequence[str] | None = None,
        *,
        proxy: str | httpx.Proxy | None = None,
    ) -> tuple[CommunityActivitySnapshot, ...]:
        """按账号缓存便笺；并发查询等待后仅补查尚未缓存的账号。"""

        from auto_mas_core.host.core import Config

        async with self._lock:
            while True:
                if Config.ToolsConfig.SignFlow.ActivityEnabled is False:
                    return ()
                config_id = id(Config.ToolsConfig)
                selected_ids = tuple(
                    item.uid for item in self._selected_accounts(account_ids)
                )
                now = monotonic()
                results: dict[str, tuple[CommunityActivitySnapshot, ...]] = {}
                missing_ids: list[str] = []
                for account_uid in selected_ids:
                    entry = self._cache.get((config_id, account_uid))
                    if entry is not None and now < entry.expires_at:
                        results[account_uid] = entry.snapshots
                    else:
                        missing_ids.append(account_uid)
                if not missing_ids:
                    return tuple(item for uid in selected_ids for item in results[uid])
                revision = self._revision
                resolved_proxy = proxy if proxy is not None else _community().proxy()
                try:
                    collected = await self.collect(missing_ids, proxy=resolved_proxy)
                except ValueError:
                    raise
                except Exception as error:
                    if revision != self._revision:
                        continue
                    logger.warning(
                        format_exception_reason(
                            error,
                            stage="游戏社区日常查询失败",
                            include_message=False,
                        )
                    )
                    if error.__traceback__ is not None:
                        # 仅保留定位信息，避免异常原文、源码或局部变量泄露凭据
                        logger.warning(
                            "社区调用位置: "
                            + " -> ".join(
                                f"{frame.filename}:{frame.lineno} in {frame.name}"
                                for frame in traceback.extract_tb(error.__traceback__)
                            )
                        )
                    collected = self.failures(missing_ids)
                    if not collected:
                        raise
                # 等待上游期间账号可能被删除、修改；旧响应不能进入新配置的缓存
                if revision != self._revision:
                    continue
                by_account: dict[str, list[CommunityActivitySnapshot]] = {
                    uid: [] for uid in missing_ids
                }
                for item in collected:
                    bucket = by_account.get(item.account_uid)
                    if bucket is not None:
                        bucket.append(item)
                completed_at = monotonic()
                for account_uid in missing_ids:
                    items = tuple(by_account[account_uid])
                    ttl = (
                        _ACTIVITY_RETRY_SECONDS
                        if any(
                            item.status not in ("success", "empty") for item in items
                        )
                        else _ACTIVITY_CACHE_SECONDS
                    )
                    self._cache[(config_id, account_uid)] = _ActivityCacheEntry(
                        snapshots=items, expires_at=completed_at + ttl
                    )
                    results[account_uid] = items
                return tuple(item for uid in selected_ids for item in results[uid])

    async def collect(
        self,
        account_ids: Sequence[str] | None = None,
        *,
        proxy: str | httpx.Proxy | None = None,
        max_concurrency: int = 4,
    ) -> tuple[CommunityActivitySnapshot, ...]:
        """逐账号逐平台查询日常；单平台失败只影响该平台自己的快照。"""

        community = _community()
        resolved_proxy = proxy if proxy is not None else community.proxy()
        snapshots: list[CommunityActivitySnapshot] = []
        for account in self._selected_accounts(account_ids):
            account_uid = account.uid
            account_name = str(account.name or "用户")
            if not account.enabled:
                continue
            # 设备字段只在米游社《绝区零》便笺签名时使用，读不到不影响其它游戏
            miyoushe_device_id = str(account.device_id or "")
            miyoushe_device_fp = str(account.device_fp or "")
            for definition in ACTIVITY_COMMUNITY_DEFINITIONS:
                try:
                    token_field = community.token_field(definition.platform)
                    token = _raw_token(account, token_field)
                except Exception:
                    for game in definition.games:
                        snapshots.append(
                            self._empty_game_snapshot(
                                account_uid=account_uid,
                                account_name=account_name,
                                definition=definition,
                                game=game,
                                status="failed",
                                reason="社区凭据无法读取",
                            )
                        )
                    continue
                if not token:
                    continue
                provider = CommunityActivityProvider(
                    platform=definition.platform,
                    raw_credential=token,
                    proxy=resolved_proxy,
                )
                try:
                    discovered = await provider.discover_roles(
                        account_uid=account_uid, account_name=account_name
                    )
                except Exception as error:
                    status, reason = self._failure_state(error)
                    logger.warning(
                        f"{account_name} {definition.platform}角色发现失败: {reason}"
                    )
                    for game in definition.games:
                        snapshots.append(
                            self._empty_game_snapshot(
                                account_uid=account_uid,
                                account_name=account_name,
                                definition=definition,
                                game=game,
                                status=status,
                                reason=reason,
                            )
                        )
                    continue
                capability = discovered.activity_capability
                if capability.status == "limited":
                    for game in definition.games:
                        game_roles = discovered.roles_for_game(game)
                        if not game_roles:
                            snapshots.append(
                                self._empty_game_snapshot(
                                    account_uid=account_uid,
                                    account_name=account_name,
                                    definition=definition,
                                    game=game,
                                )
                            )
                            continue
                        for role in game_roles:
                            snapshots.append(
                                self._empty_game_snapshot(
                                    account_uid=account_uid,
                                    account_name=account_name,
                                    definition=definition,
                                    game=game,
                                    status="limited",
                                    reason=capability.reason,
                                    role=role,
                                )
                            )
                    continue
                targets = self._targets_for_roles(
                    roles=discovered.roles,
                    account_uid=account_uid,
                    account_name=account_name,
                    miyoushe_device_id=miyoushe_device_id,
                    miyoushe_device_fp=miyoushe_device_fp,
                )
                queried: tuple[CommunityActivitySnapshot, ...] = ()
                if targets:
                    queried = await collect_community_activity(
                        targets, provider.request, max_concurrency=max_concurrency
                    )
                for game in definition.games:
                    game_snapshots = tuple(
                        item for item in queried if item.game == game
                    )
                    if game_snapshots:
                        snapshots.extend(game_snapshots)
                        continue
                    snapshots.append(
                        self._empty_game_snapshot(
                            account_uid=account_uid,
                            account_name=account_name,
                            definition=definition,
                            game=game,
                        )
                    )
        return tuple(snapshots)

    def failures(
        self,
        account_ids: Sequence[str] | None = None,
        *,
        reason: str = "游戏社区日常查询失败",
    ) -> tuple[CommunityActivitySnapshot, ...]:
        """整体失败时按「已配置凭据的账号 × 平台 × 游戏」造失败快照。

        读不到凭据的账号按「可能已配置」处理，宁可让用户看到失败提示，也不
        把账号从列表里静默抹掉。
        """

        community = _community()
        snapshots: list[CommunityActivitySnapshot] = []
        for account in self._selected_accounts(account_ids):
            if not account.enabled:
                continue
            account_name = str(account.name or "用户")
            for definition in ACTIVITY_COMMUNITY_DEFINITIONS:
                try:
                    token_field = community.token_field(definition.platform)
                    configured = bool(_raw_token(account, token_field))
                except Exception:
                    configured = True
                if not configured:
                    continue
                for game in definition.games:
                    snapshots.append(
                        self._empty_game_snapshot(
                            account_uid=account.uid,
                            account_name=account_name,
                            definition=definition,
                            game=game,
                            status="failed",
                            reason=reason,
                        )
                    )
        return tuple(snapshots)

    # ──────────────── 内部 ────────────────

    def _selected_accounts(self, account_ids: Sequence[str] | None) -> tuple[Any, ...]:
        """按账号组顺序取账号投影；指定了不存在的账号组时抛 ValueError。"""

        requested_ids = {
            str(account_id).strip()
            for account_id in (account_ids or ())
            if str(account_id).strip()
        }
        accounts = tuple(_community().accounts())
        if not requested_ids:
            return accounts
        selected = tuple(item for item in accounts if item.uid in requested_ids)
        if {item.uid for item in selected} != requested_ids:
            raise ValueError("未找到指定的游戏社区账号组")
        return selected

    def _failure_state(self, error: Exception) -> tuple[ActivityState, str]:
        """把角色发现阶段的异常归一成快照状态与用户可读原因。"""

        if isinstance(error, CommunityActivityTransportError):
            return error.status, error.reason
        if isinstance(error, ValueError):
            text = str(error)
            if any(token in text for token in ("风控", "限制", "非 JSON")):
                return "limited", "社区角色列表受到上游限制"
            return "unavailable", "社区角色列表响应无法识别"
        return "failed", "社区角色列表请求失败"

    def _empty_game_snapshot(
        self,
        *,
        account_uid: str,
        account_name: str,
        definition: CommunityActivityProviderDefinition,
        game: str,
        status: ActivityState = "empty",
        reason: str = "未发现已绑定角色",
        role: CommunityActivityRole | None = None,
    ) -> CommunityActivitySnapshot:
        """造一条不含任务明细的快照，用于空态与各类失败态。"""

        return CommunityActivitySnapshot(
            account=account_name,
            account_uid=account_uid,
            game=game,
            platform=definition.platform,
            status=status,
            reason=reason,
            updated_at=datetime.now(tz=UTC8).isoformat(),
            role_name=role.role_name if role is not None else "",
            role_uid=role.role_uid if role is not None else "",
            server=role.server if role is not None else "",
        )

    def _targets_for_roles(
        self,
        *,
        roles: Sequence[CommunityActivityRole],
        account_uid: str,
        account_name: str,
        miyoushe_device_id: str = "",
        miyoushe_device_fp: str = "",
    ) -> tuple[Any, ...]:
        """把已发现角色转成待查询目标；只有绝区零才带米游社设备签名。"""

        return tuple(
            role.to_target(
                account_uid=account_uid,
                account_name=account_name,
                device_id=(
                    miyoushe_device_id
                    if role.platform == "米游社" and role.game == "绝区零"
                    else ""
                ),
                device_fp=(
                    miyoushe_device_fp
                    if role.platform == "米游社" and role.game == "绝区零"
                    else ""
                ),
            )
            for role in roles
        )
