import socket
import struct
import asyncio
import csv
import re
import time
from pathlib import Path

# --- Configurações ---
# Timeout de conexão em segundos
TIMEOUT = 3
# Portas OTServ mais comuns
PORTAS = [7171, 7172, 7000]
# Lista de todas as versões puramente numéricas de Tibia (maior.menor)
raw_versions = [
    # 15.x (mais prováveis primeiro)
    "15.10", "15.00",
    # 14.x
    "14.12", "14.10", "14.05", "14.00",
    # 13.x
    "13.0"
    # 12.x
    "12.30","12.20","12.15","12.02","12.00",
    # 11.x
    "11.80","11.50","11.40","11.02",
    # 10.x
    "11.00","10.98","10.97","10.0",
    # 9.x
    "9.86","9.0"
    # 8.x
    "8.61","8.6",
    # 7.x
    "7.4","7.72","7.82","7.81","7.8","7.72","7.71","7.7","7.61","7.6",
]
# Converte string de versão para código de handshake (e ordena do maior ao menor)
VERSOES = sorted(
    [(int("".join(v.split("."))), v) for v in raw_versions],
    key=lambda x: x[0], reverse=True
)

# --- Função de coleta via socket estrito ---
def tentar_socket(host, porta, versao_num):
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        return None
    try:
        with socket.create_connection((ip, porta), timeout=TIMEOUT) as sock:
            # 0x0A handshake + versão
            sock.sendall(struct.pack('>BH', 0x0A, versao_num))
            data = sock.recv(5)
            # aceita opcode válido
            if len(data) < 3 or data[0] not in (0x0A, 0x0C):
                return None
            jogadores = struct.unpack('>H', data[1:3])[0]
            if jogadores < 0 or jogadores > 10000 or jogadores in PORTAS:
                return None
            return jogadores
    except Exception:
        return None

# --- Processamento de cada servidor ---
async def processar(servidor):
    host = servidor.strip().split("/")[0]
    print(f"➡️  Verificando {host}...")

    # Tenta, na ordem DESC de versões, até encontrar o primeiro que responda
    for versao_num, versao_str in VERSOES:
        for porta in PORTAS:
            jogadores = tentar_socket(host, porta, versao_num)
            if isinstance(jogadores, int):
                print(f"  ✅ Socket OK ({jogadores} jogadores) - Versão {versao_str} (porta {porta})")
                return {
                    "Servidor": host,
                    "Jogadores Online": jogadores,
                    "Versão": versao_str,
                    "Origem": "Socket",
                    "Observação": ""
                }

    # Nenhuma combinação funcionou
    print(f"  ⚠️ Sem resposta socket, pendente de validação")
    return {
        "Servidor": host,
        "Jogadores Online": "PENDENTE",
        "Versão": "PENDENTE",
        "Origem": "Pendência",
        "Observação": "⚠️ Validar manualmente"
    }

# --- Fluxo principal ---
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

    # Grava CSV
    campos = ["Servidor", "Jogadores Online", "Versão", "Origem", "Observação"]
    with open(saida, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(resultados)

    # Grava pendentes
    with open(pendentes_txt, "w", encoding="utf-8") as f:
        for p in pendentes:
            f.write(p + "\n")

    print(f"\n✅ Ranking confiável gerado em {saida}")
    print(f"⚠️ {len(pendentes)} servidores pendentes listados em {pendentes_txt}")

if __name__ == "__main__":
    asyncio.run(main())
