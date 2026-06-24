from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

driver.get("https://www.google.com")

initial_size = driver.get_window_size()
print(f"Initial Size: {initial_size['width']} X {initial_size['height']}")

driver.set_window_size(1200, 800)
new_size = driver.get_window_size()
print(f"New Size: {new_size['width']} X {new_size['height']}")

driver.maximize_window()
final_size = driver.get_window_size()
print(f"final Size: {final_size['width']} X {final_size['height']}")

driver.quit()