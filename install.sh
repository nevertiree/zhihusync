#!/bin/bash
# zhihusync 一键安装脚本 (Linux/macOS)
# 使用方法: curl -fsSL https://raw.githubusercontent.com/nevertiree/zhihusync/master/install.sh | bash
# 或本地运行: ./install.sh

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印带颜色的文本
print_color() {
    local color=$1
    local text=$2
    echo -e "${color}${text}${NC}"
}

# 检查 Docker
check_docker() {
    if command -v docker &> /dev/null; then
        local version=$(docker --version)
        echo "true|$version"
    else
        echo "false|Docker 未安装"
    fi
}

# 检查 Docker Compose
check_docker_compose() {
    if docker compose version &> /dev/null || docker-compose --version &> /dev/null; then
        local version=$(docker compose version 2>/dev/null || docker-compose --version 2>/dev/null)
        echo "true|$version"
    else
        echo "false|Docker Compose 未安装"
    fi
}

# 显示欢迎信息
show_welcome() {
    clear
    print_color "$CYAN" "
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🔄 zhihusync - 知乎点赞内容自动备份工具                    ║
║                                                           ║
║   一键安装，自动备份你的知乎点赞内容                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"
    echo ""
}

# 显示系统信息
show_system_info() {
    print_color "$YELLOW" "📋 系统信息:"
    echo "   操作系统: $(uname -s)"
    echo "   架构: $(uname -m)"
    echo ""
}

# 检查环境
check_environment() {
    print_color "$YELLOW" "🔍 检查环境依赖..."

    IFS='|' read -r docker_ok docker_info <<< "$(check_docker)"
    IFS='|' read -r compose_ok compose_info <<< "$(check_docker_compose)"

    if [ "$docker_ok" = "false" ]; then
        print_color "$RED" "❌ Docker 未安装"
        echo ""
        print_color "$YELLOW" "请按以下步骤安装 Docker:"
        echo "   curl -fsSL https://get.docker.com | sh"
        echo ""
        echo "安装完成后，请重新运行此脚本。"
        exit 1
    fi
    print_color "$GREEN" "✅ $docker_info"

    if [ "$compose_ok" = "false" ]; then
        print_color "$YELLOW" "⚠️  Docker Compose 未安装"
    else
        print_color "$GREEN" "✅ $compose_info"
    fi
    echo ""
}

# 配置安装
configure_install() {
    local default_dir="$HOME/zhihusync"

    print_color "$YELLOW" "⚙️  配置安装选项"

    # 检查是否有命令行参数
    if [ -n "$INSTALL_DIR" ]; then
        INSTALL_PATH="$INSTALL_DIR"
    else
        echo "默认安装目录: $default_dir"
        read -p "请输入安装目录 (直接回车使用默认): " custom_dir

        if [ -n "$custom_dir" ]; then
            INSTALL_PATH="$custom_dir"
        else
            INSTALL_PATH="$default_dir"
        fi
    fi

    # 展开路径
    INSTALL_PATH="${INSTALL_PATH/#\~/$HOME}"

    print_color "$GREEN" "📁 安装目录: $INSTALL_PATH"
    echo ""
}

# 创建目录结构
init_directory() {
    print_color "$YELLOW" "📂 创建目录结构..."

    mkdir -p "$INSTALL_PATH"/{data/{html,meta,images,static},config}

    print_color "$GREEN" "✅ 目录创建完成"
    echo ""
}

# 下载配置文件
download_config() {
    print_color "$YELLOW" "⬇️  下载配置文件..."

    local base_url="https://raw.githubusercontent.com/nevertiree/zhihusync/master"

    # 下载 docker-compose.yml
    if curl -fsSL "$base_url/docker-compose.yml" -o "$INSTALL_PATH/docker-compose.yml"; then
        echo "   ✅ docker-compose.yml"
    else
        print_color "$RED" "   ❌ 下载失败: docker-compose.yml"
        exit 1
    fi

    # 下载 .env.example
    if curl -fsSL "$base_url/.env.example" -o "$INSTALL_PATH/.env.example"; then
        echo "   ✅ .env.example"
    else
        print_color "$YELLOW" "   ⚠️  下载失败: .env.example (非关键文件)"
    fi

    # 创建 .env 文件
    cat > "$INSTALL_PATH/.env" << 'EOF'
# zhihusync 配置文件
# 知乎用户 ID (必填，在浏览器中登录知乎后，访问个人主页 URL 中的用户 ID)
ZHIHU_USER_ID=

# 扫描间隔（分钟）
SCAN_INTERVAL=60

# 是否无头模式运行浏览器
HEADLESS=true

# 日志级别 (DEBUG/INFO/WARNING/ERROR)
LOG_LEVEL=INFO

# 浏览器类型 (chromium/firefox/auto)
PLAYWRIGHT_BROWSER=chromium
EOF

    echo "   ✅ .env"

    print_color "$GREEN" "✅ 配置文件下载完成"
    echo ""
}

# 启动服务
start_service() {
    print_color "$YELLOW" "🚀 启动 zhihusync 服务..."

    cd "$INSTALL_PATH"

    # 使用 docker compose 启动
    if docker compose up -d 2>/dev/null || docker-compose up -d; then
        print_color "$GREEN" "✅ 服务启动成功！"
    else
        print_color "$RED" "❌ 服务启动失败"
        exit 1
    fi

    echo ""
}

# 显示完成信息
show_completion() {
    print_color "$GREEN" "
╔═══════════════════════════════════════════════════════════╗
║                   ✅ 安装完成！                           ║
╚═══════════════════════════════════════════════════════════╝
"
    echo ""
    print_color "$YELLOW" "📱 访问 Web 界面:"
    echo "   http://localhost:6067"
    echo ""
    print_color "$YELLOW" "📁 安装目录:"
    echo "   $INSTALL_PATH"
    echo ""
    print_color "$YELLOW" "⚙️  配置文件:"
    echo "   $INSTALL_PATH/.env"
    echo ""
    print_color "$YELLOW" "📝 下一步:"
    echo "   1. 编辑 .env 文件，配置你的知乎用户 ID"
    echo "      nano $INSTALL_PATH/.env"
    echo ""
    echo "   2. 访问 http://localhost:6067 配置 Cookie"
    echo ""
    echo "   3. 开始自动备份！"
    echo ""
    print_color "$YELLOW" "🔧 常用命令:"
    echo "   启动: cd $INSTALL_PATH && docker compose up -d"
    echo "   停止: cd $INSTALL_PATH && docker compose down"
    echo "   日志: cd $INSTALL_PATH && docker compose logs -f"
    echo "   更新: cd $INSTALL_PATH && docker compose pull && docker compose up -d"
    echo ""
}

# 主流程
main() {
    show_welcome
    show_system_info
    check_environment
    configure_install
    init_directory
    download_config
    start_service
    show_completion
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --dir|-d)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --help|-h)
            echo "使用方法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  -d, --dir <目录>    指定安装目录"
            echo "  -h, --help          显示帮助信息"
            echo ""
            echo "示例:"
            echo "  $0                                    # 使用默认目录"
            echo "  $0 -d /opt/zhihusync                  # 指定安装目录"
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 执行主流程
main
