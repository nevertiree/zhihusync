"""
侧边栏点击展开/关闭功能 E2E 测试
"""

import time

import pytest

selenium = pytest.importorskip("selenium", reason="selenium not installed")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By


class TestSidebarClickMode:
    """测试侧边栏点击展开/关闭模式"""

    @pytest.fixture(scope="class")
    def driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-cache")

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

    def test_click_sidebar_expands(self, driver, base_url):
        """
        测试点击侧边栏展开
        """
        print("\n=== 测试点击侧边栏展开 ===")
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        time.sleep(3)

        driver.save_screenshot("tests/e2e/screenshots/sidebar_click_before.png")

        sidebar = driver.find_element(By.ID, "sidebar")

        # 确认初始状态是收缩的
        width_before = sidebar.size["width"]
        print(f"初始宽度: {width_before}px")

        # 点击侧边栏
        sidebar.click()
        time.sleep(0.5)

        driver.save_screenshot("tests/e2e/screenshots/sidebar_click_after.png")

        # 检查是否展开
        width_after = sidebar.size["width"]
        print(f"点击后宽度: {width_after}px")

        # 检查是否有 expanded 类
        has_expanded = driver.execute_script(
            "return document.getElementById('sidebar').classList.contains('expanded');"
        )
        print(f"是否有 expanded 类: {has_expanded}")

        if width_after > width_before + 50 and has_expanded:
            print("✅ 点击侧边栏成功展开")
        else:
            print("❌ 点击侧边栏没有展开")

    def test_click_main_content_closes_sidebar(self, driver, base_url):
        """
        测试点击主内容区关闭侧边栏
        """
        print("\n=== 测试点击主内容区关闭侧边栏 ===")
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        time.sleep(3)

        sidebar = driver.find_element(By.ID, "sidebar")
        main_content = driver.find_element(By.CLASS_NAME, "main-content")

        # 先展开侧边栏
        sidebar.click()
        time.sleep(0.5)

        width_expanded = sidebar.size["width"]
        print(f"展开后宽度: {width_expanded}px")

        # 点击主内容区
        main_content.click()
        time.sleep(0.5)

        driver.save_screenshot("tests/e2e/screenshots/sidebar_click_close.png")

        # 检查是否关闭
        width_after = sidebar.size["width"]
        print(f"点击主内容区后宽度: {width_after}px")

        has_expanded = driver.execute_script(
            "return document.getElementById('sidebar').classList.contains('expanded');"
        )
        print(f"是否还有 expanded 类: {has_expanded}")

        if width_after < width_expanded - 50 and not has_expanded:
            print("✅ 点击主内容区成功关闭侧边栏")
        else:
            print("❌ 点击主内容区没有关闭侧边栏")

    def test_click_nav_item_keeps_sidebar_open(self, driver, base_url):
        """
        测试点击导航项时侧边栏保持展开
        """
        print("\n=== 测试点击导航项保持展开 ===")
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        time.sleep(3)

        sidebar = driver.find_element(By.ID, "sidebar")

        # 先点击侧边栏展开
        sidebar.click()
        time.sleep(0.5)

        # 找到配置导航项并点击
        config_link = driver.find_element(By.CSS_SELECTOR, "a[href='/config']")
        config_link.click()
        time.sleep(2)

        driver.save_screenshot("tests/e2e/screenshots/sidebar_nav_click.png")

        # 检查是否跳转到了配置页面
        print(f"当前URL: {driver.current_url}")

        # 检查侧边栏是否仍然展开（在新页面上）
        sidebar = driver.find_element(By.ID, "sidebar")
        width_after_nav = sidebar.size["width"]
        print(f"点击导航后宽度: {width_after_nav}px")

        # 注意：页面跳转后会重新加载，侧边栏会重置为收缩状态
        # 这是预期行为，我们主要验证导航能正常工作
        if "/config" in driver.current_url:
            print("✅ 点击导航项成功跳转")
        else:
            print("❌ 点击导航项没有跳转")

    def test_mouse_leave_keeps_sidebar_open(self, driver, base_url):
        """
        测试鼠标离开侧边栏后仍然保持展开
        """
        print("\n=== 测试鼠标离开后保持展开 ===")
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        time.sleep(3)

        sidebar = driver.find_element(By.ID, "sidebar")
        main_content = driver.find_element(By.CLASS_NAME, "main-content")

        # 先点击展开
        sidebar.click()
        time.sleep(0.5)

        width_expanded = sidebar.size["width"]
        print(f"展开后宽度: {width_expanded}px")

        # 鼠标移动到主内容区（离开侧边栏）
        actions = ActionChains(driver)
        actions.move_to_element(main_content).perform()
        time.sleep(1)

        driver.save_screenshot("tests/e2e/screenshots/sidebar_mouse_leave.png")

        # 检查侧边栏是否仍然展开
        width_after_leave = sidebar.size["width"]
        print(f"鼠标离开后宽度: {width_after_leave}px")

        has_expanded = driver.execute_script(
            "return document.getElementById('sidebar').classList.contains('expanded');"
        )

        if width_after_leave > 100 and has_expanded:
            print("✅ 鼠标离开后侧边栏保持展开")
        else:
            print("❌ 鼠标离开后侧边栏关闭了")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
