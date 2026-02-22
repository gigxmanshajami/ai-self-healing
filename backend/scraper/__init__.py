"""Scraper module initialization."""
from .selenium_driver import SeleniumDriver
from .base_scraper import BaseScraper, ElementInfo
from .failure_detector import FailureDetector, FailureType, FailureReport

__all__ = [
    "SeleniumDriver",
    "BaseScraper",
    "ElementInfo",
    "FailureDetector",
    "FailureType",
    "FailureReport"
]
