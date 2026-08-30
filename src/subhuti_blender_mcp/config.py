"""应用配置：统一从环境变量读取，默认值与 Blender 插件侧保持一致。"""

import os

# Blender HTTP 桥
HOST = os.environ.get("BLENDER_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("BLENDER_MCP_PORT", "9876"))
BASE = f"http://{HOST}:{PORT}"
RPC_TIMEOUT = 180  # Blender 长操作（如渲染）需要更久

# MCP 传输模式：stdio（生产） / http（开发调试）
TRANSPORT = os.environ.get("BLENDER_MCP_TRANSPORT", "stdio")
HTTP_PORT = int(os.environ.get("BLENDER_MCP_HTTP_PORT", "8100"))
