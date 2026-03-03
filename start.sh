#!/bin/bash
# zhihusync 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║         zhihusync 启动脚本               ║"
echo "║    知乎点赞内容备份工具                   ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ 未检测到 Docker，请先安装 Docker${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ 未检测到 docker-compose，请先安装${NC}"
    exit 1
fi

# 创建必要目录
echo -e "${BLUE}📁 创建数据目录...${NC}"
mkdir -p data/{html,meta,static/images}
mkdir -p templates static/css static/js

# 检查配置文件
if [ ! -f config/config.yaml ]; then
    echo -e "${YELLOW}⚠️  未检测到配置文件，将使用默认配置${NC}"
fi

# 构建镜像（如果不存在）
if ! docker images | grep -q zhihusync; then
    echo -e "${BLUE}🔨 首次运行，构建 Docker 镜像...${NC}"
    docker-compose build
fi

# 启动服务
echo -e "${BLUE}🚀 启动服务...${NC}"
docker-compose up -d

echo ""
echo -e "${GREEN}✅ zhihusync 已启动！${NC}"
echo ""
echo -e "${BLUE}访问地址：${NC}"
echo -e "  📊 管理界面: ${GREEN}http://localhost:8080${NC}"
echo ""
echo -e "${YELLOW}首次使用请：${NC}"
echo "  1. 打开管理界面"
echo "  2. 进入'配置'页面"
echo "  3. 粘贴知乎 Cookie"
echo "  4. 设置用户 ID"
echo "  5. 返回仪表盘开始同步"
echo ""
echo -e "${BLUE}常用命令：${NC}"
echo "  查看日志: docker-compose logs -f"
echo "  停止服务: docker-compose down"
echo "  查看统计: make stats"
echo ""

# 检查服务状态
sleep 2
if curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 服务运行正常${NC}"
else
    echo -e "${YELLOW}⚠️  服务启动中，请稍后访问 http://localhost:8080${NC}"
fi
