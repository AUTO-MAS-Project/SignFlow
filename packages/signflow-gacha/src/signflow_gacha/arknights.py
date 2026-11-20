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
"""明日方舟寻访记录协议。

This file incorporates work covered by the following copyright and permission notice:

    arknights-plugin (c) 2023 gxy12345 (MIT)
    https://github.com/gxy12345/arknights-plugin
    森空岛角色授权 → 明日方舟寻访记录接口的调用顺序参考自该插件，
    经由 Better-MAS-Tools 的 app/tools/gacha.py 转写。

协议三步走，每一步都只拿下一步需要的东西：

1. 用账号组里的森空岛 OAuth Token 换通行证 token（grant）；
2. 用通行证 token + 游戏 UID 换该角色的一次性 role token（u8_token_by_uid）；
3. 带 X-Account-Token / X-Role-Token 取卡池列表，再逐池翻页取记录。

授权材料不落盘、不进日志、不进异常消息：本模块抛出的每一条错误都是固定文案，
上游响应正文一律不外带。
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx
from auto_mas_core.host.utils import UTC8

from .models import GachaRecord

__all__ = ["fetch_arknights", "hg_record"]

# 森空岛开放平台给明日方舟抽卡用的固定 appCode，属于公开常量而非用户凭据。
_APP_CODE = "be36d44aa36bfb5b"
_GRANT_URL = "https://as.hypergryph.com/user/oauth2/v2/grant"
_ROLE_TOKEN_URL = (
    "https://binding-api-account-prod.hypergryph.com/account/binding/v1/u8_token_by_uid"
)
_ROLE_LOGIN_URL = "https://ak.hypergryph.com/user/api/role/login"
_CATEGORY_URL = "https://ak.hypergryph.com/user/api/inquiry/gacha/cate"
_HISTORY_URL = "https://ak.hypergryph.com/user/api/inquiry/gacha/history"

# 单池翻页之间的间隔。官方接口没有公布限流阈值，取与本体签到相同的量级，
# 宁可慢一点也不要触发账号风控。
_PAGE_INTERVAL = 0.25

# 一次最多读取的卡池数。上游一次就返回全部卡池，这里只做上限保护，
# 避免某个异常账号返回几百个卡池把读取拖成几分钟。
_MAX_CATEGORIES = 50

# 单请求超时。宿主社区客户端不预设超时，弱网下官方接口偶尔要十几秒才回，
# 25 秒既能等到又不至于让用户以为已经卡死。
_TIMEOUT_SECONDS = 25.0


async def _api_data(
    client: httpx.AsyncClient,
    url: str,
    *,
    payload: dict[str, object] | None = None,
    params: dict[str, str | int] | None = None,
    headers: dict[str, str] | None = None,
    status_key: str = "code",
    require_data: bool = True,
) -> object:
    """请求一个森空岛/明日方舟接口并按业务码判定成败。

    上游把业务码放在响应体里（森空岛用 status，明日方舟用 code），
    HTTP 200 不代表成功，所以这里必须自己看业务码；失败时不带响应正文，
    只抛固定文案。
    """

    try:
        response = await client.request(
            "POST" if payload is not None else "GET",
            url,
            params=params,
            json=payload,
            headers=headers,
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        # 连接失败、超时与 4xx/5xx 都收敛成一句可展示的话：调用方要的是
        # 「等一下再试」，不是 httpx 的异常类名和上游地址。
        raise ValueError("官方记录接口请求失败，请检查网络后重试") from error
    try:
        result = response.json()
    except ValueError as error:
        raise ValueError("官方记录接口返回了无法解析的内容") from error
    if (
        not isinstance(result, dict)
        or result.get(status_key) != 0
        or (require_data and result.get("data") is None)
    ):
        raise ValueError("官方记录接口未返回有效数据，请检查授权时效或角色绑定")
    return result.get("data")


def hg_record(uid: str, item: dict[str, object], *, pool: str) -> GachaRecord:
    """把一条上游寻访记录转成插件记录。

    上游 rarity 是 0 基星级（六星存 5），这里加一还原成玩家熟悉的
    1~6 星；时间戳可能是秒也可能是毫秒，按量级判断。
    """

    stamp = int(item["gachaTs"])  # type: ignore[arg-type]
    moment = datetime.fromtimestamp(
        stamp / (1000 if stamp > 10_000_000_000 else 1), tz=UTC8
    ).strftime("%Y-%m-%d %H:%M:%S")
    return GachaRecord(
        game="arknights",
        playerUid=uid,
        id=str(item.get("seqId") or f"{stamp}:{item['pos']}"),
        poolType=pool,
        poolName=str(item.get("poolName") or ""),
        name=str(item.get("charName") or item.get("weaponName") or ""),
        itemId=str(item.get("charId") or item.get("weaponId") or ""),
        itemType="武器" if item.get("weaponId") else "角色",
        rarity=int(item["rarity"]) + 1,  # type: ignore[arg-type]
        time=moment,
        isFree=bool(item.get("isFree", False)),
        kind=str(item.get("kind") or ""),
    )


async def _role_tokens(
    client: httpx.AsyncClient, credential: str, uid: str
) -> tuple[str, str]:
    """用账号组里的森空岛凭据换到 (account_token, role_token)。"""

    from auto_mas_core.host.tools_common_community_providers import skland

    token = skland.parse_skland_credential(credential).get("oauthToken", "")
    if not token or not uid.strip():
        raise ValueError("需要含 OAuth Token 的森空岛账号及游戏 UID")

    grant = await _api_data(
        client,
        _GRANT_URL,
        payload={"appCode": _APP_CODE, "token": token, "type": 1},
        status_key="status",
    )
    if not isinstance(grant, dict) or not isinstance(grant.get("token"), str):
        raise ValueError("森空岛通行证授权响应无效")

    role = await _api_data(
        client,
        _ROLE_TOKEN_URL,
        payload={"uid": uid.strip(), "token": grant["token"]},
        status_key="status",
    )
    if not isinstance(role, dict) or not isinstance(role.get("token"), str):
        raise ValueError("角色授权响应无效")

    role_token = role["token"]
    if not role_token:
        raise ValueError("角色授权响应无效")
    return token, role_token


async def fetch_arknights(
    client: httpx.AsyncClient,
    credential: str,
    uid: str,
    *,
    max_pages: int,
) -> tuple[list[GachaRecord], list[str]]:
    """读取一个明日方舟角色的全部寻访记录。

    单个卡池失败只记一条告警并继续下一个池：上游偶发一次 500 不代表整个账号
    的数据都取不到，把已经拿到的记录丢掉才是更大的损失。返回
    (记录列表, 告警列表)，告警文案面向用户，不含上游正文。
    """

    account_token, role_token = await _role_tokens(client, credential, uid)
    # role/login 只做登录态建立，返回体是空的，因此不要求 data 非空。
    await _api_data(
        client,
        _ROLE_LOGIN_URL,
        payload={"token": role_token},
        require_data=False,
    )

    headers = {"X-Account-Token": account_token, "X-Role-Token": role_token}
    categories = await _api_data(
        client,
        _CATEGORY_URL,
        params={"uid": uid.strip()},
        headers=headers,
    )
    if not isinstance(categories, list):
        raise ValueError("明日方舟卡池列表无效")

    records: list[GachaRecord] = []
    warnings: list[str] = []
    for category in categories[:_MAX_CATEGORIES]:
        if not isinstance(category, dict) or "id" not in category:
            continue
        pool = str(category["id"])
        try:
            records.extend(
                await _fetch_pool(client, headers, uid.strip(), pool, max_pages)
            )
        except _PageLimit as limit:
            # 翻到上限不算失败：已读到的记录照收，只提示这个池没读完。
            records.extend(limit.records)
            warnings.append(f"明日方舟卡池 {limit.pool} 达分页上限")
        except Exception:
            warnings.append(f"明日方舟卡池 {pool} 读取未完成")
    return records, warnings


async def _fetch_pool(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    uid: str,
    pool: str,
    max_pages: int,
) -> list[GachaRecord]:
    """翻页读取单个卡池；按 (gachaTs, pos) 游标继续，重复游标视为异常。"""

    params: dict[str, str | int] = {"uid": uid, "category": pool, "size": 100}
    records: list[GachaRecord] = []
    seen: set[tuple[str, str]] = set()
    for page in range(max_pages):
        data = await _api_data(
            client,
            _HISTORY_URL,
            params=params,
            headers=headers,
        )
        if not isinstance(data, dict) or not isinstance(data.get("list"), list):
            raise ValueError("寻访记录响应无效")

        batch = data["list"]
        if not batch:
            break
        records.extend(hg_record(uid, item, pool=pool) for item in batch)

        if not data.get("hasMore"):
            break
        cursor = (str(batch[-1]["gachaTs"]), str(batch[-1]["pos"]))
        if cursor in seen:
            raise ValueError("寻访分页重复")
        seen.add(cursor)
        params["gachaTs"], params["pos"] = cursor
        if page + 1 == max_pages:
            raise _PageLimit(pool, records)
        await asyncio.sleep(_PAGE_INTERVAL)
    return records


class _PageLimit(RuntimeError):
    """单池翻页达到上限；由调用方翻译成用户告警并收回已读记录。"""

    __slots__ = ("pool", "records")

    def __init__(self, pool: str, records: list[GachaRecord]) -> None:
        """记录是哪个卡池到达上限、以及该池已经取到的记录。"""

        super().__init__(pool)
        self.pool = pool
        self.records = records
