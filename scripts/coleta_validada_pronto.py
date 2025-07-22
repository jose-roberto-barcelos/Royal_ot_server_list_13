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
# Lista de todas as versões puramente numéricas de Tibia
raw_versions = [
    # 7.x
    "7.0","7.01","7.02","7.1","7.11","7.2","7.21","7.23","7.24","7.26","7.27",
    "7.3","7.35","7.4","7.41","7.5","7.55","7.6","7.61","7.7","7.71","7.72","7.8",
    "7.81","7.82","7.9","7.92",
    # 8.x
    "8.0","8.1","8.11","8.2","8.21","8.22","8.3","8.31","8.4","8.41","8.42","8.5",
    "8.51","8.52","8.53","8.54","8.55","8.56","8.57","8.6","8.61","8.62","8.7",
    "8.71","8.72","8.73","8.74",
    # 9.x
    "9.0","9.1","9.2","9.31","9.4","9.41","9.42","9.43","9.44","9.45","9.46","9.5",
    "9.51","9.52","9.53","9.54","9.60","9.62","9.63","9.7","9.71","9.8","9.83",
    "9.84","9.85","9.86",
    # 10.x
    "10.0","10.01","10.02","10.10","10.20","10.30","10.40","10.50","10.70",
    "10.80","10.90","10.92","10.94","10.95","10.96","10.97","10.98","11.00",
    # 11.x
    "11.02","11.40","11.50","11.80",
    # 12.x
    "12.00","12.02","12.15","12.20","12.30",
    # 13.x (numérico)
    "13.10","13.11","13.12","13.13","13.14","13.15","13.16","13.17",
    "13.20","13.30","13.31","13.32","13.33","13.34","13.35","13.36","13.37","13.40","13.41",
    # 14.x (numérico)
    "14.00","14.05","14.10","14.12",
    # 15.x (numérico)
    "15.00","15.10","15.20"
]
# Converte string de versão para código de handshake (ex: "8.60"→860)
# Gera a lista de versões a partir de raw_versions (inclui automaticamente "15.00")
VERSOES = [(int("".join(v.split("."))), v) for v in raw_versions]
PORTAS = [7171, 7172, 7000]
TIMEOUT = 3

# Coleta via socket estrito (aceita opcode 0x0A e 0x0C)
def tentar_socket(host, porta, versao_num):
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        return None
    try:
        with socket.create_connection((ip, porta), timeout=TIMEOUT) as sock:
            payload = struct.pack('>BH', 0x0A, versao_num)
            sock.sendall(payload)
            data = sock.recv(5)
            if len(data) < 3 or data[0] not in (0x0A, 0x0C):
                return None
            jogadores = struct.unpack('>H', data[1:3])[0]
            if jogadores < 0 or jogadores > 10000 or jogadores in PORTAS:
                return None
            return jogadores
    except Exception:
        return None

async def processar(servidor):
    host = servidor.strip().split("/")[0]
    print(f"➡️  Verificando {host}...")

    # Tenta todas as portas/versões
    for porta in PORTAS:
        for versao_num, versao_str in VERSOES:
            jogadores = tentar_socket(host, porta, versao_num)
            if isinstance(jogadores, int):
                print(f"  ✅ Socket OK ({jogadores} jogadores) - Versão {versao_str}")
                return {
                    "Servidor": host,
                    "Jogadores Online": jogadores,
                    "Versão": versao_str,
                    "Origem": "Socket",
                    "Observação": ""
                }

    # Se nenhum socket funcionou, marca como pendente
    print(f"  ⚠️ Sem resposta socket, pendente de validação")
    return {
        "Servidor": host,
        "Jogadores Online": "PENDENTE",
        "Versão": "PENDENTE",
        "Origem": "Pendência",
        "Observação": "⚠️ Validar manualmente"
    }

async def main():
    entrada = Path("servidores_otserv_socket.txt")
    saida = Path("resultado_validado.csv")
    pendentes_txt = Path("pendentes_para_revisao.txt")

    if not entrada.exists():
        print("Arquivo de entrada não encontrado.")
        return

    servidores = [l.strip() for l in entrada.read_text(encoding="utf-8").splitlines() if l.strip()]

    resultados = []
    pendentes = []

    for srv in servidores:
        res = await processar(srv)
        resultados.append(res)
        if res["Origem"] == "Pendência":
            pendentes.append(srv)

    # Grava CSV apenas com os resultados (incluindo marcadores de pendência)
    campos = ["Servidor", "Jogadores Online", "Versão", "Origem", "Observação"]
    with open(saida, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(resultados)

    # Grava lista de pendentes para revisão
    with open(pendentes_txt, "w", encoding="utf-8") as f:
        for srv in pendentes:
            f.write(srv + "\n")

    print(f"\n✅ Ranking confiável gerado em {saida}")
    print(f"⚠️ {len(pendentes)} servidores pendentes listados em {pendentes_txt}")

if __name__ == "__main__":
    asyncio.run(main())
