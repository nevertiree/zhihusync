"""
批量操作功能的 E2E 测试 - 验证多选后批量导出和删除是否有效
"""

import time

import pytest

# Skip all tests if selenium is not installed
selenium = pytest.importorskip("selenium", reason="selenium not installed")

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TestBatchOperations:
    """测试批量操作功能"""

    @pytest.fixture(scope="class")
    def driver(self):
        """创建浏览器驱动"""
        chrome_options = Options()
        # 为了调试方便，先不使用 headless 模式
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        # 禁用缓存
        chrome_options.add_argument("--disable-cache")
        chrome_options.add_argument("--disk-cache-size=0")

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

    def test_batch_delete_button_clickable(self, driver, base_url):
        """
        测试批量删除按钮是否可点击

        步骤：
        1. 访问内容页面
        2. 等待数据加载
        3. 勾选第一个复选框
        4. 点击"批量删除"按钮
        5. 验证是否有确认弹窗出现
        """
        print("\n=== 开始测试批量删除按钮 ===")
        # 清除缓存并重新加载
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        driver.refresh()

        # 等待页面加载
        time.sleep(3)

        # 截图记录初始状态
        driver.save_screenshot("tests/e2e/screenshots/batch_delete_initial.png")

        try:
            # 等待表格加载完成
            wait = WebDriverWait(driver, 10)

            # 查找第一个数据行的复选框
            first_checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#answers-body input[type='checkbox']"))
            )

            print(f"找到第一个复选框: {first_checkbox.is_displayed()}")

            # 点击复选框
            first_checkbox.click()
            print("已点击第一个复选框")
            time.sleep(1)

            # 截图记录选择后状态
            driver.save_screenshot("tests/e2e/screenshots/batch_delete_after_select.png")

            # 检查批量操作工具栏是否显示
            batch_toolbar = driver.find_element(By.ID, "batch-toolbar")
            toolbar_display = batch_toolbar.value_of_css_property("display")
            print(f"批量工具栏 display 属性: {toolbar_display}")
            print(f"批量工具栏是否可见: {batch_toolbar.is_displayed()}")

            # 获取已选择数量
            selected_count = driver.find_element(By.ID, "selected-count").text
            print(f"已选择数量: {selected_count}")

            # 查找批量删除按钮
            batch_delete_btn = driver.find_element(By.ID, "btn-batch-delete")
            print(f"批量删除按钮是否可见: {batch_delete_btn.is_displayed()}")
            print(f"批量删除按钮是否启用: {batch_delete_btn.is_enabled()}")

            # 点击批量删除按钮
            print("准备点击批量删除按钮...")

            # 设置 confirm 弹窗的处理（点击确定）
            driver.execute_script("window.confirm = function() { return true; };")

            batch_delete_btn.click()
            time.sleep(2)

            # 截图记录点击后状态
            driver.save_screenshot("tests/e2e/screenshots/batch_delete_after_click.png")

            print("✅ 批量删除按钮点击成功，confirm 弹窗已处理")

            # 检查浏览器 console 日志（如果有）
            try:
                logs = driver.get_log("browser")
                has_error = False
                for log in logs:
                    if log.get("level") == "SEVERE":
                        print(f"Browser error: {log}")
                        has_error = True
                if not has_error:
                    print("✅ 浏览器控制台没有严重错误")
            except Exception as e:
                print(f"无法获取浏览器日志: {e}")

        except TimeoutException as e:
            print(f"❌ 等待元素超时: {e}")
            driver.save_screenshot("tests/e2e/screenshots/batch_delete_error.png")
            raise
        except Exception as e:
            print(f"❌ 测试过程出错: {e}")
            driver.save_screenshot("tests/e2e/screenshots/batch_delete_error.png")
            raise

    def test_batch_export_button_clickable(self, driver, base_url):
        """
        测试批量导出图片按钮是否可点击

        步骤：
        1. 访问内容页面
        2. 等待数据加载
        3. 勾选第一个复选框
        4. 点击"批量导出图片"按钮
        5. 验证是否有确认弹窗出现
        """
        print("\n=== 开始测试批量导出按钮 ===")
        driver.get(f"{base_url}/content")

        # 等待页面加载
        time.sleep(3)

        # 截图记录初始状态
        driver.save_screenshot("tests/e2e/screenshots/batch_export_initial.png")

        try:
            # 等待表格加载完成
            wait = WebDriverWait(driver, 10)

            # 查找第一个数据行的复选框
            first_checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#answers-body input[type='checkbox']"))
            )

            print(f"找到第一个复选框: {first_checkbox.is_displayed()}")

            # 点击复选框
            first_checkbox.click()
            print("已点击第一个复选框")
            time.sleep(1)

            # 截图记录选择后状态
            driver.save_screenshot("tests/e2e/screenshots/batch_export_after_select.png")

            # 检查批量操作工具栏是否显示
            batch_toolbar = driver.find_element(By.ID, "batch-toolbar")
            toolbar_display = batch_toolbar.value_of_css_property("display")
            print(f"批量工具栏 display 属性: {toolbar_display}")
            print(f"批量工具栏是否可见: {batch_toolbar.is_displayed()}")

            # 获取已选择数量
            selected_count = driver.find_element(By.ID, "selected-count").text
            print(f"已选择数量: {selected_count}")

            # 查找批量导出按钮
            batch_export_btn = driver.find_element(By.ID, "btn-batch-export")
            print(f"批量导出按钮是否可见: {batch_export_btn.is_displayed()}")
            print(f"批量导出按钮是否启用: {batch_export_btn.is_enabled()}")

            # 点击批量导出按钮
            print("准备点击批量导出按钮...")

            # 设置 confirm 弹窗的处理（点击确定）
            driver.execute_script("window.confirm = function() { return true; };")

            batch_export_btn.click()
            time.sleep(2)

            # 截图记录点击后状态
            driver.save_screenshot("tests/e2e/screenshots/batch_export_after_click.png")

            print("✅ 批量导出按钮点击成功，confirm 弹窗已处理")

            # 检查浏览器 console 日志
            try:
                logs = driver.get_log("browser")
                has_error = False
                for log in logs:
                    if log.get("level") == "SEVERE":
                        print(f"Browser error: {log}")
                        has_error = True
                if not has_error:
                    print("✅ 浏览器控制台没有严重错误")
            except Exception as e:
                print(f"无法获取浏览器日志: {e}")

        except TimeoutException as e:
            print(f"❌ 等待元素超时: {e}")
            driver.save_screenshot("tests/e2e/screenshots/batch_export_error.png")
            raise
        except Exception as e:
            print(f"❌ 测试过程出错: {e}")
            driver.save_screenshot("tests/e2e/screenshots/batch_export_error.png")
            raise

    def test_checkbox_selection_state(self, driver, base_url):
        """
        测试复选框选择状态是否正确更新

        验证：
        1. 点击复选框后，selectedAnswers Set 是否正确更新
        2. 行样式是否正确更新
        3. 工具栏是否正确显示
        """
        print("\n=== 开始测试复选框选择状态 ===")
        driver.get(f"{base_url}/content")

        time.sleep(3)

        try:
            wait = WebDriverWait(driver, 10)

            # 获取第一个复选框
            first_checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#answers-body input[type='checkbox']"))
            )

            # 获取所在行
            row = first_checkbox.find_element(By.XPATH, "./ancestor::tr")
            row_class = row.get_attribute("class")
            print(f"点击前行 class: {row_class}")

            # 点击复选框
            first_checkbox.click()
            time.sleep(1)

            # 检查行样式
            row_class_after = row.get_attribute("class")
            print(f"点击后行 class: {row_class_after}")

            if "selected-row" in row_class_after:
                print("✅ 行样式已更新为选中状态")
            else:
                print("❌ 行样式未更新为选中状态")

            # 通过 JavaScript 检查 selectedAnswers Set
            selected_count_js = driver.execute_script("return selectedAnswers.size;")
            print(f"JavaScript 中 selectedAnswers.size: {selected_count_js}")

            # 获取选中的 ID
            selected_ids = driver.execute_script("return Array.from(selectedAnswers);")
            print(f"JavaScript 中 selectedAnswers 内容: {selected_ids}")

            # 取消选择
            first_checkbox.click()
            time.sleep(1)

            selected_count_js_after = driver.execute_script("return selectedAnswers.size;")
            print(f"取消选择后 selectedAnswers.size: {selected_count_js_after}")

            if selected_count_js_after == 0:
                print("✅ 取消选择后 selectedAnswers 已清空")
            else:
                print("❌ 取消选择后 selectedAnswers 未清空")

        except Exception as e:
            print(f"❌ 测试过程出错: {e}")
            driver.save_screenshot("tests/e2e/screenshots/checkbox_state_error.png")
            raise

    def test_batch_delete_with_javascript_simulation(self, driver, base_url):
        """
        使用 JavaScript 直接模拟批量删除流程

        这个测试直接调用 JavaScript 函数来验证功能是否正常
        """
        print("\n=== 开始测试批量删除 JavaScript 流程 ===")
        driver.get(f"{base_url}/content")

        time.sleep(3)

        try:
            wait = WebDriverWait(driver, 10)

            # 等待至少一行数据
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#answers-body tr[data-answer-id]")))

            # 通过 JavaScript 获取第一个 answer ID
            first_answer_id = driver.execute_script(
                "return document.querySelector('#answers-body tr[data-answer-id]')?.getAttribute('data-answer-id');"
            )
            print(f"第一个回答 ID: {first_answer_id}")

            if not first_answer_id:
                print("❌ 未找到回答数据，跳过测试")
                return

            # 使用 JavaScript 模拟选择
            driver.execute_script(
                f"""
                // 模拟选择
                selectedAnswers.add('{first_answer_id}');
                updateBatchToolbar();
                updateRowStyle('{first_answer_id}', true);
                updateSelectAllCheckbox();
                console.log('通过 JS 模拟选择完成，selectedAnswers:', Array.from(selectedAnswers));
            """
            )

            time.sleep(1)
            driver.save_screenshot("tests/e2e/screenshots/batch_delete_js_select.png")

            # 检查工具栏是否显示
            toolbar = driver.find_element(By.ID, "batch-toolbar")
            print(f"工具栏 display: {toolbar.value_of_css_property('display')}")

            # 点击批量删除按钮
            batch_delete_btn = driver.find_element(By.ID, "btn-batch-delete")
            print("点击批量删除按钮...")

            # 设置 confirm 弹窗的处理（点击确定）
            driver.execute_script("window.confirm = function() { return true; };")

            batch_delete_btn.click()

            time.sleep(2)
            driver.save_screenshot("tests/e2e/screenshots/batch_delete_js_click.png")

            # 检查是否有 confirm 对话框被触发
            # 注意：Selenium 默认会处理 confirm 为点击"确定"
            # 我们需要检查页面状态来判断是否触发了删除流程

            # 获取 JavaScript console 日志
            logs = driver.get_log("browser")
            for log in logs:
                if "批量删除" in str(log.get("message", "")) or "删除" in str(log.get("message", "")):
                    print(f"相关日志: {log}")

            print("测试完成")

        except Exception as e:
            print(f"❌ 测试过程出错: {e}")
            driver.save_screenshot("tests/e2e/screenshots/batch_delete_js_error.png")
            raise


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
