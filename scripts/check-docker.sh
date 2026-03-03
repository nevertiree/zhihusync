#!/bin/bash
# 检查 Docker 配置

echo "=============================================="
echo "🔍 检查 Docker 配置"
echo "=============================================="

# 检查 Dockerfile
if [ ! -f "Dockerfile" ]; then
    echo "❌ Dockerfile 不存在"
    exit 1
fi

echo "✅ Dockerfile 存在"

# 检查浏览器安装指令
if grep -q "playwright install chromium" Dockerfile; then
    echo "✅ Chromium 安装指令存在"
else
    echo "❌ Chromium 安装指令缺失"
fi

if grep -q "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1" Dockerfile; then
    echo "✅ 禁止运行时下载浏览器"
else
    echo "⚠️ 未禁止运行时下载浏览器"
fi

# 检查端口
if grep -q "EXPOSE 6067" Dockerfile; then
    echo "✅ 端口 6067 配置正确"
else
    echo "❌ 端口配置错误"
fi

# 检查 entrypoint.sh
if [ -f "entrypoint.sh" ]; then
    echo "✅ entrypoint.sh 存在"
    if grep -q "PLAYWRIGHT_BROWSERS_PATH" entrypoint.sh; then
        echo "✅ 浏览器路径配置正确"
    fi
else
    echo "❌ entrypoint.sh 不存在"
fi

# 检查 docker-compose.yml
if grep -q "6067:6067" docker-compose.yml; then
    echo "✅ docker-compose 端口映射正确"
else
    echo "❌ docker-compose 端口映射错误"
fi

if grep -q "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1" docker-compose.yml; then
    echo "✅ docker-compose 禁止运行时下载"
else
    echo "⚠️ docker-compose 未禁止运行时下载"
fi

echo ""
echo "=============================================="
echo "📝 构建命令参考:"
echo "   docker-compose build"
echo "   或"
echo "   docker-compose -f docker-compose.build.yml up --build"
echo "=============================================="
