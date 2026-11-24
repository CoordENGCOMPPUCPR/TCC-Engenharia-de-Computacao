import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================
# CONFIGURAÇÕES
# ============================================================
NUM_PAGINAS = 30
URL_BASE = "https://pncp.gov.br/app/editais?pagina={pagina}&modos_disputa=1&status=recebendo_proposta"
ARQUIVO_SAIDA = "editais_pncp.xlsx"
TEMPO_ESPERA = 20

# Retry
MAX_TENTATIVAS = 3
BACKOFF_BASE = 2  # segundos; backoff = BACKOFF_BASE ** tentativa

# Salvamento parcial
SALVAR_A_CADA = 5  # páginas
PASTA_TEMP = Path("_temp")

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"rpa_{datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("rpa")

# ============================================================
# MAPEAMENTO DE CAMPOS
# ============================================================
CAMPOS = {
    "Última atualização": "Ultima Atualizacao",
    "Data de Divulgação no PNCP": "Data Divulgacao PNCP",
    "Id contratação PNCP": "Id Contratacao PNCP",
    "Situação": "Situacao",
    "Modalidade de Contratação": "Modalidade",
    "Amparo Legal": "Amparo Legal",
    "Modo de Disputa": "Modo Disputa",
    "SRP": "SRP",
    "Fonte Orçamentária": "Fonte Orcamentaria",
    "Órgão": "Orgao",
    "Unidade": "Unidade",
    "Localidade da Unidade": "Localidade",
    "Órgão/Entidade sub-rogado": "Orgao Sub-rogado",
    "Unidade sub-rogada": "Unidade Sub-rogada",
    "Localidade da Unidade sub-rogada": "Localidade Sub-rogada",
    "Data de início de recebimento de propostas": "Inicio Propostas",
    "Data de fim de recebimento de propostas": "Fim Propostas",
    "Fonte/Plataforma": "Fonte/Plataforma",
    "Objeto": "Objeto",
    "Valor Total Estimado/Avaliado": "Valor Estimado",
    "Valor Total Homologado": "Valor Homologado",
}

# ============================================================
# SANITIZAÇÃO
# ============================================================
# Mantém \t \n \r (permitidos pelo Excel), remove os demais C0 e DEL
ILLEGAL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
LIMITE_CELULA = 32767


def limpar_texto(valor):
    if not isinstance(valor, str):
        return valor
    valor = ILLEGAL_CHARS.sub("", valor)
    valor = valor.replace("\xa0", " ")
    if len(valor) > LIMITE_CELULA:
        valor = valor[: LIMITE_CELULA - 3] + "..."
    return valor


def sanitizar_dataframe(df):
    for col in df.columns:
        df[col] = df[col].map(limpar_texto)
    return df


# ============================================================
# RETRY UTIL
# ============================================================
def com_retry(fn, descricao, tentativas=MAX_TENTATIVAS, backoff=BACKOFF_BASE, excecoes=(Exception,)):
    """Executa fn() com retry exponencial. Relança a última exceção se esgotar."""
    ultimo_erro = None
    for t in range(1, tentativas + 1):
        try:
            return fn()
        except excecoes as e:
            ultimo_erro = e
            if t < tentativas:
                espera = backoff ** t
                log.warning(f"[retry {t}/{tentativas}] {descricao}: {e}. Aguardando {espera}s…")
                time.sleep(espera)
            else:
                log.error(f"[falhou] {descricao} após {tentativas} tentativas: {e}")
    raise ultimo_erro


# ============================================================
# DRIVER
# ============================================================
def iniciar_driver(headless: bool = False):
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    options.page_load_strategy = "eager"  # não espera imagens/scripts secundários

    if headless:
        options.add_argument("--headless=new")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(30)
    return driver


def reciclar_driver(driver, headless=False):
    """Fecha e reabre o driver (útil quando o Chrome travou/morreu)."""
    try:
        driver.quit()
    except Exception:
        pass
    return iniciar_driver(headless=headless)


# ============================================================
# PARSING
# ============================================================
def parse_itens(html_br_list: str):
    soup = BeautifulSoup(html_br_list, "html.parser")
    registros = []

    for a in soup.select("a.br-item"):
        item = {"Link Detalhes": a.get("href", "")}

        for strong in a.find_all("strong"):
            txt = strong.get_text(strip=True)
            if txt.startswith("Edital nº") or txt.startswith("Edital n"):
                item["Edital"] = txt
                break

        for strong in a.find_all("strong"):
            label = strong.get_text(strip=True)
            if not label.endswith(":"):
                continue
            label_limpo = label.rstrip(":").strip()
            if label_limpo not in CAMPOS:
                continue

            parent = strong.parent
            texto_parent = parent.get_text(" ", strip=True)
            valor = texto_parent.replace(label, "", 1).strip()

            span = parent.find("span", class_="ng-star-inserted")
            if span:
                valor = span.get_text(" ", strip=True)

            item[CAMPOS[label_limpo]] = valor

        registros.append(item)

    return registros


# ============================================================
# EXTRAÇÃO
# ============================================================
def extrair_pagina(driver, url):
    """Carrega a página e devolve a lista de itens (com retry)."""
    def _acao():
        driver.get(url)
        WebDriverWait(driver, TEMPO_ESPERA).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "pncp-items-list a.br-item"))
        )
        time.sleep(1.2)  # render final do Angular
        br_list = driver.find_element(By.CSS_SELECTOR, "pncp-items-list div.br-list")
        return parse_itens(br_list.get_attribute("outerHTML"))

    return com_retry(_acao, f"extrair_pagina({url})",
                     excecoes=(TimeoutException, NoSuchElementException, WebDriverException))


def salvar_parcial(todos, prefixo="_temp/parcial"):
    """Salva um Excel parcial para não perder progresso."""
    if not todos:
        return None
    try:
        PASTA_TEMP.mkdir(exist_ok=True)
        caminho = f"{prefixo}_{len(todos)}.xlsx"
        df = sanitizar_dataframe(pd.DataFrame(todos))
        df.to_excel(caminho, index=False, engine="openpyxl")
        log.info(f"💾 parcial salvo: {caminho} ({len(todos)} registros)")
        return caminho
    except Exception as e:
        log.warning(f"falha ao salvar parcial: {e}")
        return None


# main principal
def main(num_paginas: int, headless: bool):
    log.info(f"Iniciando RPA | páginas={num_paginas} | headless={headless}")
    driver = iniciar_driver(headless=headless)
    driver.maximize_window()
    todos = []
    paginas_vazias = 0

    try:
        for pagina in range(1, num_paginas + 1):
            url = URL_BASE.format(pagina=pagina)
            log.info(f"[PÁGINA {pagina}/{num_paginas}] {url}")

            try:
                regs = extrair_pagina(driver, url)
            except Exception as e:
                log.error(f"Falha na página {pagina}: {e}. Reciclando driver…")
                try:
                    driver = reciclar_driver(driver, headless=headless)
                except Exception as e2:
                    log.critical(f"Não foi possível reciclar o driver: {e2}. Abortando.")
                    break
                continue

            if not regs:
                paginas_vazias += 1
                log.warning(f"   -> 0 itens (página vazia? {paginas_vazias}/2)")
                if paginas_vazias >= 2:
                    log.info("Duas páginas vazias consecutivas — encerrando.")
                    break
                continue

            paginas_vazias = 0
            log.info(f"   -> {len(regs)} itens (total acumulado: {len(todos) + len(regs)})")
            todos.extend(regs)

            if pagina % SALVAR_A_CADA == 0:
                salvar_parcial(todos)

        if todos:
            df = sanitizar_dataframe(pd.DataFrame(todos))
            df.to_excel(ARQUIVO_SAIDA, index=False, engine="openpyxl")
            log.info(f"✅ {len(todos)} registros salvos em '{ARQUIVO_SAIDA}'")
        else:
            log.warning("⚠️ Nenhum registro extraído.")

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        log.info("Driver encerrado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPA PNCP – extração de editais")
    parser.add_argument("-n", "--paginas", type=int, default=NUM_PAGINAS,
                        help=f"número de páginas (default: {NUM_PAGINAS})")
    parser.add_argument("--headless", action="store_true",
                        help="roda o Chrome em modo headless")
    args = parser.parse_args()

    try:
        main(args.paginas, args.headless)
    except KeyboardInterrupt:
        log.warning("Interrompido pelo usuário.")