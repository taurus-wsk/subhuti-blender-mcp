"""包入口：python -m subhuti_blender_mcp

传输模式由环境变量 BLENDER_MCP_TRANSPORT 决定：
  stdio（默认）→ 生产，由 MCP 客户端以子进程方式启动
  http         → 开发调试，PyCharm 直接运行可打断点（streamable-http）
"""

from . import config
from .core.mcp_server import mcp


def main() -> None:
    if config.TRANSPORT == "http":
        print(f"[blender-mcp] HTTP 调试模式: http://127.0.0.1:{config.HTTP_PORT}/mcp")
        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=config.HTTP_PORT,
        )
    else:
        mcp.run()  # 默认 stdio


if __name__ == "__main__":
    main()
