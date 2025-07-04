from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional, List 
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchWindowException
import time
import os
import fitz  # PyMuPDF

app = FastAPI()

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/tmp/selenium_downloads")

# --- Modelos Pydantic ---
class Credenciais(BaseModel):
    email: EmailStr
    senha: str

class RespostaTextoPdfCompleto(BaseModel):
    data_referencia: Optional[str] = None
    texto_do_pdf_completo: Optional[str] = None
    message: str = "Texto completo do PDF extraído com sucesso."

# --- Funções Helper ---
def excluir_arquivo_processado(path: str, delay: int = 5):
    try:
        time.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
            print(f"[LOG API - BackgroundTask] Arquivo PDF deletado: {path}")
        else:
            print(f"[LOG API - BackgroundTask] Arquivo PDF não encontrado para deletar: {path}")
    except Exception as e:
        print(f"[ERRO API - BackgroundTask] Falha ao deletar PDF {path}: {e}")

def wait_for_download_to_complete(download_dir: str, timeout: int = 120) -> str:
    print(f"[LOG API] Iniciando espera por download em '{download_dir}' (timeout: {timeout}s)")
    start_time = time.time()
    while time.time() - start_time < timeout:
        crdownload_files = [f for f in os.listdir(download_dir) if f.endswith('.crdownload')]
        pdf_files = sorted(
            [f for f in os.listdir(download_dir) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(download_dir, f))],
            key=lambda f_name: os.path.getmtime(os.path.join(download_dir, f_name)),
            reverse=True
        )
        if not crdownload_files and pdf_files:
            latest_pdf = os.path.join(download_dir, pdf_files[0])
            if (time.time() - os.path.getmtime(latest_pdf) < (timeout + 10)) and os.path.getsize(latest_pdf) > 100: # PDF muito pequeno pode ser inválido
                print(f"[LOG API] Download de PDF completo: {latest_pdf}, Tamanho: {os.path.getsize(latest_pdf)}")
                return latest_pdf
            else:
                print(f"[LOG API] PDF detectado ({pdf_files[0]}) mas pode ser antigo/pequeno demais. Aguardando...")
        elif crdownload_files:
            print(f"[LOG API] Download em progresso: {crdownload_files[0]}...")
        time.sleep(3)
    final_files_in_dir = os.listdir(download_dir)
    raise TimeoutException(f"Timeout esperando PDF em '{download_dir}'. PDFs: {[f for f in final_files_in_dir if f.lower().endswith('.pdf')]}. Todos: {final_files_in_dir}")

# --- Endpoint Principal ---
@app.post("/extrair-texto-pdf-completo", response_model=RespostaTextoPdfCompleto)
async def extrair_texto_pdf_completo_endpoint(credenciais: Credenciais, background_tasks: BackgroundTasks):
    print("[LOG API] Iniciando processo: Extração de Texto Completo do PDF")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    prefs = {
        "plugins.always_open_pdf_externally": True,
        "download.prompt_for_download": False,
        "download.default_directory": DOWNLOAD_DIR,
        "directory_upgrade": True,
        "safeBrowse.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--disable-notifications")

    driver = None
    downloaded_pdf_path = None
    original_window = None

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        print(f"[LOG API] Diretório de download {DOWNLOAD_DIR} criado pelo script.")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, 45)
        driver.get("https://www.eneldistribuicao.com.br/ce/Corporativo.aspx")
        original_window = driver.current_window_handle
        
        print("[LOG API] Preenchendo credenciais...")
        wait.until(EC.presence_of_element_located((By.ID, "WEBDOOR_headercorporativo_UserName"))).send_keys(credenciais.email)
        driver.find_element(By.ID, "WEBDOOR_headercorporativo_Password").send_keys(credenciais.senha)
        driver.find_element(By.ID, "WEBDOOR_headercorporativo_Ok").click()

        print("[LOG API] Aguardando login...")
        wait.until(EC.url_contains("DefaultGa.aspx"))
        print("[LOG API] Login bem-sucedido.")

        print("[LOG API] Aguardando link '2ª Via'")
        via_link_locator = (By.PARTIAL_LINK_TEXT, "2ª Via")
        try:
            link_element = wait.until(EC.presence_of_element_located(via_link_locator))
            driver.execute_script("arguments[0].scrollIntoView(true);", link_element)
            time.sleep(0.5)
            link_element = wait.until(EC.element_to_be_clickable(via_link_locator))
            driver.execute_script("arguments[0].click();", link_element)
            print("[LOG API] Link '2ª Via' clicado.")
            time.sleep(2)
            print("[LOG API] Navegando para Segunda Via.")
            driver.get("https://www.eneldistribuicao.com.br/agencia/SegundaViaGa.aspx")
            wait.until(EC.presence_of_element_located((By.ID, "CONTENT_gdHistoricoDeFaturamento")))
            print(f"[LOG API] Página de segunda via ('{driver.current_url}') carregada.")
        except Exception as e_2via:
            err_msg = f"Erro na etapa '2ª Via': {str(e_2via)}. URL: {driver.current_url if driver else 'N/A'}"
            print(f"[ERRO API] {err_msg}")
            if driver:
                try:
                    driver.save_screenshot("api_debug_2via_exception.png")
                    with open("api_debug_2via_exception.html", "w", encoding="utf-8") as f: f.write(driver.page_source)
                except Exception: pass
            raise HTTPException(status_code=500, detail=err_msg)

        print("[LOG API] Buscando data de referência (Selenium)...")
        xpath_data_referencia = "//table[@id='CONTENT_gdHistoricoDeFaturamento']/tbody/tr[2]/td[1]"
        data_referencia_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_data_referencia)))
        data_referencia_selenium = data_referencia_element.text.strip()
        print(f"[LOG API] Data de referência (Selenium): {data_referencia_selenium}")

        print("[LOG API] Selecionando conta e solicitando emissão (download direto)...")
        wait.until(EC.element_to_be_clickable((By.ID, "CONTENT_gdHistoricoDeFaturamento_chkSegundaVia_0"))).click()
        emitir_btn = wait.until(EC.element_to_be_clickable((By.ID, "CONTENT_btnEmitirSegundaVia")))
        emitir_btn.click()
        print("[LOG API] Botão 'Emitir Segunda Via' clicado.")
        
        print("[LOG API] Aguardando para download ser iniciado (15s)...")
        time.sleep(15) 
        downloaded_pdf_path = wait_for_download_to_complete(DOWNLOAD_DIR)
        
        print(f"[LOG API] Lendo PDF para extração de texto completo: {downloaded_pdf_path}")
        pdf_bytes = b''
        with open(downloaded_pdf_path, "rb") as f_pdf_texto:
            pdf_bytes = f_pdf_texto.read()
        
        if not pdf_bytes:
            # Se o arquivo foi baixado mas está vazio, ainda assim agendamos a exclusão
            background_tasks.add_task(excluir_arquivo_processado, downloaded_pdf_path)
            raise HTTPException(status_code=500, detail="PDF baixado está vazio ou não pôde ser lido.")

        texto_do_pdf_completo = ""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                # Extrai o texto da página. 'sort=True' tenta manter uma ordem de leitura lógica.
                # Você pode experimentar com outras opções de get_text() se necessário,
                # como page.get_text("text", flags=fitz.TEXTFLAGS_LAYOUT) para tentar preservar mais o layout.
                texto_do_pdf_completo += page.get_text("text", sort=True)
                if page_num < doc.page_count - 1: # Adiciona um separador de página claro
                    texto_do_pdf_completo += f"\n\n--- PÁGINA {page_num + 1} FINALIZADA | PRÓXIMA PÁGINA {page_num + 2} ---\n\n"
            doc.close()
            if not texto_do_pdf_completo.strip():
                 raise ValueError("Nenhum texto foi extraído do PDF.")
            print(f"[LOG API] Texto completo extraído. Total de caracteres: {len(texto_do_pdf_completo)}")
        except Exception as e_text_extract:
            print(f"[ERRO API] Falha ao extrair texto do PDF: {e_text_extract}")
            background_tasks.add_task(excluir_arquivo_processado, downloaded_pdf_path)
            raise HTTPException(status_code=500, detail=f"Erro ao extrair texto do PDF: {e_text_extract}")
        
        # Agendar a exclusão do arquivo PDF baixado
        background_tasks.add_task(excluir_arquivo_processado, downloaded_pdf_path)
        
        return RespostaTextoPdfCompleto(
            data_referencia=data_referencia_selenium,
            texto_do_pdf_completo=texto_do_pdf_completo
        )

    except TimeoutException as e_timeout:
        err_msg_timeout = f"Timeout na API: {str(e_timeout)}"
        print(f"[ERRO API] {err_msg_timeout}")
        if driver: 
            try: driver.save_screenshot("api_debug_timeout_exception.png")
            except Exception: pass
        if downloaded_pdf_path and os.path.exists(downloaded_pdf_path):
            background_tasks.add_task(excluir_arquivo_processado, downloaded_pdf_path)
        raise HTTPException(status_code=504, detail=err_msg_timeout)
    except HTTPException:
        # Se uma HTTPException já foi levantada, e o PDF foi baixado, agende sua exclusão
        if downloaded_pdf_path and os.path.exists(downloaded_pdf_path) and 'background_tasks' in locals():
            background_tasks.add_task(excluir_arquivo_processado, downloaded_pdf_path)
        raise
    except Exception as e:
        err_msg_geral = f"Erro geral na API: {str(e)}"
        print(f"[ERRO API] {err_msg_geral}")
        if driver:
            try: 
                driver.save_screenshot("api_debug_geral_exception.png")
                with open("api_debug_geral_exception.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except Exception as e_debug_save_api: 
                print(f"[ERRO API] Não foi possível salvar debug em erro geral: {e_debug_save_api}")
        if downloaded_pdf_path and os.path.exists(downloaded_pdf_path) and 'background_tasks' in locals():
            background_tasks.add_task(excluir_arquivo_processado, downloaded_pdf_path)
        raise HTTPException(status_code=500, detail=err_msg_geral)
    finally:
        if driver:
            try:
                if 'original_window' in locals() and original_window: 
                    current_handles = driver.window_handles
                    for handle in current_handles:
                        if handle != original_window:
                            try:
                                driver.switch_to.window(handle)
                                driver.close()
                            except NoSuchWindowException:
                                print(f"[AVISO API] Janela {handle} já estava fechada ao tentar limpar no finally.")
                    if original_window in driver.window_handles: 
                         driver.switch_to.window(original_window)
            except Exception as e_cleanup_wins:
                print(f"[AVISO API] Problema ao limpar janelas no finally: {e_cleanup_wins}")
            finally:
                 driver.quit()
            print("[LOG API] Navegador encerrado.")
        
        # Se o script falhar após o download mas antes de agendar a exclusão na task,
        # este é um último esforço, mas a task é o principal.
        if downloaded_pdf_path and os.path.exists(downloaded_pdf_path):
            print(f"[INFO API] Arquivo {downloaded_pdf_path} deveria ser excluído pela BackgroundTask.")
