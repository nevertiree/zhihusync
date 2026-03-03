#!/bin/bash
set -e

# 创建数据目录
mkdir -p /app/data/html /app/data/meta /app/data/static/images

# 清空日志文件（重启后重新开始记录）
if [ -f "/app/data/meta/zhihusync.log" ]; then
    echo "📝 清空旧日志文件..."
    > /app/data/meta/zhihusync.log
fi

echo "=============================================="
echo "🚀 zhihusync 启动中..."
echo "=============================================="

# 检查浏览器是否已安装
if [ -d "/app/ms-playwright" ] && [ "$(ls -A /app/ms-playwright)" ]; then
    echo "✅ 浏览器已打包在镜像中"
    ls -d /app/ms-playwright/* 2>/dev/null | head -5 | while read line; do
        echo "   - $(basename "$line")"
    done
else
    echo "⚠️ 警告: 浏览器未找到，可能需要手动安装"
    echo "   运行: playwright install chromium"
fi

# 设置浏览器路径环境变量（使用官方镜像中的浏览器）
export PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}

# 检查配置文件是否存在
if [ ! -f "/app/config/config.yaml" ]; then
    echo "📝 创建默认配置文件..."
    cat > /app/config/config.yaml << 'EOF'
zhihu:
  user_id: ""
  scan_interval: 60
  max_items_per_scan: 50
  save_comments: true

storage:
  html_path: "/app/data/html"
  db_path: "/app/data/meta/zhihusync.db"
  download_images: true
  images_path: "/app/data/static/images"

browser:
  headless: true
  request_delay: 2.0

logging:
  level: "INFO"
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
  file: "/app/data/meta/zhihusync.log"
  rotation: "10 MB"
  retention: "30 days"
EOF
fi

echo ""
echo "📊 服务信息:"
echo "   Web 界面: http://localhost:6067"
echo "   数据目录: /app/data"
echo "   浏览器: ${PLAYWRIGHT_BROWSER:-auto}"
echo ""
echo "=============================================="

# 执行主命令
exec "$@"
