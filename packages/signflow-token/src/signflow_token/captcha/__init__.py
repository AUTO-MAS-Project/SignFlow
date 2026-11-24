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
"""极验 v4 人机验证的本机实现。

移植自 Better-MAS-Tools 的 `app/tools/_geetest/`（AGPL-3.0），原始
实现 Copyright (c) 2025 MX，改写自 mxyooR/Kuro_login（MIT）。上游版权与
许可声明保留在 NOTICE.md；本包只做与 SignFlow 运行方式的适配：

- 网络客户端由调用方传入，不读全局代理变量，也不建第二套请求栈；
- 滑块识别在 `asyncio.to_thread` 里跑，不开子进程（宿主 main.py
  没有对应的 worker 入口，硬编码 `--captcha-slide-worker` 会在打包版里失败）；
- numpy / opencv / pycryptodome 按需导入，缺依赖时降级为人工验证，
  而不是在插件加载阶段直接 ImportError。
"""

from .errors import CaptchaError
from .geetest import KURO_CAPTCHA_ID, Geetest

__all__ = ["CaptchaError", "Geetest", "KURO_CAPTCHA_ID"]
