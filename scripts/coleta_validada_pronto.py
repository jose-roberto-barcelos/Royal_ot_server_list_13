# scripts/coleta_validada_pronto.py
# Lê servidores_otserv_socket.txt -> gera resultado_validado.csv
# Colunas FIXAS (e nesta ordem): Servidor, Versão, Jogadores Online, Origem, Observação

import asyncio, socket, struct, sys, csv, re
from pathlib import Path
from typing import Optional, Tuple, List, Dict

ARQ_ENTRADA = "servidores_otserv_socket.txt"
CSV_SAIDA   = "resultado_validado.csv"

# ---------- Parâmetros ----------
TIMEOUT_S = 5.0
CONCORRENCIA = 80
# portas mais comuns + extras (tentamos nessa ordem)
PORTAS_PADRAO = [7171, 7170, 7172, 7010, 7173, 7174, 7000, 7001, 7002]
# tentar “auto-scan” leve? (tenta essas portas extras se nada respondeu)
AUTO_SCAN_PORTAS = [7175, 7176, 7177, 7178, 7179, 7180]
FAZER_AUTO_SCAN = True

# espera entre flags no MESMO host (evita anti-flood)
ESPERA_STATUS_S = 4.8

# checagem leve de lista estendida
FAZER_VERIF_LISTA_SE_SUSPEITO = True
AMOSTRA_PLAYERS = 80

OBS_BLOCKED = "Blocked"  # <- pedido do José

# ---------- Protocolo Status ----------
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
        try: code = b.u8()
        except ValueError: break
        try:
            if code == 0x20:  # Players Info
                out["players_info"] = (b.u32(), b.u32(), b.u32())
            elif code == 0x21:  # Extended Players List
                count = b.u32(); lst=[]
                for _ in range(min(count, 5000)):
                    lst.append((b.str16(), b.u32()))
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
        try: chunk = s.recv(n - len(data))
        except socket.timeout: return None
        if not chunk: return None
        data += chunk
    return bytes(data)

def all_addrinfo(host: str, port: int):
    """resolve IPv4 e IPv6, retornando uma lista de (family, sockaddr) únicos"""
    seen=set(); out=[]
    try:
        infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        for fam, _type, _proto, _canon, sa in infos:
            key=(fam,sa)
            if key not in seen:
                seen.add(key); out.append((fam, sa))
    except socket.gaierror:
        pass
    return out

async def fetch_once_addr(fam_sa, flag: int) -> Optional[bytes]:
    fam, sa = fam_sa
    try:
        loop = asyncio.get_running_loop()
        def _do():
            with socket.socket(fam, socket.SOCK_STREAM) as s:
                s.settimeout(TIMEOUT_S)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                try: s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                except Exception: pass
                s.connect(sa)
                s.sendall(make_packet(flag))
                hdr = recv_exact(s, 2)
                if not hdr: return None
                (plen,) = struct.unpack("<H", hdr)
                if plen <= 0 or plen > 65535: return None
                payload = recv_exact(s, plen)
                if not payload: return None
                return hdr + payload
        return await loop.run_in_executor(None, _do)
    except Exception:
        return None

async def fetch_status_flags(host: str, port: int) -> Tuple[Optional[bytes], Optional[bytes], Optional[bytes]]:
    """tenta 0x08 (players), 0x80 (software), 0x20 (list) em todos IPs do host (IPv4/IPv6) com retries"""
    addrs = all_addrinfo(host, port)
    if not addrs: return (None, None, None)
    # duas tentativas rápidas por IP
    for _try in (1, 2):
        for fam_sa in addrs:
            data_players = await fetch_once_addr(fam_sa, 0x08)
            data_soft    = await fetch_once_addr(fam_sa, 0x80) if data_players else None
            data_list    = await fetch_once_addr(fam_sa, 0x20) if data_players else None
            if data_players or data_soft or data_list:
                return (data_players, data_soft, data_list)
        await asyncio.sleep(0.35 * _try)  # pequeno backoff
    return (None, None, None)

async def consulta_em_porta(host: str, porta: int):
    dp, ds, dl = await fetch_status_flags(host, porta)
    if not (dp or ds or dl): 
        return None, {}, []
    p = {"players_info": None, "software_info": {}, "players_list": []}
    if dp:
        p.update(parse_status_response(dp))
    if ds:
        sm = parse_status_response(ds)
        if sm.get("software_info"): p["software_info"] = sm["software_info"]
    if dl:
        lm = parse_status_response(dl)
        if lm.get("players_list"): p["players_list"] = lm["players_list"]
    return p.get("players_info"), p.get("software_info") or {}, p.get("players_list") or []

def parse_host_port(line: str) -> Tuple[str,int]:
    line = line.strip()
    if not line: return ("", 0)
    if ":" in line:
        h, p = line.rsplit(":", 1)
        try: return (h.strip(), int(p))
        except: return (h.strip(), PORTAS_PADRAO[0])
    return (line, PORTAS_PADRAO[0])

async def tentar_host(host: str, porta_inicial: int):
    # 1) porta declarada
    pi, si, li = await consulta_em_porta(host, porta_inicial)
    if pi: return porta_inicial, pi, si, li

    # 2) portas padrão
    for p in PORTAS_PADRAO:
        if p == porta_inicial: continue
        pi, si, li = await consulta_em_porta(host, p)
        if pi: return p, pi, si, li

    # 3) auto-scan leve
    if FAZER_AUTO_SCAN:
        for p in AUTO_SCAN_PORTAS:
            pi, si, li = await consulta_em_porta(host, p)
            if pi: return p, pi, si, li

    return None, None, {}, []

async def processar_host(line: str, sem: asyncio.Semaphore) -> Dict:
    host, porta = parse_host_port(line)
    if not host: return {}

    async with sem:
        porta_ok, players_info, software_info, plist = await tentar_host(host, porta)

    versao_str = ""
    for k in ("version", "version_str"):
        if software_info.get(k):
            versao_str = software_info[k]; break

    if not players_info:
        print(f"OK: {host}:{porta} => PENDÊNCIA ({OBS_BLOCKED})")
        return {
            "Servidor": f"{host.lower()}:{porta}",
            "Versão": versao_str or "",
            "Jogadores Online": 0,
            "Origem": "Pendência",
            "Observação": OBS_BLOCKED,
        }

    online, _maxp, _record = players_info

    observacao = ""
    if FAZER_VERIF_LISTA_SE_SUSPEITO and online >= 120 and not plist:
        observacao = "SUSPEITA"

    porta_final = porta_ok if porta_ok else porta
    print(f"OK: {host}:{porta_final} => {online} ({versao_str})")
    return {
        "Servidor": f"{host.lower()}:{porta_final}",
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
    vistos=set(); lista=[]
    for s in servidores:
        if s not in vistos:
            vistos.add(s); lista.append(s)

    sem = asyncio.Semaphore(CONCORRENCIA)
    tasks = [processar_host(h, sem) for h in lista]
    res: List[Dict] = []
    for coro in asyncio.as_completed(tasks):
        r = await coro
        if r: res.append(r)

    header = ["Servidor","Versão","Jogadores Online","Origem","Observação"]
    with open(CSV_SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in res:
            try: r["Jogadores Online"] = int(r.get("Jogadores Online", 0))
            except: r["Jogadores Online"] = 0
            w.writerow(r)

    # Preview pra checar ordem
    with open(CSV_SAIDA, "r", encoding="utf-8") as f:
        print("\n# Preview resultado_validado.csv:")
        for i, ln in enumerate(f):
            print(ln.rstrip("\n"))
            if i >= 5: break

    print(f"\n✅ '{CSV_SAIDA}' gerado com {len(res)} linhas.")

if __name__ == "__main__":
    asyncio.run(main())
