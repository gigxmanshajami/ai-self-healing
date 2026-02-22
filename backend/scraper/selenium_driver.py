"""
Selenium WebDriver Manager
Handles browser initialization, configuration, and lifecycle.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager
from typing import Optional, List, Dict, Any
from loguru import logger
import time


class SeleniumDriver:
    """
    Production-grade Selenium WebDriver wrapper with:
    - Headless Chrome configuration
    - Automatic driver management
    - Retry logic for resilience
    - Screenshot capture for debugging
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 10,
        retry_attempts: int = 3,
        user_agent: Optional[str] = None
    ):
        self.headless = headless
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        self.driver: Optional[webdriver.Chrome] = None
        self._setup_driver()

    def _setup_driver(self) -> None:
        """Initialize Chrome WebDriver with optimized settings."""
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        # Performance and stability options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument(f"--user-agent={self.user_agent}")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--lang=en-US")
        
        # Suppress logging
        options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Explicitly enable JavaScript
        prefs = {
            "profile.managed_default_content_settings.javascript": 1,
            "intl.accept_languages": "en-US,en;q=0.9"
        }
        options.add_experimental_option("prefs", prefs)
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.implicitly_wait(self.timeout)
            logger.info("Chrome WebDriver initialized successfully")
        except WebDriverException as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def navigate(self, url: str) -> bool:
        """
        Navigate to URL with retry logic.
        
        Args:
            url: Target URL to navigate to
            
        Returns:
            True if navigation successful, False otherwise
        """
        for attempt in range(self.retry_attempts):
            try:
                self.driver.get(url)
                # Wait for page to fully render (important for JS-heavy sites)
                WebDriverWait(self.driver, self.timeout).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                # Extra wait for JS frameworks (React/Next.js) to hydrate
                time.sleep(2)
                logger.info(f"Navigated to: {url}")
                return True
            except WebDriverException as e:
                logger.warning(f"Navigation attempt {attempt + 1} failed: {e}")
                time.sleep(1)
        
        logger.error(f"Failed to navigate to {url} after {self.retry_attempts} attempts")
        return False

    def find_element(
        self,
        selector: str,
        by: By = By.CSS_SELECTOR,
        wait: bool = True
    ) -> Optional[Any]:
        """
        Find single element with optional explicit wait.
        
        Args:
            selector: Element selector string
            by: Selenium By strategy (CSS_SELECTOR, XPATH, etc.)
            wait: Whether to use explicit wait
            
        Returns:
            WebElement if found, None otherwise
        """
        try:
            if wait:
                element = WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
            else:
                element = self.driver.find_element(by, selector)
            return element
        except (TimeoutException, NoSuchElementException) as e:
            logger.debug(f"Element not found with selector '{selector}': {e}")
            return None

    def find_elements(
        self,
        selector: str,
        by: By = By.CSS_SELECTOR
    ) -> List[Any]:
        """
        Find all matching elements.
        
        Args:
            selector: Element selector string
            by: Selenium By strategy
            
        Returns:
            List of WebElements (empty if none found)
        """
        try:
            elements = self.driver.find_elements(by, selector)
            return elements
        except NoSuchElementException:
            return []

    def get_page_source(self) -> str:
        """Get current page HTML source."""
        return self.driver.page_source

    def get_current_url(self) -> str:
        """Get current page URL."""
        return self.driver.current_url

    def take_screenshot(self, filename: str) -> bool:
        """
        Capture screenshot for debugging.
        
        Args:
            filename: Path to save screenshot
            
        Returns:
            True if successful
        """
        try:
            self.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved: {filename}")
            return True
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False

    def execute_script(self, script: str, *args) -> Any:
        """Execute JavaScript in browser context."""
        return self.driver.execute_script(script, *args)

    def get_all_elements(self) -> List[Any]:
        """
        Get all elements in the DOM for self-healing analysis.
        
        Returns:
            List of all WebElements in the document
        """
        return self.driver.find_elements(By.XPATH, "//*")

    def close(self) -> None:
        """Clean up and close the browser."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed successfully")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
