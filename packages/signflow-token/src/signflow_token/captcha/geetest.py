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

"""极验第四代接口的自动通过流程：load → pow → 轨迹 → verify。

移植自 Better-MAS-Tools 的 app/tools/_geetest/geetest.py（AGPL-3.0），
原始实现 Copyright (c) 2025 MX，改写自 mxyooR/Kuro_login（MIT）。

与上游的差异：HTTP 客户端由调用方传入（复用宿主的社区客户端，享受同一套
代理与 DNS 兜底），本模块不自己建连接池。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from . import slide
from .consts import DEFAULT_HEADERS, KURO_CAPTCHA_ID
from .errors import CaptchaError
from .utils import geetest_m, get_current_timestamp, get_guid

_LOAD_URL = "https://gcaptcha4.geetest.com/load"
_VERIFY_URL = "https://gcaptcha4.geetest.com/verify"

__all__ = ["Geetest", "KURO_CAPTCHA_ID", "create_client"]


def create_client(proxy: str | None = None) -> httpx.AsyncClient:
    """给极验用的客户端：固定 UA，忽略环境变量代理。"""

    return httpx.AsyncClient(
        headers=DEFAULT_HEADERS, timeout=20.0, proxy=proxy, trust_env=False
    )


class Geetest:
    """一次验证挑战的完整生命周期。

    自己建的客户端用 async with 关闭；外部传入的客户端由调用方负责。
    """

    CALLBACK_SIG = f"geetest_{get_current_timestamp()}"

    def __init__(
        self,
        captcha_id: str,
        *,
        client: httpx.AsyncClient | None = None,
        proxy: str | None = None,
        yunma_token: str = "",
    ) -> None:
        self.captcha_id = captcha_id
        self.proxy = proxy
        self.yunma_token = yunma_token
        self._owned = client is None
        self.client = client or create_client(proxy)
        self.callback_sig = f"geetest_{get_current_timestamp()}"
        self.geetest_info: dict[str, Any] = {}

    async def __aenter__(self) -> "Geetest":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def close(self) -> None:
        """只关闭自己建的客户端，外部传入的由调用方负责。"""

        if self._owned:
            await self.client.aclose()

    def _convert_callback(self, context: str) -> dict[str, Any]:
        """剥掉 JSONP 外壳。"""

        text = context.strip().removesuffix(";").strip()
        prefix = f"{self.callback_sig}("
        if text.startswith(prefix) and text.endswith(")"):
            text = text[len(prefix) : -1]
        try:
            payload = json.loads(text)
        except ValueError as error:
            raise CaptchaError("极验返回的验证数据格式无效，请重试") from error
        if not isinstance(payload, dict):
            raise CaptchaError("极验返回的验证数据格式无效，请重试")
        return payload

    async def _send_load(self) -> None:
        """拿一次挑战，拿到 lot_number 与 pow_detail。"""

        params = {
            "callback": self.callback_sig,
            "captcha_id": self.captcha_id,
            "client_type": "web",
            "pt": "1",
            "lang": "zho",
        }
        try:
            response = await self.client.get(_LOAD_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise CaptchaError("极验加载失败，请检查网络或本工具的代理设置") from error

        payload = self._convert_callback(response.text)
        if payload.get("status") != "success":
            raise CaptchaError("极验未能创建验证挑战，请重试")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise CaptchaError("极验返回的挑战数据无效，请重试")
        self.geetest_info = data

    def _get_pow(self) -> tuple[str, str]:
        """按挑战给出的哈希算法算 pow 签名。"""

        try:
            detail = self.geetest_info["pow_detail"]
            bits = int(detail["bits"])
            hash_func = str(detail["hashfunc"]).lower()
            timestamp = str(detail["datetime"])
        except (KeyError, TypeError, ValueError) as error:
            raise CaptchaError("极验返回的挑战数据无效，请重试") from error

        if bits != 0 or hash_func not in {"md5", "sha1", "sha256"}:
            raise CaptchaError("当前验证码需要人工验证")

        message = "|".join(
            [
                str(self.geetest_info.get("version", "")),
                str(bits),
                hash_func,
                timestamp,
                str(self.captcha_id),
                str(self.geetest_info["lot_number"]),
                get_guid(),
            ]
        )
        digest = hashlib.new(hash_func)
        digest.update(message.encode("utf-8"))
        return message, digest.hexdigest()

    async def _fetch_track(self, message: str, sign: str) -> dict[str, Any]:
        """按题型分派；只支持滑块与图标点选。"""

        captcha_type = str(self.geetest_info.get("captcha_type") or "")
        if captcha_type == "slide":
            return await slide.build_slide_track(
                self.client, self.geetest_info, message, sign
            )
        if captcha_type == "icon":
            if not self.yunma_token:
                raise CaptchaError("当前为图标验证码，请人工完成或在设置中配置云码")
            return await slide.build_icon_track(
                self.client,
                self.geetest_info,
                message,
                sign,
                yunma_token=self.yunma_token,
            )
        raise CaptchaError("当前验证码类型不支持自动识别，请使用人工验证")

    async def _verify(self, w: str) -> dict[str, Any]:
        """提交 w，校验回来的 seccode 四个字段齐全。"""

        params = {
            "callback": self.callback_sig,
            "captcha_id": self.captcha_id,
            "client_type": "web",
            "lot_number": str(self.geetest_info.get("lot_number", "")),
            "payload": str(self.geetest_info.get("payload", "")),
            "process_token": str(self.geetest_info.get("process_token", "")),
            "payload_protocol": "1",
            "pt": "1",
            "w": w,
        }
        try:
            response = await self.client.get(_VERIFY_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise CaptchaError("极验校验请求失败，请检查网络后重试") from error

        payload = self._convert_callback(response.text)
        data = payload.get("data")
        if payload.get("status") != "success" or not isinstance(data, dict):
            raise CaptchaError("极验未通过本次识别结果，请重试或使用人工验证")
        if data.get("result") != "success":
            raise CaptchaError("极验未通过本次识别结果，请重试或使用人工验证")

        proof = data.get("seccode")
        if not isinstance(proof, dict) or proof.get("captcha_id") != self.captcha_id:
            raise CaptchaError("极验未返回完整验证凭证，请重新验证")
        for key in ("lot_number", "pass_token", "gen_time", "captcha_output"):
            value = proof.get(key)
            if not isinstance(value, str) or not value:
                raise CaptchaError("极验未返回完整验证凭证，请重新验证")
        return data

    async def fetch_sec_code(self) -> str:
        """跑完整条链路，返回可直接塞进业务请求的 geeTestData。"""

        stage = "极验加载"
        try:
            await self._send_load()
            stage = "验证码图片识别"
            message, sign = self._get_pow()
            track = await self._fetch_track(message, sign)
            w = geetest_m(track)
            stage = "极验校验"
            result = await self._verify(w)
        except CaptchaError:
            raise
        except httpx.HTTPError as error:
            raise CaptchaError(f"{stage}网络请求失败，请重试或使用人工验证") from error
        except ValueError as error:
            # 图片尺寸、来源校验等上游 ValueError 都属于「识别不出来」。
            raise CaptchaError(f"{stage}未完成：{error}") from error

        return json.dumps(result["seccode"], ensure_ascii=False)
