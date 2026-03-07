#!/usr/bin/env python3
"""
自动化测试运行器 - 执行全套测试

使用方法:
    python run_tests.py              # 运行所有测试
    python run_tests.py unit         # 只运行单元测试
    python run_tests.py api          # 只运行API测试
    python run_tests.py e2e          # 只运行E2E测试
    python run_tests.py full         # 运行包括全量同步在内的完整测试
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'=' * 60}")
    print(f"🧪 {description}")
    print(f"{'=' * 60}")
    print(f"命令: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def check_service_running():
    """检查服务是否运行"""
    import requests

    try:
        response = requests.get("http://localhost:6067/api/stats", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def run_unit_tests():
    """运行单元测试"""
    return run_command(
        [sys.executable, "-m", "pytest", "test/test_crawler_unit.py", "-v", "-m", "unit"], "运行单元测试"
    )


def run_api_tests():
    """运行API集成测试"""
    if not check_service_running():
        print("❌ 服务未运行，请先启动Docker服务:")
        print("   docker-compose up -d")
        return False

    return run_command(
        [sys.executable, "-m", "pytest", "test/test_api_integration.py", "-v", "-m", "integration"], "运行API集成测试"
    )


def run_e2e_tests():
    """运行E2E测试"""
    if not check_service_running():
        print("❌ 服务未运行，请先启动Docker服务")
        return False

    # 检查selenium是否安装
    try:
        import selenium  # noqa: F401
    except ImportError:
        print("⚠️ Selenium未安装，尝试安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "selenium", "webdriver-manager"])

    return run_command([sys.executable, "-m", "pytest", "test/test_e2e_selenium.py", "-v", "-m", "e2e"], "运行E2E测试")


def run_sync_tests():
    """运行同步功能测试"""
    if not check_service_running():
        print("❌ 服务未运行，请先启动Docker服务")
        return False

    return run_command(
        [sys.executable, "-m", "pytest", "test/test_full_sync.py", "-v", "-m", "slow"], "运行全量同步测试（耗时较长）"
    )


def run_all_tests():
    """运行所有测试"""
    results = []

    print("\n" + "=" * 60)
    print("🚀 开始执行全量测试套件")
    print("=" * 60)

    # 1. 单元测试
    results.append(("单元测试", run_unit_tests()))

    # 2. API测试（需要服务）
    if check_service_running():
        results.append(("API集成测试", run_api_tests()))
        results.append(("E2E测试", run_e2e_tests()))
    else:
        print("\n⚠️ 服务未运行，跳过API和E2E测试")
        print("   如需完整测试，请先运行: docker-compose up -d")

    # 3. 同步测试（可选，耗时较长）
    if "--with-sync" in sys.argv:
        results.append(("同步测试", run_sync_tests()))

    # 打印总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    print("=" * 60)
    if all_passed:
        print("🎉 所有测试通过！")
        return 0
    else:
        print("⚠️ 部分测试失败")
        return 1


def main():
    parser = argparse.ArgumentParser(description="运行zhihusync测试套件")
    parser.add_argument(
        "type", nargs="?", default="all", choices=["all", "unit", "api", "e2e", "sync", "full"], help="测试类型"
    )
    parser.add_argument("--with-sync", action="store_true", help="包含耗时的同步测试")

    args = parser.parse_args()

    # 切换到项目根目录
    project_root = Path(__file__).parent
    os.chdir(project_root)

    if args.type == "unit":
        success = run_unit_tests()
    elif args.type == "api":
        success = run_api_tests()
    elif args.type == "e2e":
        success = run_e2e_tests()
    elif args.type == "sync":
        success = run_sync_tests()
    elif args.type == "full":
        sys.argv.append("--with-sync")
        success = run_all_tests() == 0
    else:
        success = run_all_tests() == 0

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    import os

    main()
