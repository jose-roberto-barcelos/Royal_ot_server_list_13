# scripts/coleta_validada_pronto.py
# Só SOCKET. Lê servidores_otserv_socket.txt -> resultado_validado.csv
# Colunas FIXAS (e nesta ordem): Servidor, Versão, Jogadores Online, Origem, Observação

import asyncio, socket, struct, sys, csv
from pathlib import Path
from typing import Optional, Tuple, List, Dict

ARQ_ENTRADA = "servidores_otserv_socket.txt"
CSV_SAIDA   = "resultado_validado.csv"

# ---------- Parâmetros ----------
TIMEOUT_S = 5.0
CONCORRENCIA = 80

# Portas mais comuns / variantes
PORTAS_PADRAO = [7171, 7170, 7172, 7010, 7173, 7174, 7175, 7176, 7000, 7001, 7002]

# Overrides (se você souber portas específicas de alguns hosts, preencha aqui)
# Ex.: {"mega.server.com": [7999, 7171]}
PORTAS_POR_HOST: Dict[str, List[int]] = {}

# Espera entre flags (leve) para não tripar anti-flood
ESPERA_STATUS_S = 4.5

OBS_BLOCKED = "Blocked"

# ---------- Protocolo Status ----------
def make_payload(flag: int) -> bytes:
    # Conteúdo do pacote de status (sem o prefixo de tamanho)
    return bytes([0xFF, 0x01, flag, 0x00, 0x00, 0x00])

def frame_le(payload: bytes) -> bytes:
    return struct.pack("<H", len(payload)) + payload

def frame_be(payload: bytes) -> bytes:
    return struct.pack(">H", len(payload)) + payload

class Buf:
    def __init__(self, data: bytes):
        self.d = memoryview(data); self.i = 0
    def left(self): return len(self.d) - self.i
    def need(self, n):
        if self.left() < n: raise ValueError("short")
    def u8(self):  self.need(1);  v=self.d[self.i]; self.i+=1; return int(v)
    def u16(self): self.need(2);  v=struct.unpack_from("<H", self.d, self.i)[0]; self.i+=2; return v
    def u32(self): self.need(4);  v=struct.unpack_from("<I", self.d, self.i)[0]; self.i+=4; return v
    def str16(self):
        ln = self.u16(); self.need(ln)
        if ln <= 0: return ""
        v = bytes(self.d[self.i:self.i+ln]).decode("utf-8", errors="ignore")
        self.i += ln; return v

def parse_status_response(pkt: bytes) -> Dict:
    """
    Aceita tanto [lenLE][payload] quanto [lenBE][payload].
    Se os 2 primeiros bytes não baterem, tenta tratar como payload direto.
    """
    if len(pkt) < 2:
        return {"players_info": None, "players_list": [], "software_info": {}}

    def _parse(payload: bytes) -> Dict:
        out = {"players_info": None, "players_list": [], "software_info": {}}
        b = Buf(payload)
        while b.left() > 0:
            try:
                code = b.u8()
            except ValueError:
                break
            try:
                if code == 0x20:  # Players Info
                    out["players_info"] = (b.u32(), b.u32(), b.u32())
                elif code == 0x21:  # Extended Players List
                    count = b.u32(); lst=[]
                    for _ in range(min(count, 5000)):
                        lst.append((b.str16(), b.u32()))
                    out["players_list"] = lst
                elif code == 0x2B:  # Software Info
                    out["software_info"] = {
                        "name": b.str16(), "version": b.str16(), "version_str": b.str16()
                    }
                else:
                    # bloco desconhecido: aborta silencioso
                    break
            except ValueError:
                break
        return out

    # tenta LE
    try:
        (plen,) = struct.unpack_from("<H", pkt, 0)
        if 0 < plen <= 65535 and 2+plen <= len(pkt):
            return _parse(pkt[2:2+plen])
    except Exception:
        pass
    # tenta BE
    try:
        (plen,) = struct.unpack_from(">H", pkt, 0)
        if 0 < plen <= 65535 and 2+plen <= len(pkt):
            return _parse(pkt[2:2+plen])
    except Exception:
        pass
    # payload direto
    return _parse(pkt)

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

async def send_status_and_read(fam: int, sa, framed_payload: bytes) -> Optional[bytes]:
    try:
        loop = asyncio.get_running_loop()
        def _do():
            with socket.socket(fam, socket.SOCK_STREAM) as s:
                s.settimeout(TIMEOUT_S)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                try: s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                except Exception: pass
                s.connect(sa)
                s.sendall(framed_payload)
                # lê sempre pelo menos 2 bytes (header), depois o resto
                hdr = recv_exact(s, 2)
                if not hdr:
                    return None
                (plen_le,) = struct.unpack("<H", hdr)
                if not (0 < plen_le <= 65535):
                    # pode ser BE; tenta ler como se fosse BE
                    (plen_be,) = struct.unpack(">H", hdr)
                    if not (0 < plen_be <= 65535):
                        return hdr  # devolve o que tem; parser tenta payload direto
                    payload = recv_exact(s, plen_be)
                    if not payload:
                        return None
                    return hdr + payload
                payload = recv_exact(s, plen_le)
                if not payload:
                    return None
                return hdr + payload
        return await loop.run_in_executor(None, _do)
    except Exception:
        return None

def all_addrinfo(host: str, port: int):
    seen=set(); out=[]
    try:
        for fam, _type, _proto, _canon, sa in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
            key=(fam,sa)
            if key not in seen:
                seen.add(key); out.append((fam, sa))
    except socket.gaierror:
        pass
    return out

async def try_status_on_ip(fam: int, sa) -> Dict:
    # tenta com length LE e BE
    payload = make_payload(0x08)  # players
    for framer in (frame_le, frame_be):
        pkt = await send_status_and_read(fam, sa, framer(payload))
        if pkt:
            return parse_status_response(pkt)
    return {"players_info": None, "players_list": [], "software_info": {}}

async def consulta_status(host: str, port: int):
    """Tenta players (0x08), depois software (0x80) e list (0x20) no mesmo IP."""
    addrs = all_addrinfo(host, port)
    if not addrs:
        return None, {}
    # duas tentativas por IP com backoff leve
    for attempt in (1, 2):
        for fam, sa in addrs:
            # 1) Players
            res = await try_status_on_ip(fam, sa)
            players = res.get("players_info")
            software = res.get("software_info") or {}
            if players:
                # 2) tenta software e lista no mesmo IP (sem travar o rápido)
                await asyncio.sleep(ESPERA_STATUS_S)
                for flag in (0x80, 0x20):
                    payload = make_payload(flag)
                    ok = None
                    for framer in (frame_le, frame_be):
                        ok = await send_status_and_read(fam, sa, framer(payload))
                        if ok: break
                    if ok:
                        parsed = parse_status_response(ok)
                        if flag == 0x80 and parsed.get("software_info"):
                            software = parsed["software_info"]
                        # lista é opcional; não influencia retorno principal
                return players, software
        await asyncio.sleep(0.35 * attempt)
    return None, {}

def parse_host_port(line: str) -> Tuple[str,int]:
    line = line.strip()
    if not line:
        return ("", 0)
    if ":" in line:
        h, p = line.rsplit(":", 1)
        try:
            return (h.strip().lower(), int(p))
        except:
            return (h.strip().lower(), PORTAS_PADRAO[0])
    return (line.lower(), PORTAS_PADRAO[0])

def portas_para_host(host: str, porta_inicial: int) -> List[int]:
    # prioridade: porta informada -> overrides -> padrão
    base = []
    if porta_inicial not in base:
        base.append(porta_inicial)
    if host in PORTAS_POR_HOST:
        for p in PORTAS_POR_HOST[host]:
            if p not in base:
                base.append(p)
    for p in PORTAS_PADRAO:
        if p not in base:
            base.append(p)
    return base

async def processar_host(line: str, sem: asyncio.Semaphore) -> Dict:
    host, porta_hint = parse_host_port(line)
    if not host:
        return {}

    portas = portas_para_host(host, porta_hint)

    players_info = None
    software_info: Dict = {}
    porta_ok = porta_hint

    async with sem:
        for p in portas:
            pi, si = await consulta_status(host, p)
            if pi:
                players_info, software_info, porta_ok = pi, si, p
                break

    versao = ""
    for k in ("version", "version_str"):
        if software_info.get(k):
            versao = software_info[k]; break

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
    print(f"OK: {host}:{porta_ok} => {online} ({versao})")
    return {
        "Servidor": f"{host}:{porta_ok}",
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

    servidores = [l.strip() for l in entrada.read_text(encoding="utf-8").splitlines() if l.strip()]
    # remove duplicados preservando ordem
    seen=set(); lst=[]
    for s in servidores:
        if s not in seen:
            seen.add(s); lst.append(s)

    sem = asyncio.Semaphore(CONCORRENCIA)
    tasks = [processar_host(s, sem) for s in lst]
    resultados: List[Dict] = []
    for coro in asyncio.as_completed(tasks):
        r = await coro
        if r: resultados.append(r)

    # escreve CSV com ordem fixa
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

    # preview
    try:
        with open(CSV_SAIDA, "r", encoding="utf-8") as f:
            print("\n# Preview resultado_validado.csv:")
            for i, ln in enumerate(f):
                print(ln.rstrip("\n"))
                if i >= 5: break
    except Exception:
        pass

    print(f"\n✅ '{CSV_SAIDA}' gerado com {len(resultados)} linhas.")

if __name__ == "__main__":
    asyncio.run(main())
