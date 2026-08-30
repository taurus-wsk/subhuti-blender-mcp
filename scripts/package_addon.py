#!/usr/bin/env python
"""打包 Blender 插件为 zip（可在 Blender 里 Install from Disk 一键安装）。

zip 内容（插件 + 附带的 MCP Server 源码）：
    subhuti_blender_mcp.py        # Blender 插件（HTTP 桥），版本由 pyproject 注入
    mcp_server/                   # MCP Server 源码（供插件自动安装/更新"翻译官"）
        pyproject.toml
        src/subhuti_blender_mcp/...

版本策略：pyproject.toml 是唯一版本源。
  - 打包时把 [project].version 注入插件 bl_info
  - 校验 src 包 __init__.py 的 __version__ 一致，不一致则中止

用法：
    python scripts/package_addon.py            # 输出到 dist/
    python scripts/package_addon.py /some/dir  # 输出到指定目录
"""

import os
import re
import sys
import tomllib
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "blender_addon", "subhuti_blender_mcp.py")
SRC = os.path.join(ROOT, "src")
PYPROJECT = os.path.join(ROOT, "pyproject.toml")


def _project_version() -> str:
    """唯一版本源：pyproject.toml 的 [project].version"""
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)["project"]["version"]


def _inject_version(addon_src: str, version: str) -> str:
    """把版本注入插件 bl_info['version']（插件源码不维护版本号）。"""
    parts = tuple(int(x) for x in version.split("."))
    return re.sub(r'("version": )\(\d+, \d+, \d+\)', rf"\1{parts}", addon_src, count=1)


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)

    version = _project_version()

    # 校验 src 包 __init__.py 的 __version__ 与 pyproject 一致
    init_py = os.path.join(SRC, "subhuti_blender_mcp", "__init__.py")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', open(init_py).read())
    if m and m.group(1) != version:
        print(f"⚠️ 版本不一致: __init__.py={m.group(1)} pyproject={version}，请同步")
        sys.exit(1)

    name = os.path.splitext(os.path.basename(ADDON))[0]  # subhuti_blender_mcp
    zip_path = os.path.join(out_dir, f"{name}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. 插件本体（版本由 pyproject 注入 bl_info）
        addon_src = _inject_version(open(ADDON).read(), version)
        zf.writestr("subhuti_blender_mcp.py", addon_src)
        # 2. 附带 MCP Server 源码（mcp_server/ 目录，含 pyproject.toml）
        #    注意保留 src/ 层级，与 pyproject 的 [tool.setuptools.packages.find] where=["src"] 一致
        for root, _dirs, files in os.walk(SRC):
            if os.path.basename(root).endswith(".egg-info"):
                continue
            for f in files:
                if f.endswith((".pyc", ".pyo")):
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, SRC)  # subhuti_blender_mcp/...
                zf.write(full, arcname=os.path.join("mcp_server", "src", rel))
        zf.write(PYPROJECT, arcname="mcp_server/pyproject.toml")

    print(f"✅ 打包完成: {zip_path} (v{version})")
    print(f"   插件名: {name}")
    print("   内容: 插件 + mcp_server/ 源码（装插件后翻译官自动就位）")
    print("   安装方式: Blender → 偏好设置 → 插件 → 安装(Install...) → 选择该 zip")


if __name__ == "__main__":
    main()
