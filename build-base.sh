#!/bin/bash
# 构建基础镜像（包含 Chrome + Playwright）
# 这个镜像只需构建一次，后续应用构建会复用它

set -e

echo "=========================================="
echo "构建 zhihusync-base 基础镜像"
echo "包含: Python 3.11 + Playwright + Chromium + Firefox"
echo "=========================================="

# 构建基础镜像
docker build \
    -f Dockerfile.base \
    -t zhihusync-base:latest \
    .

echo ""
echo "✅ 基础镜像构建完成！"
echo ""
echo "镜像信息:"
docker images zhihusync-base:latest

echo ""
echo "基础镜像大小:"
docker images zhihusync-base:latest --format "{{.Size}}"

echo ""
echo "=========================================="
echo "提示: 现在可以构建应用镜像了"
echo "  docker-compose build"
echo "=========================================="
