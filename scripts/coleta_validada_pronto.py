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

TIMEOUT_S = 4.5
CONCORRENCIA = 60
PORTAS_PADRAO = [7171, 7170, 7172, 7010]
ESPERA_STATUS_S = 5.2
FAZER_VERIF_LISTA_SE_SUSPEITO = True
AMOSTRA_PLAYERS = 80

def make_packet(flag: int) -> bytes:
    payload = bytes([0xFF, 0x01, flag, 0x00, 0x00, 0x00])
    return struct.pack("<H", len(payload)) + payload  # length little-endian

class Buf:
    def __init__(self, data: bytes):
        self.d = memoryview(data); self.i = 0
    def left(self): return len(self.d) - self.i
    def _need(self, n): 
        if self.left() < n: raise ValueError("short buffer")
    def u8(self): self._need(1); v=self.d[self.i]; self.i+=1; return int(v)
    def u16(self): self._need(2); v=struct.unpack_from("<H", self.d, self.i)[0]; self.i+=2; return v
    def u32(self): self._need(4); v=struct.unpack_from("<I", self.d, self.i)[0]; self.i+=4; return v
    def str16(self):
        ln = self.u16(); self._need(ln)
        if ln <= 0: return ""
        v = bytes(self.d[self.i:self.i+ln]).decode("utf-8", errors="ignore")
        self.i += ln; return v

def parse_status_response(full: bytes) -> Dict:
    out = {"players_info": None, "players_list": [], "software_info": {}}
    if len(full) < 2: return out
    b = Buf(full[2:])
    while True:
        if b.left() <= 0: break
        try:
            code = b.u8()
        except ValueError:
            break
        try:
            if code == 0x20:  # Players Info
                out["players_info"] = (b.u32(), b.u32(), b.u32())  # online, max, record
            elif code == 0x21:  # Extended Players List
                count = b.u32()
                lst = []
                for _ in range(min(count, 5000)):
                    nm = b.str16(); lvl = b.u32()
                    lst.append((nm, lvl))
                out["players_list"] = lst
            elif code == 0x2B:  # Software Info
                out["software_info"] = {"name": b.str16(), "version": b.str16(), "version_str": b.str16()}
            else:
                break
        except ValueError:
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
    players_info, software_info = None, {}
    data = await fetch_once(host, porta, 0x08)
    if data:
        p = parse_status_response(data)
        players_info = p.get("players_info")
        if players_info:
            await asyncio.sleep(ESPERA_STATUS_S)
            data_sw = await fetch_once(host, porta, 0x80)
            if data_sw:
                software_info = (parse_status_response(data_sw).get("software_info") or {})
            return players_info, software_info
    data_sw = await fetch_once(host, porta, 0x80)
    if data_sw:
        software_info = (parse_status_response(data_sw).get("software_info") or {})
    return None, software_info

async def consulta_lista(host: str, porta: int):
    await asyncio.sleep(ESPERA_STATUS_S)
    data = await fetch_once(host, porta, 0x20)
    if not data: return []
    p = parse_status_response(data)
    return (p.get("players_list") or [])[:AMOSTRA_PLAYERS]

def parse_host_port(line: str) -> Tuple[str,int]:
    line = line.strip()
    if not line: return ("", 0)
    if ":" in line:
        h, p = line.rsplit(":", 1)
        try: return (h.strip(), int(p))
        except: return (h.strip(), PORTAS_PADRAO[0])
    return (line, PORTAS_PADRAO[0])

async def processar_host(hostline: str, sem: asyncio.Semaphore) -> Dict:
    host, porta = parse_host_port(hostline)
    if not host: return {}

    async with sem:
        players_info, software_info = await consulta_status(host, porta)

    versao_str = ""
    if software_info:
        for k in ("version", "version_str"):
            if software_info.get(k):
                versao_str = software_info[k]; break

    if not players_info:
        for palt in PORTAS_PADRAO:
            if palt == porta: continue
            async with sem:
                players_info, software_info2 = await consulta_status(host, palt)
            if players_info:
                porta = palt
                if not versao_str and software_info2:
                    for k in ("version", "version_str"):
                        if software_info2.get(k): versao_str = software_info2[k]; break
                break

    if not players_info:
        print(f"OK: {host}:{porta} => PENDÊNCIA (status bloqueado/indisponível)")
        return {
            "Servidor": f"{host.lower()}:{porta}",
            "Versão": versao_str or "",
            "Jogadores Online": 0,
            "Origem": "Pendência",
            "Observação": "Status bloqueado/indisponível",
        }

    online, _m, _r = players_info
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

async def main():
    entrada = Path(ARQ_ENTRADA)
    if not entrada.exists():
        print(f"❌ Arquivo de entrada não encontrado: {ARQ_ENTRADA}")
        sys.exit(1)

    servidores = [l.strip() for l in entrada.read_text(encoding="utf-8").splitlines() if l.strip()]
    seen=set(); lista=[]
    for s in servidores:
        if s not in seen:
            seen.add(s); lista.append(s)

    sem = asyncio.Semaphore(CONCORRENCIA)
    tasks = [processar_host(h, sem) for h in lista]
    resultados: List[Dict] = []
    for coro in asyncio.as_completed(tasks):
        r = await coro
        if r: resultados.append(r)

    # **Escrita FINAL** na ORDEM exata que o seu front usa
    header = ["Servidor","Versão","Jogadores Online","Origem","Observação"]
    with open(CSV_SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in resultados:
            try:
                r["Jogadores Online"] = int(r.get("Jogadores Online", 0))
            except:
                r["Jogadores Online"] = 0
            w.writerow(r)

    # Mostra no log as 2 primeiras linhas do CSV (pra você confirmar a ORDEM)
    with open(CSV_SAIDA, "r", encoding="utf-8") as f:
        linhas = [next(f).rstrip("\n") for _ in range(2) if not f.closed]
    print("\n# Preview resultado_validado.csv (2 linhas):")
    for ln in linhas:
        print(ln)

    print(f"\n✅ '{CSV_SAIDA}' gerado com {len(resultados)} linhas.")

if __name__ == "__main__":
    asyncio.run(main())
