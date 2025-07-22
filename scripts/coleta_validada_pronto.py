import socket
import struct
import asyncio
import csv
import re
import time
import requests
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

API_KEY_2CAPTCHA = "ded21bd02e90ba47e71153d6f611fd89"
VERSOES = [(860, "8.60"), (1098, "10.98"), (1270, "12.70")]
PORTAS = [7171, 7172, 7000]
TIMEOUT = 3

# Função de coleta via socket com handshake estrito e validações
def tentar_socket(host, porta, versao_num):
    try:
        # 1) Resolução DNS: falha se o host não existir
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        return None
    try:
        # 2) Conexão TCP ao port listener OTServ
        with socket.create_connection((ip, porta), timeout=TIMEOUT) as sock:
            # 3) Handshake: opcode 0x0A + protocolo (big-endian)
            payload = struct.pack('>BH', 0x0A, versao_num)
            sock.sendall(payload)
            # 4) Espera resposta mínima (opcode + 2 bytes de player count)
data = sock.recv(1024)
print(f"[DEBUG] {host}:{porta} raw response:", data.hex(), data)
# então bloqueie imediatamente para ver só o dump:
return None

            # 6) Valida contagem plausível, evitando portas e valores absurdos
            if jogadores < 0 or jogadores > 10000 or jogadores in PORTAS:
                return None
            return jogadores
    except Exception:
        return None

# Funções de fallback HTML permanecem iguais
async def tentar_texto(site, resolver_captcha_flag=False):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0")
            page = await context.new_page()
            print(f"  🌐 Acessando: {site}")
            await page.goto(site, timeout=20000)
            await page.wait_for_timeout(10000)

            html = await page.content()

            if "recaptcha" in html.lower() and resolver_captcha_flag:
                print("  🧱 CAPTCHA detectado, tentando resolver...")
                sitekey_match = re.search(r"data-sitekey=[\"'](.+?)[\"']", html)
                if sitekey_match:
                    token = resolver_captcha(site, sitekey_match.group(1))
                    if token:
                        await page.evaluate(f'document.getElementById("g-recaptcha-response").innerHTML = "{token}";')
                        await page.evaluate('document.forms[0].submit();')
                        await page.wait_for_timeout(10000)
                        html = await page.content()

            textos = await page.locator("body").all_inner_texts()
            visivel = " ".join(textos)
            match = re.search(r"online[^\d]{0,10}(\d{1,5})", visivel, re.IGNORECASE)
            versao_match = re.search(r"(client|vers[aã]o)[^\d]{0,5}(\d{2,5})", visivel, re.IGNORECASE)
            await browser.close()

            jogadores = int(match.group(1)) if match else None
            versao = versao_match.group(2) if versao_match else "N/A"
            return jogadores, versao
    except TimeoutError:
        print("  ⏱️ Timeout Playwright")
    except Exception as e:
        print(f"  ❌ Erro navegador: {e}")
    return None, None

def resolver_captcha(site_url, sitekey):
    payload = {
        'key': API_KEY_2CAPTCHA,
        'method': 'userrecaptcha',
        'googlekey': sitekey,
        'pageurl': site_url,
        'json': 1
    }
    print("  🧩 Enviando para 2Captcha...")
    r = requests.post('http://2captcha.com/in.php', data=payload).json()
    request_id = r.get("request")
    for _ in range(20):
        time.sleep(5)
        res = requests.get(f"http://2captcha.com/res.php?key={API_KEY_2CAPTCHA}&action=get&id={request_id}&json=1").json()
        if res.get("status") == 1:
            return res.get("request")
    return None

async def processar(servidor):
    host = servidor.strip().replace("https://", "").replace("http://", "").split("/")[0]
    print(f"➡️  Verificando {host}...")

    # Tenta socket estrito em múltiplas portas/versões
    for porta in PORTAS:
        for versao_num, versao_str in VERSOES:
            jogadores = tentar_socket(host, porta, versao_num)
            if isinstance(jogadores, int):
                print(f"  ✅ Socket OK ({jogadores} jogadores) - Versão {versao_str}")
                return {"Servidor": host, "Jogadores Online": jogadores, "Versão": versao_str, "Origem": "Socket"}

    # Fallback HTML se socket falhar (controverso, mas mantido)
    jogadores_texto, versao_detectada = await tentar_texto("http://" + host)
    if isinstance(jogadores_texto, int):
        print(f"  ⚠️ HTML detectado ({jogadores_texto} jogadores)")
        return {"Servidor": host, "Jogadores Online": jogadores_texto, "Versão": versao_detectada or "N/A", "Origem": "HTML"}

    jogadores_captcha, versao_detectada = await tentar_texto("http://" + host, resolver_captcha_flag=True)
    if isinstance(jogadores_captcha, int):
        print(f"  ⚠️ CAPTCHA resolvido ({jogadores_captcha} jogadores)")
        return {"Servidor": host, "Jogadores Online": jogadores_captcha, "Versão": versao_detectada or "N/A", "Origem": "HTML"}

    print(f"  ❌ Falha total em {host}")
    return {"Servidor": host, "Jogadores Online": "N/A", "Versão": "N/A", "Origem": "Erro"}

async def main():
    entrada = Path("servidores_otserv_socket.txt")
    saida = Path("resultado_validado.csv")
    if not entrada.exists():
        print("Arquivo de entrada não encontrado.")
        return

    with open(entrada) as f:
        servidores = [linha.strip() for linha in f if linha.strip()]

    dados_socket = []
    dados_html = []

    for servidor in servidores:
        resultado = await processar(servidor)

        # Filtro de valores claros inválidos
        val = resultado["Jogadores Online"]
        if isinstance(val, int) and (val in [0, *PORTAS] or val > 10000):
            print(f"  🚫 Valor inválido ({val}) ignorado.")
            continue

        observacao = ""
        if resultado["Origem"] == "HTML" and isinstance(val, int) and val > 100:
            termos_suspeitos = ["god", "tutor", "cm ", "gm ", "npc", "account manager", "sample"]
            if any(term in resultado["Servidor"].lower() for term in termos_suspeitos):
                observacao = "⚠️ Possível Fake/NPC"
        resultado["Observação"] = observacao

        if resultado["Origem"] == "Socket":
            dados_socket.append(resultado)
        else:
            dados_html.append(resultado)

    # Grava CSV
    with open(saida, "w", newline="", encoding="utf-8") as f:
        campos = ["Servidor", "Jogadores Online", "Versão", "Origem", "Observação"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerow({"Servidor": "=== VIA SOCKET (CONFIÁVEL) ===", "Jogadores Online": "", "Versão": "", "Origem": "", "Observação": ""})
        writer.writerows(dados_socket)
        writer.writerow({"Servidor": "", "Jogadores Online": "", "Versão": "", "Origem": "", "Observação": ""})
        writer.writerow({"Servidor": "=== VIA HTML (POTENCIALMENTE FALSO) ===", "Jogadores Online": "", "Versão": "", "Origem": "", "Observação": ""})
        writer.writerows(dados_html)

    # JSON para o site
    ranking_completo = dados_socket + dados_html
    import json
    with open("ranking.json", "w", encoding="utf-8") as json_file:
        json.dump(ranking_completo, json_file, ensure_ascii=False, indent=2)

    print("\n✅ Coleta finalizada com versão e observação incluídas. Veja resultado_validado.csv")

if __name__ == "__main__":
    asyncio.run(main())
