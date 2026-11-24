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
"""极验 w 参数编码：随机 key 走 RSA，轨迹 JSON 走 AES-CBC。"""

from __future__ import annotations

import json
import random
import string
import time
from typing import Any

from .consts import RSA_KEY_E, RSA_KEY_N

_ALPHABET = string.ascii_lowercase + string.digits


def random_string(alphabet: str, length: int) -> str:
    """按给定字符集取随机串。"""

    return "".join(random.choice(alphabet) for _ in range(length))


def get_current_timestamp(*, is_ms: bool = True) -> int:
    """当前时间戳；默认毫秒。"""

    value = time.time() * (1000 if is_ms else 1)
    return int(round(value))


def get_guid() -> str:
    """极验要求 16 位小写字母数字标识。"""

    return random_string(_ALPHABET, 16)


def geetest_rsa_enc(plaintext: str) -> str:
    """用固定公钥加密明文，返回偶数长度 hex。"""

    from Crypto.Cipher import PKCS1_v1_5
    from Crypto.PublicKey import RSA

    public_key = RSA.construct((RSA_KEY_N, RSA_KEY_E))
    cipher = PKCS1_v1_5.new(public_key)
    encrypted = cipher.encrypt(plaintext.encode("utf-8")).hex()
    # PKCS1 加密结果偶尔出现奇数长度 hex，极验侧按字节数解析，补前导 0。
    return encrypted if len(encrypted) % 2 == 0 else "0" + encrypted


def geetest_m(track: dict[str, Any]) -> str:
    """把轨迹 JSON 压成极验的 w 参数。"""

    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad

    key = get_guid()
    rsa_hex = geetest_rsa_enc(key)
    iv = "0000000000000000".encode()
    payload = json.dumps(track).encode("utf-8")
    aes_hex = (
        AES.new(key=key.encode(), mode=AES.MODE_CBC, iv=iv)
        .encrypt(pad(payload, 16, "pkcs7"))
        .hex()
    )
    return aes_hex + rsa_hex
