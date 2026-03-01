"""RBC Companies publisher with browser automation."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from core.config import config


class RBCPublisher:
    """Publishes content to RBC Companies using browser automation."""
    
    LOGIN_URL = "https://companies.rbc.ru/login"
    CREATE_URL = "https://companies.rbc.ru/cabinet/materials/create"
    TIMEOUT = 30000  # 30 seconds
    
    async def publish(
        self, title: str, text: str, image_path: Optional[str] = None
    ) -> bool:
        """
        Publish content to RBC Companies.
        
        Args:
            title: Article title
            text: Article content
            image_path: Optional path to cover image
        
        Returns:
            True if published successfully, False otherwise
        """
        if not config.rbc_login or not config.rbc_password:
            logger.warning("RBC_LOGIN or RBC_PASSWORD не заданы, публикация пропущена")
            return False

        try:
            from playwright.async_api import (
                TimeoutError as PlaywrightTimeout,
                async_playwright,
            )
        except ImportError:
            logger.error("playwright не установлен. Запускай в Docker.")
            return False
        
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
                page = await context.new_page()
                
                # Step 1: Login
                logger.info("RBC: Navigating to login page")
                await page.goto(self.LOGIN_URL, wait_until="networkidle")
                
                # Find and fill login form
                logger.info("RBC: Filling login credentials")
                try:
                    # Common selectors for login forms
                    await page.fill('input[type="email"], input[name="email"], input[name="login"]', config.rbc_login)
                    await page.fill('input[type="password"], input[name="password"]', config.rbc_password)
                    
                    # Click submit button
                    await page.click('button[type="submit"], input[type="submit"], button:has-text("Войти")')
                    
                    # Wait for successful login (URL should not contain /login)
                    logger.info("RBC: Waiting for login redirect")
                    await page.wait_for_url(lambda url: "/login" not in url, timeout=self.TIMEOUT)
                    logger.info("RBC: Login successful")
                    
                except PlaywrightTimeout as e:
                    logger.error(f"RBC: Login timeout - {e}")
                    await self._save_error_screenshot(page, "login_timeout")
                    return False
                except Exception as e:
                    logger.error(f"RBC: Login failed - {e}")
                    await self._save_error_screenshot(page, "login_failed")
                    return False
                
                # Step 2: Navigate to create page
                logger.info("RBC: Navigating to create material page")
                try:
                    await page.goto(self.CREATE_URL, wait_until="networkidle")
                except Exception as e:
                    logger.error(f"RBC: Failed to navigate to create page - {e}")
                    await self._save_error_screenshot(page, "navigate_create_failed")
                    return False
                
                # Step 3: Fill article form
                logger.info("RBC: Filling article form")
                try:
                    # Fill title
                    await page.fill('input[name="title"], input[placeholder*="Заголовок"]', title)
                    
                    # Fill text content (could be textarea, rich text editor, or iframe)
                    # Try multiple selectors
                    text_selectors = [
                        'textarea[name="text"]',
                        'textarea[name="content"]',
                        'div[contenteditable="true"]',
                        '.ql-editor',  # Quill editor
                        '.tox-edit-area',  # TinyMCE editor
                    ]
                    
                    filled = False
                    for selector in text_selectors:
                        try:
                            await page.fill(selector, text, timeout=5000)
                            filled = True
                            break
                        except:
                            continue
                    
                    if not filled:
                        logger.warning("RBC: Could not find text field, trying to type into focused element")
                        await page.keyboard.type(text)
                    
                    logger.info("RBC: Article form filled")
                    
                except Exception as e:
                    logger.error(f"RBC: Failed to fill article form - {e}")
                    await self._save_error_screenshot(page, "fill_form_failed")
                    return False
                
                # Step 4: Upload image if provided
                if image_path:
                    logger.info(f"RBC: Uploading image {image_path}")
                    try:
                        # Wait for file input to appear
                        file_input = page.locator('input[type="file"]')
                        await file_input.set_input_files(image_path)
                        
                        # Wait for upload to complete
                        await page.wait_for_timeout(2000)
                        logger.info("RBC: Image uploaded successfully")
                        
                    except Exception as e:
                        logger.warning(f"RBC: Image upload failed (non-critical) - {e}")
                        await self._save_error_screenshot(page, "upload_image_failed")
                
                # Step 5: Submit for moderation
                logger.info("RBC: Submitting for moderation")
                try:
                    # Look for submit button
                    submit_selectors = [
                        'button:has-text("Отправить")',
                        'button:has-text("Опубликовать")',
                        'button:has-text("На модерацию")',
                        'button[type="submit"]',
                        'input[type="submit"]',
                    ]
                    
                    submitted = False
                    for selector in submit_selectors:
                        try:
                            await page.click(selector, timeout=5000)
                            submitted = True
                            break
                        except:
                            continue
                    
                    if not submitted:
                        logger.error("RBC: Could not find submit button")
                        await self._save_error_screenshot(page, "submit_button_not_found")
                        return False
                    
                    # Wait for success confirmation
                    await page.wait_for_timeout(3000)
                    logger.info("RBC: Article submitted successfully")
                    
                    return True
                    
                except Exception as e:
                    logger.error(f"RBC: Submission failed - {e}")
                    await self._save_error_screenshot(page, "submission_failed")
                    return False
                
            except Exception as e:
                logger.error(f"RBC: Unexpected error during publishing - {e}")
                if browser:
                    try:
                        page = (await browser.contexts)[0].pages[0]
                        await self._save_error_screenshot(page, "unexpected_error")
                    except:
                        pass
                return False
            
            finally:
                if browser:
                    await browser.close()
    
    async def _save_error_screenshot(self, page, error_type: str) -> None:
        """Save screenshot on error for debugging."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_dir = config.logs_dir / "rbc_errors"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            
            screenshot_path = screenshot_dir / f"{error_type}_{timestamp}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"RBC: Error screenshot saved to {screenshot_path}")
        except Exception as e:
            logger.error(f"RBC: Failed to save error screenshot - {e}")
