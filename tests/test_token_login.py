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

"""短信登录门面：手机号校验、验证码前置、冷却与写回，逐条覆盖。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from auto_mas_core import Plugin
from signflow_token import login
from signflow_token.captcha import CaptchaError
from signflow_token.login import MAX_ATTEMPTS, MAX_SESSIONS, LoginFacade

_CAPTCHA_ID = "3f7e2d848ce0cb7e7d019d621e556ce2"


@dataclass
class _Account:
    """账号门面的最小投影。"""

    uid: str
    name: str = "主号"
    enabled: bool = True


class _Community:
    """核心插件账号门面的替身：只实现短信登录用到的三个方法。"""

    def __init__(self, accounts: list[_Account]) -> None:
        self._accounts = accounts

    def account(self, account_uid: str):
        """按 UID 取账号；None 表示账号组不存在。"""

        return next((item for item in self._accounts if item.uid == account_uid), None)

    def token_field(self, platform: str) -> str:
        """库街区对应的凭据字段名。"""

        assert platform == "库街区"
        return "KuroToken"

    def proxy(self) -> str:
        """宿主代理设置；测试里留空，不真的走网络。"""

        return ""


class _Registry:
    """宿主服务表的替身：require 返回「调用后得到门面」的方法。"""

    def __init__(self, community: _Community) -> None:
        self._community = community

    def require(self, name: str):
        """只认核心插件账号服务。"""

        assert name == "signflow.community"
        return lambda: self._community


_PERSISTED: list[tuple[str, str, str]] = []


async def _recorder(account_uid: str, field_name: str, credential: str) -> None:
    """记录写回动作，避免真的改账号配置。"""

    _PERSISTED.append((account_uid, field_name, credential))


def _patch(monkeypatch, *, accounts=None, mode="manual", yunma=""):
    """把账号门面、配置与写回全部换成替身。"""

    community = _Community(accounts if accounts is not None else [_Account("acc")])
    monkeypatch.setattr(Plugin, "services", _Registry(community), raising=False)
    config = SimpleNamespace(Captcha=SimpleNamespace(Mode=mode, YunmaToken=yunma))
    facade = LoginFacade(lambda: config)
    monkeypatch.setattr(login, "_persist", _recorder)
    _PERSISTED.clear()
    return facade


def _verification(**overrides) -> dict[str, str]:
    """一份完整的极验验证材料。"""

    payload = {
        "captcha_id": _CAPTCHA_ID,
        "lot_number": "lot",
        "pass_token": "pass",
        "gen_time": "1",
        "captcha_output": "out",
    }
    payload.update(overrides)
    return payload


def _stub_sms(monkeypatch, error: Exception | None = None) -> list[dict]:
    """把短信发送换成记录调用，不真的打库街区接口。"""

    calls: list[dict] = []

    async def _request_sms(**kwargs):
        """记录一次发送请求。"""

        calls.append(kwargs)
        if error is not None:
            raise error

    monkeypatch.setattr(login.kuro_api, "request_sms", _request_sms)
    return calls


def _stub_login(monkeypatch, credential: str) -> list[dict]:
    """把验证码换凭据换成固定返回值。"""

    calls: list[dict] = []

    async def _login_with_sms(**kwargs):
        """记录一次登录请求。"""

        calls.append(kwargs)
        return credential

    monkeypatch.setattr(login.kuro_api, "login_with_sms", _login_with_sms)
    return calls


def test_open_rejects_unknown_account(monkeypatch) -> None:
    """账号组不存在时提示去选一个，不抛 KeyError。"""

    facade = _patch(monkeypatch, accounts=[])

    async def _scenario():
        """按真实调用顺序开窗。"""

        with pytest.raises(ValueError, match="已保存的社区账号"):
            await facade.open("missing", "13800000000")

    asyncio.run(_scenario())


def test_open_rejects_bad_phone(monkeypatch) -> None:
    """手机号必须是 11 位大陆号码，否则不发请求。"""

    facade = _patch(monkeypatch)

    async def _scenario():
        """按真实调用顺序开窗。"""

        with pytest.raises(ValueError, match="中国大陆手机号"):
            await facade.open("acc", "12345")

    asyncio.run(_scenario())


def test_open_returns_session_and_captcha_id(monkeypatch) -> None:
    """开窗成功给出会话号与极验标识，手机号不回显。"""

    facade = _patch(monkeypatch)

    async def _scenario():
        """开窗后检查回话内容。"""

        result = await facade.open("acc", " 13800000000 ")
        assert result["captchaId"] == _CAPTCHA_ID
        assert isinstance(result["sessionId"], str) and result["sessionId"]
        assert "13800000000" not in repr(result)
        facade.close()

    asyncio.run(_scenario())


def test_open_rejects_when_too_many_sessions(monkeypatch) -> None:
    """会话数到上限就要求先关窗，避免手机号长期留在进程里。"""

    facade = _patch(monkeypatch)

    async def _scenario():
        """开满上限再多开一个。"""

        for _ in range(MAX_SESSIONS):
            await facade.open("acc", "13800000000")
        with pytest.raises(ValueError, match="登录会话过多"):
            await facade.open("acc", "13800000000")
        facade.close()

    asyncio.run(_scenario())


def test_send_requires_verification(monkeypatch) -> None:
    """没有验证材料就要求先过极验，不能只凭会话号发码。"""

    facade = _patch(monkeypatch)

    async def _scenario():
        """不带验证材料发码。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        with pytest.raises(ValueError, match="请先完成人机验证"):
            await facade.send(session_id, None)
        facade.close()

    asyncio.run(_scenario())


def test_send_rejects_foreign_captcha_id(monkeypatch) -> None:
    """验证材料来自别的极验场景时也拒绝。"""

    facade = _patch(monkeypatch)

    async def _scenario():
        """拿别的场景的验证材料发码。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        with pytest.raises(ValueError, match="请先完成人机验证"):
            await facade.send(session_id, _verification(captcha_id="other"))
        facade.close()

    asyncio.run(_scenario())


def test_send_marks_session_sent(monkeypatch) -> None:
    """发码成功后会话进入已发送，验证码可以接着提交。"""

    facade = _patch(monkeypatch)
    calls = _stub_sms(monkeypatch)

    async def _scenario():
        """发一次码并检查请求内容。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        result = await facade.send(session_id, _verification())
        assert result == {"sent": True, "message": "短信已发送"}
        assert calls[0]["phone"] == "13800000000"
        assert calls[0]["verification"]["lot_number"] == "lot"
        facade.close()

    asyncio.run(_scenario())
    assert len(calls) == 1


def test_send_cools_down_same_phone(monkeypatch) -> None:
    """同一手机号 60 秒内只发一条。"""

    facade = _patch(monkeypatch)
    _stub_sms(monkeypatch)

    async def _scenario():
        """连开两个会话、各发一次。"""

        first = (await facade.open("acc", "13800000000"))["sessionId"]
        second = (await facade.open("acc", "13800000000"))["sessionId"]
        await facade.send(first, _verification())
        with pytest.raises(ValueError, match="过于频繁"):
            await facade.send(second, _verification())
        facade.close()

    asyncio.run(_scenario())


def test_send_automatic_falls_back_when_manual_mode(monkeypatch) -> None:
    """没开自动验证时如实说请人工，不返回假成功。"""

    facade = _patch(monkeypatch, mode="manual")
    calls = _stub_sms(monkeypatch)

    async def _scenario():
        """按自动验证方式发码。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        result = await facade.send(session_id, None, automatic=True)
        assert result == {"sent": False, "message": "请完成人工验证"}
        assert calls == []
        facade.close()

    asyncio.run(_scenario())


def test_send_automatic_reports_captcha_failure(monkeypatch) -> None:
    """自动验证失败把极验原因带出来，让用户改走人工。"""

    facade = _patch(monkeypatch, mode="yunma")
    calls = _stub_sms(monkeypatch)

    async def _fail(self, token: str):
        """模拟极验未通过。"""

        raise CaptchaError("极验未通过本次识别结果")

    # 门面用 __slots__，实例属性只读，替身只能打在类上。
    monkeypatch.setattr(LoginFacade, "_auto_verification", _fail)

    async def _scenario():
        """自动验证失败时不得发出短信。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        result = await facade.send(session_id, None, automatic=True)
        assert result["sent"] is False
        assert "极验未通过本次识别结果" in str(result["message"])
        assert calls == []
        facade.close()

    asyncio.run(_scenario())


def test_finish_requires_sent_code(monkeypatch) -> None:
    """没发短信就提交验证码会被拦住。"""

    facade = _patch(monkeypatch)

    async def _scenario():
        """跳发码直接提交。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        with pytest.raises(ValueError, match="请先发送短信验证码"):
            await facade.finish(session_id, "123456")
        facade.close()

    asyncio.run(_scenario())


def test_finish_rejects_bad_code_shape(monkeypatch) -> None:
    """验证码必须是六位数字。"""

    facade = _patch(monkeypatch)
    _stub_sms(monkeypatch)

    async def _scenario():
        """发码后提交四位码。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        await facade.send(session_id, _verification())
        with pytest.raises(ValueError, match="六位短信验证码"):
            await facade.finish(session_id, "1234")
        facade.close()

    asyncio.run(_scenario())


def test_finish_persists_credential_and_closes_session(monkeypatch) -> None:
    """登录成功把凭据写回账号组，并立刻丢掉会话。"""

    facade = _patch(monkeypatch)
    _stub_sms(monkeypatch)
    login_calls = _stub_login(monkeypatch, "{kuro}")

    async def _scenario():
        """走完发码与登录两步。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        await facade.send(session_id, _verification())
        result = await facade.finish(session_id, "123456")
        assert result == {
            "uid": "acc",
            "field": "KuroToken",
            "message": "库街区凭据已保存",
        }
        with pytest.raises(ValueError, match="已过期"):
            await facade.finish(session_id, "123456")

    asyncio.run(_scenario())
    assert _PERSISTED == [("acc", "KuroToken", "{kuro}")]
    assert len(login_calls) == 1


def test_finish_stops_after_attempt_limit(monkeypatch) -> None:
    """连续输错到上限就要求重新发码，不再打上游接口。"""

    facade = _patch(monkeypatch)
    _stub_sms(monkeypatch)
    calls = _stub_login(monkeypatch, "")

    async def _wrong(**kwargs):
        """模拟验证码错误。"""

        raise ValueError("库街区登录未完成（code=1001）")

    monkeypatch.setattr(login.kuro_api, "login_with_sms", _wrong)

    async def _scenario():
        """把尝试次数用完再提交一次。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        await facade.send(session_id, _verification())
        for _ in range(MAX_ATTEMPTS):
            with pytest.raises(ValueError, match="未完成"):
                await facade.finish(session_id, "123456")
        with pytest.raises(ValueError, match="尝试次数已用完"):
            await facade.finish(session_id, "123456")
        facade.close()

    asyncio.run(_scenario())
    assert calls == []


def test_close_drops_sessions(monkeypatch) -> None:
    """插件停用后会话不可再用，在途手机号随之释放。"""

    facade = _patch(monkeypatch)

    async def _scenario():
        """停用后再用旧会话号。"""

        session_id = (await facade.open("acc", "13800000000"))["sessionId"]
        facade.close()
        with pytest.raises(ValueError, match="已过期"):
            await facade.send(session_id, _verification())

    asyncio.run(_scenario())
