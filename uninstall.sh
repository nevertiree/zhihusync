#!/bin/bash
# zhihusync 卸载脚本 (Linux/macOS/WSL2)
# 使用方法: curl -fsSL https://raw.githubusercontent.com/nevertiree/zhihusync/master/uninstall.sh | bash

# 不要在管道执行时退出
[[ -t 0 ]] && set -e

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

# 显示警告
show_warning() {
    printf '\033[2J\033[H' 2>/dev/null || echo ""
    print_color "$RED" "
╔═══════════════════════════════════════════════════════════╗
║                     ⚠️  警告！⚠️                         ║
║                                                           ║
║   此操作将删除 zhihusync 容器及相关数据                   ║
║   包括：Docker 容器、备份的知乎回答、数据库、图片等        ║
║                                                           ║
║   数据删除后无法恢复！请确保已备份重要数据！              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"
}

# 检查 Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_color "$YELLOW" "⚠️  Docker 未安装，可能已手动卸载"
        return 1
    fi
    if ! docker info &> /dev/null; then
        print_color "$YELLOW" "⚠️  Docker 未运行，请启动 Docker Desktop 或 Docker 服务"
        return 1
    fi
    return 0
}

# 查找已存在的容器
find_container() {
    local container_id
    container_id=$(docker ps -aq --filter "name=zhihusync" 2>/dev/null)
    echo "$container_id"
}

# 从 Docker 容器获取挂载的数据目录
get_data_dir_from_container() {
    local container_id=$1
    local data_dir=""

    if [ -n "$container_id" ]; then
        # 从容器的挂载点获取数据目录
        # 格式: /host/path:/app/data/html
        data_dir=$(docker inspect "$container_id" 2>/dev/null | \
            grep -oE '"[^:]+:/app/data/html"' | \
            sed 's/"//g' | \
            sed 's|:/app/data/html||')
    fi

    echo "$data_dir"
}

# 配置数据目录（优先从容器获取，用户确认）
configure_data_dir() {
    print_color "$YELLOW" "💾 配置数据目录位置"
    echo ""

    # 优先从容器获取
    local detected_dir=""
    if [ -n "$CONTAINER_ID" ]; then
        detected_dir=$(get_data_dir_from_container "$CONTAINER_ID")
    fi

    if [ -n "$detected_dir" ] && [ -d "$detected_dir" ]; then
        print_color "$CYAN" "📌 从容器检测到数据目录:"
        echo "   $detected_dir"
        echo ""
        read -p "确认卸载此目录? [Y/n]: " confirm
        if [[ ! "$confirm" =~ ^[Nn]$ ]]; then
            DATA_DIR="$detected_dir"
            CONFIG_DIR="$(dirname "$DATA_DIR")/config"
            return 0
        fi
    fi

    print_color "$CYAN" "📌 请输入数据保存目录："
    echo "   这是 zhihusync 保存备份数据的位置，卸载将删除此目录"
    echo ""

    while true; do
        echo ""
        read -p "请输入数据目录路径: " data_dir

        # 使用默认值
        if [ -z "$data_dir" ]; then
            print_color "$RED" "❌ 请输入有效的目录路径"
            continue
        fi

        # 展开 ~ 符号
        data_dir="${data_dir/#\~/$HOME}"

        # 检查目录是否存在
        if [ -d "$data_dir" ]; then
            echo ""
            print_color "$YELLOW" "⚠️  发现目录: $data_dir"
            read -p "确认卸载此目录的数据? [y/N]: " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                DATA_DIR="$data_dir"
                CONFIG_DIR="$(dirname "$data_dir")/config"
                return 0
            fi
            # 用户不确认，继续循环
            print_color "$CYAN" "请重新输入正确的数据目录"
        else
            echo ""
            print_color "$RED" "❌ 目录不存在: $data_dir"
            read -p "是否尝试其他路径? [Y/n]: " retry
            if [[ "$retry" =~ ^[Nn]$ ]]; then
                return 1
            fi
        fi
    done
}

# 最终确认
final_confirm() {
    local container_id=$1

    echo ""
    print_color "$RED" "═══════════════════════════════════════════════════════════"
    print_color "$RED" "                    最终确认"
    print_color "$RED" "═══════════════════════════════════════════════════════════"
    echo ""

    if [ -n "$container_id" ]; then
        echo "🐳 Docker 容器: zhihusync ($container_id)"
    else
        echo "🐳 Docker 容器: 未找到运行中的容器"
    fi

    if [ -n "$DATA_DIR" ]; then
        echo "📁 数据目录: $DATA_DIR"
        echo "⚙️  配置目录: $CONFIG_DIR"
    fi

    echo ""
    print_color "$RED" "⚠️  以上数据和容器将被永久删除，无法恢复！"
    echo ""

    read -p "请输入 DELETE 确认卸载: " confirm

    if [ "$confirm" != "DELETE" ]; then
        print_color "$YELLOW" "❌ 卸载已取消"
        exit 0
    fi
}

# 执行卸载
perform_uninstall() {
    local container_id=$1

    print_color "$YELLOW" "🗑️  开始卸载..."
    echo ""

    # 停止并删除容器
    if [ -n "$container_id" ]; then
        print_color "$BLUE" "📦 停止并删除 Docker 容器..."
        docker stop zhihusync 2>/dev/null || true
        docker rm -f zhihusync 2>/dev/null || true
        print_color "$GREEN" "✅ Docker 容器已删除"
        echo ""
    fi

    # 询问是否删除镜像
    if docker images | grep -q "nevertiree26/zhihusync"; then
        read -p "是否删除 Docker 镜像? [y/N]: " delete_image
        if [[ "$delete_image" =~ ^[Yy]$ ]]; then
            print_color "$BLUE" "🖼️  删除 Docker 镜像..."
            docker rmi nevertiree26/zhihusync:latest 2>/dev/null || true
            print_color "$GREEN" "✅ Docker 镜像已删除"
            echo ""
        fi
    fi

    # 删除数据目录
    if [ -n "$DATA_DIR" ] && [ -d "$DATA_DIR" ]; then
        print_color "$BLUE" "📁 删除数据目录..."
        rm -rf "$DATA_DIR"
        rm -rf "$CONFIG_DIR"
        print_color "$GREEN" "✅ 数据目录已删除"
        echo ""
    fi

    print_color "$GREEN" "
╔═══════════════════════════════════════════════════════════╗
║                   ✅ 卸载完成！                           ║
╚═══════════════════════════════════════════════════════════╝
"
    echo ""
    print_color "$CYAN" "📋 残留检查清单:"
    echo "   • Docker 卷: docker volume ls | grep zhihusync"
    echo "   • 网络配置: docker network ls | grep zhihusync"
    echo ""
    print_color "$YELLOW" "如需重新安装，请访问:"
    echo "   https://github.com/nevertiree/zhihusync"
    echo ""
}

# 主流程
main() {
    show_warning

    # 检查 Docker
    check_docker
    local docker_available=$?

    # 查找容器（保存到全局变量供后续使用）
    CONTAINER_ID=""
    if [ $docker_available -eq 0 ]; then
        CONTAINER_ID=$(find_container)
    fi

    # 配置数据目录（会使用 CONTAINER_ID 自动检测）
    if ! configure_data_dir; then
        print_color "$YELLOW" "❌ 卸载已取消"
        exit 0
    fi

    # 最终确认
    final_confirm "$CONTAINER_ID"

    # 执行卸载
    perform_uninstall "$CONTAINER_ID"
}

# 执行
main
