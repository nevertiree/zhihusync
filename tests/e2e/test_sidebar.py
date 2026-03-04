"""
侧边栏动态伸缩功能 E2E 测试
"""

import time

import pytest

selenium = pytest.importorskip("selenium", reason="selenium not installed")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By


class TestSidebar:
    """测试侧边栏动态伸缩功能"""

    @pytest.fixture(scope="class")
    def driver(self):
        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
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

    def test_sidebar_default_collapsed(self, driver, base_url):
        """
        测试侧边栏默认是收缩状态
        """
        print("\n=== 测试侧边栏默认状态 ===")

        # 清除所有缓存
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        driver.execute_cdp_cmd("Network.clearBrowserCookies", {})

        # 强制刷新
        driver.refresh()
        time.sleep(3)

        # 截图记录
        driver.save_screenshot("tests/e2e/screenshots/sidebar_default.png")

        # 获取侧边栏宽度
        sidebar = driver.find_element(By.ID, "sidebar")
        sidebar_width = sidebar.size["width"]
        print(f"侧边栏默认宽度: {sidebar_width}px")

        # 检查是否应该是收缩状态 (约64px)
        if sidebar_width <= 80:
            print("✅ 侧边栏默认是收缩状态")
        else:
            print(f"❌ 侧边栏默认不是收缩状态，宽度为 {sidebar_width}px")

        # 检查文字是否隐藏
        try:
            logo_text = driver.find_element(By.CLASS_NAME, "logo-text")
            nav_texts = driver.find_elements(By.CLASS_NAME, "nav-text")

            # 检查 logo-text 的透明度
            logo_opacity = driver.execute_script("return window.getComputedStyle(arguments[0]).opacity;", logo_text)
            print(f"Logo 文字透明度: {logo_opacity}")

            if float(logo_opacity) < 0.5:
                print("✅ Logo 文字默认是隐藏的")
            else:
                print("❌ Logo 文字默认是显示的")

        except Exception as e:
            print(f"检查文字显示状态时出错: {e}")

    def test_sidebar_expand_on_hover(self, driver, base_url):
        """
        测试鼠标悬停时侧边栏展开
        """
        print("\n=== 测试侧边栏悬停展开 ===")
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        time.sleep(2)

        sidebar = driver.find_element(By.ID, "sidebar")

        # 记录悬停前的宽度
        width_before = sidebar.size["width"]
        print(f"悬停前宽度: {width_before}px")

        # 鼠标悬停在侧边栏上
        actions = ActionChains(driver)
        actions.move_to_element(sidebar).perform()

        # 等待动画完成
        time.sleep(0.5)

        # 截图记录
        driver.save_screenshot("tests/e2e/screenshots/sidebar_hover.png")

        # 记录悬停后的宽度
        width_after = sidebar.size["width"]
        print(f"悬停后宽度: {width_after}px")

        if width_after > width_before + 50:
            print("✅ 侧边栏悬停后展开")
        else:
            print("❌ 侧边栏悬停后没有明显展开")

        # 检查文字是否显示
        try:
            logo_text = driver.find_element(By.CLASS_NAME, "logo-text")
            logo_opacity = driver.execute_script("return window.getComputedStyle(arguments[0]).opacity;", logo_text)
            print(f"悬停后 Logo 文字透明度: {logo_opacity}")

            if float(logo_opacity) > 0.5:
                print("✅ 悬停后 Logo 文字显示")
            else:
                print("❌ 悬停后 Logo 文字仍然隐藏")
        except Exception as e:
            print(f"检查文字显示状态时出错: {e}")

    def test_logo_click_navigates_to_dashboard(self, driver, base_url):
        """
        测试点击 Logo 跳转到仪表盘
        """
        print("\n=== 测试 Logo 点击跳转 ===")

        # 先访问内容页面
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        time.sleep(2)

        print(f"当前页面: {driver.current_url}")

        # 找到 Logo 链接并点击
        try:
            logo_link = driver.find_element(By.CSS_SELECTOR, ".logo-link")
            print(f"找到 Logo 链接: {logo_link.is_displayed()}")

            # 截图点击前
            driver.save_screenshot("tests/e2e/screenshots/logo_click_before.png")

            # 点击 Logo
            logo_link.click()
            time.sleep(2)

            # 截图点击后
            driver.save_screenshot("tests/e2e/screenshots/logo_click_after.png")

            # 检查是否跳转到了首页
            print(f"点击后页面: {driver.current_url}")

            if driver.current_url.rstrip("/") == base_url or driver.current_url == f"{base_url}/":
                print("✅ 点击 Logo 成功跳转到仪表盘")
            else:
                print("❌ 点击 Logo 没有跳转到仪表盘")

        except Exception as e:
            print(f"点击 Logo 时出错: {e}")
            driver.save_screenshot("tests/e2e/screenshots/logo_click_error.png")

    def test_nav_items_icon_visible(self, driver, base_url):
        """
        测试导航图标始终可见
        """
        print("\n=== 测试导航图标可见性 ===")
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        time.sleep(2)

        # 获取所有导航项
        nav_items = driver.find_elements(By.CSS_SELECTOR, ".nav-item")
        print(f"找到 {len(nav_items)} 个导航项")

        for i, item in enumerate(nav_items):
            try:
                icon = item.find_element(By.CSS_SELECTOR, ".icon")
                is_visible = icon.is_displayed()
                icon_text = icon.text
                print(f"导航项 {i}: 图标 '{icon_text}' 可见性: {is_visible}")
            except Exception as e:
                print(f"导航项 {i}: 获取图标失败 - {e}")

    def test_main_content_margin(self, driver, base_url):
        """
        测试主内容区边距随侧边栏变化
        """
        print("\n=== 测试主内容区边距 ===")
        driver.get(f"{base_url}/content")
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        time.sleep(2)

        main_content = driver.find_element(By.CLASS_NAME, "main-content")
        sidebar = driver.find_element(By.ID, "sidebar")

        # 默认状态下的 margin-left
        margin_before = driver.execute_script("return window.getComputedStyle(arguments[0]).marginLeft;", main_content)
        print(f"默认状态下主内容区 margin-left: {margin_before}")

        # 悬停侧边栏
        actions = ActionChains(driver)
        actions.move_to_element(sidebar).perform()
        time.sleep(0.5)

        # 悬停后的 margin-left
        margin_after = driver.execute_script("return window.getComputedStyle(arguments[0]).marginLeft;", main_content)
        print(f"悬停后主内容区 margin-left: {margin_after}")

        if margin_before != margin_after:
            print("✅ 主内容区边距随侧边栏变化")
        else:
            print("❌ 主内容区边距没有变化")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
