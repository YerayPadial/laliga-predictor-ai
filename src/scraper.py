import os
import time
import logging
import pandas as pd
from datetime import datetime
from typing import Optional, List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_headless_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=chrome_options)

def clean_team_name(text: str) -> str:
    """Elimina residuos como ' 2', '(Match)', etc."""
    if not text: return ""
    # Si el nombre termina en dígito (ej: 'Real Oviedo 2'), lo quitamos
    import re
    text = re.sub(r'\s\d+$', '', text) 
    return text.strip()

def safe_extract_text(row, selectors: List[str]) -> Optional[str]:
    for selector in selectors:
        try:
            elements = row.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                text = elements[0].text.strip()
                return clean_team_name(text)
        except:
            continue
    return None

def scrape_data(driver: webdriver.Chrome, url: str, is_history: bool) -> pd.DataFrame:
    """Función genérica para scrapear tanto Resultados (history) como Calendario (upcoming)."""
    logger.info(f"Scraping ({'History' if is_history else 'Upcoming'}): {url}")
    data = []
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".sportName, .leagues--static")))
        time.sleep(3) 

        match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='event__match']")
        if not match_rows:
            match_rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'event__match')]")

        # Selectores
        home_sels = [".event__participant--home", ".event__homeParticipant", ".wcl-participant_..."] 
        away_sels = [".event__participant--away", ".event__awayParticipant", ".wcl-participant_..."]
        # Scores (solo para historial)
        score_home_sels = [".event__score--home", ".event__part--home"]
        score_away_sels = [".event__score--away", ".event__part--away"]
        # Hora (solo para calendario)
        time_sels = [".event__time"]

        for row in match_rows:
            try:
                home = safe_extract_text(row, home_sels)
                away = safe_extract_text(row, away_sels)
                
                if not home or not away: continue

                match_info = {
                    "home_team": home,
                    "away_team": away,
                }

                if is_history:
                    # Lógica Historial (Resultados)
                    s_home = safe_extract_text(row, score_home_sels)
                    s_away = safe_extract_text(row, score_away_sels)
                    if s_home and s_away and s_home.isdigit() and s_away.isdigit():
                        match_info["date"] = datetime.now().strftime("%Y-%m-%d") # Flashscore oculta fechas exactas en lista simple
                        match_info["home_score"] = int(s_home)
                        match_info["away_score"] = int(s_away)
                        data.append(match_info)
                else:
                    # Lógica Futuro (Calendario)
                    match_time = safe_extract_text(row, time_sels) # Ej: "18.01. 14:00"
                    # Procesar fecha real si es posible, sino usar today
                    match_info["date_str"] = match_time if match_time else "Upcoming"
                    data.append(match_info)

            except Exception:
                continue

    except Exception as e:
        logger.error(f"Error en scraping: {e}")

    return pd.DataFrame(data)

def main():
    driver = get_headless_driver()
    
    # 1. Scraping Histórico (Para entrenar)
    df_hist = scrape_data(driver, "https://www.flashscore.es/futbol/espana/laliga/resultados/", is_history=True)
    if not df_hist.empty:
        df_hist.to_csv(os.path.join(DATA_DIR, "laliga_results_raw.csv"), index=False)
        logger.info(f"✅ Histórico guardado: {len(df_hist)} partidos.")

    # 2. Scraping Futuro (Para la Quiniela)
    df_future = scrape_data(driver, "https://www.flashscore.es/futbol/espana/laliga/calendario/", is_history=False)
    if not df_future.empty:
        df_future.to_csv(os.path.join(DATA_DIR, "laliga_fixtures.csv"), index=False)
        logger.info(f"✅ Calendario guardado: {len(df_future)} partidos próximos.")
    
    driver.quit()

if __name__ == "__main__":
    main()