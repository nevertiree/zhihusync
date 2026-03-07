# zhihusync Makefile

.PHONY: help build up down logs login shell stats backup clean init web

# 默认目标
help:
	@echo "zhihusync - 知乎点赞内容备份工具"
	@echo ""
	@echo "🚀 快速开始:"
	@echo "  make setup    - 设置开发环境（首次）"
	@echo "  make lint     - 运行代码检查（Ruff，提交前必须）"
	@echo ""
	@echo "🐳 Docker 命令:"
	@echo "  make build    - 构建 Docker 镜像"
	@echo "  make up       - 启动服务 (Web + 定时任务)"
	@echo "  make web      - 仅启动 Web 界面"
	@echo "  make down     - 停止服务"
	@echo "  make logs     - 查看日志"
	@echo "  make shell    - 进入容器 shell"
	@echo "  make stats    - 查看备份统计"
	@echo "  make backup   - 备份数据"
	@echo "  make clean    - 清理数据"
	@echo ""
	@echo "🧪 开发与测试:"
	@echo "  make lint-fix - 自动修复代码问题"
	@echo "  make test     - 运行所有测试"
	@echo "  make dev      - 本地开发模式"

# 初始化
init:
	@bash scripts/init.sh

# 构建镜像
build:
	docker-compose build

# 启动完整服务
up:
	docker-compose up -d
	@echo ""
	@echo "✅ 服务已启动!"
	@echo "📊 Web 管理界面: http://localhost:6067"

# 仅启动 Web 界面（用于配置 Cookie）
web:
	docker-compose run --rm -p 6067:6067 zhihusync python -m src.app --mode web

# 停止服务
down:
	docker-compose down

# 查看日志
logs:
	docker-compose logs -f zhihusync

# 进入容器 shell
shell:
	docker-compose exec zhihusync /bin/bash

# 查看统计
stats:
	@docker-compose exec zhihusync python -c "
from src.config_loader import load_config
from src.db import DatabaseManager

config = load_config()
db = DatabaseManager(config.storage.db_path)
stats = db.get_stats()
print('=' * 40)
print('📊 备份统计')
print('=' * 40)
print(f'📄 总回答数: {stats[\"total_answers\"]}')
print(f'💬 总评论数: {stats[\"total_comments\"]}')
print(f'✅ 有评论的回答: {stats[\"with_comments\"]}')
print(f'🗑️  已删除: {stats[\"deleted_answers\"]}')
print('=' * 40)
"

# 手动同步一次
sync:
	@curl -X POST http://localhost:6067/api/sync/start 2>/dev/null || echo "服务未启动"

# 备份数据
backup:
	@bash scripts/backup.sh

# 启动带 Nginx 的版本（直接浏览 HTML）
nginx:
	docker-compose --profile nginx up -d
	@echo "📄 备份浏览: http://localhost:8081"

# 清理数据
clean:
	@echo "⚠️  这将删除所有备份数据!"
	@read -p "确定要继续吗? [y/N] " ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
		docker-compose down -v; \
		rm -rf data/*; \
		echo "✅ 数据已清理"; \
	else \
		echo "❌ 已取消"; \
	fi

# 开发模式（本地运行）
dev:
	cd src && python -m app

# 安装依赖（本地开发）
install:
	pip install -r requirements.txt
	playwright install chromium

# ========== 代码质量检查 ==========

# 设置开发环境（安装 pre-commit）
setup:
	@echo "🔧 设置开发环境..."
	pip install pre-commit ruff black mypy
	pre-commit install
	@echo "✅ 开发环境设置完成"
	@echo ""
	@echo "现在可以运行: make lint"

# 运行所有代码检查（只用 Ruff，替代 flake8 + black）
lint:
	@echo "🔍 运行代码检查..."
	ruff check src/ tests/
	ruff format --check src/ tests/
	@echo "✅ 代码检查完成"

# 自动修复代码问题
lint-fix:
	@echo "🔧 自动修复代码问题..."
	ruff check src/ tests/ --fix
	ruff format src/ tests/
	@echo "✅ 代码修复完成"

# ========== 测试命令 ==========

# 运行所有测试（本地完整测试）
test:
	pytest tests/ -v --tb=short

# 运行单元测试（GitHub Actions 会运行）
test-unit:
	pytest tests/unit/ -v --tb=short -m unit

# 运行集成测试（本地运行，GitHub Actions 不运行）
test-integration:
	@echo "⚠️  集成测试需要在本地运行，确保服务已启动"
	pytest tests/integration/ -v --tb=short -m integration

# 运行 E2E 测试（本地运行，需要浏览器）
test-e2e:
	@echo "⚠️  E2E 测试需要在本地运行，确保浏览器和服务已就绪"
	pytest tests/e2e/ -v --tb=short -m e2e --headed

# 运行 E2E 测试（无头模式，适合 CI）
test-e2e-ci:
	pytest tests/e2e/ -v --tb=short -m e2e

# 测试提取错误功能（特定测试）
test-errors:
	pytest tests/e2e/test_extraction_errors.py -v --tb=short --headed -s

# 生成测试报告
test-report:
	pytest tests/ -v --html=tests/report.html --self-contained-html

# 启动测试服务器（后台运行，用于测试）
test-server:
	@echo "启动测试服务器..."
	@cd src && python -c "
import threading
import time
from app import app
import uvicorn

def run_server():
    uvicorn.run(app, host='127.0.0.1', port=6067, log_level='error')

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2)
print('测试服务器已启动于 http://127.0.0.1:6067')
while True:
    time.sleep(1)
" &
	@echo "服务器 PID: $$!"

# 停止测试服务器
stop-test-server:
	@pkill -f "python -c" 2>/dev/null || true
	@echo "测试服务器已停止"
