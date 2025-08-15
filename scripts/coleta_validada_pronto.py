# scripts/coleta_validada_pronto.py
# Só SOCKET. Lê servidores_otserv_socket.txt -> resultado_validado.csv
# Colunas (fixas): Servidor, Versão, Jogadores Online, Origem, Observação

import asyncio, socket, struct, sys, csv, os, urllib.parse
from pathlib import Path
from typing import Optional, Tuple, List, Dict

ARQ_ENTRADA = "servidores_otserv_socket.txt"
CSV_SAIDA   = "resultado_validado.csv"

# ---- Parâmetros ----
CONNECT_TIMEOUT = 2.5         # conexão
READ_TIMEOUT    = 2.5         # leitura
CONCORRENCIA    = 120         # hosts simultâneos

# portas mais comuns (rodamos TODAS em paralelo por host)
PORTAS_PADRAO = [7171, 7170, 7172, 7010, 7173, 7174, 7175, 7176, 7000, 7001, 7002]

# overrides específicos (se quiser forçar portas de certos hosts)
PORTAS_POR_HOST: Dict[str, List[int]] = {
    # "megaserv.com": [7999, 7171],
}

# espera leve entre flags no MESMO IP (evita anti-flood)
ESPERA_FLAGS_S = 0.25

OBS_BLOCKED = "Blocked"

# ---- Proxy SOCKS5 opcional ----
SOCKS5_URL = os.getenv("SOCKS5_PROXY", "").strip()
USE_SOCKS = False
SOCKS_KW = {}
try:
    import socks  # PySocks
    if SOCKS5_URL:
        u = urllib.parse.urlparse(SOCKS5_URL)
        if u.scheme.startswith("socks5") and u.hostname and u.port:
            USE_SOCKS = True
            SOCKS_KW = dict(
                proxy_type=socks.SOCKS5,
                addr=u.hostname,
                port=u.port,
                username=u.username,
                password=u.password,
            )
except Exception:
    USE_SOCKS = False

# ---- framing/status ----
def _payload(flag: int) -> bytes:
    return bytes([0xFF, 0x01, flag, 0x00, 0x00, 0x00])

def _frame_le(b: bytes) -> bytes: return struct.pack("<H", len(b)) + b
def _frame_be(b: bytes) -> bytes: return struct.pack(">H", len(b)) + b

class Buf:
    def __init__(self, data: bytes): self.d=memoryview(data); self.i=0
    def left(self): return len(self.d)-self.i
    def need(self,n): 
        if self.left()<n: raise ValueError("short")
    def u8(self):  self.need(1); v=self.d[self.i]; self.i+=1; return int(v)
    def u16(self): self.need(2); v=struct.unpack_from("<H", self.d, self.i)[0]; self.i+=2; return v
    def u32(self): self.need(4); v=struct.unpack_from("<I", self.d, self.i)[0]; self.i+=4; return v
    def s16(self):
        ln=self.u16(); self.need(ln)
        if ln<=0: return ""
        v=bytes(self.d[self.i:self.i+ln]).decode("utf-8", errors="ignore"); self.i+=ln; return v

def _parse(pkt: bytes) -> Dict:
    out={"players_info":None,"players_list":[],"software_info":{}}
    if len(pkt)<2: return out
    # tenta como [lenLE][payload], depois [lenBE], depois payload cru
    for as_be in (False, True, None):
        try:
            b = None
            if as_be is False:
                (plen,) = struct.unpack_from("<H", pkt, 0)
                if 0<plen<=65535 and 2+plen<=len(pkt): b = Buf(pkt[2:2+plen])
            elif as_be is True:
                (plen,) = struct.unpack_from(">H", pkt, 0)
                if 0<plen<=65535 and 2+plen<=len(pkt): b = Buf(pkt[2:2+plen])
            else:
                b = Buf(pkt)
            if not b: continue
            while b.left()>0:
                code=b.u8()
                if code==0x20:
                    out["players_info"]=(b.u32(), b.u32(), b.u32())
                elif code==0x21:
                    n=b.u32(); lst=[]
                    for _ in range(min(n,5000)):
                        lst.append((b.s16(), b.u32()))
                    out["players_list"]=lst
                elif code==0x2B:
                    out["software_info"]={"name":b.s16(),"version":b.s16(),"version_str":b.s16()}
                else:
                    break
            return out
        except Exception:
            continue
    return out

def _recv_exact(s: socket.socket, n: int) -> Optional[bytes]:
    data=bytearray()
    while len(data)<n:
        try:
            chunk=s.recv(n-len(data))
        except socket.timeout:
            return None
        if not chunk: return None
        data+=chunk
    return bytes(data)

def _make_socket(fam: int) -> socket.socket:
    if USE_SOCKS:
        sock = socks.socksocket(fam, socket.SOCK_STREAM)
        sock.set_proxy(**SOCKS_KW)
    else:
        sock = socket.socket(fam, socket.SOCK_STREAM)
    sock.settimeout(CONNECT_TIMEOUT)
    try: sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception: pass
    try: sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except Exception: pass
    return sock

async def _send_and_read(fam: int, sa, framed: bytes) -> Optional[bytes]:
    try:
        loop = asyncio.get_running_loop()
        def _do():
            with _make_socket(fam) as s:
                s.connect(sa)
                s.settimeout(READ_TIMEOUT)
                s.sendall(framed)
                hdr=_recv_exact(s,2)
                if not hdr: return None
                # tenta ler resto como LE, senão BE, senão devolve hdr (parser tenta cru)
                try:
                    (plen,) = struct.unpack("<H", hdr); payload=_recv_exact(s, plen)
                    if payload: return hdr+payload
                except Exception: pass
                try:
                    (plen,) = struct.unpack(">H", hdr); payload=_recv_exact(s, plen)
                    if payload: return hdr+payload
                except Exception: pass
                return hdr
        return await loop.run_in_executor(None, _do)
    except Exception:
        return None

def _addrinfo(host: str, port: int):
    out=[]
    try:
        for fam, _t, _p, _c, sa in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
            out.append((fam, sa))
    except socket.gaierror:
        pass
    # remove duplicados mantendo ordem
    seen=set(); uniq=[]
    for it in out:
        if it not in seen:
            seen.add(it); uniq.append(it)
    return uniq

async def _query_one_ip(fam:int, sa) -> Optional[Tuple[Tuple[int,int,int], Dict]]:
    # 0x08 (players) com LE, se falhar tenta BE; depois tenta 0x80 (software)
    p=_payload(0x08)
    for framer in (_frame_le, _frame_be):
        pkt = await _send_and_read(fam, sa, framer(p))
        if pkt:
            res=_parse(pkt)
            if res.get("players_info"):
                # tenta software rapidinho
                await asyncio.sleep(ESPERA_FLAGS_S)
                ps=_payload(0x80)
                for fr in (_frame_le, _frame_be):
                    pkt2 = await _send_and_read(fam, sa, fr(ps))
                    if pkt2:
                        sw=_parse(pkt2).get("software_info") or {}
                        return res["players_info"], sw
                return res["players_info"], {}
    return None

async def _query_port(host: str, port: int) -> Optional[Tuple[int, Tuple[int,int,int], Dict]]:
    addrs = _addrinfo(host, port)
    if not addrs:
        return None
    # corre IPs do host em paralelo; pega o primeiro que responder
    tasks = [asyncio.create_task(_query_one_ip(fam, sa)) for fam, sa in addrs]
    try:
        while tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                res = t.result()
                if res:
                    # cancela o resto
                    for p in pending: p.cancel()
                    players, sw = res
                    return port, players, sw
            tasks = list(pending)
    except Exception:
        pass
    finally:
        for t in tasks: t.cancel()
    return None

def _parse_host_port(line: str) -> Tuple[str,int]:
    line=line.strip()
    if not line: return ("", 0)
    if ":" in line:
        h,p=line.rsplit(":",1)
        try: return (h.strip().lower(), int(p))
        except: return (h.strip().lower(), 7171)
    return (line.lower(), 7171)

def _portlist_for(host: str, hint: int) -> List[int]:
    base=[]
    if hint not in base: base.append(hint)
    for p in PORTAS_POR_HOST.get(host, []):
        if p not in base: base.append(p)
    for p in PORTAS_PADRAO:
        if p not in base: base.append(p)
    return base

async def processar_host(line: str, sem: asyncio.Semaphore) -> Dict:
    host, porta_hint = _parse_host_port(line)
    if not host: return {}

    portas = _portlist_for(host, porta_hint)

    async with sem:
        # tenta TODAS as portas em paralelo e pega a 1ª que responder
        port_tasks = [asyncio.create_task(_query_port(host, p)) for p in portas]
        porta_ok, players_info, swinfo = None, None, {}
        try:
            while port_tasks:
                done, pending = await asyncio.wait(port_tasks, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    res = t.result()
                    if res:
                        porta_ok, players_info, swinfo = res
                        for p in pending: p.cancel()
                        port_tasks = []
                        break
                port_tasks = list(pending)
        finally:
            for t in port_tasks: t.cancel()

    versao=""
    for k in ("version","version_str"):
        if swinfo.get(k):
            versao = swinfo[k]; break

    if not players_info:
        print(f"OK: {host}:{porta_hint} => PENDÊNCIA ({OBS_BLOCKED})")
        return {
            "Servidor": f"{host}:{porta_hint}",
            "Versão": versao,
            "Jogadores Online": 0,
            "Origem": "Pendência",
            "Observação": OBS_BLOCKED,
        }

    online, _maxp, _rec = players_info
    print(f"OK: {host}:{(porta_ok or porta_hint)} => {online} ({versao})")
    return {
        "Servidor": f"{host}:{(porta_ok or porta_hint)}",
        "Versão": versao,
        "Jogadores Online": int(online),
        "Origem": "Socket",
        "Observação": "",
    }

async def main():
    entrada = Path(ARQ_ENTRADA)
    if not entrada.exists():
        print(f"❌ Arquivo de entrada não encontrado: {ARQ_ENTRADA}")
        sys.exit(1)

    servidores=[l.strip() for l in entrada.read_text(encoding="utf-8").splitlines() if l.strip()]
    seen=set(); lista=[]
    for s in servidores:
        if s not in seen:
            seen.add(s); lista.append(s)

    sem = asyncio.Semaphore(CONCORRENCIA)
    tasks=[processar_host(s, sem) for s in lista]
    resultados=[]
    for coro in asyncio.as_completed(tasks):
        r=await coro
        if r: resultados.append(r)

    header=["Servidor","Versão","Jogadores Online","Origem","Observação"]
    with open(CSV_SAIDA,"w",newline="",encoding="utf-_
