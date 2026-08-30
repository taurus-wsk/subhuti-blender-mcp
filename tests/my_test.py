"""
手写 JSON-RPC 客户端：不依赖 mcp SDK，直接通过 stdio 与 MCP Server 通信。

作用：模拟 MCP 客户端（如 WorkBuddy）发送原始协议报文，观察路由机制。

用法：
    1. 先启动 Blender 桥（任选其一）：
       make run-logs                  # 或 GUI 打开 Blender（addon 自动加载）
    2. 运行本脚本：
       .venv/bin/python tests/my_test.py
"""

import json
import subprocess
import sys

# 启动 MCP Server 子进程（stdio 通信：stdin/stdout 就是"网络线缆"）
server = subprocess.Popen(
    [sys.executable, "-m", "subhuti_blender_mcp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
    bufsize=1,
)


def send(obj: dict) -> dict:
    """发送一行 JSON-RPC 请求，读取一行响应（MCP stdio = 按行分隔的 JSON）。"""
    server.stdin.write(json.dumps(obj) + "\n")
    server.stdin.flush()
    return json.loads(server.stdout.readline())


def main() -> None:
    # 1. 握手：客户端声明自己是谁、协议版本
    print(">>> initialize")
    resp = send({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "my_test", "version": "1.0"},
        },
    })
    print("<<<", json.dumps(resp, ensure_ascii=False)[:120], "...\n")

    # 2. 通知：告诉服务端握手完成（无响应）
    server.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    server.stdin.flush()

    # 3. 查询工具注册表（可选，看路由表里有什么）
    print(">>> tools/list")
    resp = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    print("<<< 注册表:", [t["name"] for t in resp["result"]["tools"]], "\n")

    # 4. 调用工具：让 Blender 执行代码并打印 hi
    print('>>> tools/call  name=blender_run_code  code="import bpy\\nprint(\'hi\')"')
    resp = send({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "blender_run_code",
            "arguments": {"code": "import bpy\nprint('hi')"},
        },
    })
    # 响应里的 text 就是 Blender 执行后的 stdout（含 "hi"）
    print("<<< 服务端返回:", resp["result"]["content"][0]["text"])

    server.terminate()


if __name__ == "__main__":
    main()
