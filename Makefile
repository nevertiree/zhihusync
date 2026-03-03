# zhihusync Makefile

.PHONY: help build up down logs login shell stats backup clean init web

# 默认目标
help:
	@echo "zhihusync - 知乎点赞内容备份工具"
	@echo ""
	@echo "可用命令:"
	@echo "  make init     - 初始化项目"
	@echo "  make build    - 构建 Docker 镜像"
	@echo "  make up       - 启动服务 (Web + 定时任务)"
	@echo "  make web      - 仅启动 Web 界面"
	@echo "  make down     - 停止服务"
	@echo "  make logs     - 查看日志"
	@echo "  make shell    - 进入容器 shell"
	@echo "  make stats    - 查看备份统计"
	@echo "  make backup   - 备份数据"
	@echo "  make clean    - 清理数据"

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
