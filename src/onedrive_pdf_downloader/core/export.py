"""
Core functionality for exporting PDFs from web browser.
"""

import logging
import os
import shutil
import tempfile
from time import sleep

import img2pdf
from selenium.common.exceptions import (
    JavascriptException,
    NoSuchElementException,
)
from selenium.webdriver.common.by import By

from onedrive_pdf_downloader.browser.constants import ARIA_LABELS_NEXT_PAGE
from onedrive_pdf_downloader.browser.utils import find_element, hide_toolbar
from onedrive_pdf_downloader.utils.image_utils import crop_image, create_collage


def detect_slide_mode(browser):
    """
    Detect if the PDF is in slide/presentation mode by checking canvas dimensions.
    
    Returns:
        bool: True if in slide mode (aspect ratio suggests slides)
    """
    try:
        canvas = browser.find_element(By.CSS_SELECTOR, "canvas")
        width = canvas.size['width']
        height = canvas.size['height']
        aspect_ratio = width / height if height > 0 else 0
        
        # Typical slide aspect ratios: 16:9 (1.78), 4:3 (1.33), 16:10 (1.6)
        # If aspect ratio > 1.2, likely a slide presentation
        is_slide = aspect_ratio > 1.2
        logging.debug(f"Canvas aspect ratio: {aspect_ratio:.2f}, Slide mode: {is_slide}")
        return is_slide
    except Exception as e:
        logging.debug(f"Could not detect slide mode: {e}")
        return False


def scroll_to_page_top(browser):
    """
    Scroll the canvas container to the very top to ensure we start from page 1.
    """
    try:
        # Scroll the main content area to top
        browser.execute_script("""
            var canvas = document.querySelector('canvas');
            if (canvas && canvas.parentElement) {
                var container = canvas.parentElement;
                while (container && container.scrollHeight === container.clientHeight) {
                    container = container.parentElement;
                }
                if (container) {
                    container.scrollTop = 0;
                }
            }
        """)
        sleep(0.5)  # Wait for scroll to complete
        logging.debug("Scrolled to top of document")
    except Exception as e:
        logging.warning(f"Could not scroll to top: {e}")


def get_canvas_position(browser):
    """
    Get the current scroll position and canvas dimensions.
    
    Returns:
        dict: Contains scroll position, canvas height, and container height
    """
    try:
        position = browser.execute_script("""
            var canvas = document.querySelector('canvas');
            if (!canvas) return null;
            
            var container = canvas.parentElement;
            while (container && container.scrollHeight === container.clientHeight) {
                container = container.parentElement;
            }
            
            if (!container) return null;
            
            return {
                scrollTop: container.scrollTop,
                scrollHeight: container.scrollHeight,
                clientHeight: container.clientHeight,
                canvasHeight: canvas.height,
                canvasWidth: canvas.width
            };
        """)
        return position
    except Exception as e:
        logging.debug(f"Error getting canvas position: {e}")
        return None


def scroll_by_exact_amount(browser, pixels):
    """
    Scroll by an exact pixel amount.
    
    Args:
        browser: Browser instance
        pixels: Number of pixels to scroll
    """
    try:
        browser.execute_script(f"""
            var canvas = document.querySelector('canvas');
            if (canvas && canvas.parentElement) {{
                var container = canvas.parentElement;
                while (container && container.scrollHeight === container.clientHeight) {{
                    container = container.parentElement;
                }}
                if (container) {{
                    container.scrollTop += {pixels};
                }}
            }}
        """)
        sleep(0.3)  # Brief pause for rendering
    except Exception as e:
        logging.warning(f"Error scrolling: {e}")


def export_pdf_slide_mode(args, browser, total_of_pages, filename):
    """
    Export PDF in slide mode - scrolls by exact canvas height for each slide.
    
    Args:
        args: Command line arguments
        browser: Browser instance
        total_of_pages: Total number of pages
        filename: Output filename
        
    Returns:
        bool: True if successful
    """
    files_list = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Hide toolbar
        try:
            hide_toolbar(browser)
            logging.info("Toolbar hidden for clean screenshots.")
        except NoSuchElementException:
            logging.warning("Could not hide toolbar.")
        
        # Scroll to the very top first
        scroll_to_page_top(browser)
        
        # Get canvas dimensions
        position = get_canvas_position(browser)
        if not position:
            logging.error("Could not get canvas dimensions")
            return False
        
        canvas_height = position['canvasHeight']
        logging.info(f"Detected canvas height: {canvas_height}px")
        logging.info("Using slide mode: scrolling by exact canvas height")
        
        # Process each page
        for page_number in range(1, total_of_pages + 1):
            image_path = f"{temp_dir}/{page_number}.png"
            raw_image_path = f"{temp_dir}/raw_{page_number}.png"
            
            try:
                canvas = browser.find_element(By.CSS_SELECTOR, "canvas")
                canvas.screenshot(raw_image_path)
            except NoSuchElementException:
                logging.error("Cannot find PDF canvas")
                return False
            
            shutil.copy(raw_image_path, image_path)
            crop_image(image_path)
            files_list.append(image_path)
            
            logging.info(f"Page {page_number} of {total_of_pages} exported.")
            
            # Scroll to next slide (exact canvas height)
            if page_number < total_of_pages:
                scroll_by_exact_amount(browser, canvas_height)
        
        # Save results
        return save_pdf_results(args, filename, files_list, temp_dir, total_of_pages)


def export_pdf_standard_mode(args, browser, total_of_pages, filename):
    """
    Export PDF using standard navigation button mode.
    
    Args:
        args: Command line arguments
        browser: Browser instance
        total_of_pages: Total number of pages
        filename: Output filename
        
    Returns:
        bool: True if successful
    """
    files_list = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Hide toolbar
        try:
            hide_toolbar(browser)
            logging.info("Toolbar hidden for clean screenshots.")
        except NoSuchElementException:
            logging.warning("Could not hide toolbar.")
        
        # Process each page
        page_number = 1
        while page_number <= total_of_pages:
            sleep(1)  # Wait for page to load
            image_path = f"{temp_dir}/{page_number}.png"
            raw_image_path = f"{temp_dir}/raw_{page_number}.png"
            
            try:
                browser.find_element(By.CSS_SELECTOR, "canvas").screenshot(raw_image_path)
            except NoSuchElementException:
                logging.error("Cannot find PDF canvas")
                return False
            
            shutil.copy(raw_image_path, image_path)
            crop_image(image_path)
            files_list.append(image_path)
            
            logging.info(f"Page {page_number} of {total_of_pages} exported.")
            
            page_number += 1
            
            # Navigate to next page using button
            if page_number <= total_of_pages:
                try:
                    next_page_button = find_element(browser, ARIA_LABELS_NEXT_PAGE, By.XPATH)
                    browser.execute_script("arguments[0].scrollIntoView(true);", next_page_button)
                    sleep(1)
                    browser.execute_script("arguments[0].click();", next_page_button)
                except (NoSuchElementException, JavascriptException):
                    logging.error("Cannot find next page button. Saving pages obtained so far.")
                    break
        
        # Save results
        return save_pdf_results(args, filename, files_list, temp_dir, page_number)


def save_pdf_results(args, filename, files_list, temp_dir, page_count):
    """
    Save the final PDF and optional outputs (images, collage).
    
    Args:
        args: Command line arguments
        filename: Output filename
        files_list: List of image file paths
        temp_dir: Temporary directory path
        page_count: Number of pages processed
        
    Returns:
        bool: True if successful
    """
    try:
        logging.info(f"Saving the file as '{filename}'.")
        with open(filename, "wb") as out_file:
            out_file.write(img2pdf.convert(files_list))
        
        # Save raw images if requested
        if args.keep_raw_imgs:
            raw_keep_dir = f"{filename}_raw_images"
            os.makedirs(raw_keep_dir, exist_ok=True)
            for i in range(1, page_count):
                raw_path = f"{temp_dir}/raw_{i}.png"
                if os.path.exists(raw_path):
                    shutil.copy(raw_path, raw_keep_dir)
            logging.info(f"Raw images kept in directory '{raw_keep_dir}'.")
        
        # Save cropped images if requested
        if args.keep_imgs:
            keep_dir = f"{filename}_images"
            os.makedirs(keep_dir, exist_ok=True)
            for file_path in files_list:
                shutil.copy(file_path, keep_dir)
            logging.info(f"Images kept in directory '{keep_dir}'.")
        
        # Create collage if requested
        if args.create_collage:
            collage_path = f"{filename}_collage.png"
            create_collage(files_list, collage_path)
            logging.info(f"Collage saved as '{collage_path}'.")
        
        logging.info("PDF export completed successfully.")
        return True
        
    except IOError as e:
        logging.error(f"Error saving PDF: {e}")
        return False


def export_pdf(args, browser, total_of_pages, filename):
    """
    Export the PDF by taking screenshots of each page.
    Automatically detects slide mode and uses appropriate scrolling method.
    
    Args:
        args (argparse.Namespace): Command line arguments
        browser (webdriver): Browser instance
        total_of_pages (int): Total number of pages
        filename (str): Output filename

    Returns:
        bool: True if successful, False otherwise
    """
    # Detect if we're in slide mode
    is_slide_mode = detect_slide_mode(browser)
    
    if is_slide_mode:
        logging.info("Detected slide/presentation format - using precise slide scrolling")
        return export_pdf_slide_mode(args, browser, total_of_pages, filename)
    else:
        logging.info("Using standard page navigation")
        return export_pdf_standard_mode(args, browser, total_of_pages, filename)
