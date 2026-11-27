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

"""库街区短信登录的会话编排。

移植自 Better-MAS-Tools 的 app/core/kuro_login.py（AGPL-3.0）。

与上游的差异只在运行方式：会话挂在插件门面上而不是模块全局，插件停用或
重载时能把在途会话一起收掉；手机号、设备码与凭据一律不进日志与 repr。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import kuro_api

SESSION_SECONDS = 600.0
SMS_INTERVAL = 60.0
MAX_ATTEMPTS = 5
MAX_SESSIONS = 16
AUTO_TIMEOUT = 15.0
YUNMA_TIMEOUT = 30.0

_PHONE = re.compile("1[3-9][0-9]{9}")
_CODE = re.compile("[0-9]{6}")

__all__ = ["LoginFacade"]


@dataclass
class _Session:
    """一次待完成的短信登录。"""

    account_uid: str
    phone: str = field(repr=False)
    device: str = field(repr=False)
    distinct: str = field(repr=False)
    sent: bool = False
    busy: bool = False
    attempts: int = 0
    credential: str = field(default="", repr=False)
    handle: asyncio.TimerHandle | None = field(default=None, repr=False)


def _community() -> Any:
    """取核心插件的账号门面实例。"""

    from auto_mas_core import Plugin

    return Plugin.services.require("signflow.community")()


def _kuro_field(community: Any) -> str:
    """库街区的凭据字段名由宿主平台注册表给出，这里不写死。"""

    return community.token_field("库街区")


async def _persist(account_uid: str, field_name: str, credential: str) -> None:
    """把登录结果写回账号组。"""

    from auto_mas_core.host.core import Config

    await Config.update_sign_flow_account(
        account_uid, {"SignFlowAccount": {field_name: credential}}
    )


class LoginFacade:
    """短信登录的三个动作：开窗、发码、换凭据。

    实例随插件存活，所以会话不需要额外清理线程；插件停用时的 `close()`
    会取消全部定时器并清空会话。
    """

    __slots__ = ("_sessions", "_cooldowns", "_config")

    def __init__(self, config_provider: Callable[[], Any]) -> None:
        self._sessions: dict[str, _Session] = {}
        self._cooldowns: dict[str, float] = {}
        self._config = config_provider

    async def open(self, account_uid: str, phone: str) -> dict[str, object]:
        """校验手机号并开一个新会话。

        做成协程是为了拿到运行中的事件循环来挂超时定时器；所有服务方法都是
        协程，调用方不用为哪个同步哪个异步分叉。
        """

        from .captcha import KURO_CAPTCHA_ID

        if _community().account(account_uid) is None:
            raise ValueError("请选择一个已保存的社区账号")
        value = str(phone or "").strip()
        if not _PHONE.fullmatch(value):
            raise ValueError("请输入有效的中国大陆手机号")
        if len(self._sessions) >= MAX_SESSIONS:
            raise ValueError("登录会话过多，请关闭其他登录窗口或稍后重试")

        session_id = secrets.token_urlsafe(32)
        session = _Session(
            account_uid=str(account_uid),
            phone=value,
            device=secrets.token_hex(20),
            distinct=secrets.token_hex(16),
        )
        loop = asyncio.get_running_loop()
        session.handle = loop.call_later(SESSION_SECONDS, self._cancel, session_id)
        self._sessions[session_id] = session
        return {"sessionId": session_id, "captchaId": KURO_CAPTCHA_ID}

    def _cancel(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None and session.handle is not None:
            session.handle.cancel()

    def cancel(self, session_id: str) -> None:
        """用户主动关窗：立刻丢弃手机号与在途凭据。"""

        self._cancel(session_id)

    def close(self) -> None:
        """插件停用：连带取消全部定时器，避免回调打到已停用的实例。"""

        for session_id in list(self._sessions):
            self._cancel(session_id)
        self._cooldowns.clear()

    def _require(self, session_id: str) -> _Session:
        session = self._sessions.get(str(session_id))
        if session is None:
            raise ValueError("短信登录已过期，请重新开始")
        return session

    def _check_interval(self, phone: str) -> str:
        """只查同一手机号距上次发送够不够 60 秒，不占用配额。"""

        key = hashlib.sha256(phone.encode("utf-8")).hexdigest()
        if self._cooldowns.get(key, 0.0) > time.monotonic():
            raise ValueError("短信发送过于频繁，请 60 秒后重试")
        return key

    def _cool_down(self, phone: str) -> None:
        """占用一条配额；真正发出短信前调用一次。"""

        key = self._check_interval(phone)
        self._cooldowns[key] = time.monotonic() + SMS_INTERVAL

    def _captcha_settings(self) -> tuple[str, str]:
        """返回（验证方式，云码密钥）。配置缺失时按人工验证处理。"""

        captcha = getattr(self._config(), "Captcha", None)
        mode = str(getattr(captcha, "Mode", "manual") or "manual")
        token = str(getattr(captcha, "YunmaToken", "") or "")
        return mode, token

    async def _auto_verification(self, token: str) -> dict[str, Any]:
        """跑一次极验自动通过。"""

        from .captcha import KURO_CAPTCHA_ID, Geetest

        async with Geetest(
            KURO_CAPTCHA_ID, proxy=_community().proxy(), yunma_token=token
        ) as geetest:
            return json.loads(await geetest.fetch_sec_code())

    async def send(
        self,
        session_id: str,
        verification: dict[str, str] | None = None,
        *,
        automatic: bool = False,
    ) -> dict[str, object]:
        """发短信；automatic=True 时先自己过一遍极验。"""

        session = self._require(session_id)
        if not automatic:
            return await self._deliver(session_id, session, verification)

        mode, token = self._captcha_settings()
        if mode != "yunma":
            # 没配云码就直接让调用方走人工，不要返回假成功。
            return {"sent": False, "message": "请完成人工验证"}

        # 自动验证要跑几秒，这里只查不占配额，配额留给真正发短信的那一刻。
        self._check_interval(session.phone)
        session.busy = True
        try:
            result = await asyncio.wait_for(
                self._auto_verification(token),
                timeout=YUNMA_TIMEOUT if token else AUTO_TIMEOUT,
            )
        except TimeoutError:
            return {"sent": False, "message": "自动验证超时，请改用人工验证"}
        except ValueError as error:
            return {"sent": False, "message": str(error)}
        finally:
            session.busy = False

        if not isinstance(result, dict):
            return {"sent": False, "message": "自动验证未取得有效结果，请使用人工验证"}
        return await self._deliver(session_id, session, result)

    async def _deliver(
        self,
        session_id: str,
        session: _Session,
        verification: dict[str, str] | None,
    ) -> dict[str, object]:
        """发出短信；调用方已备好验证材料。"""

        from .captcha import KURO_CAPTCHA_ID

        payload = dict(verification or {})
        if payload.get("captcha_id") != KURO_CAPTCHA_ID:
            raise ValueError("请先完成人机验证")
        for key in ("lot_number", "pass_token", "gen_time", "captcha_output"):
            if not str(payload.get(key) or ""):
                raise ValueError("请先完成人机验证")

        if session.busy:
            raise ValueError("登录请求正在执行，请稍候")
        self._cool_down(session.phone)
        session.busy = True
        try:
            await kuro_api.request_sms(
                phone=session.phone,
                verification={key: str(value) for key, value in payload.items()},
                device=session.device,
                distinct=session.distinct,
                proxy=_community().proxy(),
            )
            # 请求期间会话可能被关窗或超时回收，写状态前重新确认。
            self._require(session_id)
            session.sent = True
            session.attempts = 0
            session.credential = ""
        finally:
            session.busy = False
        return {"sent": True, "message": "短信已发送"}

    async def finish(self, session_id: str, code: str) -> dict[str, object]:
        """校验验证码、换凭据并写回账号。"""

        session = self._require(session_id)
        if session.busy:
            raise ValueError("登录请求正在执行，请稍候")
        if not session.sent:
            raise ValueError("请先发送短信验证码")
        value = str(code or "").strip()
        if not _CODE.fullmatch(value):
            raise ValueError("请输入六位短信验证码")
        if session.attempts >= MAX_ATTEMPTS and not session.credential:
            raise ValueError("验证码尝试次数已用完，请重新发送")

        proxy = _community().proxy()
        if not session.credential:
            session.attempts += 1
            session.credential = await kuro_api.login_with_sms(
                phone=session.phone,
                code=value,
                device=session.device,
                distinct=session.distinct,
                proxy=proxy,
            )

        field_name = _kuro_field(_community())
        # 写盘失败时保留短时正式凭据：重试保存不会再消费一次短信码。
        await _persist(session.account_uid, field_name, session.credential)
        account_uid = session.account_uid
        self.cancel(session_id)
        return {
            "uid": account_uid,
            "field": field_name,
            "message": "库街区凭据已保存",
        }
