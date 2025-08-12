# scripts/coleta_validada_pronto.py
# Coleta via Status Protocol (7171/variantes) com leitura "exact length"
# Saídas:
#   - resultado_validado_detalhado.csv  (com Max/Record etc.)
#   - ranking_site.csv                  (compatível com o layout do seu site)
#   - ranking_final.xlsx                (se openpyxl/xlsxwriter disponíveis)

import asyncio
import socket
import struct
import sys
import re
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import pandas as pd
from collections import Counter

# ===== XLSX engines (fallback) =====
try:
    import openpyxl  # noqa
    HAVE_OPENPYXL = True
except Exception:
    HAVE_OPENPYXL = False

try:
    import xlsxwriter  # noqa
    HAVE_XLSXWRITER = True
except Exception:
    HAVE_XLSXWRITER = False

# ==========================
# Configurações
# ==========================
ARQ_ENTRADA = "servidores_otserv_socket.txt"
CSV_DETALHADO = "resultado_validado_detalhado.csv"  # novo nome p/ não conflitar
CSV_SITE = "ranking_site.csv"                        # ordem compatível com seu front
XLSX_SAIDA = "ranking_final.xlsx"

TIMEOUT_S = 4.5
CONCORRENCIA = 60
PORTAS_PADRAO = [7171, 7170, 7172, 7010]

FAZER_VERIFICACAO_LISTA_SE_SUSPEITO = True
AMOSTRA_PLAYERS = 80
ESPERA_ANTES_DA_LISTA_S = 5.2  # intervalo mínimo entre chamadas de status no mesmo host

# ==========================
# Heurística de suspeita
# ==========================
def avalia_suspeita(online: int, nomes: List[str]) -> Tuple[bool, str]:
    if online <= 0:
        return (False, "")
    if not nomes and online >= 50:
        return (True, "Sem lista estendida mesmo com online alto")
    if nomes:
        c = Counter(nomes)
        dups = sum(1 for n, q in c.items() if q > 1)
        dup_ratio = dups / max(1, len(nomes))
        robo_like = sum(bool(re.search(r"(player|test|acc|char|bot)\d{2,}$", n, re.I)) for n in nomes)
        robo_ratio = robo_like / max(1, len(nomes))
        prefixes = [n[:4].lower() for n in nomes if len(n) >= 4]
        pref_common = Counter(prefixes).most_common(1)
        pref_ratio = (pref_common[0][1] / len(prefixes)) if prefixes else 0.0

        motivos = []
        suspeito = False
        if dup_ratio >= 0.20:
            suspeito = True
            motivos.append(f"muitos duplicados (~{dup_ratio:.0%})")
        if robo_ratio >= 0.25:
            suspeito = True
            motivos.append(f"padrão robótico (~{robo_ratio:.0%})")
        if online >= 150 and pref_ratio >= 0.40:
            suspeito = True
            motivos.append(f"prefixo repetido (~{pref_ratio:.0%})")
        return (suspeito, "; ".join(motivos))
    return (False, "")

# ==========================
# Montagem de pacote
# ==========================
def make_packet(flag: int) -> bytes:
    payload = bytes([0xFF, 0x01, flag, 0x00, 0x00, 0x00])
    return struct.pack("<H", len(payload)) + payload

# ==========================
# Buffer seguro
# ==========================
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
        self._need(1); v = self.d[self.i]; self.i += 1; return int(v)
    def u16(self) -> int:
        self._need(2); v = struct.unpack_from("<H", self.d, self.i)[0]; self.i += 2; return v
    def u32(self) -> int:
        self._need(4); v = struct.unpack_from("<I", self.d, self.i)[0]; self.i += 4; return v
    def str16(self) -> str:
        ln = self.u16(); self._need(ln)
        if ln <= 0: return ""
        v = bytes(self.d[self.i:self.i+ln]).decode("utf-8", errors="ignore")
        self.i += ln
        return v

# ==========================
# Parser defensivo
# ==========================
def parse_status_response(full_data: bytes) -> Dict:
    out = {
        "players_info": None,    # (online, max, record)
        "players_list": [],      # [(name, level), ...]
        "basic_info": {},
        "software_info": {},     # name, version, version_str
        "map_info": {},
    }
    if len(full_data) < 2:
        return out
    data = full_data[2:]  # remove u16 length
    b = Buf(data)

    while True:
        if b.left() <= 0:
            break
        try:
            code = b.u8()
        except ValueError:
            break
        try:
            if code == 0x20:  # Players Info
                online = b.u32(); maxp = b.u32(); record = b.u32()
                out["players_info"] = (online, maxp, record)
            elif code == 0x21:  # Extended Players List
                count = b.u32(); lst = []
                for _ in range(min(count, 5000)):
                    nm = b.str16(); lvl = b.u32()
                    lst.append((nm, lvl))
                out["players_list"] = lst
            elif code == 0x10:  # Basic Info
                name = b.str16(); ip = b.str16(); login_port = b.str16()
                out["basic_info"] = {"name": name, "ip": ip, "login_port": login_port}
            elif code == 0x2B:  # Software Info
                sname = b.str16(); vers = b.str16(); vstr = b.str16()
                out["software_info"] = {"name": sname, "version": vers, "version_str": vstr}
            elif code == 0x30:  # Map Info
                mname = b.str16(); author = b.str16(); sx = b.u16(); sy = b.u16()
                out["map_info"] = {"name": mname, "author": author, "size": f"{sx}x{sy}"}
            else:
                break  # bloco desconhecido → aborta parsing silenciosamente
        except ValueError:
            break  # bloco truncado → devolve o que já tem
    return out

# ==========================
# Recepção "exact length"
# ==========================
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
                if not hdr: return None
                (plen,) = struct.unpack("<H", hdr)
                if plen <= 0 or plen > 65535: return None
                payload = recv_exact(s, plen)
                if not payload: return None
                return hdr + payload
        return await loop.run_in_executor(None, _do)
    except Exception:
        return None

# ==========================
# Consultas
# ==========================
async def consulta_status(host: str, porta: int) -> Tuple[Optional[Tuple[int,int,int]], Dict, List[Tuple[str,int]]]:
    players_info = None
    software_info = {}
    sample_players: List[Tuple[str,int]] = []

    data = await fetch_once(host, porta, 0x08)
    if data:
        parsed = parse_status_response(data)
        players_info = parsed.get("players_info")
        if players_info:
            await asyncio.sleep(ESPERA_ANTES_DA_LISTA_S)
            data_sw = await fetch_once(host, porta, 0x80)
            if data_sw:
                p2 = parse_status_response(data_sw)
                software_info = p2.get("software_info") or {}
            return players_info, software_info, sample_players

    # sem players_info, tenta só software_info p/ detectar "vida"
    data_sw = await fetch_once(host, porta, 0x80)
    if data_sw:
        p2 = parse_status_response(data_sw)
        software_info = p2.get("software_info") or {}
    return None, software_info, sample_players

async def consulta_validacao_lista(host: str, porta: int) -> List[Tuple[str,int]]:
    await asyncio.sleep(ESPERA_ANTES_DA_LISTA_S)
    data = await fetch_once(host, porta, 0x20)
    if not data:
        return []
    p = parse_status_response(data)
    lst = p.get("players_list") or []
    return lst[:AMOSTRA_PLAYERS]

def parse_host_port(line: str) -> Tuple[str,int]:
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

async def processar_host(hostline: str, sem: asyncio.Semaphore) -> Dict:
    host, porta = parse_host_port(hostline)
    if not host:
        return {}

    async with sem:
        players_info, software_info, _ = await consulta_status(host, porta)

    versao_str = ""
    if software_info:
        for k in ("version", "version_str"):
            if software_info.get(k):
                versao_str = software_info[k]
                break

    if not players_info:
        for palt in PORTAS_PADRAO:
            if palt == porta:
                continue
            async with sem:
                players_info, software_info2, _ = await consulta_status(host, palt)
            if players_info:
                porta = palt
                if not versao_str and software_info2:
                    for k in ("version", "version_str"):
                        if software_info2.get(k):
                            versao_str = software_info2[k]
                            break
                break

    if not players_info:
        print(f"OK: {host}:{porta} => PENDENTE () Status bloqueado/indisponível")
        return {
            "Servidor": f"{host}:{porta}",
            "Jogadores Online": "PENDENTE",
            "Max": "",
            "Record": "",
            "Versão": versao_str or "",
            "Origem": "Pendência",
            "Observação": "Status bloqueado/indisponível",
            "AmostraJogadores": "",
        }

    online, maxp, record = players_info

    nomes = []
    if FAZER_VERIFICACAO_LISTA_SE_SUSPEITO and online >= 100:
        async with sem:
            lst = await consulta_validacao_lista(host, porta)
        nomes = [n for (n,_lvl) in lst]

    suspeito, motivo = avalia_suspeita(online, nomes)
    observacao = f"SUSPEITA: {motivo}" if suspeito else ""

    print(f"OK: {host}:{porta} => {online} ({versao_str}) {observacao}")
    return {
        "Servidor": f"{host}:{porta}",
        "Jogadores Online": int(online),
        "Max": int(maxp),
        "Record": int(record),
        "Versão": versao_str or "",
        "Origem": "Socket",
        "Observação": observacao,
        "AmostraJogadores": ", ".join(nomes) if nomes else "",
    }

async def main():
    entrada = Path(ARQ_ENTRADA)
    if not entrada.exists():
        print(f"Arquivo de entrada não encontrado: {ARQ_ENTRADA}")
        sys.exit(1)

    servidores = [l.strip() for l in entrada.read_text(encoding="utf-8").splitlines() if l.strip()]
    seen = set(); srv = []
    for s in servidores:
        if s not in seen:
            seen.add(s); srv.append(s)

    sem = asyncio.Semaphore(CONCORRENCIA)
    tasks = [processar_host(h, sem) for h in srv]
    resultados: List[Dict] = []
    for coro in asyncio.as_completed(tasks):
        res = await coro
        if res:
            resultados.append(res)

    df = pd.DataFrame(resultados)

    # -------- CSV detalhado (para auditoria) --------
    cols_detalhe = ["Servidor","Jogadores Online","Max","Record","Versão","Origem","Observação","AmostraJogadores"]
    df[cols_detalhe].to_csv(CSV_DETALHADO, index=False, encoding="utf-8")

    # -------- CSV do site (ordem compatível) --------
    def linha_site(row):
        # Jogadores Online no site deve ser número; se pendência, envia 0
        jog = row["Jogadores Online"]
        jog_num = int(jog) if isinstance(jog, (int, float)) and not pd.isna(jog) else 0
        if row["Origem"] != "Socket":
            jog_num = 0
        vers = str(row["Versão"]) if row["Versão"] is not None else ""
        return pd.Series({
            "Servidor": row["Servidor"],
            "Versão": vers,
            "Jogadores Online": jog_num,
            "Origem": row["Origem"],
            "Observação": row["Observação"] or ""
        })

    df_site = df.apply(linha_site, axis=1)
    # ordena por jogadores desc no site
    df_site = df_site.sort_values(by=["Jogadores Online"], ascending=False, na_position="last")
    df_site.to_csv(CSV_SITE, index=False, encoding="utf-8")

    # -------- XLSX (se possível) --------
    df_socket = df[df["Origem"] == "Socket"].sort_values(by=["Jogadores Online"], ascending=False, na_position='last')
    df_sus = df_socket[df_socket["Observação"].str.contains("SUSPEITA", na=False)]
    df_pend = df[df["Origem"] == "Pendência"]

    xlsx_ok = False
    try:
        if HAVE_OPENPYXL:
            with pd.ExcelWriter(XLSX_SAIDA, engine="openpyxl") as w:
                df_socket.to_excel(w, index=False, sheet_name="Socket")
                if not df_sus.empty: df_sus.to_excel(w, index=False, sheet_name="Suspeitas")
                if not df_pend.empty: df_pend.to_excel(w, index=False, sheet_name="Pendencias")
            xlsx_ok = True
        elif HAVE_XLSXWRITER:
            with pd.ExcelWriter(XLSX_SAIDA, engine="xlsxwriter") as w:
                df_socket.to_excel(w, index=False, sheet_name="Socket")
                if not df_sus.empty: df_sus.to_excel(w, index=False, sheet_name="Suspeitas")
                if not df_pend.empty: df_pend.to_excel(w, index=False, sheet_name="Pendencias")
            xlsx_ok = True
        else:
            print("⚠️ Nenhuma engine de XLSX instalada (openpyxl/xlsxwriter). Pulando XLSX.")
    except Exception as e:
        print(f"⚠️ Falha ao gerar XLSX: {e}. Seguindo com CSV apenas.")

    # Logs finais
    if xlsx_ok:
        print(f"\n✅ Planilha gerada: {XLSX_SAIDA}")
    print(f"✅ CSV detalhado: {CSV_DETALHADO}")
    print(f"✅ CSV do site: {CSV_SITE}")
    print(f"ℹ️  Socket OK: {len(df_socket)} | Suspeitas: {len(df_sus)} | Pendências: {len(df_pend)}")

if __name__ == "__main__":
    asyncio.run(main())
