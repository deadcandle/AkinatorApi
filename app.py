from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import uuid
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, filename="runtime.log", filemode="w")

app = FastAPI()

games = {}

class AkinatorGame:
    def __init__(self, theme="1"):
        firefox_options = FirefoxOptions()
        firefox_options.add_argument("--headless")
        firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--disable-dev-shm-usage")
        firefox_options.add_argument("--disable-gpu")
        firefox_options.add_argument("--disable-web-security")
        firefox_options.add_argument("--disable-features=VizDisplayCompositor")
        
        self.driver = webdriver.Firefox(
            service=FirefoxService(GeckoDriverManager().install()),
            options=firefox_options
        )
        self.driver.set_window_size(1366, 768)
        self.current_question = None
        self.game_stage = "starting"
        self.start_game(theme)

    def start_game(self, theme="1"):
        try:
            self.driver.get("https://en.akinator.com")
            
            # Click the play button
            play_button_div = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'btn-play')]"))
            )
            play_button = play_button_div.find_element(By.TAG_NAME, "a")
            play_button.click()
            
            # Select game mode (theme)
            # Wait for the theme selection to appear
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'database-selection')]"))
            )
            
            # Theme IDs: 1 = Characters, 2 = Objects, 14 = Animals
            theme_xpath = f'//li[contains(@class, "li-game") and contains(@onclick, "chooseTheme(\'{theme}\')")]'
            theme_selector = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, theme_xpath))
            )
            theme_selector.click()
            
            # Wait for the first question to appear
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.ID, "question-label"))
            )

            logging.info("Game started successfully")
            self.game_stage = "playing"
            self.current_question = self.get_current_question()
            return self.current_question
            
        except Exception as e:
            self.game_stage = "error"
            logging.error(f"Error starting game: {e.__class__.__name__}: {str(e)}")
            # Log the HTML when an error occurs for debugging
            try:
                logging.error(f"Error page HTML: {self.driver.page_source}")
            except Exception as page_err:
                logging.error(f"Could not retrieve page source during error: {str(page_err)}")
            return f"Error starting game: {e.__class__.__name__}: {str(e)}"

    def get_current_question(self):
        try:
            # Check if we're in the propose/guess stage first
            try:
                propose_block = self.driver.find_element(By.ID, "proposeGameBlock")
                if propose_block.is_displayed():
                    # We're in the guess stage
                    try:
                        character_name = self.driver.find_element(By.ID, "name_proposition").text
                        
                        # Try to get the image URL
                        image_url = ""
                        try:
                            img_element = self.driver.find_element(By.XPATH, "//div[@id='img_character']//img")
                            image_url = img_element.get_attribute("src")
                        except NoSuchElementException:
                            logging.warning("Could not find character image")
                        
                        # Try to get description (might be empty)
                        try:
                            character_desc = self.driver.find_element(By.ID, "description_proposition").text
                            if character_desc == "-":
                                character_desc = ""
                        except NoSuchElementException:
                            character_desc = ""
                        
                        self.game_stage = "guess"
                        result = {
                            "type": "guess",
                            "character_name": character_name,
                            "character_description": character_desc,
                            "image_url": image_url,
                            "message": f"I think of: {character_name}"
                        }
                        if character_desc:
                            result["message"] += f" - {character_desc}"
                        
                        logging.info(f"Akinator made a guess: {character_name}")
                        return result
                        
                    except NoSuchElementException as e:
                        logging.error(f"Error getting character info: {str(e)}")
                        self.game_stage = "guess"
                        return {"type": "guess", "message": "Akinator made a guess but couldn't get details"}
            except NoSuchElementException:
                pass  # Not in propose stage, continue to check for question
            
            # Check if we're in the normal question stage
            try:
                question_block = self.driver.find_element(By.ID, "questionGameBlock")
                if question_block.is_displayed():
                    question_element = self.driver.find_element(By.ID, "question-label")
                    question_text = question_element.text
                    logging.info(f"Found question: {question_text}")
                    return {"type": "question", "message": question_text}
            except NoSuchElementException:
                pass  # Not in question stage
            
            # Check if game is finished
            try:
                end_selectors = [
                    "//p[contains(@class, 'end-text')]",
                    ".end-text",
                    ".game-over"
                ]
                
                for selector in end_selectors:
                    try:
                        if selector.startswith("//"):
                            end_text = self.driver.find_element(By.XPATH, selector)
                        else:
                            end_text = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if end_text.is_displayed():
                            self.game_stage = "finished"
                            return {"type": "finished", "message": end_text.text}
                    except NoSuchElementException:
                        continue
            except:
                pass
            
            return {"type": "unknown", "message": "Couldn't identify the current game state"}
            
        except Exception as e:
            logging.error(f"Error in get_current_question: {str(e)}")
            return {"type": "error", "message": f"Error getting question: {str(e)}"}

    def handle_overlays(self):
        """Try to close any overlays, popups, or ads that might be blocking clicks"""
        try:
            # Check for common overlay/popup close buttons
            close_selectors = [
                "//button[contains(@class, 'close')]",
                "//span[contains(@class, 'close')]", 
                "//div[contains(@class, 'close')]",
                "//*[@aria-label='Close']",
                "//button[contains(text(), '×')]",
                "//button[contains(text(), 'Close')]",
                ".modal-close",
                ".popup-close",
                ".overlay-close"
            ]
            
            for selector in close_selectors:
                try:
                    if selector.startswith("//"):
                        close_button = self.driver.find_element(By.XPATH, selector)
                    else:
                        close_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if close_button.is_displayed():
                        close_button.click()
                        logging.info(f"Closed overlay using selector: {selector}")
                        time.sleep(1)
                        return True
                except:
                    continue
            
            # Try to dismiss any iframes or overlays by clicking outside
            try:
                body = self.driver.find_element(By.TAG_NAME, "body")
                self.driver.execute_script("arguments[0].click();", body)
                time.sleep(1)
            except:
                pass
                
            return False
        except Exception as e:
            logging.warning(f"Error handling overlays: {str(e)}")
            return False

    def safe_click(self, element):
        """Safely click an element using multiple strategies"""
        try:
            # First try normal click
            element.click()
            return True
        except Exception as first_error:
            logging.warning(f"Normal click failed: {str(first_error)}")
            
            # Try to handle overlays
            self.handle_overlays()
            
            try:
                # Try clicking again after handling overlays
                element.click()
                return True
            except Exception as second_error:
                logging.warning(f"Click after overlay handling failed: {str(second_error)}")
                
                try:
                    # Try JavaScript click as fallback
                    self.driver.execute_script("arguments[0].click();", element)
                    logging.info("Successfully clicked using JavaScript")
                    return True
                except Exception as js_error:
                    logging.error(f"JavaScript click failed: {str(js_error)}")
                    
                    try:
                        # Try scrolling to element and clicking
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(1)
                        self.driver.execute_script("arguments[0].click();", element)
                        logging.info("Successfully clicked after scrolling")
                        return True
                    except Exception as scroll_error:
                        logging.error(f"Scroll and click failed: {str(scroll_error)}")
                        return False

    def make_turn(self, answer):
        try:
            # Handle different types of answers based on game stage
            if self.game_stage == "guess":
                # Convert 1/0 to Yes/No for guess responses
                if answer == "1" or answer.lower() == "yes":
                    answer = "Yes"
                elif answer == "0" or answer.lower() == "no":
                    answer = "No"
                
                valid_guess_answers = ["Yes", "No"]
                if answer not in valid_guess_answers:
                    return {"error": f"For character guess, use: Yes, No, 1, or 0"}
                
                # Click the appropriate guess button
                if answer == "Yes":
                    button_id = "a_propose_yes"
                else:
                    button_id = "a_propose_no"
                
                try:
                    button = WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located((By.ID, button_id))
                    )
                    
                    logging.info(f"Clicking guess button: {answer}")
                    if not self.safe_click(button):
                        return {"error": f"Could not click guess button for: {answer}"}
                    
                    # If we clicked "No", we need to handle the continue dialog
                    if answer == "No":
                        time.sleep(2)  # Wait for continue dialog to appear
                        
                        # Look for continue buttons and automatically click "Yes" to continue
                        continue_selectors = [
                            "a_continue_yes",
                            "a_continue_no"  # In case the structure is different
                        ]
                        
                        continue_clicked = False
                        for continue_id in continue_selectors:
                            try:
                                continue_button = WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located((By.ID, continue_id))
                                )
                                
                                if continue_button.is_displayed():
                                    logging.info(f"Auto-clicking continue button: {continue_id}")
                                    if self.safe_click(continue_button):
                                        continue_clicked = True
                                        break
                            except TimeoutException:
                                continue
                        
                        if not continue_clicked:
                            logging.warning("Could not find or click continue button after 'No' guess")
                    
                    time.sleep(3)  # Wait for page transition

                finally:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
            else:
                # Normal question answering
                valid_answers = ["Yes", "No", "I don't know", "Probably", "Probably not"]
                
                if answer not in valid_answers:
                    return {"error": f"Invalid answer. Use one of: {', '.join(valid_answers)}"}
                
                # Map answers to the actual button IDs from the HTML
                answer_id_map = {
                    "Yes": "a_yes",
                    "No": "a_no", 
                    "I don't know": "a_dont_know",
                    "Probably": "a_probably",
                    "Probably not": "a_probaly_not"  # Note: typo in original HTML "probaly_not"
                }
                
                button_id = answer_id_map[answer]
                button = WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.ID, button_id))
                )
                
                logging.info(f"Found button for answer: {answer}")
                
                # Use safe click method
                if not self.safe_click(button):
                    return {"error": f"Could not click button for answer: {answer}"}
                
                logging.info(f"Successfully clicked button for answer: {answer}")
                time.sleep(3)  # Wait for page transition
            
            # Get the updated game state
            self.current_question = self.get_current_question()
            
            return {
                "stage": self.game_stage,
                "content": self.current_question
            }
        except Exception as e:
            logging.error(f"Error in make_turn: {e.__class__.__name__}: {str(e)}")
            try:
                logging.error(f"Page HTML omitted")  # Limit output
            except Exception as page_err:
                logging.error(f"Could not retrieve page source during error: {str(page_err)}")
            return {"error": f"{e.__class__.__name__}: {str(e)}"}

    def close(self):
        self.driver.quit()

class AnswerModel(BaseModel):
    answer: str

class GuessAnswerModel(BaseModel):
    answer: str  # Should be "1"/"0" or "Yes"/"No"

@app.post("/start")
def start_game(theme: str = Query("1", description="Game theme: 1=Characters, 2=Objects, 14=Animals")):
    game_id = str(uuid.uuid4())
    try:
        game = AkinatorGame(theme)
        games[game_id] = game
        return JSONResponse(content={
            "game_id": game_id,
            "content": game.current_question,
            "stage": game.game_stage
        })
    except Exception as e:
        logging.error(f"API error in start_game: {e.__class__.__name__}: {str(e)}")
        return JSONResponse(
            status_code=500, 
            content={"error": f"Failed to start game: {e.__class__.__name__}: {str(e)}"}
        )

@app.post("/turn/{game_id}")
def turn(game_id: str, answer_data: AnswerModel):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = games[game_id]
    response = game.make_turn(answer_data.answer)
    return JSONResponse(content=response)

@app.post("/end/{game_id}")
def end_game(game_id: str):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = games.pop(game_id)
    game.close()
    return JSONResponse(content={"detail": "Game ended"})

# List all active games
@app.get("/games")
def list_games():
    return JSONResponse(content={
        "active_games": [
            {"game_id": gid, "stage": g.game_stage} for gid, g in games.items()
        ],
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app="app:app", host="127.0.0.1", port=8080, reload=True)
