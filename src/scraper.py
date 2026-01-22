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
    url = "https://www.flashscore.es/futbol/espana/laliga/resultados/"
    logger.info(f"Scraping Historial: {url}")
    data = []
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)

        # 1. Intentar cerrar cookies
        try:
            cookie_btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
            cookie_btn.click()
            logger.info("Cookies aceptadas.")
            time.sleep(2)
        except: 
            logger.info("No se encontró banner de cookies.")

        # 2. Esperar a los partidos
        try:
            logger.info("Esperando a que carguen los partidos...")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.event__match")))
        except Exception:
            logger.error("No cargaron los partidos.")
            return pd.DataFrame()
        
        # 3. Extraer datos
        match_rows = driver.find_elements(By.CSS_SELECTOR, "div.event__match")
        logger.info(f"Se encontraron {len(match_rows)} elementos de partido. Procesando...")

        for row in match_rows:
            try:
                raw_text = row.get_attribute('innerText')
                # Limpiamos líneas vacías y espacios
                text_lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
                
                # LA ESTRUCTURA RECIBIDA ES:
                # [0] Fecha, [1] Local, [2] Visitante, [3] Gol Local, [4] Gol Visitante
                
                # Verificamos que tenga al menos 5 líneas y que las líneas 3 y 4 sean números
                if len(text_lines) >= 5:
                    score_home_str = text_lines[3]
                    score_away_str = text_lines[4]
                    
                    # Verificamos si son dígitos (para evitar leer partidos suspendidos o textos raros)
                    if score_home_str.isdigit() and score_away_str.isdigit():
                        data.append({
                            "date": datetime.now().strftime("%Y-%m-%d"), 
                            "home_team": clean_team_name(text_lines[1]),
                            "away_team": clean_team_name(text_lines[2]),
                            "home_score": int(score_home_str),
                            "away_score": int(score_away_str)
                        })
            except Exception: 
                continue
            
    except Exception as e:
        logger.error(f"Error general scraping: {e}")
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
            logger.warning("El scraper terminó pero NO encontró ningún partido (0 registros).")
            if os.path.exists("debug_screenshot.png"):
                logger.info("Hay una captura de pantalla del error disponible en el entorno.")
    finally:
        driver.quit()

# corro el main si este script es ejecutado directamente
if __name__ == "__main__":
    main()