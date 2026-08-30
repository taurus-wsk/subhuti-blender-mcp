"""
开发调试客户端（HTTP 模式）

配合 HTTP 调试模式使用：PyCharm 里对 mcp_server/server.py 打断点后 F5 运行
（BLENDER_MCP_TRANSPORT=http），再运行本脚本触发调用，断点即可命中。

用法：
  BLENDER_MCP_TRANSPORT=http .venv/bin/python mcp_server/server.py   # 终端 1
  .venv/bin/python tests/debug_client.py                              # 终端 2（或 PyCharm 调试）
"""

import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

HTTP_URL = os.environ.get("BLENDER_MCP_HTTP_URL", "http://127.0.0.1:8100/mcp")


async def call(session: ClientSession, name: str, args: dict) -> str:
    res = await session.call_tool(name, args)
    if res.content:
        return res.content[0].text
    return str(res)


async def main() -> None:
    async with streamable_http_client(HTTP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("可用工具:", [t.name for t in tools.tools])

            print("\n=== blender_status ===")
            print(await call(session, "blender_status", {}))

            print("\n=== blender_run_code（在 Blender 里执行并返回结果）===")
            code = (
                "import bpy\n"
                "for o in bpy.data.objects:\n"
                "    print(f'{o.name} [{o.type}]')\n"
            )
            print(await call(session, "blender_run_code", {"code": code}))


if __name__ == "__main__":
    asyncio.run(main())
