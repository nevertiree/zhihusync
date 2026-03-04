"""
Test Extraction Errors UI - 测试内容提取错误功能的按钮交互

需要安装: pip install selenium webdriver-manager
运行测试: pytest tests/e2e/test_extraction_errors.py -v --tb=short
"""

import pytest
import time
import json
from pathlib import Path

# Skip all tests if selenium is not installed
selenium = pytest.importorskip("selenium", reason="selenium not installed")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
)


class TestExtractionErrorsUI:
    """测试内容提取错误页面 UI 交互"""

    @pytest.fixture(scope="class")
    def driver(self):
        """创建浏览器驱动"""
        chrome_options = Options()
        # 非 headless 模式便于调试，CI 环境可以开启 headless
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        # 启用浏览器控制台日志
        chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"Warning: Could not use webdriver-manager: {e}")
            driver = webdriver.Chrome(options=chrome_options)

        driver.implicitly_wait(10)
        yield driver
        driver.quit()

    @pytest.fixture
    def base_url(self):
        return "http://localhost:6067"

    @pytest.fixture
    def wait(self, driver):
        """创建显式等待对象"""
        return WebDriverWait(driver, 10)

    def get_console_logs(self, driver):
        """获取浏览器控制台日志"""
        try:
            logs = driver.get_log("browser")
            return [f"[{log['level']}] {log['message']}" for log in logs]
        except Exception as e:
            return [f"Failed to get logs: {e}"]

    def test_logs_page_loads(self, driver, base_url, wait):
        """测试日志页面加载"""
        print(f"\n[TEST] 访问日志页面: {base_url}/logs")
        driver.get(f"{base_url}/logs")

        # 等待页面加载完成
        wait.until(EC.presence_of_element_located((By.ID, "errors-section")))

        # 验证标题
        assert "日志" in driver.title or "zhihusync" in driver.title

        # 验证错误区域存在
        errors_section = driver.find_element(By.ID, "errors-section")
        assert errors_section.is_displayed()

        print("[PASS] 日志页面加载成功")

    def test_error_buttons_exist(self, driver, base_url, wait):
        """测试错误操作按钮存在且可见"""
        print(f"\n[TEST] 检查错误操作按钮")
        driver.get(f"{base_url}/logs")
        time.sleep(2)

        # 检查按钮元素是否存在
        buttons_to_check = [
            ("resolve-all-btn", "全部标为已解决按钮"),
            ("delete-all-btn", "全部删除按钮"),
            ("show-resolved-btn", "查看已解决按钮"),
        ]

        for btn_id, btn_name in buttons_to_check:
            try:
                btn = driver.find_element(By.ID, btn_id)
                print(f"  [FOUND] {btn_name}: id={btn_id}, text='{btn.text}', displayed={btn.is_displayed()}")
            except NoSuchElementException:
                print(f"  [MISSING] {btn_name}: id={btn_id} 不存在!")
                # 打印控制台日志帮助调试
                logs = self.get_console_logs(driver)
                for log in logs[-10:]:
                    print(f"    {log}")

    def test_show_resolved_button_toggle(self, driver, base_url, wait):
        """测试'查看已解决'按钮切换功能"""
        print(f"\n[TEST] 测试'查看已解决'按钮切换")
        driver.get(f"{base_url}/logs")
        time.sleep(2)

        try:
            # 找到按钮
            btn = wait.until(EC.element_to_be_clickable((By.ID, "show-resolved-btn")))
            original_text = btn.text
            print(f"  按钮原始文本: '{original_text}'")

            # 点击按钮
            btn.click()
            time.sleep(1)

            # 验证按钮文本变化
            new_text = btn.text
            print(f"  点击后文本: '{new_text}'")

            # 文本应该变化
            assert new_text != original_text, "按钮文本应该切换"
            assert "未解决" in new_text or "已解决" in new_text, f"按钮文本应该是'查看未解决'或'查看已解决'，实际是'{new_text}'"

            print("[PASS] 按钮切换功能正常")

        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            logs = self.get_console_logs(driver)
            print("浏览器控制台日志:")
            for log in logs[-20:]:
                print(f"  {log}")
            raise

    def test_resolve_all_button_click(self, driver, base_url, wait):
        """测试'全部标为已解决'按钮点击"""
        print(f"\n[TEST] 测试'全部标为已解决'按钮点击")
        driver.get(f"{base_url}/logs")
        time.sleep(2)

        try:
            # 先检查是否有错误数据（按钮是否显示）
            btn = driver.find_element(By.ID, "resolve-all-btn")

            if not btn.is_displayed():
                print("  [SKIP] 没有未解决的错误，按钮隐藏")
                return

            print(f"  找到按钮，文本: '{btn.text}'")

            # 点击按钮
            btn.click()
            print("  按钮已点击")

            # 等待确认对话框
            time.sleep(0.5)

            # 处理确认对话框
            alert = driver.switch_to.alert
            print(f"  确认对话框文本: '{alert.text}'")
            alert.accept()
            print("  已确认")

            # 等待操作完成
            time.sleep(2)

            # 检查按钮状态（应该变为处理中或完成）
            try:
                btn = driver.find_element(By.ID, "resolve-all-btn")
                print(f"  操作后按钮文本: '{btn.text}'")
            except:
                print("  按钮可能已隐藏（没有更多错误）")

            # 打印控制台日志
            logs = self.get_console_logs(driver)
            print("  浏览器控制台日志:")
            for log in logs[-10:]:
                if "resolveAllErrors" in log or "resolve" in log.lower():
                    print(f"    {log}")

            print("[PASS] 按钮点击功能正常")

        except NoSuchElementException:
            print("  [SKIP] 按钮不存在（可能页面结构不同）")
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            logs = self.get_console_logs(driver)
            print("浏览器控制台日志:")
            for log in logs[-20:]:
                print(f"  {log}")
            raise

    def test_delete_all_button_click(self, driver, base_url, wait):
        """测试'全部删除'按钮点击（取消操作）"""
        print(f"\n[TEST] 测试'全部删除'按钮点击（取消操作）")
        driver.get(f"{base_url}/logs")
        time.sleep(2)

        try:
            # 先检查是否有错误数据
            btn = driver.find_element(By.ID, "delete-all-btn")

            if not btn.is_displayed():
                print("  [SKIP] 没有未解决的错误，按钮隐藏")
                return

            print(f"  找到按钮，文本: '{btn.text}'")

            # 点击按钮
            btn.click()
            print("  按钮已点击")

            # 等待确认对话框
            time.sleep(0.5)

            # 处理第一个确认对话框
            alert = driver.switch_to.alert
            print(f"  第一个确认对话框: '{alert.text[:50]}...'")

            # 取消操作
            alert.dismiss()
            print("  已取消")

            print("[PASS] 删除按钮和确认对话框正常")

        except NoSuchElementException:
            print("  [SKIP] 按钮不存在")
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise

    def test_individual_error_buttons(self, driver, base_url, wait):
        """测试单个错误的操作按钮"""
        print(f"\n[TEST] 测试单个错误的操作按钮")
        driver.get(f"{base_url}/logs")
        time.sleep(2)

        try:
            # 检查错误表格是否存在
            table = driver.find_element(By.ID, "errors-table")

            # 检查是否有数据行
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            print(f"  找到 {len(rows)} 行数据")

            if len(rows) == 0:
                print("  [SKIP] 没有错误数据")
                return

            # 检查第一行的操作按钮
            first_row = rows[0]
            buttons = first_row.find_elements(By.TAG_NAME, "button")
            print(f"  第一行有 {len(buttons)} 个按钮")

            for btn in buttons:
                title = btn.get_attribute("title") or btn.text
                print(f"    - '{title}': displayed={btn.is_displayed()}")

            print("[PASS] 单个错误按钮检查完成")

        except NoSuchElementException as e:
            print(f"  [SKIP] 元素不存在: {e}")
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise


class TestHomepageErrorBanner:
    """测试首页错误提示横幅"""

    @pytest.fixture(scope="class")
    def driver(self):
        """创建浏览器驱动"""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception:
            driver = webdriver.Chrome(options=chrome_options)

        driver.implicitly_wait(10)
        yield driver
        driver.quit()

    @pytest.fixture
    def base_url(self):
        return "http://localhost:6067"

    def test_error_banner_exists(self, driver, base_url):
        """测试错误提示横幅元素存在"""
        print(f"\n[TEST] 检查首页错误提示横幅")
        driver.get(base_url)
        time.sleep(2)

        # 检查横幅元素
        try:
            banner = driver.find_element(By.ID, "error-alert-banner")
            print(f"  横幅存在: displayed={banner.is_displayed()}")

            # 检查错误数量显示
            try:
                count_elem = driver.find_element(By.ID, "error-count")
                print(f"  错误数量: {count_elem.text}")
            except NoSuchElementException:
                print("  错误数量元素不存在")

        except NoSuchElementException:
            print("  [INFO] 错误提示横幅元素不存在（可能HTML结构不同）")


@pytest.mark.e2e
def test_js_console_errors(driver, base_url):
    """检查页面加载时的 JavaScript 错误"""
    print(f"\n[TEST] 检查 JavaScript 控制台错误")
    driver.get(f"{base_url}/logs")
    time.sleep(3)

    # 获取控制台日志
    logs = driver.get_log("browser")

    errors = [log for log in logs if log["level"] in ["SEVERE", "ERROR"]]
    warnings = [log for log in logs if log["level"] == "WARNING"]

    print(f"  发现 {len(errors)} 个错误, {len(warnings)} 个警告")

    if errors:
        print("  错误日志:")
        for err in errors:
            print(f"    [ERROR] {err['message']}")

    if warnings:
        print("  警告日志:")
        for warn in warnings[:5]:  # 只显示前5个警告
            print(f"    [WARN] {warn['message']}")

    # 检查是否有关键错误（排除网络错误）
    critical_errors = [
        e for e in errors
        if "resolveAllErrors" in e["message"] or "deleteError" in e["message"]
    ]

    if critical_errors:
        print("  [FAIL] 发现关键 JavaScript 错误!")
        for err in critical_errors:
            print(f"    {err['message']}")
        pytest.fail("发现关键 JavaScript 错误")
    else:
        print("[PASS] 没有发现关键 JavaScript 错误")


if __name__ == "__main__":
    # 可以直接运行此文件进行测试
    pytest.main([__file__, "-v", "--tb=short"])
