"""把 SignFlow 的四个包联接进 AUTO-MAS 的 plugins 目录，供源码联调。

用法：
    python scripts/link_dev.py --auto-mas D:\\GitHub\\AUTO-MAS
    python scripts/link_dev.py --auto-mas D:\\GitHub\\AUTO-MAS --unlink

AUTO-MAS 的 .gitignore 已忽略 /plugins/*，因此这些联接不会进入主仓版本控制。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGES = ("signflow", "signflow-notes", "signflow-gacha", "signflow-token")


def _link(source: Path, target: Path) -> None:
    """建立目录联接；Windows 优先用 junction，其他平台用软链接。"""

    if target.exists() or target.is_symlink():
        print(f"跳过已存在：{target}")
        return
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise OSError(
                f"创建目录联接失败：{target}\n{result.stderr or result.stdout}"
            )
    else:
        os.symlink(source, target, target_is_directory=True)
    print(f"已联接：{target} -> {source}")


def _unlink(target: Path) -> None:
    """移除联接，不触碰源目录内容。"""

    if not (target.exists() or target.is_symlink()):
        return
    joined = target.is_symlink()
    if sys.platform == "win32" and not joined:
        # junction 不是符号链接，rmdir 只卸联接，不会删源目录。
        result = subprocess.run(
            ["cmd", "/c", "rmdir", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            # 不是联接时按普通目录保留，避免误删源码。
            raise OSError(
                f"移除目录联接失败：{target}\n{result.stderr or result.stdout}"
            )
    else:
        shutil.rmtree(target)
    print(f"已移除：{target}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="把 SignFlow 包联接进 AUTO-MAS plugins 目录"
    )
    parser.add_argument("--auto-mas", required=True, help="AUTO-MAS 仓库根目录")
    parser.add_argument("--unlink", action="store_true", help="撤销联接")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    plugins = Path(args.auto_mas).resolve() / "plugins"
    if not plugins.is_dir():
        raise SystemExit(f"未找到 AUTO-MAS plugins 目录：{plugins}")

    for name in PACKAGES:
        source = root / "packages" / name
        if not (source / "pyproject.toml").is_file():
            raise SystemExit(f"缺少包工程：{source}")
        target = plugins / name
        if args.unlink:
            _unlink(target)
        else:
            _link(source, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
