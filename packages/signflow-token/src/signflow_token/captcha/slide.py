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

"""极验滑块与图标验证的轨迹构造。

移植自 Better-MAS-Tools 的 app/tools/_geetest/track_detact/（AGPL-3.0）。
与上游的差异：识别在本进程的线程里跑（不开子进程），且只在图片确实来自
static.geetest.com 时下载。
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from .errors import CaptchaError
from .image import open_captcha_image

_STATIC_HOST = "static.geetest.com"
_MAX_BACKGROUND_SIDE = (640, 400)
_MAX_IMAGE_BYTES = 2_000_000
_MIN_CONFIDENCE = 0.15


async def download_image(client: httpx.AsyncClient, path: str) -> bytes:
    """只允许从极验静态域下载图片，其余来源一律拒绝。"""

    url = urljoin("https://static.geetest.com/", path)
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != _STATIC_HOST:
        raise ValueError("验证码图片来源不受支持")
    if parts.port not in (None, 443):
        raise ValueError("验证码图片来源不受支持")

    chunks: list[bytes] = []
    total = 0
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > _MAX_IMAGE_BYTES:
                raise ValueError("验证码图片过大")
            chunks.append(chunk)
    return b"".join(chunks)


def _check_slide_size(size: tuple[int, int]) -> None:
    """滑块图片尺寸异常时直接交给人工，避免在错误输入上做卷积。"""

    width, height = size
    if not (
        2 <= width <= _MAX_BACKGROUND_SIDE[0] and 2 <= height <= _MAX_BACKGROUND_SIDE[1]
    ):
        raise ValueError("当前滑块图片尺寸需要人工验证")


def _distance_with_cv2(background: bytes, target: bytes) -> int:
    """用 Canny 边缘加归一化互相关找缺口横向位置。"""

    import cv2
    import numpy as np

    bg = cv2.imdecode(np.frombuffer(background, np.uint8), cv2.IMREAD_COLOR)
    tp = cv2.imdecode(np.frombuffer(target, np.uint8), cv2.IMREAD_COLOR)
    if bg is None or tp is None:
        raise ValueError("滑块图片格式无效")
    _check_slide_size((bg.shape[1], bg.shape[0]))
    _check_slide_size((tp.shape[1], tp.shape[0]))
    if tp.shape[1] > bg.shape[1]:
        raise ValueError("滑块尺寸不能大于背景")
    edge_bg = cv2.Canny(bg, 100, 200)
    edge_tp = cv2.Canny(tp, 100, 200)
    result = cv2.matchTemplate(edge_bg, edge_tp, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(result)
    return int(max_loc[0])


def _distance_with_numpy(background: bytes, target: bytes) -> int:
    """没有 opencv 时的纯 numpy 兜底：梯度边缘图加 FFT 互相关。"""

    import numpy as np

    with open_captcha_image(background) as bg_image:
        bg = np.asarray(bg_image.convert("L"), dtype=np.float64)
    with open_captcha_image(target) as tp_image:
        tp = np.asarray(tp_image.convert("L"), dtype=np.float64)
    _check_slide_size((bg.shape[1], bg.shape[0]))
    _check_slide_size((tp.shape[1], tp.shape[0]))
    if tp.shape[0] > bg.shape[0] or tp.shape[1] > bg.shape[1]:
        raise ValueError("滑块尺寸不能大于背景")

    def edges(image: Any) -> Any:
        dy, dx = np.gradient(image)
        return np.hypot(dx, dy)

    background_edges = edges(bg)
    target_edges = edges(tp)
    if float(target_edges.std()) < 1:
        raise ValueError("滑块图片缺少有效特征")

    height, width = target_edges.shape
    shape = (
        1 << (background_edges.shape[0] + height - 2).bit_length(),
        1 << (background_edges.shape[1] + width - 2).bit_length(),
    )
    kernel = target_edges - target_edges.mean()
    correlation = np.fft.irfft2(
        np.fft.rfft2(background_edges, shape) * np.fft.rfft2(kernel[::-1, ::-1], shape),
        s=shape,
    )
    correlation = correlation[
        height - 1 : background_edges.shape[0], width - 1 : background_edges.shape[1]
    ]

    def window_sum(values: Any) -> Any:
        integral = np.pad(values.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        return (
            integral[height:, width:]
            - integral[:-height, width:]
            - integral[height:, :-width]
            + integral[:-height, :-width]
        )

    energy = np.maximum(
        window_sum(background_edges * background_edges)
        - window_sum(background_edges) ** 2 / target_edges.size,
        1.0,
    )
    score = correlation / np.sqrt(energy * float((kernel * kernel).sum()))
    if float(score.max()) < _MIN_CONFIDENCE:
        raise ValueError("滑块匹配置信度不足，请人工验证")
    return int(np.unravel_index(score.argmax(), score.shape)[1])


def calculate_slide_distance(background: bytes, target: bytes) -> int:
    """同步识别缺口位置；优先 opencv，缺依赖时退回 numpy。"""

    try:
        return _distance_with_cv2(background, target)
    except ImportError:
        return _distance_with_numpy(background, target)


async def _slide_distance(client: httpx.AsyncClient, info: dict[str, Any]) -> int:
    """并发取回两张图后在线程里识别，避免阻塞事件循环。"""

    background_path = str(info.get("bg") or "")
    slice_path = str(info.get("slice") or "")
    if not background_path or not slice_path:
        raise ValueError("极验未返回滑块图片")
    background, target = await asyncio.gather(
        download_image(client, background_path),
        download_image(client, slice_path),
    )
    try:
        return await asyncio.to_thread(calculate_slide_distance, background, target)
    except ImportError as error:
        raise CaptchaError("本地缺少滑块识别依赖，请使用人工验证") from error


def slide_track(
    info: dict[str, Any], message: str, sign: str, distance: int
) -> dict[str, Any]:
    """拼出极验滑块题的 w 轨迹。"""

    return {
        "setLeft": distance,
        "passtime": 1718,
        "userresponse": distance / 1.0059466666666665 + 2,
        "device_id": "",
        "lot_number": info["lot_number"],
        "pow_msg": message,
        "pow_sign": sign,
        "geetest": "captcha",
        "lang": "zh",
        "ep": "123",
        "biht": "1426265548",
        "dRjQ": "738u",
        "em": {"ph": 0, "cp": 0, "ek": "11", "wd": 1, "nt": 0, "si": 0, "sc": 0},
    }


async def build_slide_track(
    client: httpx.AsyncClient, info: dict[str, Any], message: str, sign: str
) -> dict[str, Any]:
    """识别滑块并返回 w 轨迹。"""

    distance = await _slide_distance(client, info)
    return slide_track(info, message, sign, distance)


def compose_icons(background: bytes, icons: list[bytes]) -> tuple[bytes, int, int]:
    """把图标条贴到背景下方，拼成云码要求的单图。"""

    import io

    from PIL import Image

    with open_captcha_image(background) as bg_image:
        canvas = Image.new("RGB", (bg_image.width, bg_image.height + 64), "white")
        canvas.paste(bg_image.convert("RGB"), (0, 0))
        width, height = bg_image.width, bg_image.height

    for index, raw in enumerate(icons):
        with open_captcha_image(raw) as icon:
            rgba = icon.convert("RGBA")
            rgba.thumbnail((48, 48))
            alpha = rgba.getchannel("A")
            # 透明底白图标直接贴到白底上看不出轮廓，换成黑底再保留 Alpha。
            if (
                alpha.getextrema()[0] < 255
                and len(set(rgba.convert("RGB").getdata())) == 1
            ):
                dark = Image.new("RGBA", rgba.size, "black")
                dark.putalpha(alpha)
                rgba = dark
            canvas.paste(rgba, (12 + index * 56, height + 8), rgba)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue(), width, height


async def build_icon_track(
    client: httpx.AsyncClient,
    info: dict[str, Any],
    message: str,
    sign: str,
    *,
    yunma_token: str,
) -> dict[str, Any]:
    """图标点选题：识别坐标后按极验的百分比口径回填。"""

    from .yunma import recognize_icons

    questions = info.get("ques")
    if not isinstance(questions, list) or not 1 <= len(questions) <= 5:
        raise ValueError("当前图标验证码暂不支持")
    background_path = str(info.get("imgs") or "")
    icon_paths = info.get("icons") or []
    if not background_path or not isinstance(icon_paths, list) or not icon_paths:
        raise ValueError("极验未返回图标验证图片")

    background, *icons = await asyncio.gather(
        download_image(client, background_path),
        *(download_image(client, str(path)) for path in icon_paths),
    )
    image, width, height = await asyncio.to_thread(compose_icons, background, icons)
    points = await recognize_icons(client, image, token=yunma_token, count=len(icons))

    response: list[list[int]] = []
    for x, y in points:
        if x > width or y > height:
            raise ValueError("云码返回坐标超出验证图片范围")
        response.append([round(x / width * 10000), round(y / height * 10000)])

    return {
        "passtime": 2098,
        "userresponse": response,
        "device_id": "",
        "lot_number": info["lot_number"],
        "pow_msg": message,
        "pow_sign": sign,
        "geetest": "captcha",
        "lang": "zh",
        "ep": "123",
        "biht": "1426265548",
        "HufC": "hxdr",
        "d229": {"543fa0": "24e1b527"},
        "em": {"ph": 0, "cp": 0, "ek": "11", "wd": 1, "nt": 0, "si": 0, "sc": 0},
    }
