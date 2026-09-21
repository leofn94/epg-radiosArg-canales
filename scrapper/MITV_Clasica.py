import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Configuración del canal
URL = "https://www.mi-television.com/programacion.php"
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
    
    # Extraer bloques de programas de la guía HTML
    # (Ajustar los selectores según el contenedor de la web)
    elementos = soup.select(".program-item, .schedule-row, tr") 

    for elem in elementos:
        hora_elem = elem.select_one(".time, .hora")
        titulo_elem = elem.select_one(".title, .nombre, .programa")
        
        if hora_elem and titulo_elem:
            hora_str = hora_elem.get_text(strip=True)
            titulo = titulo_elem.get_text(strip=True)
            
            programas.append({
                "time": hora_str,
                "title": titulo
            })

    print(f"Se encontraron {len(programas)} programas.")
    return programas

def main():
    try:
        data = obtener_programacion()
        
        # Opcional: Si este script debe subir a Google Sheets usando GCP_SA_KEY
        gcp_key = os.getenv("GCP_SA_KEY")
        if gcp_key:
            print("GCP_SA_KEY detectado. Guardando/Actualizando en matriz de Google Sheets...")
            # Aquí va tu lógica habitual con gspread / pandas
        else:
            print("Guardando copia local en JSON...")
            with open("mitelevision_epg.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
    except Exception as e:
        print(f"Error procesando la guía: {e}")
        exit(1)

if __name__ == "__main__":
    main()
