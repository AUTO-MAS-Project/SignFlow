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
"""云码图标点选识别：只在用户配置了密钥的图标验证码上使用。

移植自 Better-MAS-Tools 的 app/tools/yunma.py（AGPL-3.0）。密钥由用户自备，
请求只发一次；任何失败都降级为人工验证，不在自动识别上反复重试。
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from .errors import CaptchaError

YUNMA_URL = "https://api.jfbym.com/api/YmServer/customApi"
_CODE_REASON = {
    "10001": "云码请求参数有误，请改用人工验证",
    "10002": "云码余额不足，请充值后重试或改用人工验证",
    "10003": "云码 API 密钥无效或没有访问权限，请检查设置",
    "10004": "云码不支持当前识别类型，请使用人工验证",
    "10007": "云码暂时无法识别此次验证码，请使用人工验证",
}


async def recognize_icons(
    client: httpx.AsyncClient, image: bytes, *, token: str, count: int
) -> list[tuple[int, int]]:
    """返回按点击顺序排列的图片坐标。"""

    if not token:
        raise CaptchaError("当前为图标验证码，请人工完成或在设置中配置云码")

    payload = {
        "token": token,
        "type": "30332",
        "image": base64.b64encode(image).decode("ascii"),
        "direction": "bottom",
        "click_num": str(count),
    }
    try:
        response = await client.post(YUNMA_URL, json=payload)
        response.raise_for_status()
        body: Any = response.json()
    except httpx.HTTPError as error:
        raise CaptchaError("云码识别请求失败，请使用人工验证") from error
    except ValueError as error:
        raise CaptchaError("云码返回了无效响应，请使用人工验证") from error

    if not isinstance(body, dict):
        raise CaptchaError("云码返回了无效响应，请使用人工验证")
    code = str(body.get("code"))
    if code != "10000":
        raise CaptchaError(
            _CODE_REASON.get(code, "云码未能识别此次验证码，请使用人工验证")
        )

    result = body.get("data")
    if (
        not isinstance(result, dict)
        or result.get("code") not in (None, 0, "0")
        or not isinstance(result.get("data"), str)
    ):
        raise CaptchaError("云码返回了无效的坐标结果")

    points: list[tuple[int, int]] = []
    for pair in result["data"].split("|"):
        parts = pair.split(",")
        if len(parts) != 2:
            raise CaptchaError("云码返回的点击坐标不匹配")
        try:
            x, y = int(float(parts[0])), int(float(parts[1]))
        except ValueError as error:
            raise CaptchaError("云码返回的点击坐标不匹配") from error
        if x < 0 or y < 0:
            raise CaptchaError("云码返回的点击坐标不匹配")
        points.append((x, y))
    if len(points) != count:
        raise CaptchaError("云码返回的点击坐标不匹配")
    return points
