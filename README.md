# 📄 Enel CE CORPORATIVO ACCOUNT EXTRACTOR API

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Selenium](https://img.shields.io/badge/Selenium-4.0+-orange.svg)](https://selenium.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

API automatizada para **extração de texto** de faturas de energia elétrica da **Enel Distribuição Ceará**. Realiza login automático, baixa o PDF da segunda via e retorna todo o texto extraído em formato JSON.

## 📋 Funcionalidades

- ✅ **Login automatizado** no portal Enel
- ✅ **Seleção inteligente** de clientes (contas múltiplas)
- ✅ **Download automático** de PDF da segunda via
- ✅ **Extração completa** de texto do PDF
- ✅ **Retorno em JSON** com texto extraído
- ✅ **Limpeza automática** de arquivos temporários
- ✅ **API REST** com FastAPI
- ✅ **Logs detalhados** para debugging

> **⚠️ Importante:** A API retorna o **texto extraído** do PDF, não o arquivo PDF em si. O PDF é baixado temporariamente e deletado após a extração.

## 🚀 Instalação

### Pré-requisitos

```bash
# Python 3.8+
python --version

# Google Chrome
google-chrome --version

# ChromeDriver (compatível com sua versão do Chrome)
chromedriver --version
```

### Dependências

```bash
pip install fastapi selenium pymupdf uvicorn email-validator
```

### Configuração do ChromeDriver

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# macOS
brew install chromedriver
```

**Windows:**
1. Baixe o ChromeDriver: https://chromedriver.chromium.org/
2. Adicione ao PATH ou coloque na pasta do projeto

## 🏃‍♂️ Uso Rápido

### 1. Executar a API

```bash
python app.py
```

A API estará disponível em: `http://localhost:8000`

### 2. Fazer Requisição

**curl:**
```bash
curl -X POST http://localhost:8000/extrair-texto-pdf-completo \
  -H "Content-Type: application/json" \
  -d '{
    "email": "seu_email@exemplo.com",
    "senha": "sua_senha",
    "numero_cliente": "123456789"
  }'
```

**Python:**
```python
import requests

response = requests.post("http://localhost:8000/extrair-texto-pdf-completo", json={
    "email": "seu_email@exemplo.com",
    "senha": "sua_senha", 
    "numero_cliente": "123456789"
})

data = response.json()
print("Texto extraído:")
print(data["texto_do_pdf_completo"])  # ← String com todo o texto do PDF
```

## 📖 Documentação da API

### Endpoint Principal

```
POST /extrair-texto-pdf-completo
```

**Request Body:**
```json
{
  "email": "string (EmailStr)",
  "senha": "string", 
  "numero_cliente": "string"
}
```

**Response (200):**
```json
{
  "data_referencia": "12/2024",
  "texto_do_pdf_completo": "ENEL DISTRIBUIÇÃO CEARÁ\n\nConta de Energia...",
  "numero_cliente_selecionado": "123456789",
  "message": "Texto completo do PDF extraído com sucesso."
}
```

**Possíveis Erros:**
- `401` - Credenciais inválidas ou timeout no login
- `404` - Cliente não encontrado
- `500` - Erro interno (ChromeDriver, PDF, etc.)
- `504` - Timeout na operação

### Endpoints Auxiliares

```
GET /health
```
Verifica se a API está funcionando.

```
GET /docs
```
Documentação interativa (Swagger UI).

## ⚙️ Configuração

### Variáveis de Ambiente

```bash
# Diretório para downloads (opcional)
export DOWNLOAD_DIR="/tmp/enel_downloads"
```

### Parâmetros Personalizáveis

No código, você pode ajustar:

```python
DOWNLOAD_DIR = "/custom/path"  # Diretório de download
# Timeouts estão configurados automaticamente
```

## 🧪 Testes

### Health Check
```bash
curl http://localhost:8000/health
# Resposta: {"status": "ok"}
```

### Teste Completo
Use o arquivo `test_credentials.json`:

```json
{
  "email": "test@email.com",
  "senha": "password123",
  "numero_cliente": "987654321"
}
```

```bash
curl -X POST http://localhost:8000/extrair-texto-pdf-completo \
  -H "Content-Type: application/json" \
  -d @test_credentials.json
```

## 🏗️ Arquitetura

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│   FastAPI       │────│   Selenium   │────│  Chrome     │
│   (REST API)    │    │  (Automação) │    │ (Headless)  │
└─────────────────┘    └──────────────┘    └─────────────┘
         │                       │                 │
         ▼                       ▼                 ▼
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│  JSON Response  │◄───│   PyMuPDF    │◄───│ PDF (temp)  │
│  (texto_do_pdf) │    │  (Extração)  │    │ (deletado)  │
└─────────────────┘    └──────────────┘    └─────────────┘
```

**Fluxo:**
1. Selenium faz login e baixa PDF
2. PyMuPDF extrai texto do PDF
3. **Retorna JSON com texto**
4. PDF temporário é deletado

## 📊 Performance

| Operação | Tempo Médio | Descrição |
|----------|-------------|-----------|
| **Login** | 8-15s | Autenticação no portal Enel |
| **Seleção Cliente** | 2-5s | Escolha do número de cliente |
| **Download PDF** | 10-30s | Download temporário do arquivo |
| **Extração Texto** | 1-3s | Conversão PDF → texto |
| **Limpeza** | <1s | Remoção do PDF temporário |
| **Total** | **25-50s** | **Retorna JSON com texto** |

## 🔧 Troubleshooting

### ChromeDriver não encontrado
```bash
# Verifique se está no PATH
chromedriver --version

# Ou baixe e adicione ao projeto
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE
```

### Timeout no login
- Verifique credenciais
- Teste acesso manual ao site
- Verifique conectividade

### PDF não baixa
- Verifique permissões do diretório
- Espaço em disco suficiente
- Firewall/antivírus

### Erro de memória
```bash
# Monitorar recursos
htop

# Limitar uso do Chrome
export CHROME_FLAGS="--memory-pressure-off --max_old_space_size=4096"
```

## 🐳 Docker (Opcional)

```dockerfile
FROM python:3.9-slim

# Instalar Chrome e dependências
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    chromium-chromedriver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build e run
docker build -t enel-api .
docker run -p 8000:8000 enel-api
```

## 📝 Exemplo de Integração

### Script Python Completo

```python
#!/usr/bin/env python3
"""
Exemplo de uso da Enel PDF Extractor API
"""
import requests
import json
from typing import Dict, Any

class EnelExtractor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def extract_pdf_text(self, email: str, senha: str, numero_cliente: str) -> Dict[str, Any]:
        """Extrai texto do PDF da fatura e retorna em JSON"""
        url = f"{self.base_url}/extrair-texto-pdf-completo"
        
        payload = {
            "email": email,
            "senha": senha,
            "numero_cliente": numero_cliente
        }
        
        try:
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json()  # ← Retorna JSON com texto, não PDF
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro na requisição: {e}")
    
    def health_check(self) -> bool:
        """Verifica se a API está funcionando"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

# Uso
if __name__ == "__main__":
    extractor = EnelExtractor()
    
    # Verificar se API está online
    if not extractor.health_check():
        print("❌ API não está funcionando")
        exit(1)
    
    # Extrair texto
    try:
        result = extractor.extract_pdf_text(
            email="seu_email@exemplo.com",
            senha="sua_senha",
            numero_cliente="123456789"
        )
        
        print(f"✅ Extração concluída!")
        print(f"📅 Data: {result['data_referencia']}")
        print(f"👤 Cliente: {result['numero_cliente_selecionado']}")
        print(f"📝 Texto extraído: {len(result['texto_do_pdf_completo'])} caracteres")
        
        # Salvar texto em arquivo se necessário
        with open("fatura_texto.txt", "w", encoding="utf-8") as f:
            f.write(result['texto_do_pdf_completo'])
        print("💾 Texto salvo em fatura_texto.txt")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
```

## ⚠️ Disclaimer

Esta API é para fins educacionais e de automação pessoal. Certifique-se de estar em conformidade com os termos de uso da Enel e leis aplicáveis ao usar este código.

