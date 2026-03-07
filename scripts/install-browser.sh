#!/bin/bash
# 首次启动时检查并安装浏览器

set -e

BROWSER_DIR="/app/ms-playwright"
CHROMIUM_MARKER="$BROWSER_DIR/chromium-*/chrome-linux/chrome"

# 设置国内镜像源加速
export PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST:-https://npmmirror.com/mirrors/playwright}

echo "=========================================="
echo "🔍 检查浏览器状态..."
echo "=========================================="

# 检查 Chromium 是否已安装
if ls $BROWSER_DIR/chromium-*/chrome-linux/chrome 1> /dev/null 2>&1; then
    echo "✅ Chromium 已安装"
else
    echo "⬇️  Chromium 未安装，开始下载..."
    echo "   使用镜像源: $PLAYWRIGHT_DOWNLOAD_HOST"

    # 安装 Chromium
    playwright install chromium

    echo "✅ Chromium 安装完成"
fi

# 设置跳过下载（避免重复下载）
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

echo "=========================================="
echo "🚀 启动 zhihusync..."
echo "=========================================="

# 执行原启动命令
exec /app/entrypoint.sh "$@"
