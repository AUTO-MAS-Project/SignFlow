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

"""SignFlow Token 获取附属插件。插件实例。"""

from __future__ import annotations

from collections.abc import Iterable

from auto_mas_core import ExtensionPlugin

from .config import TokenConfig
from .credentials import TokenFacade
from .login import LoginFacade


class Plugin(ExtensionPlugin):
    """SignFlow Token 获取附属插件。

    只声明对核心插件服务 `signflow.community` 的依赖：账号列表、凭据字段、
    平台名和代理一律经核心插件门面取，本插件不自己读宿主配置。
    """

    requires = ("signflow.community",)

    config_class = TokenConfig

    provides_services = {
        "signflow.token": "credential_status",
        "signflow.token.refresh": "refresh_credential",
        "signflow.token.login": "open_login",
        "signflow.token.login.send": "send_login_code",
        "signflow.token.login.submit": "submit_login_code",
    }

    def __init__(self, config=None, record=None) -> None:
        super().__init__(config=config, record=record)
        self._tokens = TokenFacade()
        # 会话里带着手机号与在途凭据，只能随插件实例存活。
        self._login = LoginFacade(lambda: self.config)

    async def on_disable(self) -> None:
        """停用插件时收掉在途短信登录，别让定时器打到已停用的实例上。"""

        self._login.close()

    async def credential_status(
        self, account_ids: Iterable[str] | None = None
    ) -> tuple[dict[str, object], ...]:
        """盘点各账号的社区凭据配置与格式状态。

        做成协程与其他附属插件服务保持一致：调用方不必为哪个同步哪个异步分叉。
        """

        return self._tokens.status(account_ids)

    async def refresh_credential(
        self, account_uid: str, fields: Iterable[str] | None = None
    ) -> dict[str, object]:
        """刷新指定账号的凭据并写回账号组。"""

        return await self._tokens.refresh(account_uid, fields)

    async def open_login(self, account_uid: str, phone: str) -> dict[str, object]:
        """开启一次库街区短信登录会话，返回会话号与极验标识。"""

        return await self._login.open(account_uid, phone)

    async def send_login_code(
        self,
        session_id: str,
        verification: dict[str, str] | None = None,
        *,
        automatic: bool = False,
    ) -> dict[str, object]:
        """发送短信验证码；automatic=True 时先自己过一遍极验。"""

        return await self._login.send(session_id, verification, automatic=automatic)

    async def submit_login_code(self, session_id: str, code: str) -> dict[str, object]:
        """提交短信验证码，成功后把库街区凭据写回账号组。"""

        return await self._login.finish(session_id, code)
