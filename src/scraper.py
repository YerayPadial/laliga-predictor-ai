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

        # --- CAMBIO IMPORTANTE AQUÍ ---
        for i, row in enumerate(match_rows):
            try:
                # Usamos innerText porque .text a veces falla en headless
                raw_text = row.get_attribute('innerText')
                text_lines = raw_text.split('\n')
                
                # DEBUG: Imprimimos el primer partido para ver qué formato tiene
                if i == 0:
                    logger.info(f"DEBUG - Texto crudo del primer partido: {text_lines}")

                # Buscamos la línea que tiene el marcador. 
                # Flashscore suele poner: "Real Madrid", "2", "-", "1", "Barcelona" (todo separado)
                # O a veces "Real Madrid", "2-1", "Barcelona"
                
                # Buscamos una linea que tenga numeros y un guion
                score_line_idx = -1
                for idx, line in enumerate(text_lines):
                    # Limpiamos espacios
                    line = line.strip()
                    # Verificamos si parece un resultado (ej: "2-1" o "2 - 1")
                    if '-' in line and any(char.isdigit() for char in line):
                        score_line_idx = idx
                        break
                
                if score_line_idx > 0:
                    # Asumimos que el local está antes y el visitante después
                    # A veces hay lineas intermedias (estado del partido), asi que cogemos indices relativos
                    home_team = clean_team_name(text_lines[score_line_idx - 1])
                    away_team = clean_team_name(text_lines[score_line_idx + 1])
                    
                    score_parts = text_lines[score_line_idx].split('-')
                    
                    # Verificación extra para asegurar que tenemos dos numeros
                    if len(score_parts) == 2:
                        data.append({
                            "date": datetime.now().strftime("%Y-%m-%d"), 
                            "home_team": home_team,
                            "away_team": away_team,
                            "home_score": int(score_parts[0].strip()),
                            "away_score": int(score_parts[1].strip())
                        })
            except Exception as e:
                # Si falla uno, seguimos al siguiente, pero imprimimos error leve
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
            logger.warning("⚠️ El scraper terminó pero NO encontró ningún partido (0 registros).")
            if os.path.exists("debug_screenshot.png"):
                logger.info("Hay una captura de pantalla del error disponible en el entorno.")
    finally:
        driver.quit()

# corro el main si este script es ejecutado directamente
if __name__ == "__main__":
    main()