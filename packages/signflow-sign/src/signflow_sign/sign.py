# Copyright (C) 2024-2025 DLmaster361
# Copyright (C) 2025-2026 AUTO-MAS Team

# This file is part of AUTO-MAS.

# AUTO-MAS is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# AUTO-MAS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

# Contact: DLmaster_361@163.com

"""签到编排：遍历账号、并发跑平台、回写凭据与完成日期。

触发时机仍由宿主决定（定时、启动、MAS 任务与手动按钮），本模块只负责
"把已配置的平台跑完"。平台协议实现与平台注册表都留在宿主，本包不复制
第二份平台名单或凭据字段清单，只经 SDK 门牌调用宿主的签到实现。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from auto_mas_core.host.tools_common_community_contracts import CommunitySignResult
from auto_mas_core.host.tools_common_community_credentials import (
    is_community_credential_configured,
)
from auto_mas_core.host.tools_common_community_sign import (
    get_community_sign_providers,
    run_community_provider,
)
from auto_mas_core.host.utils import UTC8, get_logger

logger = get_logger("游戏社区签到")


def _community() -> Any:
    """取核心插件的账号门面实例。

    宿主把方法包过一层 CallGate，require 拿到的是方法本身，要再调用一次才
    得到门面实例；这一步写错会拿到一个不可调用的包装对象。
    """

    from auto_mas_core import Plugin

    return Plugin.services.require("signflow.community")()


def _raw_token(account: Any, token_field: str) -> str:
    """从账号投影里取凭据原文，取不到时返回空串。"""

    tokens = getattr(account, "tokens", None)
    if not isinstance(tokens, dict):
        return ""
    return str(tokens.get(token_field, "") or "")


def all_enabled_platforms_signed(
    results: list[dict[str, object]],
    *,
    account_uid: str,
    enabled_platforms: list[str],
) -> bool:
    """判断某账号本轮启用过的平台是否全部签到完成。

    成功判据只认宿主契约里的 `is_community_sign_completed`，不在这里另立一套。
    """

    from auto_mas_core.host.tools_common_community_contracts import (
        is_community_sign_completed,
    )

    if not enabled_platforms:
        return False
    for platform in enabled_platforms:
        matched = [
            result
            for result in results
            if result.get("account_uid") == account_uid
            and result.get("platform") == platform
        ]
        if not matched or not all(
            is_community_sign_completed(result) for result in matched
        ):
            return False
    return True


class SignFacade:
    """签到执行的对外门面；实例由插件在 `provides_services` 中暴露。"""

    __slots__ = ()

    async def run(self, force: bool = False) -> list[dict[str, object]]:
        """执行所有已配置平台的签到。

        平台由宿主的凭据字段注册表驱动。同一账号的独立社区并发执行，适配器
        内部仍自行控制请求间隔和风控策略；凭据刷新结果优先即时回写，收尾阶段
        再统一兜底。
        """

        results: list[dict[str, object]] = []
        today = datetime.now(tz=UTC8).strftime("%Y-%m-%d")
        community = _community()
        providers = get_community_sign_providers()

        for account in community.accounts():
            account_name = account.name or "默认账号"
            account_uid = str(account.uid)

            if not account.enabled:
                continue

            # 非强制模式：跳过今日已签到的账号。
            if not force and account.last_signed_on == today:
                logger.debug(f"[{account_name}] 今日已签到，跳过")
                continue

            tokens = {
                provider.token_field: _raw_token(account, provider.token_field)
                for provider in providers
            }
            runtime_tokens = dict(tokens)
            miyoushe_token = tokens.get("MiyousheToken", "")
            if is_community_credential_configured("MiyousheToken", miyoushe_token):
                # 云原神只在本轮从米游社 Cookie 换取临时凭据；旧字段继续作为
                # 没有米游社凭据时的兼容后备，不回写临时 token。
                runtime_tokens["CloudGenshinToken"] = miyoushe_token
            configured = [
                provider
                for provider in providers
                if is_community_credential_configured(
                    provider.token_field,
                    runtime_tokens.get(provider.token_field, ""),
                )
            ]
            if not configured:
                continue

            credential_update_lock = asyncio.Lock()
            credential_update_failures: dict[str, str] = {}
            credential_update_platforms: dict[str, tuple[str, ...]] = {}

            async def save_credential_update(
                field: str,
                value: str,
                *,
                retry: bool,
            ) -> bool:
                """保存轮换凭据；提交失败时保留重试状态并返回可展示的原因。"""

                updated_token = str(value or "").strip()
                if not updated_token or updated_token == tokens.get(field, ""):
                    return True

                attempts = 2 if retry else 1
                for attempt in range(attempts):
                    try:
                        # 更新凭据不重置 LastSignDate；提交失败时事务回滚，可直接重试。
                        await community.save_credential(
                            account_uid, field, updated_token
                        )
                    except Exception as error:
                        if attempt + 1 < attempts:
                            logger.warning(
                                f"[{account_name}] 保存{field}失败，将重试: {type(error).__name__}"
                            )
                            continue
                        reason = "刷新凭据已生成，但保存失败，请稍后重试或重新登录"
                        credential_update_failures[field] = reason
                        logger.warning(
                            f"[{account_name}] 保存{field}失败: {type(error).__name__}"
                        )
                        return False
                    else:
                        tokens[field] = updated_token
                        credential_update_failures.pop(field, None)
                        return True
                return False

            async def persist_credential_update(field: str, value: str) -> None:
                """在社区运行期间写穿轮换凭据，失败时交给收尾兜底。"""

                if not str(value or "").strip():
                    return
                async with credential_update_lock:
                    saved = await save_credential_update(field, value, retry=False)
                    if not saved:
                        # 让内置 provider 保留其既有收尾兜底，同时由本层记录失败状态。
                        raise RuntimeError(f"{field}凭据保存失败")

            # 不同社区互不依赖，按注册顺序并发执行，完成后仍按固定顺序合并结果。
            provider_runs = await asyncio.gather(
                *(
                    run_community_provider(
                        provider,
                        runtime_tokens[provider.token_field],
                        account_name=account_name,
                        account_uid=account_uid,
                        on_credential_update=persist_credential_update,
                    )
                    for provider in configured
                )
            )
            enabled_platforms: list[str] = []
            for provider, run in zip(configured, provider_runs):
                for platform in run.platforms:
                    if platform not in enabled_platforms:
                        enabled_platforms.append(platform)
                results.extend(run.results)
                for field, updated_token in run.credential_updates.items():
                    credential_update_platforms[field] = run.platforms or (
                        provider.log_name,
                    )
                    if not updated_token or updated_token == tokens.get(field, ""):
                        continue
                    # 收尾兜底写回前重读存量：签到期间该凭据可能已被其他链路（如
                    # 养成练度拉取）轮换写新；存量偏离本轮起点说明已有更新者，
                    # 保留新值，避免把可能已被服务作废的旧 token 覆盖回去。
                    fresh = community.account(account_uid)
                    if _raw_token(fresh, field) != tokens.get(field, ""):
                        logger.warning(
                            f"[{account_name}] {field}已在签到期间被其他链路更新，"
                            "跳过收尾回写"
                        )
                        continue
                    async with credential_update_lock:
                        await save_credential_update(field, updated_token, retry=True)

            for field, reason in credential_update_failures.items():
                platforms = credential_update_platforms.get(field, (field,))
                provider = next(
                    (item for item in configured if item.token_field == field),
                    None,
                )
                provider_name = provider.log_name if provider is not None else field
                results.extend(
                    CommunitySignResult(
                        account=f"{account_name}/{platform}",
                        account_uid=account_uid,
                        game=f"{provider_name}凭据",
                        platform=platform,
                        status="失败",
                        reason=reason,
                    ).to_legacy()
                    for platform in platforms
                )

            # 自动签到每天只尝试一次。失败也要记住当天的尝试，避免后续 MAS 任务反复请求；
            # 手动签到使用 force=True，仍只在所有已配置平台完成后更新日期。
            all_platforms_signed = all_enabled_platforms_signed(
                results,
                account_uid=account_uid,
                enabled_platforms=enabled_platforms,
            )
            should_mark_signed = bool(enabled_platforms) and (
                not force or all_platforms_signed
            )
            if should_mark_signed:
                try:
                    # 多账号串行签到可能跨越 0 点，写入时重新取当前日期，
                    # 避免把新一天的签到记成旧日期导致次日误判。
                    await community.mark_signed(account_uid)
                except Exception as error:
                    logger.warning(f"[{account_name}] 保存签到完成日期失败: {error}")

        if not results:
            logger.info("没有配置任何社区平台")

        return results
