import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 1. Configuración de URLs y Google Sheets
URL = "https://www.mi-television.com/programacion.php"
SHEET_NAME = "japn epg"  # <-- Cambia esto por el nombre EXACTO de tu archivo en Google Drive
WORKSHEET_NAME = "MITV"         # <-- Nombre de la pestaña dentro del sheet

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def obtener_programacion():
    print(f"Obteniendo programación desde {URL}...")
    response = requests.get(URL, headers=HEADERS)
    
    if response.status_code != 200:
        raise Exception(f"Error al acceder a la web: Código {response.status_code}")
        
    soup = BeautifulSoup(response.content, "html.parser")
    programas = []
    
    # Selectores específicos para la estructura de mi-television.com
    # Busca las filas/bloques donde se listan las emisiones
    elementos = soup.select(".listing .program, .broadcast, .row-program, .program, article, tr")

    for elem in elementos:
        # Extrae la hora
        hora_elem = elem.select_one(".time, .hora, time, .date")
        # Extrae el título del programa
        titulo_elem = elem.select_one(".title, .nombre, h3, h4, .program-name, a.title")
        # Extrae la descripción o categoría (opcional)
        desc_elem = elem.select_one(".category, .desc, .sub-title, p")
        
        if hora_elem and titulo_elem:
            hora = hora_elem.get_text(strip=True)
            titulo = titulo_elem.get_text(strip=True)
            descripcion = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Evita duplicados agregando solo si hay texto válido
            if hora and titulo:
                programas.append({
                    "Hora": hora,
                    "Programa": titulo,
                    "Detalles": descripcion
                })

    # Si el selector genérico falla por renderizado especial, intentamos extraer mediante bloques
    if not programas:
        for div in soup.find_all(['div', 'li'], class_=lambda c: c and 'program' in c.lower()):
            textos = [t.strip() for t in div.stripped_strings if t.strip()]
            if len(textos) >= 2:
                programas.append({
                    "Hora": textos[0],
                    "Programa": textos[1],
                    "Detalles": " ".join(textos[2:]) if len(textos) > 2 else ""
                })

    print(f"Se encontraron {len(programas)} programas.")
    return programas

def actualizar_google_sheets(datos):
    gcp_key_raw = os.getenv("GCP_SA_KEY")
    if not gcp_key_raw:
        raise ValueError("No se encontró GCP_SA_KEY en los Secrets de GitHub.")

    print("GCP_SA_KEY detectado. Guardando/Actualizando en matriz de Google Sheets...")

    # Cargar credenciales desde el Secret JSON
    creds_dict = json.loads(gcp_key_raw)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    # Abrir el documento de Google Sheets
    sheet = client.open(SHEET_NAME)
    
    # Seleccionar o crear la pestaña
    try:
        worksheet = sheet.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=WORKSHEET_NAME, rows="200", cols="5")

    # Convertir los datos a DataFrame
    df = pd.DataFrame(datos)

    # Limpiar y volcar la nueva información
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    print("¡Proceso completado con éxito! Datos guardados en Google Sheets.")

def main():
    try:
        programacion = obtener_programacion()
        if programacion:
            actualizar_google_sheets(programacion)
        else:
            print("No se encontraron elementos con los selectores aplicados.")
    except Exception as e:
        print(f"Error procesando la guía: {e}")
        exit(1)

if __name__ == "__main__":
    main()
