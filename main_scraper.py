# main_scraper.py
"""
IRCTC Train Chart Scraper - Modular Version

This module provides functions to scrape IRCTC train chart data.
Can be used as a standalone script or imported by other modules.

Usage as script:
    python main_scraper.py

Usage as module:
    from main_scraper import scrape_complete_train_data, scrape_train_data_with_driver
    
    # Complete scraping (handles driver creation and cleanup)
    data = scrape_complete_train_data("12802", "today")
    
    # Use existing driver
    data = scrape_train_data_with_driver(driver, train_number, date_option)
"""

from firstpage import load_first_page, setup_driver
from chart_scraper import scrape_train_chart
import time


def scrape_complete_train_data(train_number, date_option="today", keep_browser_open=False):
    """
    Complete scraping function that handles everything from setup to cleanup.
    
    Args:
        train_number (str): Train number to scrape
        date_option (str): Date option - "yesterday", "today", or "tomorrow"
        keep_browser_open (bool): Whether to keep browser open after scraping
        
    Returns:
        list: Scraped data records, or None if failed
    """
    driver = None
    
    try:
        print(f"🚀 Starting scraping for Train {train_number} ({date_option})")
        
        # Step 1: Load first page and fill form
        print("📝 Loading and filling form...")
        driver = load_first_page(train_number, date_option)
        
        if not driver:
            print("❌ Failed to load first page")
            return None
        
        print("✅ Form loaded successfully")
        time.sleep(3)
        
        # Step 2: Scrape chart data, passing the train number for CSV naming
        print("📊 Scraping chart data...")
        all_data = scrape_train_chart(driver, train_number)
        
        if all_data:
            print(f"✅ Successfully scraped {len(all_data)} records")
            return all_data
        else:
            print("⚠️ No data was scraped")
            return None
            
    except Exception as e:
        print(f"❌ Error during scraping: {str(e)}")
        return None
        
    finally:
        if driver and not keep_browser_open:
            try:
                driver.quit()
                print("🔒 Browser closed")
            except:
                pass


def scrape_train_data_with_driver(driver, train_number, date_option="today"):
    """
    Scrape train data using an existing WebDriver instance.
    Useful when you want to manage the driver lifecycle yourself.
    
    Args:
        driver: Selenium WebDriver instance
        train_number (str): Train number to scrape
        date_option (str): Date option - "yesterday", "today", or "tomorrow"
        
    Returns:
        list: Scraped data records, or None if failed
    """
    try:
        print(f"🚀 Starting scraping for Train {train_number} ({date_option})")
        print("📊 Scraping chart data...")
        all_data = scrape_train_chart(driver, train_number)
        
        if all_data:
            print(f"✅ Successfully scraped {len(all_data)} records")
            return all_data
        else:
            print("⚠️ No data was scraped")
            return None
            
    except Exception as e:
        print(f"❌ Error during scraping: {str(e)}")
        return None


def create_driver_and_navigate(train_number, date_option="today"):
    """
    Create a driver and navigate to the chart page without scraping.
    Useful for manual inspection or custom scraping logic.
    
    Args:
        train_number (str): Train number
        date_option (str): Date option - "yesterday", "today", or "tomorrow"
        
    Returns:
        WebDriver: Configured driver on the chart page, or None if failed
    """
    try:
        print(f"🚀 Setting up browser for Train {train_number} ({date_option})")
        
        driver = load_first_page(train_number, date_option)
        
        if driver:
            print("✅ Browser ready on chart page")
            return driver
        else:
            print("❌ Failed to setup browser")
            return None
            
    except Exception as e:
        print(f"❌ Error setting up browser: {str(e)}")
        return None


def main():
    """Main execution function for standalone usage"""
    TRAIN_NUMBER = "15013"
    DATE_OPTION = "today"
    
    print("="*60)
    print("IRCTC TRAIN CHART SCRAPER")
    print("="*60)
    
    try:
        data = scrape_complete_train_data(
            train_number=TRAIN_NUMBER,
            date_option=DATE_OPTION,
            keep_browser_open=True
        )
        
        if data:
            print(f"\n📊 Scraping completed! Total records: {len(data)}")
            print("📁 Data saved to 'scraped_data' directory")
        else:
            print("\n⚠️ Scraping failed or no data found")
        
        print("\n" + "="*60)
        print("PROCESS COMPLETED")
        print("="*60)
        
        input("\n👀 Press Enter to exit...")
        
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")


# Shortcut wrapper

def get_train_data(train_number, date_option="today"):
    data = scrape_complete_train_data(train_number, date_option, keep_browser_open=False)
    return data if data else []


if __name__ == "__main__":
    main()