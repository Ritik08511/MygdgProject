from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import csv
import os
import re
from datetime import datetime

DEBUG_NEXT_PAGE_CLICK = True

class ChartScraper:
    def __init__(self, driver):
        self.driver = driver
        self.page_load_wait = WebDriverWait(driver, 10)
        self.quick_element_wait = WebDriverWait(driver, 1.5)
        self.very_quick_wait = WebDriverWait(driver, 0.5)
        self.instant_wait = WebDriverWait(driver, 0.1)  # For client-side operations
        self.all_data = []
        self.initial_url = None 

    def _save_debug_info(self, stage_name="debug"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        screenshot_file = f"debug_{stage_name}_{timestamp}.png"
        page_source_file = f"debug_{stage_name}_{timestamp}.html"
        try:
            self.driver.save_screenshot(screenshot_file)
            with open(page_source_file, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
        except Exception as e:
            pass

    def _find_main_chart_summary_table(self):
        coach_class_pattern = re.compile(r'\([\dA-Z]{1,2}E?A?\)$') 
        possible_table_selectors_xpath = [
            "//table[thead/tr/th[contains(text(), '(') and contains(text(), ')')] and tbody/tr/td//span[contains(text(), 'Berth Details') or contains(@style, 'cursor: pointer')]]",
            "//div[.//table[thead/tr/th and tbody/tr/td//span[contains(text(), 'Berth Details')]]]//table[thead/tr/th and tbody/tr/td//span[contains(text(), 'Berth Details')]]",
            "//table[thead/tr/th and tbody/tr/td//span[contains(text(), 'Berth Details') or contains(@style, 'cursor: pointer')]]"
        ]
        possible_table_selectors_css = ["div.MuiPaper-root table", "div[class*='TableContainer'] table", "table"]
        all_selectors = [(s, 'xpath') for s in possible_table_selectors_xpath] + [(s, 'css') for s in possible_table_selectors_css]
        for i, (selector, selector_type) in enumerate(all_selectors):
            try:
                candidate_tables = []
                wait_for_table_list = self.quick_element_wait 
                if selector_type == 'xpath':
                    candidate_tables = wait_for_table_list.until(lambda d: d.find_elements(By.XPATH, selector))
                else: 
                    candidate_tables = wait_for_table_list.until(lambda d: d.find_elements(By.CSS_SELECTOR, selector))
                if not candidate_tables: continue
                for table_idx, table_candidate in enumerate(candidate_tables):
                    if not table_candidate.is_displayed(): continue
                    try:
                        table_candidate.find_element(By.XPATH, ".//tbody/tr/td//span[contains(text(), 'Berth Details') or contains(@style, 'cursor: pointer')]")
                        headers = table_candidate.find_elements(By.CSS_SELECTOR, "thead > tr > th")
                        if not headers: continue
                        if any(coach_class_pattern.search(th.text.strip()) for th in headers):
                            return table_candidate
                    except Exception: continue
            except Exception: continue
        return None

    def get_available_categories(self):
        categories = []
        main_table = self._find_main_chart_summary_table()
        if not main_table: return []
        try:
            header_rows = main_table.find_elements(By.CSS_SELECTOR, "thead > tr")
            target_header_row = None
            coach_class_pattern = re.compile(r'\([\dA-Z]{1,2}E?A?\)$')
            for hr in header_rows:
                if any(coach_class_pattern.search(th.text.strip()) for th in hr.find_elements(By.TAG_NAME, "th")):
                    target_header_row = hr; break
            if not target_header_row: return []
            header_cells = target_header_row.find_elements(By.TAG_NAME, "th")
            if not header_cells: return []
            berth_details_container_row = None
            tbody_rows = main_table.find_elements(By.CSS_SELECTOR, "tbody > tr")
            if not tbody_rows: return []
            for row_candidate in tbody_rows:
                try:
                    if len(row_candidate.find_elements(By.TAG_NAME, "td")) < len(header_cells): continue
                    row_candidate.find_element(By.XPATH, ".//td//span[contains(text(), 'Berth Details') or contains(@style, 'cursor: pointer')]")
                    berth_details_container_row = row_candidate; break 
                except: continue
            if not berth_details_container_row: return []
            for index, th_cell in enumerate(header_cells):
                category_name = th_cell.text.strip()
                if category_name and coach_class_pattern.search(category_name):
                    try:
                        td_cell = berth_details_container_row.find_element(By.CSS_SELECTOR, f"td:nth-child({index + 1})")
                        if td_cell.find_element(By.XPATH, ".//span[contains(text(), 'Berth Details') or contains(@style, 'cursor: pointer')]").is_displayed():
                            categories.append({"name": category_name, "click_index": index + 1})
                    except Exception: pass
            return categories
        except Exception as e: return []

    def click_berth_category(self, category_click_index, category_name_for_logging=""):
        try:
            main_table = self._find_main_chart_summary_table() 
            if not main_table: return False
            berth_details_container_row = None
            tbody_rows = main_table.find_elements(By.CSS_SELECTOR, "tbody > tr") 
            if not tbody_rows: return False
            for row_candidate in tbody_rows: 
                try:
                    td_cell = row_candidate.find_element(By.CSS_SELECTOR, f"td:nth-child({category_click_index})")
                    td_cell.find_element(By.XPATH, ".//span[contains(text(), 'Berth Details') or contains(@style, 'cursor: pointer')]")
                    berth_details_container_row = row_candidate; break 
                except: continue 
            if not berth_details_container_row: return False
            target_td = berth_details_container_row.find_element(By.CSS_SELECTOR, f"td:nth-child({category_click_index})")
            span_element = self.quick_element_wait.until(
                EC.element_to_be_clickable(target_td.find_element(By.XPATH, ".//span[contains(text(), 'Berth Details') or contains(@style, 'cursor: pointer')]"))
            )
            if not span_element or not span_element.is_displayed(): return False
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", span_element)
            click_success = False
            try:
                actions = ActionChains(self.driver); actions.move_to_element(span_element).click().perform(); click_success = True
            except Exception:
                try: self.driver.execute_script("arguments[0].click();", span_element); click_success = True
                except Exception: pass
            if click_success:
                try:
                    self.page_load_wait.until(
                        EC.any_of(
                            EC.visibility_of_element_located((By.XPATH, "//div[contains(@class, 'MuiTablePagination-displayedRows')]")), 
                            EC.visibility_of_element_located((By.XPATH, "//div[contains(@class, 'MuiTableContainer-root')]//table/tbody[./tr]")) 
                        )
                    )
                except Exception as e_wait_details:
                    if DEBUG_NEXT_PAGE_CLICK: self._save_debug_info(f"cat_load_fail_{category_name_for_logging.replace(' ','_')}")
                return True
            return False
        except Exception as e: return False

    def get_pagination_info(self):
        try:
            pagination_selectors = [
                "//div[contains(@class, 'MuiTablePagination-root')]//p[contains(@class, 'MuiTablePagination-displayedRows')]",
                "//table[contains(@class, 'MuiTable-root')]/tfoot//span[contains(text(), 'of')]",
                "//div[contains(@class, 'MuiTablePagination-displayedRows')]"
            ]
            
            for selector in pagination_selectors:
                try:
                    # Direct find - no wait since it's client-side rendered
                    pagination_element = self.driver.find_element(By.XPATH, selector)
                    if pagination_element and pagination_element.is_displayed():
                        pagination_text = pagination_element.text.strip()
                        match_of_z = re.search(r'of\s+(\d+)', pagination_text)
                        if match_of_z: 
                            return int(match_of_z.group(1)), pagination_text
                        numbers = re.findall(r'\d+', pagination_text)
                        if numbers: 
                            return max(map(int, numbers)), pagination_text
                        return None, pagination_text
                except Exception: 
                    continue
            return None, None
        except Exception: 
            return None, None

    def scroll_to_bottom_of_table(self):
        try:
            # Direct JS scroll - no element finding delays
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            return True
        except Exception: 
            return False

    def click_next_page(self):
        try:
            # Direct DOM search - no waits since it's client-side
            next_button_selectors = [
                "//button[not(@disabled) and .//span[contains(@class, 'jss2020') and text()='chevron_right']]",
                "//button[not(@disabled) and .//span[contains(@class, 'material-icons') and text()='chevron_right']]",
                "//button[@aria-label='Next page' and not(@disabled)]",
                "//button[@aria-label='Go to next page' and not(@disabled)]",
                "//table[contains(@class, 'MuiTable-root')]/tfoot//button[not(@disabled) and .//span[text()='chevron_right']]",
            ]
            
            for selector in next_button_selectors:
                try:
                    # Direct find - no wait
                    next_button = self.driver.find_element(By.XPATH, selector)
                    if next_button and next_button.is_displayed() and next_button.is_enabled():
                        # Direct JS click for maximum speed
                        self.driver.execute_script("arguments[0].click();", next_button)
                        return True
                except Exception:
                    continue
                    
            return False
        except Exception:
            return False
    
    def scrape_table_data(self):
        try:
            table_body_selectors = [
                "//div[contains(@class, 'MuiTableContainer-root')]//table/tbody",
                "//table[contains(@class, 'MuiTable-root')]/tbody", "table tbody"
            ]
            tbody = None
            for selector in table_body_selectors:
                try:
                    if selector.startswith("//"): tbody_candidate = self.driver.find_element(By.XPATH, selector)
                    else: tbody_candidate = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if tbody_candidate and tbody_candidate.is_displayed(): tbody = tbody_candidate; break
                except Exception: continue
            if not tbody: return [] 
            rows = tbody.find_elements(By.TAG_NAME, "tr"); page_data = []
            if not rows: return []
            for i, row_element in enumerate(rows):
                try:
                    cells = row_element.find_elements(By.TAG_NAME, "td"); 
                    if not cells: continue
                    cell_texts = [cell.text.strip() for cell in cells] 
                    page_data.append({
                        'from_station': cell_texts[0] if len(cell_texts) > 0 else '',
                        'to_station': cell_texts[1] if len(cell_texts) > 1 else '',
                        'coach': cell_texts[2] if len(cell_texts) > 2 else '',
                        'berth_no': cell_texts[3] if len(cell_texts) > 3 else '',
                        'berth_type': cell_texts[4] if len(cell_texts) > 4 else '',
                        'cabin': cell_texts[5] if len(cell_texts) > 5 else '',
                        'cabin_no': cell_texts[6] if len(cell_texts) > 6 else ''})
                except Exception: continue
            return page_data
        except Exception: return []

    def scrape_all_pages_for_category(self, category_name):
        category_data = []
        page_number = 1
        max_pages = 150
        
        # Get total count once at start
        total_count, _ = self.get_pagination_info()
        expected_total = total_count if total_count and total_count > 0 else float('inf')
        
        while page_number <= max_pages:
            # Scrape current page data
            current_page_data = self.scrape_table_data()
            
            if current_page_data:
                for row in current_page_data: 
                    row.update({'category': category_name, 'page_number': page_number})
                category_data.extend(current_page_data)
                
                # Quick exit if we have all expected data
                if len(category_data) >= expected_total and expected_total != float('inf'):
                    break
            else:
                # No data on this page - likely end of pagination
                break
            
            # Lightning-fast next page click
            if not self.click_next_page():
                break
                
            page_number += 1
            
        return category_data
    
    def click_back_button(self):
        try:
            back_selectors = [
                "#root > div > header.jss107.jss113.jss98.jss99.jss104.mui-fixed.jss332 > div > button.jss549.jss539.jss541.jss547 > span.jss540 > svg",
                "#root > div > header > div > button > span > svg", "header button[class*='jss549'] svg",
                "header button svg", "button[class*='back']", "//button[contains(@class, 'back')]",
                "//svg[contains(@class, 'back')]/parent::button", "//button//svg", "//header//button" 
            ]
            for i, selector in enumerate(back_selectors):
                try:
                    back_button = self.quick_element_wait.until(EC.element_to_be_clickable((By.XPATH if selector.startswith("//") else By.CSS_SELECTOR, selector)))
                    if back_button.is_displayed() and back_button.is_enabled():
                        try: back_button.click() 
                        except Exception: self.driver.execute_script("arguments[0].click();", back_button)
                        try:
                            self.page_load_wait.until(lambda d: self._find_main_chart_summary_table() is not None)
                        except Exception:
                            time.sleep(0.2)
                        return True
                except Exception: continue 
            return False
        except Exception: return False

    def scrape_all_categories(self):
        try:
            if not self.initial_url: self.initial_url = self.driver.current_url
        except Exception: pass
        try:
            self.page_load_wait.until(lambda d: self._find_main_chart_summary_table() is not None)
        except Exception: return self.all_data
        available_categories = self.get_available_categories()
        if not available_categories: return self.all_data
        
        for i, category_info in enumerate(available_categories):
            cat_name, cat_idx = category_info["name"], category_info["click_index"]
            if self.initial_url and self.driver.current_url != self.initial_url:
                try:
                    self.driver.get(self.initial_url)
                    self.page_load_wait.until(EC.url_to_be(self.initial_url)) 
                    self.page_load_wait.until(lambda d: self._find_main_chart_summary_table() is not None)
                except Exception: continue
            try:
                if not self.click_berth_category(cat_idx, cat_name): continue 
                category_data = self.scrape_all_pages_for_category(cat_name)
                if category_data: self.all_data.extend(category_data)
                if i < len(available_categories) - 1:
                    if not self.click_back_button():
                        if self.initial_url:
                            self.driver.get(self.initial_url)
                            self.page_load_wait.until(EC.url_to_be(self.initial_url))
                            self.page_load_wait.until(lambda d: self._find_main_chart_summary_table() is not None)
                        else: break 
                    if self.initial_url and self.driver.current_url != self.initial_url:
                        self.driver.get(self.initial_url)
                        self.page_load_wait.until(EC.url_to_be(self.initial_url))
                        self.page_load_wait.until(lambda d: self._find_main_chart_summary_table() is not None)
            except Exception:
                if i < len(available_categories) - 1 and self.initial_url:
                    try:
                        self.driver.get(self.initial_url)
                        self.page_load_wait.until(EC.url_to_be(self.initial_url))
                        self.page_load_wait.until(lambda d: self._find_main_chart_summary_table() is not None)
                    except Exception: break 
                elif not self.initial_url: break
        return self.all_data
    
    def save_to_csv(self, filename=None):
        if not self.all_data:
            return False
        if not filename:
            filename = f"irctc_chart_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            os.makedirs("scraped_data", exist_ok=True)
            filepath = os.path.join("scraped_data", filename)
            headers = ['category', 'page_number', 'from_station', 'to_station', 'coach', 'berth_no', 'berth_type', 'cabin', 'cabin_no']
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                writer.writerows(self.all_data)
            return True
        except Exception:
            return False

    def print_summary(self):
        if not self.all_data:
            return
        counts = {}
        for r in self.all_data:
            cat = r.get('category', 'Unknown')
            counts[cat] = counts.get(cat, 0) + 1


def scrape_train_chart(driver, train_number=None):
    start = time.time()
    scraper = ChartScraper(driver)
    data = scraper.scrape_all_categories()
    scraper.print_summary()
    if data:
        filename = f"{train_number}.csv" if train_number else None
        scraper.save_to_csv(filename=filename)
    elapsed = time.time()-start
    return data

if __name__ == '__main__':
    pass