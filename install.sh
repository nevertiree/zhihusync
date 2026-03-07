#!/bin/bash
# zhihusync 全自动安装脚本 (Linux/macOS)
# 使用方法: curl -fsSL https://raw.githubusercontent.com/nevertiree/zhihusync/master/install.sh | bash

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

print_color() {
    echo -e "${1}${2}${NC}"
}

# 显示欢迎信息
show_welcome() {
    clear
    print_color "$CYAN" "
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🔄 zhihusync - 知乎点赞内容自动备份工具                    ║
║                                                           ║
║   全自动安装，只需配置数据保存位置                          ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"
}

# 检查并安装 Docker
check_and_install_docker() {
    print_color "$YELLOW" "🔍 检查 Docker 环境..."

    if command -v docker &> /dev/null; then
        print_color "$GREEN" "✅ Docker 已安装: $(docker --version)"
        return 0
    fi

    print_color "$YELLOW" "⚠️  Docker 未安装，准备自动安装..."
    echo ""

    # 检测操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        print_color "$CYAN" "📥 正在安装 Docker..."
        curl -fsSL https://get.docker.com | sh

        # 启动 Docker 服务
        sudo systemctl start docker
        sudo systemctl enable docker

        # 将当前用户加入 docker 组
        sudo usermod -aG docker $USER

        print_color "$GREEN" "✅ Docker 安装完成！"
        print_color "$YELLOW" "⚠️  请重新登录或执行 'newgrp docker' 使权限生效"

    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            print_color "$CYAN" "📥 正在通过 Homebrew 安装 Docker..."
            brew install --cask docker
            print_color "$YELLOW" "⚠️  请手动启动 Docker Desktop 应用"
            read -p "按回车键继续..."
        else
            print_color "$RED" "❌ 请先安装 Homebrew: https://brew.sh"
            exit 1
        fi
    else
        print_color "$RED" "❌ 不支持的操作系统: $OSTYPE"
        print_color "$YELLOW" "请手动安装 Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # 验证安装
    if ! docker --version &> /dev/null; then
        print_color "$RED" "❌ Docker 安装失败或需要重新登录"
        exit 1
    fi

    print_color "$GREEN" "✅ Docker 就绪: $(docker --version)"
    echo ""
}

# 配置数据目录（核心配置）
configure_data_dir() {
    print_color "$YELLOW" "💾 配置数据保存目录（重要！）"
    echo ""
    print_color "$CYAN" "📌 数据目录用于保存："
    echo "   • 备份的知乎回答 HTML 文件"
    echo "   • 数据库（备份记录、元数据）"
    echo "   • 下载的图片"
    echo ""
    print_color "$RED" "⚠️  请选择一个安全的位置，数据丢失无法恢复！"
    echo ""

    # 显示参考示例
    print_color "$BLUE" "📋 路径参考示例："
    echo "   Linux/macOS:"
    echo "     • $HOME/zhihusync/data    (推荐，用户目录)"
    echo "     • /mnt/data/zhihusync     (独立数据盘)"
    echo "     • /opt/zhihusync/data     (系统目录)"
    echo ""
    echo "   NAS/服务器:"
    echo "     • /volume1/docker/zhihusync    (群晖)"
    echo "     • /share/Container/zhihusync   (威联通)"
    echo ""

    # 默认路径
    default_dir="$HOME/zhihusync/data"

    while true; do
        read -p "请输入数据保存目录 [默认: $default_dir]: " data_dir

        # 使用默认值
        if [ -z "$data_dir" ]; then
            data_dir="$default_dir"
        fi

        # 展开 ~ 符号
        data_dir="${data_dir/#\~/$HOME}"

        # 检查目录是否存在
        if [ -d "$data_dir" ]; then
            echo ""
            print_color "$YELLOW" "⚠️  目录已存在: $data_dir"
            read -p "是否继续使用此目录? [Y/n]: " confirm
            if [[ ! "$confirm" =~ ^[Nn]$ ]]; then
                break
            fi
        else
            # 尝试创建目录
            if mkdir -p "$data_dir" 2>/dev/null; then
                print_color "$GREEN" "✅ 目录创建成功"
                break
            else
                print_color "$RED" "❌ 无法创建目录: $data_dir"
                echo "   请检查权限或选择其他位置"
                echo ""
            fi
        fi
    done

    DATA_DIR="$data_dir"
    CONFIG_DIR="$(dirname "$data_dir")/config"
    mkdir -p "$CONFIG_DIR"

    echo ""
    print_color "$GREEN" "✅ 数据目录: $DATA_DIR"
    print_color "$GREEN" "✅ 配置目录: $CONFIG_DIR"
    echo ""
}

# 配置知乎用户 ID
configure_zhihu() {
    print_color "$YELLOW" "⚙️  配置知乎账号"
    echo ""
    print_color "$CYAN" "📋 如何获取知乎用户 ID:"
    echo "   1. 浏览器登录知乎 https://www.zhihu.com"
    echo "   2. 点击头像 → 我的主页"
    echo "   3. 地址栏 URL 格式: https://www.zhihu.com/people/xxxxx"
    echo "   4. xxxxx 就是你的用户 ID"
    echo ""
    print_color "$BLUE" "   示例:"
    echo "     • https://www.zhihu.com/people/zhang-san-123 → zhang-san-123"
    echo "     • https://www.zhihu.com/people/wang-wu → wang-wu"
    echo ""

    read -p "请输入知乎用户 ID (可直接回车稍后在网页配置): " zhihu_id

    ZHIHU_USER_ID="$zhihu_id"
    echo ""
}

# 启动服务
start_service() {
    print_color "$YELLOW" "🚀 启动 zhihusync 服务..."
    echo ""

    # 停止可能存在的旧容器
    docker rm -f zhihusync 2>/dev/null || true

    # 使用 docker run 直接启动（无需下载任何文件）
    docker run -d \
        --name zhihusync \
        --restart unless-stopped \
        -p 6067:6067 \
        -v "$DATA_DIR/html:/app/data/html" \
        -v "$DATA_DIR/meta:/app/data/meta" \
        -v "$DATA_DIR/images:/app/data/images" \
        -v "$DATA_DIR/static:/app/data/static" \
        -v "$CONFIG_DIR:/app/config" \
        -e ZHIHUSYNC_ZHIHU_USER_ID="$ZHIHU_USER_ID" \
        -e ZHIHUSYNC_ZHIHU_SCAN_INTERVAL=60 \
        -e ZHIHUSYNC_BROWSER_HEADLESS=true \
        -e ZHIHUSYNC_LOGGING_LEVEL=INFO \
        -e PLAYWRIGHT_BROWSER=chromium \
        -e PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
        nevertiree26/zhihusync:latest

    if [ $? -eq 0 ]; then
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
    print_color "$CYAN" "📱 访问 Web 界面:"
    echo "   http://localhost:6067"
    echo ""
    print_color "$YELLOW" "💾 数据保存位置（重要！）:"
    echo "   $DATA_DIR"
    echo ""
    print_color "$YELLOW" "📝 下一步操作:"

    if [ -z "$ZHIHU_USER_ID" ]; then
        echo "   1. 访问 http://localhost:6067"
        echo "   2. 在网页中配置知乎用户 ID"
    else
        echo "   1. 访问 http://localhost:6067"
    fi
    echo "   2. 配置知乎 Cookie（按页面指引操作）"
    echo "   3. 开始自动备份！"
    echo ""
    print_color "$BLUE" "🔧 常用命令:"
    echo "   查看日志: docker logs -f zhihusync"
    echo "   停止服务: docker stop zhihusync"
    echo "   启动服务: docker start zhihusync"
    echo "   重启服务: docker restart zhihusync"
    echo ""
    print_color "$RED" "⚠️  重要提醒:"
    echo "   数据保存在: $DATA_DIR"
    echo "   请确保此目录安全，定期备份！"
    echo ""
}

# 主流程
main() {
    show_welcome
    check_and_install_docker
    configure_data_dir
    configure_zhihu
    start_service
    show_completion
}

# 执行
main
