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

from .credentials import TokenFacade


class Plugin(ExtensionPlugin):
    """SignFlow Token 获取附属插件。

    只声明对核心插件服务 `signflow.community` 的依赖：账号列表、凭据字段、
    平台名和代理一律经核心插件门面取，本插件不自己读宿主配置。
    """

    requires = ("signflow.community",)

    provides_services = {
        "signflow.token": "credential_status",
        "signflow.token.refresh": "refresh_credential",
    }

    def __init__(self, config=None, record=None) -> None:
        super().__init__(config=config, record=record)
        self._tokens = TokenFacade()

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
