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

## 目录结构（标准 src 布局）

```
subhuti-blender-mcp/
├── src/subhuti_blender_mcp/        # 主包（可安装、可导入）
│   ├── __main__.py                 # 入口：python -m subhuti_blender_mcp
│   ├── config.py                   # 配置模块（环境变量统一管理）
│   ├── core/                       # 核心应用服务
│   │   └── mcp_server.py           #   MCP Server 定义 + 4 个工具
│   └── utils/                      # 基础工具
│       └── http_client.py          #   与 Blender 桥通信的 HTTP 封装
├── blender_addon/                  # 部署物：Blender 插件（独立于 Python 包）
│   └── subhuti_blender_mcp.py
├── scripts/                        # 辅助启动脚本
│   ├── start_blender_gui.py
│   └── start_blender_headless.py
├── tests/                          # 测试
│   ├── test_client.py              #   stdio 端到端测试
│   └── debug_client.py             #   HTTP 模式调试客户端
├── pyproject.toml                  # 构建配置（src 布局）
├── requirements.txt
└── README.md
```

分层职责：
- **core/** = 核心应用服务：MCP 协议、工具定义，只关心"提供什么能力"
- **utils/** = 基础工具：无业务语义的通用能力（HTTP 封装），可被任意模块复用
- **config.py** = 配置集中管理，环境变量不散落在代码里
- **blender_addon/** 单独放是因为它是部署到 Blender 的产物（import bpy，依赖 Blender 内置 Python），不属于可安装的 Python 包

安装包（src 布局需要先安装才能 import）：

```bash
.venv/bin/python -m pip install -e .
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

### 1b. 打包分发（zip 一键安装）

```bash
make package   # 生成 dist/subhuti_blender_mcp.zip
```

**安装 zip（两种方式任选）：**
- **GUI（最常用）**：Blender → 偏好设置 → 插件 → 右上角"安装(Install...)"→ 选择 zip → 勾选启用
- **命令行**：
  ```bash
  /Applications/Blender.app/Contents/MacOS/Blender -b -y --python-expr "
  import bpy, addon_utils
  bpy.ops.preferences.addon_install(filepath='dist/subhuti_blender_mcp.zip')
  addon_utils.enable('subhuti_blender_mcp', default_set=True, persistent=True)
  bpy.ops.wm.save_userpref()
  "
  ```

**分发给别人**：直接发 zip，对方同样 Install from Disk 即可（需先 `pip install -e .` 安装 MCP Server 侧）。

> 修改插件源码后需重新 `make package` 再安装；已装环境可直接重新拷贝 `blender_addon/subhuti_blender_mcp.py` 覆盖后重启 Blender。

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

## Makefile 管理（启动 / 关闭 / 状态 / 日志）

```bash
make run-logs          # ★ 前台日志模式：启动 + 日志实时滚动，Ctrl+C 统一关闭（推荐日常）
make start             # 后台启动 Blender(GUI) + MCP Server(HTTP)，启动前自动清理残留实例
make start-headless    # 同上，但 Blender 无头模式（自动化/CI）
make stop              # 彻底关闭所有相关进程（SIGTERM + 兜底 SIGKILL）
make status            # 查看各组件运行状态
make logs              # 查看当前会话日志
make clean             # stop + 删除日志/运行时文件
```

- **自动清理**：所有 `start*`/`run-logs` 都会先执行 `stop`，把其他位置启动的 Blender 桥和 MCP Server 实例关掉，避免端口冲突。
- **日志模式**：`run-logs` 前台运行，Blender 与 MCP Server 的输出实时滚动打印到终端，同时落盘 `logs/blender.log` 与 `logs/mcp.log`（每次启动自动清空旧日志）；`make logs` 查看历史、`make status` 看运行状态。
- 指定文件：`make run-logs BLEND_FILE=/path/to/file.blend`

## 开发调试（PyCharm 里断点调试 MCP）

MCP Server 支持两种传输模式，生产用 stdio，**开发调试用 HTTP**（PyCharm 直接 F5 运行 + 打断点）：

```bash
# 终端 1：以 HTTP 模式启动 server（默认 127.0.0.1:8100/mcp）
BLENDER_MCP_TRANSPORT=http .venv/bin/python -m subhuti_blender_mcp

# 终端 2 / PyCharm 调试：触发调用（server 端断点会命中）
.venv/bin/python tests/debug_client.py
```

- 在 PyCharm 里：`core/mcp_server.py` 中任意工具函数打断点 → F5 运行（配置环境变量 `BLENDER_MCP_TRANSPORT=http`，入口选 `__main__.py`）→ 运行 `tests/debug_client.py` 触发 → 断点命中、可单步。
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
      "args": ["-m", "subhuti_blender_mcp"],
      "env": {
        "BLENDER_MCP_HOST": "127.0.0.1",
        "BLENDER_MCP_PORT": "9876"
      }
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
