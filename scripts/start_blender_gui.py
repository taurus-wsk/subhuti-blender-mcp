#!/usr/bin/env python
"""GUI 模式启动 Blender。

Addon（subhuti_blender_mcp）已安装并默认启用，正常打开 Blender 即自动加载；
本脚本额外支持指定要打开的 .blend 文件。

用法：
    python scripts/start_blender_gui.py                 # 打开默认文件
    python scripts/start_blender_gui.py xxx.blend       # 打开指定文件
"""

import subprocess
import sys

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"

if __name__ == "__main__":
    blend = sys.argv[1] if len(sys.argv) > 1 else None
    cmd = [BLENDER] + ([blend] if blend else [])
    print("启动 Blender:", " ".join(cmd))
    subprocess.run(cmd)
