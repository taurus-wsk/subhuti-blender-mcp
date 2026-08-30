#!/usr/bin/env python
"""打包 Blender 插件为 zip（可在 Blender 里 Install from Disk 一键安装）。

用法：
    python scripts/package_addon.py            # 输出到 dist/
    python scripts/package_addon.py /some/dir  # 输出到指定目录
"""

import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "blender_addon", "subhuti_blender_mcp.py")


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)

    name = os.path.splitext(os.path.basename(ADDON))[0]  # subhuti_blender_mcp
    zip_path = os.path.join(out_dir, f"{name}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(ADDON, arcname=os.path.basename(ADDON))

    print(f"✅ 打包完成: {zip_path}")
    print(f"   插件名: {name}")
    print("   安装方式: Blender → 偏好设置 → 插件 → 安装(Install...) → 选择该 zip")


if __name__ == "__main__":
    main()
