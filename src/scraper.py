# robot que navega a la web de flashcore y descarga resultados historicos
import os
import time
import logging
import pandas as pd
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# configuro el logging con nivel info para ver los mensajes que importo
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# creo el logger
logger = logging.getLogger(__name__)

# configuro el directorio para guardar los datos
DATA_DIR = "data"
# me aseguro que exista la carpeta
os.makedirs(DATA_DIR, exist_ok=True)

# funcion que abre un navegador Chrome sin ventana gráfica para que el programa pueda navegar por internet automáticamente
def get_headless_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

# funcion que limpia los nombres de los equipos (quita espacios extra o sufijos como "SAD")
def clean_team_name(text: str) -> str:
    if not text: return ""
    import re
    text = re.sub(r'\s\d+$', '', text) 
    text = text.replace("SAD", "").strip()
    return text

# f. que entra a la web, busca la tabla de resultados, extrae quién jugó contra quién y cuánto quedaron, y lo guarda en una lista.
def scrape_historical_results(driver) -> pd.DataFrame:
    """Solo descarga resultados pasados para entrenamiento."""
    url = "https://www.flashscore.es/futbol/espana/laliga/resultados/"
    logger.info(f"Scraping Historial: {url}")
    data = []
    try:
        driver.get(url)
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        except: pass

        wait = WebDriverWait(driver, 10)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "div[class*='event__match']") or d.find_elements(By.CLASS_NAME, "footer"))
        
        match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='event__match']")
        
        for row in match_rows:
            try:
                text = row.text.split('\n')
                # Buscamos formato de resultado: Local - Goles - Visitante
                res_idx = next((i for i, x in enumerate(text) if '-' in x and x[0].isdigit()), -1)
                if res_idx > 0:
                    data.append({
                        "date": datetime.now().strftime("%Y-%m-%d"), # Flashscore oculta fecha exacta en la lista, uso fetch date como remplazo
                        "home_team": clean_team_name(text[res_idx-1]),
                        "away_team": clean_team_name(text[res_idx+1]),
                        "home_score": int(text[res_idx].split('-')[0]),
                        "away_score": int(text[res_idx].split('-')[1])
                    })
            except: continue
    except Exception as e:
        logger.error(f"Error scraping historial: {e}")
        return pd.DataFrame()
        
    return pd.DataFrame(data)

# f. que ejecuta todo lo anterior y guarda los resultados históricos en laliga_results_raw.csv
def main():
    driver = get_headless_driver()
    try:
        df_hist = scrape_historical_results(driver)
        if not df_hist.empty:
            df_hist.to_csv(os.path.join(DATA_DIR, "laliga_results_raw.csv"), index=False)
            logger.info(f"Historial actualizado: {len(df_hist)} registros.")
        else:
            logger.warning("⚠️ El scraper terminó pero NO encontró ningún partido (0 registros).")
    finally:
        driver.quit()

# corro el main si este script es ejecutado directamente
if __name__ == "__main__":
    main()