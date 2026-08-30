"""
手写 HTTP JSON-RPC 客户端：不依赖 mcp SDK，直接向 streamable-http 模式的
MCP Server（BLENDER_MCP_TRANSPORT=http）发送 JSON-RPC 报文。

用途：PyCharm 里对 server 打断点（HTTP 模式运行）后，本脚本发请求即可命中断点。

用法：
    1. 以 HTTP 模式启动 server（PyCharm 里打断点 F5，或终端）：
       BLENDER_MCP_TRANSPORT=http .venv/bin/python -m subhuti_blender_mcp
    2. 另开终端运行本脚本：
       .venv/bin/python tests/my_test_http.py
"""

import json
import os
import urllib.request

# 默认连 8100（匹配 PyCharm HTTP 调试），可用环境变量覆盖
URL = os.environ.get("BLENDER_MCP_HTTP_URL", "http://127.0.0.1:8100/mcp")
PROTOCOL_VERSION = "2025-06-18"

session_id: str | None = None  # streamable-http 有状态模式的会话标识


def post(payload: dict, timeout: int = 30) -> tuple[dict | None, str | None]:
    """发送一条 JSON-RPC 报文，返回 (解析后的响应, 最新的 session id)。"""
    global session_id
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        new_sid = resp.headers.get("Mcp-Session-Id")
        if new_sid:
            session_id = new_sid
        body = resp.read().decode("utf-8")
        return _parse(body), new_sid


def _parse(body: str) -> dict | None:
    """streamable-http 可能返回 SSE（text/event-stream）或纯 JSON。"""
    body = body.strip()
    if not body:
        return None  # 通知类请求无响应体
    if body.startswith("event:"):
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return json.loads(body)


def main() -> None:
    # 1. 握手：拿到会话 ID
    print(">>> POST initialize")
    resp, sid = post({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "my_test_http", "version": "1.0"},
        },
    })
    print(f"<<< session_id={sid}")
    print(f"<<< 服务端能力: {json.dumps(resp, ensure_ascii=False)[:120]}...\n")

    # 2. 通知握手完成（无响应体）
    print(">>> POST notifications/initialized")
    _, _ = post({"jsonrpc": "2.0", "method": "notifications/initialized"})
    print("<<< (无响应体，正常)\n")

    # 3. 查询工具注册表
    print(">>> POST tools/list")
    resp, _ = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    print("<<< 注册表:", [t["name"] for t in resp["result"]["tools"]], "\n")

    # 4. 调用工具（这一条会命中 server 里 blender_run_code 的断点）
    print('>>> POST tools/call  name=blender_run_code')
    resp, _ = post({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "blender_run_code",
            "arguments": {"code": "import bpy\nprint('hi from http')"},
        },
    })
    print("<<< 服务端返回:", resp["result"]["content"][0]["text"])


if __name__ == "__main__":
    main()
