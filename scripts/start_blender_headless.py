#!/usr/bin/env python
"""无头模式启动 Blender 并加载 MCP 插件（自动化 / CI 测试用）。

注意：正式 Addon 的无头模式（-b）下进程会随启动退出，不适合自动化；
本脚本用 --python 方式注入插件，脚本内含主循环使进程常驻。

用法：
    python scripts/start_blender_headless.py                      # 默认文件
    python scripts/start_blender_headless.py /path/to/file.blend  # 指定文件
"""

import os
import subprocess
import sys

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
DEFAULT_BLEND = "/Users/hezenghui/Public/blender/cli_test.blend"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ADDON = os.path.join(ROOT, "blender_addon", "subhuti_blender_mcp.py")

if __name__ == "__main__":
    blend = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BLEND
    print(f"无头启动 Blender: {blend}")
    subprocess.run([BLENDER, "-b", blend, "--python", ADDON])
