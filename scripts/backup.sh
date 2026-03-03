#!/bin/bash
# 备份脚本 - 备份 zhihusync 数据

set -e

BACKUP_DIR="${1:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="zhihusync_backup_${DATE}.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "📦 创建备份..."
tar -czf "${BACKUP_DIR}/${BACKUP_NAME}" \
    data/meta \
    data/html \
    config/ \
    2>/dev/null || true

echo "✅ 备份完成: ${BACKUP_DIR}/${BACKUP_NAME}"

# 保留最近 10 个备份
ls -t "${BACKUP_DIR}"/zhihusync_backup_*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm

echo "🗑️  已清理旧备份，保留最近 10 个"
