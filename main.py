from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchWindowException, WebDriverException, NoSuchElementException
import time
import os
import fitz
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/tmp/selenium_downloads")

# --- Modelos Pydantic ---
class Credenciais(BaseModel):
    email: EmailStr
    senha: str
    numero_cliente: str

class RespostaTextoPdfCompleto(BaseModel):
    data_referencia: Optional[str] = None
    texto_do_pdf_completo: Optional[str] = None
    numero_cliente_selecionado: Optional[str] = None
    message: str = "Texto completo do PDF extraído com sucesso."

# --- Função para Selecionar Cliente ---
def selecionar_cliente_por_numero(driver: webdriver.Chrome, numero_cliente: str) -> bool:
    """Seleciona cliente específico baseado no número"""
    try:
        wait = WebDriverWait(driver, 30)
        
        # Aguardar a tabela carregar
        wait.until(EC.presence_of_element_located((By.ID, "CONTENT_gdEscolherClienteDoAgrupamento")))
        logger.info(f"Procurando cliente: {numero_cliente}")
        
        # XPath para encontrar a checkbox do cliente específico
        xpath_checkbox = f"//table[@id='CONTENT_gdEscolherClienteDoAgrupamento']//tr[td[text()='{numero_cliente}']]//input[@type='checkbox']"
        
        try:
            checkbox = driver.find_element(By.XPATH, xpath_checkbox)
            if not checkbox.is_selected():
                driver.execute_script("arguments[0].click();", checkbox)
                logger.info(f"Cliente {numero_cliente} selecionado")
            return True
        except NoSuchElementException:
            # Fallback: buscar por iteração
            linhas = driver.find_elements(By.XPATH, "//table[@id='CONTENT_gdEscolherClienteDoAgrupamento']//tr[position()>1]")
            
            for linha in linhas:
                try:
                    celulas = linha.find_elements(By.TAG_NAME, "td")
                    if celulas and celulas[0].text.strip() == numero_cliente:
                        checkbox = linha.find_element(By.XPATH, ".//input[@type='checkbox']")
                        if not checkbox.is_selected():
                            driver.execute_script("arguments[0].click();", checkbox)
                            logger.info(f"Cliente {numero_cliente} selecionado via iteração")
                        return True
                except Exception:
                    continue
            
            logger.error(f"Cliente {numero_cliente} não encontrado")
            return False
            
    except Exception as e:
        logger.error(f"Erro ao selecionar cliente {numero_cliente}: {e}")
        return False

def obter_clientes_disponiveis(driver: webdriver.Chrome) -> list:
    """Lista todos os clientes disponíveis"""
    try:
        xpath_numeros = "//table[@id='CONTENT_gdEscolherClienteDoAgrupamento']//tr[position()>1]/td[1]"
        celulas_cliente = driver.find_elements(By.XPATH, xpath_numeros)
        clientes = [celula.text.strip() for celula in celulas_cliente if celula.text.strip()]
        return clientes
    except Exception as e:
        logger.error(f"Erro ao obter lista de clientes: {e}")
        return []

def verificar_necessidade_selecao_cliente(driver: webdriver.Chrome) -> bool:
    """Verifica se existe a tela de seleção de cliente"""
    try:
        driver.find_element(By.ID, "CONTENT_gdEscolherClienteDoAgrupamento")
        return True
    except NoSuchElementException:
        return False

# --- Funções Helper ---
def excluir_arquivo_processado(path: str, delay: int = 5):
    try:
        time.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Arquivo PDF deletado: {path}")
        else:
            logger.warning(f"Arquivo PDF não encontrado para deletar: {path}")
    except Exception as e:
        logger.error(f"Falha ao deletar PDF {path}: {e}")

def wait_for_download_to_complete(download_dir: str, timeout: int = 120) -> str:
    logger.info(f"Aguardando download em '{download_dir}' (timeout: {timeout}s)")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            crdownload_files = [f for f in os.listdir(download_dir) if f.endswith('.crdownload')]
            pdf_files = sorted(
                [f for f in os.listdir(download_dir) 
                 if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(download_dir, f))],
                key=lambda f_name: os.path.getmtime(os.path.join(download_dir, f_name)),
                reverse=True
            )
            
            if not crdownload_files and pdf_files:
                latest_pdf = os.path.join(download_dir, pdf_files[0])
                if (time.time() - os.path.getmtime(latest_pdf) < (timeout + 10)) and os.path.getsize(latest_pdf) > 100:
                    logger.info(f"Download completo: {latest_pdf}, Tamanho: {os.path.getsize(latest_pdf)}")
                    return latest_pdf
                else:
                    logger.info(f"PDF detectado ({pdf_files[0]}) mas pode ser antigo/pequeno demais. Aguardando...")
            elif crdownload_files:
                logger.info(f"Download em progresso: {crdownload_files[0]}...")
                
        except OSError as e:
            logger.error(f"Erro ao acessar diretório de download: {e}")
            
        time.sleep(3)
    
    try:
        final_files_in_dir = os.listdir(download_dir)
        pdf_files_final = [f for f in final_files_in_dir if f.lower().endswith('.pdf')]
        raise TimeoutException(f"Timeout esperando PDF em '{download_dir}'. PDFs encontrados: {pdf_files_final}")
    except OSError:
        raise TimeoutException(f"Timeout esperando PDF e erro ao acessar diretório '{download_dir}'")

def setup_chrome_driver(download_dir: str) -> webdriver.Chrome:
    """Configuração robusta do Chrome"""
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
    chrome_options.add_argument("--disable-notifications")
    
    prefs = {
        "plugins.always_open_pdf_externally": True,
        "download.prompt_for_download": False,
        "download.default_directory": download_dir,
        "directory_upgrade": True,
        "safeBrowse.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        return webdriver.Chrome(options=chrome_options)
    except WebDriverException as e:
        logger.error(f"Erro ao inicializar Chrome: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao inicializar navegador: {str(e)}")

def cleanup_browser(driver: webdriver.Chrome, original_window: Optional[str] = None):
    """Limpa recursos do navegador de forma segura"""
    if not driver:
        return
        
    try:
        if original_window:
            try:
                current_handles = driver.window_handles
                for handle in current_handles:
                    if handle != original_window:
                        try:
                            driver.switch_to.window(handle)
                            driver.close()
                        except NoSuchWindowException:
                            logger.warning(f"Janela {handle} já estava fechada")
                            
                if original_window in driver.window_handles:
                    driver.switch_to.window(original_window)
            except Exception as e:
                logger.warning(f"Problema ao limpar janelas: {e}")
    except Exception as e:
        logger.error(f"Erro durante cleanup das janelas: {e}")
    finally:
        try:
            driver.quit()
            logger.info("Navegador encerrado")
        except Exception as e:
            logger.error(f"Erro ao encerrar navegador: {e}")

# --- Endpoint Principal ---
@app.post("/extrair-texto-pdf-completo", response_model=RespostaTextoPdfCompleto)
async def extrair_texto_pdf_completo_endpoint(credenciais: Credenciais, background_tasks: BackgroundTasks):
    logger.info("Iniciando processo: Extração de Texto Completo do PDF")
    
    # Variáveis inicializadas para evitar referências não definidas
    driver = None
    downloaded_pdf_path = None
    original_window = None
    data_referencia_selenium = None
    numero_cliente_usado = None

    # Criar diretório de download se não existir
    try:
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            logger.info(f"Diretório de download {DOWNLOAD_DIR} criado")
        else:
            logger.info(f"Usando diretório de download: {DOWNLOAD_DIR}")
    except OSError as e:
        logger.error(f"Erro ao criar diretório de download: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar diretório de download: {str(e)}")

    try:
        # Inicializar driver
        driver = setup_chrome_driver(DOWNLOAD_DIR)
        wait = WebDriverWait(driver, 45)
        
        # Navegar e fazer login
        driver.get("https://www.eneldistribuicao.com.br/ce/Corporativo.aspx")
        original_window = driver.current_window_handle
        
        logger.info("Fazendo login...")
        try:
            username_field = wait.until(EC.presence_of_element_located((By.ID, "WEBDOOR_headercorporativo_UserName")))
            username_field.clear()
            username_field.send_keys(credenciais.email)
            
            password_field = driver.find_element(By.ID, "WEBDOOR_headercorporativo_Password")
            password_field.clear()
            password_field.send_keys(credenciais.senha)
            
            login_button = driver.find_element(By.ID, "WEBDOOR_headercorporativo_Ok")
            login_button.click()
        except Exception as e:
            logger.error(f"Erro no login: {e}")
            raise HTTPException(status_code=401, detail=f"Erro no login: {str(e)}")

        # Aguardar login
        logger.info("Aguardando login...")
        try:
            wait.until(EC.url_contains("DefaultGa.aspx"))
            logger.info("Login bem-sucedido")
        except TimeoutException:
            raise HTTPException(status_code=401, detail="Falha no login - credenciais inválidas ou timeout")

        # Verificar necessidade de seleção de cliente
        logger.info("Verificando necessidade de seleção de cliente...")
        
        if verificar_necessidade_selecao_cliente(driver):
            logger.info("Detectada tela de seleção de cliente")
            
            clientes_disponiveis = obter_clientes_disponiveis(driver)
            logger.info(f"Clientes disponíveis: {clientes_disponiveis}")
            
            # Selecionar o cliente fornecido
            if not selecionar_cliente_por_numero(driver, credenciais.numero_cliente):
                raise HTTPException(
                    status_code=404, 
                    detail=f"Cliente {credenciais.numero_cliente} não encontrado. Disponíveis: {clientes_disponiveis}"
                )
            numero_cliente_usado = credenciais.numero_cliente
            
            time.sleep(2)
        else:
            logger.info("Não há necessidade de seleção de cliente")
            numero_cliente_usado = credenciais.numero_cliente

        # Navegar para 2ª Via
        logger.info("Navegando para 2ª Via")
        try:
            via_link_locator = (By.PARTIAL_LINK_TEXT, "2ª Via")
            link_element = wait.until(EC.presence_of_element_located(via_link_locator))
            driver.execute_script("arguments[0].scrollIntoView(true);", link_element)
            time.sleep(0.5)
            
            link_element = wait.until(EC.element_to_be_clickable(via_link_locator))
            driver.execute_script("arguments[0].click();", link_element)
            logger.info("Link '2ª Via' clicado")
            
            time.sleep(2)
            driver.get("https://www.eneldistribuicao.com.br/agencia/SegundaViaGa.aspx")
            wait.until(EC.presence_of_element_located((By.ID, "CONTENT_gdHistoricoDeFaturamento")))
            logger.info("Página de segunda via carregada")
            
        except Exception as e:
            logger.error(f"Erro na navegação para 2ª Via: {e}")
            # Salvar debug se possível
            try:
                driver.save_screenshot("api_debug_2via_exception.png")
                with open("api_debug_2via_exception.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Erro na navegação para 2ª Via: {str(e)}")

        # Buscar data de referência
        logger.info("Buscando data de referência...")
        try:
            xpath_data_referencia = "//table[@id='CONTENT_gdHistoricoDeFaturamento']/tbody/tr[2]/td[1]"
            data_referencia_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_data_referencia)))
            data_referencia_selenium = data_referencia_element.text.strip()
            logger.info(f"Data de referência encontrada: {data_referencia_selenium}")
        except Exception as e:
            logger.warning(f"Erro ao buscar data de referência: {e}")
            data_referencia_selenium = None

        # Solicitar emissão do PDF
        logger.info("Selecionando conta e solicitando emissão...")
        try:
            checkbox = wait.until(EC.element_to_be_clickable((By.ID, "CONTENT_gdHistoricoDeFaturamento_chkSegundaVia_0")))
            checkbox.click()
            logger.info("Checkbox selecionada")
            
            emitir_btn = wait.until(EC.element_to_be_clickable((By.ID, "CONTENT_btnEmitirSegundaVia")))
            emitir_btn.click()
            logger.info("Botão 'Emitir Segunda Via' clicado")
        except Exception as e:
            logger.error(f"Erro ao solicitar emissão: {e}")
            raise HTTPException(status_code=500, detail=f"Erro ao solicitar emissão do PDF: {str(e)}")
        
        # Aguardar download
        logger.info("Aguardando download...")
        time.sleep(15)
        downloaded_pdf_path = wait_for_download_to_complete(DOWNLOAD_DIR)
        
        # Extrair texto do PDF
        logger.info(f"Extraindo texto do PDF: {downloaded_pdf_path}")
        try:
            with open(downloaded_pdf_path, "rb") as f_pdf:
                pdf_bytes = f_pdf.read()
            
            if not pdf_bytes:
                raise ValueError("PDF baixado está vazio")

            texto_do_pdf_completo = ""
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                texto_pagina = page.get_text("text", sort=True)
                texto_do_pdf_completo += texto_pagina
                
                if page_num < doc.page_count - 1:
                    texto_do_pdf_completo += f"\n\n--- PÁGINA {page_num + 1} FINALIZADA | PRÓXIMA PÁGINA {page_num + 2} ---\n\n"
            
            doc.close()
            
            if not texto_do_pdf_completo.strip():
                raise ValueError("Nenhum texto foi extraído do PDF")
                
            logger.info(f"Texto extraído com sucesso. Total de caracteres: {len(texto_do_pdf_completo)}")
            
        except Exception as e:
            logger.error(f"Erro ao extrair texto do PDF: {e}")
            if downloaded_pdf_path and os.path.exists(downloaded_pdf_path):
                background_tasks.add_task(excluir_arquivo_processado, downloaded_pdf_path)
            raise HTTPException(status_code=500, detail=f"Erro ao extrair texto do PDF: {str(e)}")
        
        # Agendar exclusão do arquivo
        if downloaded_pdf_path and os.path.exists(downloaded_pdf_path):
            background_tasks.add_task(excluir_arquivo_processado, downloaded_pdf_path)
        
        return RespostaTextoPdfCompleto(
            data_referencia=data_referencia_selenium,
            texto_do_pdf_completo=texto_do_pdf_completo,
            numero_cliente_selecionado=numero_cliente_usado
        )

    except HTTPException:
        # Re-raise HTTPExceptions sem modificar
        raise
    except TimeoutException as e:
        logger.error(f"Timeout na API: {e}")
        if driver:
            try:
                driver.save_screenshot("api_debug_timeout_exception.png")
            except Exception:
                pass
        raise HTTPException(status_code=504, detail=f"Timeout na operação: {str(e)}")
    except Exception as e:
        logger.error(f"Erro geral na API: {e}")
        if driver:
            try:
                driver.save_screenshot("api_debug_geral_exception.png")
                with open("api_debug_geral_exception.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {str(e)}")
    finally:
        # Cleanup seguro
        cleanup_browser(driver, original_window)
        
        # Cleanup final de emergência para o PDF (caso a background task falhe)
        if downloaded_pdf_path and os.path.exists(downloaded_pdf_path):
            logger.info(f"Arquivo {downloaded_pdf_path} deveria ser excluído pela BackgroundTask")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)