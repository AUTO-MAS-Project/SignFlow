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
"""测试夹具：把四个包的 src 目录加进导入路径，无需安装即可跑单元测试。

插件包在模块级导入 `auto_mas_core`（插件基类、配置原语与公共模型），
而 SDK 依赖宿主 `app.*`，无法从 PyPI 单独安装。因此需要一份 AUTO-MAS
源码树：设置环境变量 `AUTO_MAS_ROOT` 指向它，或者直接在有主仓的机器上
把主仓根目录放进 `PYTHONPATH`。跑法见 `tests/README.md`。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGES = Path(__file__).resolve().parents[1] / "packages"

for src in sorted(PACKAGES.glob("*/src")):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


# SDK 的源码在 `<主仓>/plugins/auto_mas_core/src`，但它自己又要 import 主仓的
# `app.*`，两个路径都得给：SDK 那层提供 `auto_mas_core`，主仓根提供它依赖的
# `app`。少任何一个都只能在收集阶段报 ModuleNotFoundError。
_AUTO_MAS_ROOT = os.environ.get("AUTO_MAS_ROOT")
if _AUTO_MAS_ROOT:
    _root = Path(_AUTO_MAS_ROOT).expanduser().resolve()
    for _path in (_root / "plugins" / "auto_mas_core" / "src", _root):
        if str(_path) not in sys.path:
            sys.path.insert(0, str(_path))


def pytest_report_header(config: object) -> str | None:
    """缺 SDK 时直接把补法写在测试输出第一屏，省得对着收集错误猜。"""
    try:
        import auto_mas_core  # noqa: F401
    except ModuleNotFoundError:
        return (
            "auto_mas_core 不可用：把 AUTO_MAS_ROOT 指向 AUTO-MAS 主仓根目录再跑，"
            "例如 AUTO_MAS_ROOT=D:/GitHub/AUTO-MAS。详见 tests/README.md。"
        )
    return None
