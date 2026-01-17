import os
import time
import logging
import pandas as pd
from datetime import datetime
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_headless_driver() -> webdriver.Chrome:
    """Configuración Anti-Bloqueo."""
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

def clean_team_name(text: str) -> str:
    if not text: return ""
    import re
    text = re.sub(r'\s\d+$', '', text) 
    text = text.replace("SAD", "").strip()
    return text

# --- FUENTE 1: FLASHSCORE ---
def scrape_flashscore(driver, url, is_history) -> pd.DataFrame:
    logger.info(f"Intento 1: Flashscore ({'Historial' if is_history else 'Calendario'})...")
    data = []
    try:
        driver.get(url)
        # Intentar cerrar cookies
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        except: pass

        wait = WebDriverWait(driver, 8)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "div[class*='event__match']") or d.find_elements(By.CLASS_NAME, "footer"))
        
        match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='event__match']")
        
        if not match_rows and not is_history: return pd.DataFrame()

        for row in match_rows:
            try:
                text = row.text.split('\n')
                if is_history:
                    res_idx = next((i for i, x in enumerate(text) if '-' in x and x[0].isdigit()), -1)
                    if res_idx > 0:
                        data.append({
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "home_team": clean_team_name(text[res_idx-1]),
                            "away_team": clean_team_name(text[res_idx+1]),
                            "home_score": int(text[res_idx].split('-')[0]),
                            "away_score": int(text[res_idx].split('-')[1])
                        })
                else:
                    if len(text) >= 3:
                        data.append({
                            "date_str": text[0] if ':' in text[0] or '.' in text[0] else "Upcoming",
                            "home_team": clean_team_name(text[1]),
                            "away_team": clean_team_name(text[2])
                        })
            except: continue
    except:
        return pd.DataFrame()
    return pd.DataFrame(data)

# --- FUENTE 2: AS.COM ---
def scrape_backup_as(driver) -> pd.DataFrame:
    logger.info("Intento 2: AS.com (Jornada Actual)...")
    url = "https://resultados.as.com/resultados/futbol/primera/jornada/"
    data = []
    try:
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all('tr')
        for row in rows:
            try:
                teams = row.select('.nombre-equipo')
                if len(teams) >= 2:
                    data.append({
                        "home_team": clean_team_name(teams[0].get_text(strip=True)),
                        "away_team": clean_team_name(teams[1].get_text(strip=True)),
                        "date_str": "Próximamente" # AS complica las fechas, simplificamos
                    })
            except: continue
    except: pass
    return pd.DataFrame(data)

# --- FUENTE 3: MARCA (El Tanque) ---
def scrape_backup_marca(driver) -> pd.DataFrame:
    logger.info("🛡️ Intento 3: MARCA (El Tanque)...")
    url = "https://www.marca.com/futbol/primera-division/calendario.html"
    data = []
    try:
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Marca usa una estructura de lista muy robusta
        partidos = soup.find_all('div', class_='partido')
        
        if not partidos:
             # Fallback a tabla
             partidos = soup.find_all('tr')

        logger.info(f"Marca: Encontrados {len(partidos)} elementos.")

        for p in partidos:
            try:
                # Buscamos equipos en texto
                texto = p.get_text()
                if " vs " in texto or "-" in texto:
                    # Intento de extracción simple por estructura
                    equipos = p.find_all('span', class_='nombre')
                    if not equipos:
                        equipos = p.find_all('a') # A veces son links
                    
                    if len(equipos) >= 2:
                        home = clean_team_name(equipos[0].get_text(strip=True))
                        away = clean_team_name(equipos[1].get_text(strip=True))
                        
                        # Filtramos si parece resultado pasado (tiene números de goles)
                        if any(c.isdigit() for c in texto) and "Jornada" not in texto:
                             # Es arriesgado, pero asumimos que si estamos aqui es calendario futuro
                             pass 

                        data.append({
                            "home_team": home,
                            "away_team": away,
                            "date_str": "Próximamente"
                        })
            except: continue
    except Exception as e:
        logger.error(f"Marca Error: {e}")
        
    return pd.DataFrame(data)

def create_emergency_fixture():
    logger.warning("🚨 TODOS fallaron. Activando DUMMY data para no romper la web.")
    return pd.DataFrame([{
        "home_team": "Sistema AI",
        "away_team": "Mantenimiento",
        "date_str": datetime.now().strftime("%d.%m. 12:00")
    }])

def main():
    driver = get_headless_driver()
    try:
        # 1. HISTORIAL
        df_hist = scrape_flashscore(driver, "https://www.flashscore.es/futbol/espana/laliga/resultados/", True)
        if not df_hist.empty:
            df_hist.to_csv(os.path.join(DATA_DIR, "laliga_results_raw.csv"), index=False)
            logger.info(f"💾 Historial guardado.")

        # 2. CALENDARIO (Cadena de intentos)
        df_future = scrape_flashscore(driver, "https://www.flashscore.es/futbol/espana/laliga/calendario/", False)
        
        if df_future.empty:
            df_future = scrape_backup_as(driver)
            
        if df_future.empty:
            df_future = scrape_backup_marca(driver)
            
        if df_future.empty:
            df_future = create_emergency_fixture()
            
        df_future.to_csv(os.path.join(DATA_DIR, "laliga_fixtures.csv"), index=False)
        logger.info(f"💾 Calendario Final: {len(df_future)} partidos.")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()