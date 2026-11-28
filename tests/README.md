<!--
    SignFlow: AUTO-MAS 游戏社区插件集合
    Copyright © 2025-2026 AUTO-MAS Team
-->

# 测试怎么跑

本目录是四个插件包的单元测试。跑之前要先准备 AUTO-MAS 主仓，原因见下。

## 为什么要准备主仓

`packages/` 里的每个插件在**模块级**就 `import auto_mas_core`（如
`packages/signflow/src/signflow/plugin.py` 的 `from auto_mas_core import ExtensionPlugin`），
而这个 SDK 并不是独立可安装的库：它自己又在模块级 `from app.config import ...`，
直接依赖 AUTO-MAS 主仓的 `app.*`。所以 `pip install auto-mas-core` 之后仍然 `import` 不了，
必须让 Python 能同时看到主仓根目录和 SDK 的 `src`。

`tests/conftest.py` 会读环境变量 `AUTO_MAS_ROOT` 完成这件事，并把四个包的 `src`
加到 `sys.path` 的最前面；没有设这个变量时，测试输出第一屏会给出提示。

## 本地跑法

```powershell
# 1. 指向本机的主仓根目录（不要指向 app 或 plugins 子目录）
$env:AUTO_MAS_ROOT = "D:\GitHub\AUTO-MAS"

# 2. 用主仓的虚拟环境跑（宿主依赖都装在这里）
& "$env:AUTO_MAS_ROOT\.venv\Scripts\python.exe" -m pytest tests -q
Remove-Item Env:\AUTO_MAS_ROOT   # 用完就清，别写进全局环境变量
```

预期结果：`75 passed`。

## 没有主仓克隆怎么办

全量克隆主仓约 1.6 GB，测试用不到前端和资源。用稀疏检出即可（约 11 MB）：

```bash
git clone --depth=1 --filter=blob:none --sparse \
  --branch dev https://github.com/AUTO-MAS-Project/AUTO-MAS.git host
git -C host sparse-checkout set app plugins/auto_mas_core
```

`pyproject.toml` 与 `uv.lock` 在 cone 模式下默认就在工作区里，不用另加。

## 静态检查

`ruff` 不需要主仓，也不用装依赖：

```bash
uvx --from ruff==0.16.8 ruff check .
uvx --from ruff==0.16.8 ruff format --check .
```

规则见仓库根的 `ruff.toml`，与 AUTO-MAS 主仓同口径。

## CI

`.github/workflows/python-check.yml` 分两个作业：`lint` 在 ubuntu 上跑 ruff；
`pytest` 在 windows 上稀疏检出主仓 `dev` 分支、`uv sync --locked --group dev` 之后
用 `AUTO_MAS_ROOT` 跑本目录。目前没有挂 Linux 的测试作业 —— 宿主 `app/utils` 里
有模块级 `win32` 导入，跨平台是否成立还没有验证过。
