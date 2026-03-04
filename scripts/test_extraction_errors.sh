#!/bin/bash
# 手动测试提取错误功能的脚本
# 用法: bash scripts/test_extraction_errors.sh

set -e

echo "=========================================="
echo "🧪 测试内容提取错误功能"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查服务是否运行
check_server() {
    if curl -s http://localhost:6067/api/stats > /dev/null; then
        echo -e "${GREEN}✓${NC} 服务运行正常"
        return 0
    else
        echo -e "${RED}✗${NC} 服务未运行，请先启动服务"
        echo "   运行: make web 或 python -m src.app"
        return 1
    fi
}

# 测试 API
test_api() {
    echo ""
    echo "📡 测试 API 接口..."

    # 测试获取错误列表
    echo -n "获取错误列表... "
    response=$(curl -s http://localhost:6067/api/extraction-errors?resolved=false)
    if echo "$response" | grep -q "total"; then
        count=$(echo "$response" | grep -o '"total":[0-9]*' | cut -d: -f2)
        echo -e "${GREEN}✓${NC} (当前有 $count 条未解决错误)"
    else
        echo -e "${RED}✗${NC} 响应格式错误"
        echo "$response"
    fi

    # 测试统计信息
    echo -n "获取统计信息... "
    response=$(curl -s http://localhost:6067/api/stats)
    if echo "$response" | grep -q "extraction_errors"; then
        error_count=$(echo "$response" | grep -o '"extraction_errors":[0-9]*' | cut -d: -f2)
        echo -e "${GREEN}✓${NC} (extraction_errors: $error_count)"
    else
        echo -e "${RED}✗${NC} 响应格式错误"
    fi
}

# 测试标记全部为已解决
test_resolve_all() {
    echo ""
    echo "🔧 测试标记全部为已解决..."

    # 获取当前错误数
    before=$(curl -s http://localhost:6067/api/stats | grep -o '"extraction_errors":[0-9]*' | cut -d: -f2)
    echo "   当前未解决错误数: $before"

    if [ "$before" -eq 0 ]; then
        echo -e "${YELLOW}⚠${NC} 没有未解决的错误，测试跳过"
        return
    fi

    # 调用 API
    echo -n "调用 resolve-all API... "
    response=$(curl -s -X POST http://localhost:6067/api/extraction-errors/resolve-all)

    if echo "$response" | grep -q "success"; then
        echo -e "${GREEN}✓${NC}"
        message=$(echo "$response" | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
        echo "   响应: $message"
    else
        echo -e "${RED}✗${NC}"
        echo "$response"
        return
    fi

    # 验证结果
    echo -n "验证错误数... "
    after=$(curl -s http://localhost:6067/api/stats | grep -o '"extraction_errors":[0-9]*' | cut -d: -f2)
    if [ "$after" -eq 0 ]; then
        echo -e "${GREEN}✓${NC} (错误数已清零)"
    else
        echo -e "${RED}✗${NC} (错误数仍为 $after)"
    fi
}

# 打开测试页面
open_test_page() {
    echo ""
    echo "🌐 打开调试页面..."
    echo "   本地测试页面: http://localhost:6067/static/test_errors.html"
    echo "   日志页面: http://localhost:6067/logs"
    echo ""

    # 尝试自动打开浏览器
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:6067/static/test_errors.html" 2>/dev/null || true
    elif command -v open &> /dev/null; then
        open "http://localhost:6067/static/test_errors.html" 2>/dev/null || true
    elif command -v start &> /dev/null; then
        start "http://localhost:6067/static/test_errors.html" 2>/dev/null || true
    fi
}

# 运行 Selenium 测试
run_selenium_tests() {
    echo ""
    echo "🤖 运行 Selenium E2E 测试..."

    if ! python -c "import selenium" 2>/dev/null; then
        echo -e "${YELLOW}⚠${NC} Selenium 未安装，跳过 E2E 测试"
        echo "   安装: pip install selenium webdriver-manager"
        return
    fi

    pytest tests/e2e/test_extraction_errors.py -v --tb=short -s || true
}

# 主流程
main() {
    # 检查服务
    if ! check_server; then
        exit 1
    fi

    # 运行测试
    test_api
    test_resolve_all
    open_test_page

    echo ""
    echo "=========================================="
    echo -e "${GREEN}✓${NC} 基础测试完成"
    echo "=========================================="
    echo ""
    echo "💡 提示:"
    echo "   1. 请在浏览器中打开调试页面进行手动测试"
    echo "   2. 检查控制台日志是否有 JavaScript 错误"
    echo "   3. 点击按钮验证功能是否正常"
    echo ""

    # 询问是否运行 Selenium 测试
    read -p "是否运行 Selenium E2E 测试? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_selenium_tests
    fi
}

# 运行主流程
main
