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
