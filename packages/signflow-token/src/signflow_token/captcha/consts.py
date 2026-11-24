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

"""极验 v4 请求常量。

RSA 公钥与 captcha_id 取自 mxyooR/Kuro_login（MIT），经 Better-MAS-Tools
（AGPL-3.0）的 app/tools/_geetest/consts.py 转述。
"""

from __future__ import annotations

# 库街区登录页固定使用的 captcha_id；换站点时换这一个常量即可。
KURO_CAPTCHA_ID = "3f7e2d848ce0cb7e7d019d621e556ce2"

# 极验 w 参数加密用的固定 RSA 公钥（模数与指数），来源同上游 Kuro_login。
RSA_KEY_N = int(
    "00C1E3934D1614465B33053E7F48EE4EC87B14B95EF88947713D25EECBFF7E74C7977D02DC1D"
    "9451F79DD5D1C10C29ACB6A9B4D6FB7D0A0279B6719E1772565F09AF627715919221AEF91899"
    "CAE08C0D686D748B20A3603BE2318CA6BC2B59706592A9219D0BF05C9F65023A21D233080725"
    "2AE0066D59CEEFA5F2748EA80BAB81",
    16,
)
RSA_KEY_E = int("10001", 16)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
    )
}
