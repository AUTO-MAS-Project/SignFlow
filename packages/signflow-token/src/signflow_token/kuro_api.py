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

"""库街区短信登录的两个官方接口。

移植自 Better-MAS-Tools 的 app/tools/kuro.py 中 request_kuro_sms /
login_kuro_sms / _check_kuro_login_response（AGPL-3.0），请求字段与头部
模板参考 mxyooR/Kuro_login（MIT）。

只做协议本身：不建会话、不管冷却、不写账号，那些由上层门面负责。
错误消息只回显业务码，绝不回显可能含手机号或 Token 的响应正文。
"""

from __future__ import annotations

import json
from typing import Any

import httpx

SMS_URL = "https://api.kurobbs.com/user/getSmsCode"
LOGIN_URL = "https://api.kurobbs.com/user/sdkLogin"

__all__ = ["LOGIN_URL", "SMS_URL", "login_with_sms", "request_sms"]


def _headers(device: str, distinct: str) -> dict[str, str]:
    """复用宿主的库街区头部模板，登录前没有 Token 就留空。"""

    from auto_mas_core.host.tools_common_community_providers import kuro

    return kuro._kuro_request_headers(kuro.BBS_HEADERS, "", device, distinct)


def _check(response: httpx.Response, stage: str) -> dict[str, Any]:
    """把业务码翻成可展示的失败原因，成功时返回整个响应体。"""

    try:
        payload: Any = response.json()
    except ValueError as error:
        raise ValueError(f"库街区{stage}响应无效，请稍后重试") from error
    if not isinstance(payload, dict):
        raise ValueError(f"库街区{stage}响应格式无效，请稍后重试")

    code = str(payload.get("code", ""))
    if not response.is_success or code != "200":
        safe_code = code if code.isdigit() and len(code) <= 8 else "未知"
        raise ValueError(
            f"库街区{stage}未完成（code={safe_code}），请检查验证码或稍后重试"
        )
    return payload


async def request_sms(
    *,
    phone: str,
    verification: dict[str, str],
    device: str,
    distinct: str,
    proxy: str | None = None,
) -> None:
    """带上极验通过的凭据请求一条短信。"""

    from auto_mas_core.host.tools_common_community_providers import kuro

    client = kuro.create_community_client(proxy)
    try:
        response = await client.post(
            SMS_URL,
            headers=_headers(device, distinct),
            data={"mobile": phone, "geeTestData": json.dumps(verification)},
            timeout=20.0,
        )
    except httpx.HTTPError as error:
        raise ValueError("库街区短信发送请求失败，请检查网络后重试") from error
    finally:
        await client.aclose()

    _check(response, "短信发送")


async def login_with_sms(
    *,
    phone: str,
    code: str,
    device: str,
    distinct: str,
    proxy: str | None = None,
) -> str:
    """用短信验证码换凭据，返回可直接写进账号配置的 JSON 串。"""

    from auto_mas_core.host.tools_common_community_providers import kuro

    client = kuro.create_community_client(proxy)
    try:
        response = await client.post(
            LOGIN_URL,
            headers=_headers(device, distinct),
            data={"mobile": phone, "code": code, "devCode": device, "gameList": ""},
            timeout=20.0,
        )
    except httpx.HTTPError as error:
        raise ValueError("库街区登录请求失败，请检查网络后重试") from error
    finally:
        await client.aclose()

    data = _check(response, "登录").get("data")
    if not isinstance(data, dict):
        raise ValueError("库街区登录未取得完整凭据")
    token = data.get("token")
    user_id = data.get("userId")
    if not isinstance(token, str) or not token.strip() or not user_id:
        raise ValueError("库街区登录未取得完整凭据")

    return json.dumps(
        {
            "token": token.strip(),
            "userId": str(user_id),
            "devCode": device,
            "distinctId": distinct,
        },
        ensure_ascii=False,
    )
