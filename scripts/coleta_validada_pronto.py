# scripts/coleta_validada_pronto.py
# Lê servidores_otserv_socket.txt -> gera resultado_validado.csv
# Colunas FIXAS (e nesta ordem): Servidor, Versão, Jogadores Online, Origem, Observação

import asyncio
import socket
import struct
import sys
import re
import csv
from pathlib import Path
from typing import Optional, Tuple, List, Dict

ARQ_ENTRADA = "servidores_otserv_socket.txt"
CSV_SAIDA   = "resultado_validado.csv"

# ===== Ajustes rápidos =====
TIMEOUT_S = 4.5               # timeout por conexão
CONCORRENCIA = 60             # consultas simultâneas
# Liste aqui as portas que quer tentar quando a linha não vem com :porta
PORTAS_PADRAO = [7171, 7170, 7172, 7010]

# Espera mínima entre chamadas de status no MESMO host (evita anti-flood)
ESPERA_STATUS_S = 5.2
# Se quiser rodar uma checagem simples quando online >= 100 (lista estendida)
FAZER_VERIF_LISTA_SE_SUSPEITO = True
AMOSTRA_PLAYERS = 80

# ==========================
# Helpers de protocolo
# ==========================
def make_packet(flag: int) -> bytes:
    # pacote: [u16 len little-endian][0xFF,0x01,flag,0,0,0]
    payload = bytes([0xFF, 0x01, flag, 0x00, 0x00, 0x00])
    return struct.pack("<H", len(payload)) + payload

class Buf:
    def __init__(self, data: bytes):
        self.d = memoryview(data)
        self.i = 0
    def left(self) -> int:
        return len(self.d) - self.i
    def _need(self, n: int):
        if self.left() < n:
            raise ValueError("short buffer")
    def u8(self) -> int:
        self._need(1)
        v = self.d[self.i]
        self.i += 1
        return int(v)
    def u16(self) -> int:
        self._need(2)
        v = struct.unpack_from("<H", self.d, self.i)[0]
        self.i += 2
        return v
    def u32(self) -> int:
        self._need(4)
        v = struct.unpack_from("<I", self.d, self.i)[0]
        self.i += 4
        return v
    def str16(self) -> str:
        ln = self.u16()
        self._need(ln)
        if ln <= 0:
            return ""
        v = bytes(self.d[self.i:self.i+ln]).decode("utf-8", errors="ignore")
        self.i += ln
        return v

def parse_status_response(full: bytes) -> Dict:
    """
    Lê resposta com prefixo u16 de tamanho e tenta extrair:
      - 0x20 Players Info: (online, max, record) -> usamos só 'online'
      - 0x2B Software Info: (name, version, version_str) -> usamos 'version'/'version_str'
      - 0x21 Players List (opcional p/ checagem)
    Parser é tolerante a blocos desconhecidos/truncados.
    """
    out = {"players_info": None, "players_list": [], "software_info": {}}
    if len(full) < 2:
        return out
    b = Buf(full[2:])
    while True:
        if b.left() <= 0:
            break
        try:
            code = b.u8()
        except ValueError:
            break
        try:
            if code == 0x20:
                online = b.u32(); _maxp = b.u32(); _rec = b.u32()
                out["players_info"] = (online, _maxp, _rec)
            elif code == 0x2B:
                sname = b.str16(); vers = b.str16(); vstr = b.str16()
                out["software_info"] = {"name": sname, "version": vers, "version_str": vstr}
            elif code == 0x21:
                count = b.u32()
                lst = []
                for _ in range(min(count, 5000)):
                    nm = b.str16(); lvl = b.u32()
                    lst.append((nm, lvl))
                out["players_list"] = lst
            else:
                # bloco desconhecido -> aborta parsing silenciosamente
                break
        except ValueError:
            # bloco truncado -> retorna o que deu
            break
    return out

def recv_exact(s: socket.socket, n: int) -> Optional[bytes]:
    data = bytearray()
    while len(data) < n:
        try:
            chunk = s.recv(n - len(data))
        except socket.timeout:
            return None
        if not chunk:
            return None
        data += chunk
    return bytes(data)

async def fetch_once(host: str, port: int, flag: int) -> Optional[bytes]:
    """Abre TCP, envia 1 pedido de status (flag) e lê exatamente 1 resposta."""
    try:
        loop = asyncio.get_running_loop()
        def _do():
            with socket.create_connection((host, port), timeout=TIMEOUT_S) as s:
                s.settimeout(TIMEOUT_S)
                s.sendall(make_packet(flag))

                hdr = recv_exact(s, 2)
                if not hdr:
                    return None

                (plen,) = struct.unpack("<H", hdr)
                if plen <= 0 or plen > 65535:
                    return None

                payload = recv_exact(s, plen)
                if not payload:
                    return None

                return hdr + payload
        return await loop.run_in_executor(None, _do)
    except Exception:
        return None

async def consulta_status(host: str, porta: int):
    """Retorna (players_info, software_info) ou (None, maybe_software)."""
    players_info, software_info = None, {}
    data = await fetch_once(host, porta, 0x08)   # Players Info
    if data:
        p = parse_status_response(data)
        players_info = p.get("players_info")
        if players_info:
            await asyncio.sleep(ESPERA_STATUS_S)
            data_sw = await fetch_once(host, porta, 0x80)  # Software Info
            if data_sw:
                software_info = (parse_status_response(data_sw).get("software_info") or {})
            return players_info, software_info
    # tentativa apenas de software p/ "pulsar vida"
    data_sw = await fetch_once(host, porta, 0x80)
    if data_sw:
        software_info = (parse_status_response(data_sw).get("software_info") or {})
    return None, software_info

async def consulta_lista(host: str, porta: int):
    await asyncio.sleep(ESPERA_STATUS_S)
    data = await fetch_once(host, porta, 0x20)  # Extended Players List
    if not data:
        return []
    p = parse_status_response(data)
    return (p.get("players_list") or [])[:AMOSTRA_PLAYERS]

def parse_host_port(line: str) -> Tuple[str, int]:
    line = line.strip()
    if not line:
        return ("", 0)
    if ":" in line:
        h, p = line.rsplit(":", 1)
        try:
            return (h.strip(), int(p))
        except:
            return (h.strip(), PORTAS_PADRAO[0])
    return (line, PORTAS_PADRAO[0])

# ==========================
# Pipeline por servidor
# ==========================
async def processar_host(hostline: str, sem: asyncio.Semaphore) -> Dict:
    host, porta = parse_host_port(hostline)
    if not host:
        return {}

    async with sem:
        players_info, software_info = await consulta_status(host, porta)

    versao_str = ""
    if software_info:
        for k in ("version", "version_str"):
            if software_info.get(k):
                versao_str = software_info[k]
                break

    # tentar portas alternativas, se 1ª falhou
    if not players_info:
        for palt in PORTAS_PADRAO:
            if palt == porta:
                continue
            async with sem:
                players_info, software_info2 = await consulta_status(host, palt)
            if players_info:
                porta = palt
                if not versao_str and software_info2:
                    for k in ("version", "version_str"):
                        if software_info2.get(k):
                            versao_str = software_info2[k]
                            break
                break

    # sem status -> pendência
    if not players_info:
        print(f"OK: {host}:{porta} => PENDÊNCIA (status bloqueado/indisponível)")
        return {
            "Servidor": f"{host.lower()}:{porta}",
            "Versão": versao_str or "",
            "Jogadores Online": 0,
            "Origem": "Pendência",
            "Observação": "Status bloqueado/indisponível",
        }

    online, _maxp, _record = players_info

    observacao = ""
    if FAZER_VERIF_LISTA_SE_SUSPEITO and online >= 100:
        async with sem:
            lst = await consulta_lista(host, porta)
        if not lst:
            observacao = "SUSPEITA: Sem lista estendida mesmo com online alto"

    print(f"OK: {host}:{porta} => {online} ({versao_str}) {observacao}")
    return {
        "Servidor": f"{host.lower()}:{porta}",
        "Versão": versao_str or "",
        "Jogadores Online": int(online),
        "Origem": "Socket",
        "Observação": observacao,
    }

# ==========================
# Main
# ==========================
async def main():
    entrada = Path(ARQ_ENTRADA)
    if not entrada.exists():
        print(f"❌ Arquivo de entrada não encontrado: {ARQ_ENTRADA}")
        sys.exit(1)

    # lista sem duplicatas
    servidores = [l.strip() for l in entrada.read_text(encoding="utf-8").splitlines() if l.strip()]
    seen = set(); lista = []
    for s in servidores:
        if s not in seen:
            seen.add(s); lista.append(s)

    sem = asyncio.Semaphore(CONCORRENCIA)
    tasks = [processar_host(h, sem) for h in lista]
    resultados: List[Dict] = []
    for coro in asyncio.as_completed(tasks):
        r = await coro
        if r:
            resultados.append(r)

    # Escreve CSV na ORDEM EXATA que o seu site espera
    with open(CSV_SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Servidor","Versão","Jogadores Online","Origem","Observação"])
        w.writeheader()
        for r in resultados:
            # segurança: força numérico na saída
            try:
                r["Jogadores Online"] = int(r["Jogadores Online"])
            except:
                r["Jogadores Online"] = 0
            w.writerow(r)

    print(f"\n✅ '{CSV_SAIDA}' gerado com {len(resultados)} linhas.")

if __name__ == "__main__":
    asyncio.run(main())
