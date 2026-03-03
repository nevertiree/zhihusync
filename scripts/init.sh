#!/bin/bash
# zhihusync 初始化脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🚀 zhihusync 初始化"
echo "===================="
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未检测到 Docker，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ 未检测到 docker-compose，请先安装"
    exit 1
fi

echo "✅ Docker 环境检查通过"
echo ""

# 创建数据目录
echo "📁 创建数据目录..."
mkdir -p data/{html,meta,static/images}

# 复制环境变量模板
if [ ! -f .env ]; then
    echo "📝 创建 .env 文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，设置你的知乎用户ID"
fi

# 构建镜像
echo "🔨 构建 Docker 镜像..."
docker-compose build

echo ""
echo "✅ 初始化完成！"
echo ""
echo "下一步:"
echo "1. 编辑 .env 文件，设置 ZHIHU_USER_ID"
echo "2. 运行: make login (登录知乎)"
echo "3. 运行: make up (启动服务)"
echo ""
