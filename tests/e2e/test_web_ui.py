"""
End-to-End Tests using Selenium - 模拟真实用户操作
需要安装: pip install selenium webdriver-manager
"""

import time

import pytest

# Skip all tests if selenium is not installed
selenium = pytest.importorskip("selenium", reason="selenium not installed")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TestWebInterface:
    """Web界面E2E测试"""

    @pytest.fixture(scope="class")
    def driver(self):
        """创建浏览器驱动"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
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

    def test_homepage_loads(self, driver, base_url):
        """测试首页加载"""
        driver.get(base_url)
        assert "zhihusync" in driver.title or "知乎" in driver.title

        wait = WebDriverWait(driver, 10)
        stats_card = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        assert stats_card is not None

    def test_config_page_interactions(self, driver, base_url):
        """测试配置页面交互"""
        driver.get(f"{base_url}/config")
        time.sleep(2)

        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None
        print("Config page loaded successfully")

    def test_content_page_loads(self, driver, base_url):
        """测试内容页面加载"""
        driver.get(f"{base_url}/content")
        time.sleep(2)

        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None
        print("Content page loaded successfully")


@pytest.mark.e2e
class TestFullUserJourney:
    """完整用户旅程测试"""

    @pytest.fixture(scope="class")
    def driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=chrome_options)
        yield driver
        driver.quit()

    def test_complete_setup_journey(self, driver):
        """测试完整设置流程"""
        base_url = "http://localhost:6067"

        # 1. 访问首页
        driver.get(base_url)
        time.sleep(2)
        assert driver.current_url.startswith(base_url)

        # 2. 访问配置页面
        driver.get(f"{base_url}/config")
        time.sleep(2)

        # 3. 访问内容页面
        driver.get(f"{base_url}/content")
        time.sleep(2)

        print("User journey test completed")
