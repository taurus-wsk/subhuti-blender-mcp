# Subhuti Blender MCP

通过 MCP 协议用自然语言/代码控制本机 Blender 的桥梁项目。

## 架构

```
┌──────────────┐   stdio (JSON-RPC)   ┌───────────────────┐   HTTP (127.0.0.1:9876)   ┌──────────────────┐
│ MCP 客户端    │ ──────────────────▶ │ MCP Server        │ ───────────────────────▶ │ Blender 插件      │
│ WorkBuddy /  │                     │ mcp_server/       │                          │ blender_addon/    │
│ Claude 等     │ ◀────────────────── │ server.py         │ ◀─────────────────────── │ subhuti_..._mcp.py│
└──────────────┘                     └───────────────────┘                          └──────────────────┘
      工具调用                             转发请求/结果                             主线程执行 bpy 代码
```

- **Blender 插件**：启动一个本地 HTTP 服务，所有 `bpy` 代码调度到 **Blender 主线程**执行（bpy 线程不安全的唯一解法）。GUI 模式用 `bpy.app.timers` 轮询，无头模式（`-b`）用脚本主循环。
- **MCP Server**：stdio 协议，把工具调用翻译成 HTTP 请求转发给 Blender。
- **客户端**：任何 MCP 客户端（WorkBuddy、Claude Desktop、mcp inspector 等）。

## 目录结构

```
subhuti-blender-mcp/
├── blender_addon/
│   └── subhuti_blender_mcp.py   # Blender 插件（HTTP 桥）—— 唯一需要装进 Blender 的文件
├── mcp_server/
│   └── server.py                # MCP Server（4 个工具）—— 生产入口
├── scripts/
│   ├── start_blender_gui.py     # 辅助：GUI 模式 + 指定 blend 文件启动
│   └── start_blender_headless.py# 辅助：无头模式（脚本主循环常驻，供自动化）
├── tests/
│   ├── test_client.py           # 测试：stdio 模式端到端测试
│   └── debug_client.py          # 测试：HTTP 模式调试客户端（配合断点）
├── requirements.txt             # 仅 mcp>=1.2（Blender 侧零依赖）
└── README.md
```

## 快速开始

### 1. 安装为正式 Addon（推荐，Blender 启动即用）

```bash
# 复制插件到 Blender 用户级 addons 目录
mkdir -p "$HOME/Library/Application Support/Blender/4.3/scripts/addons"
cp blender_addon/subhuti_blender_mcp.py \
   "$HOME/Library/Application Support/Blender/4.3/scripts/addons/"

# 启用并保存为用户偏好（只需一次，之后 Blender 启动自动加载）
/Applications/Blender.app/Contents/MacOS/Blender -b -y --python-expr "
import bpy, addon_utils
addon_utils.enable('subhuti_blender_mcp', default_set=True, persistent=True)
bpy.ops.wm.save_userpref()
"
```

之后**正常双击打开 Blender 即可**，插件随启动自动加载，无需任何参数。
也可以在 Blender 偏好设置 → 插件 → 搜索 "Subhuti Blender MCP" 勾选启用。

### 2. 连通性自检

```bash
curl --noproxy '*' http://127.0.0.1:9876/health
# {"status": "ok", "blender": "4.3.2", "background": false, ...}
```

> 提示：如本机配置了 HTTP 代理，curl 请加 `--noproxy '*'`，否则可能得到 502。

### 3. 端到端测试（MCP 协议全链路）

```bash
.venv/bin/python tests/test_client.py
```

预期输出：4 个工具依次调用成功，包括在 Blender 里新建物体并保存文件。

### 无头模式（自动化/CI）

正式 Addon 的无头模式（`-b`）下进程会随启动退出，不适合自动化。
自动化请改用脚本方式（脚本内含主循环，进程常驻）：

```bash
.venv/bin/python scripts/start_blender_headless.py /Users/hezenghui/Public/blender/cli_test.blend
```

## 开发调试（PyCharm 里断点调试 MCP）

MCP Server 支持两种传输模式，生产用 stdio，**开发调试用 HTTP**（PyCharm 直接 F5 运行 + 打断点）：

```bash
# 终端 1：以 HTTP 模式启动 server（默认 127.0.0.1:8100/mcp）
BLENDER_MCP_TRANSPORT=http .venv/bin/python mcp_server/server.py

# 终端 2 / PyCharm 调试：触发调用（server 端断点会命中）
.venv/bin/python tests/debug_client.py
```

- 在 PyCharm 里：`server.py` 中任意工具函数打断点 → F5 运行（配置环境变量 `BLENDER_MCP_TRANSPORT=http`）→ 运行 `tests/debug_client.py` 触发 → 断点命中、可单步。
- 也可以用官方 Inspector 可视化调试：`npx @modelcontextprotocol/inspector` 后连接 `http://127.0.0.1:8100/mcp`。
- 调试**建模代码**：在 PyCharm 里把 bpy 代码片段作为字符串传给 `blender_run_code`，返回的 stdout 就是 Blender 里 print 的输出；建模逻辑写在 `tests/debug_client.py` 里可以全程打断点。

## 可用工具

| 工具 | 说明 |
|---|---|
| `blender_status` | 检查与 Blender 的连接状态 |
| `blender_run_code(code)` | 在 Blender 主线程执行任意 Python 代码（可用 `bpy`/`C`/`D`），返回 stdout |
| `blender_scene_summary` | 列出场景中所有对象（名称/类型/可见性） |
| `blender_object_info(object_name)` | 查询对象的位置、旋转、缩放、网格统计、材质 |

## 接入 MCP 客户端

### WorkBuddy（本机）

编辑 `~/.workbuddy/mcp.json`（如不存在则创建）：

```json
{
  "mcpServers": {
    "blender-mcp": {
      "command": "/Users/hezenghui/PycharmProjects/subhuti-blender-mcp/.venv/bin/python",
      "args": ["/Users/hezenghui/PycharmProjects/subhuti-blender-mcp/mcp_server/server.py"]
    }
  }
}
```

然后在 WorkBuddy 的连接器管理页右上角"自定义连接器"里对该服务点击 **信任** 即可启用。

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` 中 `mcpServers` 增加同名配置。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `BLENDER_MCP_HOST` | `127.0.0.1` | 监听地址（**不要**改成非回环地址，存在安全风险） |
| `BLENDER_MCP_PORT` | `9876` | 监听端口（Blender 侧与 MCP Server 侧需一致） |

## 安全说明

- 该桥允许执行**任意 Python 代码**，功能等价于在 Blender 里开 Python 控制台，仅供本机可信环境使用。
- 默认只监听 `127.0.0.1`，请勿暴露到公网。

## 常见问题

**Q: MCP Server 报 Connection refused？**
A: Blender 未启动或插件未加载成功，先确认 `curl http://127.0.0.1:9876/health` 能返回 JSON。

**Q: 无头模式下 `bpy.context.object` 报错？**
A: 无头模式没有 active object 概念，改用 `bpy.context.view_layer.objects.active` 或直接索引 `bpy.data.objects`。

**Q: GUI 模式看不到视口刷新？**
A: 确认是 GUI 模式启动（脚本在 `-b` 参数下运行就是无头模式），且 RPC 请求已正确返回。
