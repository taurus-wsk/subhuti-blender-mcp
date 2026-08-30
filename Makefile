# Subhuti Blender MCP — 启动 / 关闭 / 状态 / 日志 统一管理
#
# 常用命令：
#   make start            后台启动 Blender(GUI) + MCP Server(HTTP)，启动前自动清理残留实例
#   make start-headless   同上，但 Blender 以无头模式运行（自动化/CI）
#   make run-logs         前台日志模式：启动 + 日志实时滚动输出，Ctrl+C 统一关闭（推荐日常使用）
#   make stop             彻底关闭所有相关进程（Blender 桥 + MCP Server）
#   make status           查看各组件运行状态
#   make logs             查看最近日志（当前会话）
#   make clean            stop + 删除日志/运行时文件
#   make package          打包插件

SHELL := /bin/bash

VENV_PYTHON := .venv/bin/python
BLENDER := /Applications/Blender.app/Contents/MacOS/Blender
BLEND_FILE ?= /Users/hezenghui/Public/blender/cli_test.blend
ADDON := $(CURDIR)/blender_addon/subhuti_blender_mcp.py

LOG_DIR := $(CURDIR)/logs
RUN_DIR := $(CURDIR)/.run

PORT := 9876
HTTP_PORT := 8100

.PHONY: start start-gui start-headless run-logs package stop status logs clean

## 启动（默认 GUI；先自动关闭其他实例，避免端口冲突）
start start-gui: stop
	@mkdir -p $(LOG_DIR) $(RUN_DIR)
	@echo "==> [1/3] 启动 Blender (GUI)..."
	@nohup $(BLENDER) $(BLEND_FILE) > $(LOG_DIR)/blender.log 2>&1 &
	@echo $$! > $(RUN_DIR)/blender.pid
	@$(call wait_bridge)
	@echo "==> [2/3] 启动 MCP Server (HTTP 调试模式 :$(HTTP_PORT))..."
	@BLENDER_MCP_TRANSPORT=http nohup $(VENV_PYTHON) -m subhuti_blender_mcp > $(LOG_DIR)/mcp.log 2>&1 &
	@echo $$! > $(RUN_DIR)/mcp.pid
	@echo "==> [3/3] 全部就绪 ✅  查看状态: make status / 日志: make logs"

## 启动（无头模式，自动化/CI 用）
start-headless: stop
	@mkdir -p $(LOG_DIR) $(RUN_DIR)
	@echo "==> [1/3] 启动 Blender (无头)..."
	@nohup $(VENV_PYTHON) scripts/start_blender_headless.py $(BLEND_FILE) > $(LOG_DIR)/blender.log 2>&1 &
	@echo $$! > $(RUN_DIR)/blender.pid
	@$(call wait_bridge)
	@echo "==> [2/3] 启动 MCP Server (HTTP 调试模式 :$(HTTP_PORT))..."
	@BLENDER_MCP_TRANSPORT=http nohup $(VENV_PYTHON) -m subhuti_blender_mcp > $(LOG_DIR)/mcp.log 2>&1 &
	@echo $$! > $(RUN_DIR)/mcp.pid
	@echo "==> [3/3] 全部就绪 ✅  查看状态: make status / 日志: make logs"

## 前台日志模式（推荐日常使用）：启动 + 日志实时滚动，Ctrl+C 统一关闭
run-logs: stop
	@$(VENV_PYTHON) scripts/run_logs.py $(BLEND_FILE)

## 彻底关闭：Blender 桥进程 + MCP Server + 占用端口的进程
stop:
	@echo "==> 关闭 MCP Server 与 Blender 桥相关进程..."
	@-pkill -f "subhuti_blender_mcp" 2>/dev/null || true
	@sleep 1
	@-pkill -9 -f "subhuti_blender_mcp" 2>/dev/null || true
	@echo "==> 关闭占用端口 $(PORT) 的进程 (Blender)..."
	@-lsof -ti tcp:$(PORT) | xargs kill 2>/dev/null || true
	@echo "==> 全部已关闭 ✅"

## 查看运行状态
status:
	@echo "--- Blender 桥 (端口 $(PORT)) ---"
	@curl -s --noproxy '*' -m 2 http://127.0.0.1:$(PORT)/health 2>/dev/null || echo "未运行"
	@echo ""
	@echo "--- MCP Server (HTTP :$(HTTP_PORT)) ---"
	@lsof -ti tcp:$(HTTP_PORT) >/dev/null 2>&1 && echo "运行中" || echo "未运行"
	@echo "--- blender-mcp 相关进程 ---"
	@pgrep -fl "subhuti_blender_mcp" 2>/dev/null || echo "无"

## 打包插件为 zip（可分发 / Blender 里 Install from Disk 一键安装）
package:
	@$(VENV_PYTHON) scripts/package_addon.py

## 查看最近日志（当前会话）
logs:
	@echo "===== blender.log ====="
	@tail -n 20 $(LOG_DIR)/blender.log 2>/dev/null || echo "(暂无)"
	@echo ""
	@echo "===== mcp.log ====="
	@tail -n 20 $(LOG_DIR)/mcp.log 2>/dev/null || echo "(暂无)"

## 清理：stop + 删除日志与运行时文件
clean: stop
	@rm -rf $(LOG_DIR) $(RUN_DIR)
	@echo "==> 已清理日志与运行时文件"

# 等待 Blender 桥就绪（最多 30 秒）
define wait_bridge
	@echo "==> 等待 Blender 桥就绪..."
	@for i in $$(seq 1 30); do \
		curl -s --noproxy '*' http://127.0.0.1:$(PORT)/health >/dev/null 2>&1 && break; \
		sleep 1; \
	done
	@curl -s --noproxy '*' http://127.0.0.1:$(PORT)/health && echo ""
endef
