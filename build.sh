#!/bin/bash
# zhihusync 智能构建脚本 - 自动处理网络问题

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║      zhihusync Docker 构建脚本           ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ 未检测到 Docker${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ 未检测到 docker-compose${NC}"
    exit 1
fi

echo -e "${BLUE}🧹 清理旧构建...${NC}"
docker-compose down -v 2>/dev/null || true

# 创建必要目录
mkdir -p data/{html,meta,static/images}

# 检测网络环境
echo -e "${BLUE}📡 检测网络环境...${NC}"
NETWORK_OK=false

# 测试阿里云镜像
if curl -s --max-time 5 http://mirrors.aliyun.com > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 阿里云镜像可用${NC}"
    NETWORK_OK=true
else
    echo -e "${YELLOW}⚠️  阿里云镜像延迟较高${NC}"
fi

echo -e "${BLUE}🔨 开始构建...${NC}"
echo ""

# 尝试构建，最多 3 次
for i in 1 2 3; do
    echo -e "${BLUE}尝试 $i/3...${NC}"

    if docker-compose build --progress=plain 2>&1 | tee build.log; then
        echo ""
        echo -e "${GREEN}✅ 构建成功！${NC}"
        echo ""
        echo -e "${BLUE}启动服务:${NC}"
        echo "  docker-compose up -d"
        echo ""
        echo -e "${BLUE}访问地址:${NC}"
        echo "  http://localhost:8080"
        exit 0
    fi

    echo ""
    echo -e "${YELLOW}⚠️  构建失败，等待重试...${NC}"
    sleep 5
done

# 所有尝试都失败
 echo ""
echo -e "${RED}❌ 常规构建失败，尝试使用预构建镜像...${NC}"
echo ""

if [ -f "docker-compose.alternative.yml" ]; then
    echo -e "${BLUE}🔄 使用预构建镜像方案...${NC}"
    docker-compose -f docker-compose.alternative.yml pull
    docker-compose -f docker-compose.alternative.yml up -d

    echo ""
    echo -e "${GREEN}✅ 服务已启动（使用预构建镜像）${NC}"
    echo ""
    echo -e "${BLUE}访问地址:${NC}"
    echo "  http://localhost:8080"
else
    echo -e "${RED}❌ 所有构建方式都失败了${NC}"
    echo ""
    echo "请尝试以下方法："
    echo "1. 检查网络连接"
    echo "2. 配置 Docker 镜像加速"
    echo "3. 使用本地运行: python run_local.py"
    echo ""
    echo "查看详细文档: DOCKER_BUILD.md"
    exit 1
fi
