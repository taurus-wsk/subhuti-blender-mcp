"""基础工具：与 Blender HTTP 桥通信的底层 HTTP 封装。"""

from __future__ import annotations

import json
import urllib.request

from .. import config


def request(method: str, path: str, payload: dict | None = None, timeout: float = 30.0) -> dict:
    """向 Blender 桥发起 HTTP 请求并解析 JSON 响应。"""
    if method == "GET":
        req = urllib.request.Request(f"{config.BASE}{path}", method="GET")
    else:
        req = urllib.request.Request(
            f"{config.BASE}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))
