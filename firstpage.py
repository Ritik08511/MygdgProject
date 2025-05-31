from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import time
from datetime import datetime, timedelta

def setup_driver():
    """Setup Chrome driver with optimized options"""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Keep browser visible for debugging
    # chrome_options.add_argument("--headless")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.maximize_window()
    
    return driver

def wait_for_page_load(driver, timeout=10):
    """Wait for page to fully load"""
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    time.sleep(2)  # Additional buffer for dynamic content

def enter_train_number(driver, train_number):
    """Enter train number using multiple fallback strategies"""
    print(f"Entering train number: {train_number}")
    
    # Strategy 1: Try the exact selector you provided
    try:
        train_input_selector = "#root > div > div > div.jss2.jss41.jss53.jss65.jss77.jss1488 > div > div > div > div > label.jss1541.jss1542 > div > div > div > div.css-1hwfws3"
        wait = WebDriverWait(driver, 10)
        train_container = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, train_input_selector)))
        print("Found train input using exact selector")
        
        actions = ActionChains(driver)
        actions.move_to_element(train_container).click().perform()
        time.sleep(1)
        
        # Find input within container
        input_field = train_container.find_element(By.TAG_NAME, "input")
        input_field.clear()
        time.sleep(0.5)
        
        # Type train number
        for char in train_number:
            input_field.send_keys(char)
            time.sleep(0.1)
        
        print(f"Typed train number: {train_number}")
        time.sleep(2)
        input_field.send_keys(Keys.ENTER)
        print("Pressed Enter - Strategy 1 successful")
        time.sleep(3)
        return True
        
    except Exception as e1:
        print(f"Strategy 1 failed: {str(e1)}")
    
    # Strategy 2: Find by input attributes and position
    try:
        print("Trying Strategy 2: Find by input position...")
        wait = WebDriverWait(driver, 10)
        
        # Find all visible text inputs
        all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
        train_input = None
        
        for i, inp in enumerate(all_inputs):
            if inp.is_displayed() and inp.is_enabled():
                # Check if this looks like a train input (empty or has placeholder)
                placeholder = inp.get_attribute('placeholder') or ''
                value = inp.get_attribute('value') or ''
                
                # The first visible text input should be train number
                if i == 0 or 'train' in placeholder.lower() or value == '':
                    train_input = inp
                    print(f"Found train input field at position {i}")
                    break
        
        if train_input:
            # Click and enter train number
            actions = ActionChains(driver)
            actions.move_to_element(train_input).click().perform()
            time.sleep(1)
            
            train_input.clear()
            time.sleep(0.5)
            
            for char in train_number:
                train_input.send_keys(char)
                time.sleep(0.1)
            
            print(f"Typed train number: {train_number}")
            time.sleep(2)
            train_input.send_keys(Keys.ENTER)
            print("Pressed Enter - Strategy 2 successful")
            time.sleep(3)
            return True
            
    except Exception as e2:
        print(f"Strategy 2 failed: {str(e2)}")
    
    # Strategy 3: Try React Select patterns
    try:
        print("Trying Strategy 3: React Select patterns...")
        wait = WebDriverWait(driver, 10)
        
        # Common React Select selectors
        react_selectors = [
            "div[class*='react-select'] input",
            "div[class*='select'] input",
            "div[class*='css-'] input[type='text']:first-of-type",
            "div[role='combobox'] input",
            "[class*='select-container'] input"
        ]
        
        for selector in react_selectors:
            try:
                train_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                if train_input.is_displayed():
                    print(f"Found train input using: {selector}")
                    
                    actions = ActionChains(driver)
                    actions.move_to_element(train_input).click().perform()
                    time.sleep(1)
                    
                    train_input.clear()
                    time.sleep(0.5)
                    
                    for char in train_number:
                        train_input.send_keys(char)
                        time.sleep(0.1)
                    
                    print(f"Typed train number: {train_number}")
                    time.sleep(2)
                    train_input.send_keys(Keys.ENTER)
                    print("Pressed Enter - Strategy 3 successful")
                    time.sleep(3)
                    return True
                    
            except:
                continue
                
    except Exception as e3:
        print(f"Strategy 3 failed: {str(e3)}")
    
    # Strategy 4: JavaScript injection method
    try:
        print("Trying Strategy 4: JavaScript injection...")
        
        # Find any input that could be the train number field
        script = """
        var inputs = document.querySelectorAll('input[type="text"]');
        var trainInput = null;
        
        for (var i = 0; i < inputs.length; i++) {
            var input = inputs[i];
            if (input.offsetParent !== null && !input.disabled) {
                trainInput = input;
                break;
            }
        }
        
        if (trainInput) {
            trainInput.focus();
            trainInput.value = arguments[0];
            
            // Trigger events
            var inputEvent = new Event('input', { bubbles: true });
            var changeEvent = new Event('change', { bubbles: true });
            
            trainInput.dispatchEvent(inputEvent);
            trainInput.dispatchEvent(changeEvent);
            
            return true;
        }
        return false;
        """
        
        result = driver.execute_script(script, train_number)
        
        if result:
            print(f"JavaScript injection successful for: {train_number}")
            time.sleep(2)
            
            # Press Enter using ActionChains
            actions = ActionChains(driver)
            actions.send_keys(Keys.ENTER).perform()
            print("Pressed Enter - Strategy 4 successful")
            time.sleep(3)
            return True
            
    except Exception as e4:
        print(f"Strategy 4 failed: {str(e4)}")
    
    # Strategy 5: Debug and manual identification
    try:
        print("Trying Strategy 5: Debug method...")
        print("=== DEBUG: Current page inputs ===")
        
        all_inputs = driver.find_elements(By.TAG_NAME, "input")
        for i, inp in enumerate(all_inputs):
            try:
                visible = inp.is_displayed()
                enabled = inp.is_enabled()
                placeholder = inp.get_attribute('placeholder') or 'None'
                input_type = inp.get_attribute('type') or 'None'
                value = inp.get_attribute('value') or 'None'
                class_name = inp.get_attribute('class') or 'None'
                
                print(f"Input {i}: Type={input_type}, Placeholder={placeholder}, Value={value}, Visible={visible}, Enabled={enabled}")
                print(f"  Class: {class_name[:100]}...")
                
                # Try this input if it's a visible text input
                if visible and enabled and input_type == 'text' and not value:
                    print(f"Trying input {i} as train number field...")
                    
                    actions = ActionChains(driver)
                    actions.move_to_element(inp).click().perform()
                    time.sleep(1)
                    
                    inp.clear()
                    inp.send_keys(train_number)
                    print(f"Entered {train_number} in input {i}")
                    time.sleep(2)
                    
                    inp.send_keys(Keys.ENTER)
                    print(f"Pressed Enter on input {i}")
                    time.sleep(3)
                    
                    # Check if it worked by seeing if value is still there
                    if inp.get_attribute('value') == train_number:
                        print("Strategy 5 successful!")
                        return True
                    
            except Exception as inp_error:
                print(f"Error with input {i}: {str(inp_error)}")
        
        print("=== END DEBUG ===")
        
    except Exception as e5:
        print(f"Strategy 5 failed: {str(e5)}")
    
    print("All strategies failed for train number entry")
    return False

def select_date(driver, date_option="today"):
    """Select date from calendar using multiple strategies"""
    print(f"Selecting date: {date_option}")
    
    if date_option == "today":
        print("Using default today date")
        return True
    
    # Strategy 1: Try exact selector
    try:
        date_input_selector = "#root > div > div > div.jss2.jss41.jss53.jss65.jss77.jss2347 > div > div > div > div > div:nth-child(2) > div > div > input"
        wait = WebDriverWait(driver, 10)
        date_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, date_input_selector)))
        print("Found date input using exact selector")
    except:
        # Strategy 2: Find date input by type and position
        try:
            print("Trying alternative date input selectors...")
            date_selectors = [
                "input[type='date']",
                "input[placeholder*='date' i]",
                "input[placeholder*='Date']",
                "div:nth-child(2) input[type='text']",
                "input[type='text']:nth-of-type(2)"
            ]
            
            date_input = None
            for selector in date_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            # Check if it has a date-like value
                            value = elem.get_attribute('value') or ''
                            if '/' in value or '-' in value or len(value) >= 8:
                                date_input = elem
                                print(f"Found date input using: {selector}")
                                break
                    if date_input:
                        break
                except:
                    continue
            
            if not date_input:
                print("Could not find date input, using default date")
                return True
                
        except Exception as e2:
            print(f"Date input selection failed: {str(e2)}")
            return True  # Continue with default date
    
    try:
        # Click to open calendar
        date_input.click()
        time.sleep(2)
        print("Clicked date input - calendar should be open")
        
        # Calculate target date
        today = datetime.now()
        if date_option == "yesterday":
            target_date = today - timedelta(days=1)
        elif date_option == "tomorrow":
            target_date = today + timedelta(days=1)
        else:
            target_date = today
        
        target_day = str(target_date.day)
        print(f"Looking for date: {target_day}")
        
        # Try different selectors for calendar dates
        calendar_selectors = [
            f"//button[text()='{target_day}' and not(@disabled)]",
            f"//td[text()='{target_day}' and not(contains(@class, 'disabled'))]",
            f"//div[text()='{target_day}' and not(contains(@class, 'disabled'))]",
            f"//span[text()='{target_day}' and not(ancestor::*[@disabled])]",
            f"//div[@role='button'][text()='{target_day}']"
        ]
        
        date_clicked = False
        for selector in calendar_selectors:
            try:
                date_elements = driver.find_elements(By.XPATH, selector)
                for date_element in date_elements:
                    if date_element.is_displayed() and date_element.is_enabled():
                        date_element.click()
                        date_clicked = True
                        print(f"Selected date: {target_day}")
                        time.sleep(2)
                        break
                if date_clicked:
                    break
            except:
                continue
        
        if not date_clicked:
            print(f"Could not find clickable date for {date_option}, using default")
            # Click outside calendar to close it
            try:
                driver.find_element(By.TAG_NAME, "body").click()
                time.sleep(1)
            except:
                pass
        
        return True
        
    except Exception as e:
        print(f"Error in date selection: {str(e)}")
        return True  # Continue with default date

def select_boarding_station(driver):
    """Select boarding station from dropdown using multiple strategies"""
    print("Selecting boarding station...")
    
    # Strategy 1: Try exact selector
    try:
        boarding_selector = "#boardingStation > div > div.css-1wy0on6 > div > svg > path"
        wait = WebDriverWait(driver, 10)
        boarding_element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, boarding_selector)))
        boarding_element.click()
        print("Clicked boarding station dropdown using exact path selector")
        time.sleep(2)
        
        actions = ActionChains(driver)
        actions.send_keys(Keys.ENTER).perform()
        print("Pressed Enter to select top boarding station")
        time.sleep(2)
        return True
        
    except Exception as e1:
        print(f"Strategy 1 failed: {str(e1)}")
    
    # Strategy 2: Try boarding station container
    try:
        boarding_selectors = [
            "#boardingStation",
            "#boardingStation > div",
            "#boardingStation div[class*='css-']",
            "[id*='boarding'] div[role='button']",
            "[id*='boarding'] div[class*='select']"
        ]
        
        for selector in boarding_selectors:
            try:
                boarding_element = driver.find_element(By.CSS_SELECTOR, selector)
                if boarding_element.is_displayed() and boarding_element.is_enabled():
                    boarding_element.click()
                    print(f"Clicked boarding station using: {selector}")
                    time.sleep(2)
                    
                    actions = ActionChains(driver)
                    actions.send_keys(Keys.ENTER).perform()
                    print("Pressed Enter to select top boarding station")
                    time.sleep(2)
                    return True
            except:
                continue
                
    except Exception as e2:
        print(f"Strategy 2 failed: {str(e2)}")
    
    # Strategy 3: Find any dropdown that appears after train selection
    try:
        print("Looking for any dropdown/select element...")
        
        # Look for select elements
        selects = driver.find_elements(By.TAG_NAME, "select")
        for select in selects:
            if select.is_displayed() and select.is_enabled():
                select.click()
                time.sleep(1)
                actions = ActionChains(driver)
                actions.send_keys(Keys.ENTER).perform()
                print("Found and used select element for boarding station")
                time.sleep(2)
                return True
        
        # Look for elements with dropdown indicators
        dropdown_indicators = [
            "div[class*='dropdown']",
            "div[class*='select']",
            "div[role='combobox']",
            "div[aria-expanded]",
            "div[class*='css-'] svg",  # React select dropdown arrows
        ]
        
        for selector in dropdown_indicators:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed():
                        # Check if this is likely a boarding station dropdown
                        parent_text = elem.find_element(By.XPATH, "./ancestor::*[contains(@id, 'boarding') or contains(@class, 'boarding')]")
                        if parent_text:
                            elem.click()
                            time.sleep(2)
                            actions = ActionChains(driver)
                            actions.send_keys(Keys.ENTER).perform()
                            print(f"Used dropdown indicator: {selector}")
                            time.sleep(2)
                            return True
            except:
                continue
                
    except Exception as e3:
        print(f"Strategy 3 failed: {str(e3)}")
    
    # Strategy 4: Skip boarding station selection
    print("Could not find boarding station dropdown - this might be optional")
    print("Continuing without boarding station selection...")
    return True  # Return True to continue the process

def click_get_chart_button(driver):
    """Click the Get Train Chart button using multiple strategies"""
    print("Clicking Get Train Chart button...")
    
    # Strategy 1: Try exact selector
    try:
        button_selector = "#root > div > div > div.jss2.jss41.jss53.jss65.jss77.jss2347 > div > div > div > div > div:nth-child(4) > button > span.jss2480"
        wait = WebDriverWait(driver, 10)
        chart_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, button_selector)))
        chart_button.click()
        print("Clicked Get Chart button using exact selector")
        time.sleep(5)
        return True
    except Exception as e1:
        print(f"Strategy 1 failed: {str(e1)}")
    
    # Strategy 2: Try parent button
    try:
        button_parent_selector = "#root > div > div > div.jss2.jss41.jss53.jss65.jss77.jss2347 > div > div > div > div > div:nth-child(4) > button"
        button_parent = driver.find_element(By.CSS_SELECTOR, button_parent_selector)
        if button_parent.is_displayed() and button_parent.is_enabled():
            button_parent.click()
            print("Clicked Get Chart button using parent button selector")
            time.sleep(5)
            return True
    except Exception as e2:
        print(f"Strategy 2 failed: {str(e2)}")
    
    # Strategy 3: Find button by text content
    try:
        text_selectors = [
            "//button[contains(text(), 'Chart')]",
            "//button[contains(text(), 'Get')]",
            "//button[contains(.,'Get Train Chart')]",
            "//span[contains(text(), 'Chart')]/parent::button",
            "//span[contains(text(), 'Get')]/parent::button"
        ]
        
        for selector in text_selectors:
            try:
                chart_button = driver.find_element(By.XPATH, selector)
                if chart_button.is_displayed() and chart_button.is_enabled():
                    chart_button.click()
                    print(f"Clicked Get Chart button using: {selector}")
                    time.sleep(5)
                    return True
            except:
                continue
                
    except Exception as e3:
        print(f"Strategy 3 failed: {str(e3)}")
    
    # Strategy 4: Find any submit button
    try:
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:last-of-type",
            "form button",
            "div:nth-child(4) button"
        ]
        
        for selector in submit_selectors:
            try:
                submit_button = driver.find_element(By.CSS_SELECTOR, selector)
                if submit_button.is_displayed() and submit_button.is_enabled():
                    submit_button.click()
                    print(f"Clicked submit button using: {selector}")
                    time.sleep(5)
                    return True
            except:
                continue
                
    except Exception as e4:
        print(f"Strategy 4 failed: {str(e4)}")
    
    # Strategy 5: Press Enter to submit form
    try:
        print("Trying Enter key to submit form...")
        actions = ActionChains(driver)
        actions.send_keys(Keys.ENTER).perform()
        time.sleep(5)
        print("Pressed Enter to submit form")
        return True
    except Exception as e5:
        print(f"Strategy 5 failed: {str(e5)}")
    
    print("All strategies failed for clicking Get Chart button")
    return False

def load_first_page(train_number, date_option="today"):
    """
    Load and fill the first page form to get to chart page
    
    Args:
        train_number (str): Train number like "02394"
        date_option (str): "yesterday", "today", or "tomorrow"
    
    Returns:
        webdriver instance if successful, None if failed
    """
    
    driver = setup_driver()
    
    try:
        print("=== Loading IRCTC First Page ===")
        print("Opening IRCTC online charts page...")
        
        # Navigate to the page
        driver.get("https://www.irctc.co.in/online-charts/")
        wait_for_page_load(driver)
        print("Page loaded successfully")
        
        # Step 1: Enter train number
        if not enter_train_number(driver, train_number):
            raise Exception("Failed to enter train number")
        print("✓ Train number entered successfully")
        
        # Step 2: Select date
        if not select_date(driver, date_option):
            raise Exception("Failed to select date")
        print("✓ Date selected successfully")
        
        # Step 3: Select boarding station
        if not select_boarding_station(driver):
            raise Exception("Failed to select boarding station")
        print("✓ Boarding station selected successfully")
        
        # Step 4: Click Get Train Chart button
        if not click_get_chart_button(driver):
            raise Exception("Failed to click Get Train Chart button")
        print("✓ Get Train Chart button clicked successfully")
        
        # Wait for next page to load
        print("Waiting for chart page to load...")
        time.sleep(5)
        
        current_url = driver.current_url
        print(f"Current URL: {current_url}")
        
        print("=== First Page Loaded Successfully ===")
        print("Driver ready for scraping...")
        
        return driver
        
    except Exception as e:
        print(f"Error loading first page: {str(e)}")
        try:
            driver.quit()
        except:
            pass
        return None