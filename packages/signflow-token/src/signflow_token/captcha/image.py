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
"""验证码图片解码：限制大小与格式，剥掉 PNG 元数据后再交给识别。

移植自 Better-MAS-Tools 的 app/tools/captcha_image.py（AGPL-3.0）。
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

MAX_IMAGE_BYTES = 2_000_000
MAX_IMAGE_SIDE = 2048
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_PNG_KEEP = {b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND"}
_PNG_ANIMATED = {b"acTL", b"fcTL", b"fdAT"}


def _strip_png(raw: bytes) -> bytes:
    """只保留渲染必需的分块，丢弃可执行的文本与动画帧。"""

    if not raw.startswith(_PNG_MAGIC):
        return raw
    out = bytearray(_PNG_MAGIC)
    offset = len(_PNG_MAGIC)
    while offset + 8 <= len(raw):
        length = int.from_bytes(raw[offset : offset + 4], "big")
        kind = raw[offset + 4 : offset + 8]
        end = offset + 12 + length
        if length < 0 or end > len(raw):
            raise ValueError("验证码 PNG 格式无效")
        if kind in _PNG_ANIMATED:
            raise ValueError("验证码不支持动画图片")
        if kind in _PNG_KEEP:
            out += raw[offset:end]
        offset = end
        if kind == b"IEND":
            break
    return bytes(out)


@contextmanager
def open_captcha_image(raw: bytes) -> Iterator[Any]:
    """把下载到的字节解成图像对象，限制总大小与边长。"""

    from PIL import Image

    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("验证码图片大小无效")
    image = Image.open(io.BytesIO(_strip_png(raw)), formats=("PNG", "JPEG"))
    width, height = image.size
    if not (1 <= width <= MAX_IMAGE_SIDE and 1 <= height <= MAX_IMAGE_SIDE):
        raise ValueError("验证码图片尺寸无效")
    try:
        yield image
    finally:
        image.close()
