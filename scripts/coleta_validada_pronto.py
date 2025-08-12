# coleta_status_definitivo.py
# Coleta robusta via Status Protocol (TFS 7171) com verificação opcional por lista de players
# Saídas: ranking_final.xlsx (abas: Socket, Suspeitas) e resultado_validado.csv
# Autor: você (com carinho)

import asyncio
import socket
import struct
import sys
import re
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import pandas as pd
from collections import Counter

# ==========================
# Configurações
# ==========================
ARQ_ENTRADA = "servidores_otserv_socket.txt"
CSV_SAIDA = "resultado_validado.csv"
XLSX_SAIDA = "ranking_final.xlsx"

TIMEOUT_S = 4.5            # timeout por conexão
CONCORRENCIA = 80          # quantas consultas em paralelo
AMOSTRA_PLAYERS = 80       # quantos nomes coletar no modo "lista estendida" (para não explodir memória)
FAZER_VERIFICACAO_LISTA_SE_SUSPEITO = True
ESPERA_ANTES_DA_LISTA_S = 5.2  # recomendação da comunidade: ~5s entre status calls do mesmo host

# Se quiser testar portas alternativas (alguns trocam a porta do status)
PORTAS_PADRAO = [7171]

# Heurísticas simples de suspeita
def avalia_suspeita(online: int, nomes: List[str]) -> Tuple[bool, str]:
    """
    Regras simples: muitos duplicados, padrões artificiais de nomes,
    ou lista vazia quando online alto.
    """
    if online <= 0:
        return (False, "")

    if not nomes and online >= 50:
        return (True, "Sem lista estendida mesmo com online alto")

    if nomes:
        # duplicados
        dup_ratio = 0.0
        c = Counter(nomes)
        dups = sum(1 for n, q in c.items() if q > 1)
        if len(nomes) > 0:
            dup_ratio = dups / len(nomes)

        # padrões muito robóticos: ex.: Nome12345, Player000X etc.
        robo_like = sum(bool(re.search(r"(player|test|acc|char|bot)\d{2,}$", n, re.I)) for n in nomes)
        robo_ratio = robo_like / max(1, len(nomes))

        # nomes com muitas repetições de mesmo prefixo
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
            motivos.append(f"muitos nomes com mesmo prefixo (~{pref_ratio:.0%})")

        return (suspeito, "; ".join(motivos))
    return (False, "")

# ==========================
# Protocolo Status TFS
# ==========================
# Pacote: [len_u16 little endian] [0xFF] [0x01] [FLAG] [0x00,0x00,0x00]
# FLAGS:
# 0x08 Players Info (online, max, record)
# 0x20 Extended Players List (players: count + (name_u16 + level_u32)*N)
# 0x10 Map Info; 0x2B bloco Software Info (via flag 0x80)
# 0x80 Software Info (name/version/version_str)
# Referência comunidade: OTLand - Advanced Status/Players List. (enviar consultas com intervalo para não tomar bloqueio)

def make_packet(flag: int) -> bytes:
    payload = bytes([0xFF, 0x01, flag, 0x00, 0x00, 0x00])
    return struct.pack("<H", len(payload)) + payload  # little-endian length

class Buf:
    def __init__(self, data: bytes):
        self.d = memoryview(data)
        self.i = 0
    def left(self) -> int:
        return len(self.d) - self.i
    def u8(self) -> int:
        v = self.d[self.i]
        self.i += 1
        return int(v)
    def u16(self) -> int:
        v = struct.unpack_from("<H", self.d, self.i)[0]
        self.i += 2
        return v
    def u32(self) -> int:
        v = struct.unpack_from("<I", self.d, self.i)[0]
        self.i += 4
        return v
    def str16(self) -> str:
        ln = self.u16()
        if ln <= 0:
            return ""
        v = bytes(self.d[self.i:self.i+ln]).decode("utf-8", errors="ignore")
        self.i += ln
        return v

def parse_status_response(data: bytes) -> Dict:
    """
    Remove o length inicial (2 bytes) e interpreta blocos:
      0x20 => players info (online, max, record)
      0x21 => players list (count + (name,level)*N)
      0x10 => basic server info (name, ip, loginPort como string)
      0x2B => software info (name, version, version_str)
      0x30 => map info (name, author, size_u16,u16)
      0x11 / 0x12 => owner/misc
    """
    out = {
        "players_info": None,    # (online, max, record)
        "players_list": [],      # [(name, level), ...]
        "basic_info": {},        # name, ip, login_port
        "software_info": {},     # name, version, version_str
        "map_info": {},          # name, author, size
    }
    if len(data) < 3:
        return out

    # remove u16 length
    data = data[2:]
    b = Buf(data)

    while b.left() > 0:
        code = b.u8()
        if code == 0x20:
            online = b.u32()
            maxp = b.u32()
            record = b.u32()
            out["players_info"] = (online, maxp, record)
        elif code == 0x21:
            count = b.u32()
            lst = []
            for _ in range(count):
                nm = b.str16()
                lvl = b.u32()
                lst.append((nm, lvl))
            out["players_list"] = lst
        elif code == 0x10:
            name = b.str16()
            ip = b.str16()
            login_port = b.str16()  # em muitos TFS vem como string
            out["basic_info"] = {"name": name, "ip": ip, "login_port": login_port}
        elif code == 0x2B:
            sname = b.str16()
            vers = b.str16()
            vstr = b.str16()
            out["software_info"] = {"name": sname, "version": vers, "version_str": vstr}
        elif code == 0x30:
            mname = b.str16()
            author = b.str16()
            sx = b.u16()
            sy = b.u16()
            out["map_info"] = {"name": mname, "author": author, "size": f"{sx}x{sy}"}
        else:
            # blocos 0x11, 0x12 etc. (owner/misc) têm strings e inteiros variados; pulamos de forma segura
            # Como não sabemos o layout exato aqui, tentamos consumir cautelosamente algo:
            # Esses blocos vêm em sequência; se falhar parsing exato, quebramos o loop
            # para não corromper processamento.
            # (opcional: implementar quando houver necessidade)
            pass

    return out

async def fetch_once(host: str, port: int, flag: int) -> Optional[bytes]:
    """
    Abre conexão TCP e envia 1 requisição de status (flag).
    """
    try:
        # socket.create_connection dentro threadpool para resolver IPv4/6 e respeitar timeout
        loop = asyncio.get_running_loop()
        def _do():
            with socket.create_connection((host, port), timeout=TIMEOUT_S) as s:
                s.settimeout(TIMEOUT_S)
                s.sendall(make_packet(flag))
                chunks = []
                while True:
                    try:
                        chunk = s.recv(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                    except socket.timeout:
                        break
                return b"".join(chunks)
        data = await loop.run_in_executor(None, _do)
        return data if data else None
    except Exception:
        return None

async def consulta_status(host: str, porta: int) -> Tuple[Optional[Tuple[int,int,int]], Dict, List[Tuple[str,int]]]:
    """
    Retorna:
      - players_info (online,max,record) ou None
      - software_info dict
      - amostra de players_list (até AMOSTRA_PLAYERS) (pode ser vazia)
    """
    # 1) Players Info
    data = await fetch_once(host, porta, 0x08)  # players info
    players_info = None
    software_info = {}
    sample_players: List[Tuple[str,int]] = []

    if data:
        parsed = parse_status_response(data)
        players_info = parsed.get("players_info")
        # tentar extrair software num segundo passo só se necessário
        # (muitos servidores não liberam 0x80; então é "best-effort")
        # Se players_info veio, tentamos software_info numa segunda chamada, com pausa
        if players_info:
            await asyncio.sleep(ESPERA_ANTES_DA_LISTA_S)  # respeitar statusTimeout
            data_sw = await fetch_once(host, porta, 0x80)  # software info
            if data_sw:
                p2 = parse_status_response(data_sw)
                software_info = p2.get("software_info") or {}
        return players_info, software_info, sample_players

    # Falhou players info; pode ser bloqueado. Tentamos software_info só para confirmar vida
    data_sw = await fetch_once(host, porta, 0x80)
    if data_sw:
        p2 = parse_status_response(data_sw)
        software_info = p2.get("software_info") or {}

    return None, software_info, sample_players

async def consulta_validacao_lista(host: str, porta: int, online: int) -> List[Tuple[str,int]]:
    """
    Busca lista estendida (nomes+níveis). Requer espera entre chamadas.
    """
    await asyncio.sleep(ESPERA_ANTES_DA_LISTA_S)
    data = await fetch_once(host, porta, 0x20)  # extended players list
    if not data:
        return []
    parsed = parse_status_response(data)
    lst = parsed.get("players_list") or []
    if not lst:
        return []
    # reduz amostra
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
        players_info, software_info, sample_players = await consulta_status(host, porta)

    observacao = ""
    origem = "Socket"
    versao_str = ""
    if software_info:
        # servir como "Versão"
        for k in ("version", "version_str"):
            if software_info.get(k):
                versao_str = software_info[k]
                break

    if not players_info:
        # tentar nas portas alternativas, se definido
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

    # verificação via lista estendida (opcional, só quando fizer sentido)
    nomes = []
    if FAZER_VERIFICACAO_LISTA_SE_SUSPEITO and online >= 100:
        async with sem:
            lst = await consulta_validacao_lista(host, porta, online)
        nomes = [n for (n,_lvl) in lst]

    suspeito, motivo = avalia_suspeita(online, nomes)
    if suspeito:
        observacao = f"SUSPEITA: {motivo}"

    return {
        "Servidor": f"{host}:{porta}",
        "Jogadores Online": int(online),
        "Max": int(maxp),
        "Record": int(record),
        "Versão": versao_str or "",
        "Origem": origem,
        "Observação": observacao,
        "AmostraJogadores": ", ".join(nomes) if nomes else "",
    }

async def main():
    entrada = Path(ARQ_ENTRADA)
    if not entrada.exists():
        print(f"Arquivo de entrada não encontrado: {ARQ_ENTRADA}")
        sys.exit(1)

    servidores = [l.strip() for l in entrada.read_text(encoding="utf-8").splitlines() if l.strip()]
    # dedup mantendo ordem
    seen = set()
    srv = []
    for s in servidores:
        if s not in seen:
            seen.add(s)
            srv.append(s)

    sem = asyncio.Semaphore(CONCORRENCIA)
    tasks = [processar_host(h, sem) for h in srv]
    resultados: List[Dict] = []
    pendentes: List[str] = []

    for coro in asyncio.as_completed(tasks):
        res = await coro
        if not res:
            continue
        resultados.append(res)
        if res.get("Origem") == "Pendência":
            pendentes.append(res.get("Servidor",""))

        print(f"OK: {res.get('Servidor')} => {res.get('Jogadores Online')} ({res.get('Versão','')}) {res.get('Observação','')}")

    # DataFrames
    df = pd.DataFrame(resultados)

    # Socket confiável
    df_socket = df[df["Origem"] == "Socket"].sort_values(by=["Jogadores Online"], ascending=False, na_position='last')
    # Suspeitas separadas
    df_sus = df_socket[df_socket["Observação"].str.contains("SUSPEITA", na=False)]
    # Pendências
    df_pend = df[df["Origem"] == "Pendência"]

    # CSV geral
    cols_csv = ["Servidor","Jogadores Online","Max","Record","Versão","Origem","Observação","AmostraJogadores"]
    df[cols_csv].to_csv(CSV_SAIDA, index=False, encoding="utf-8")

    # XLSX com abas
    with pd.ExcelWriter(XLSX_SAIDA, engine="openpyxl") as writer:
        df_socket.to_excel(writer, index=False, sheet_name="Socket")
        if not df_sus.empty:
            df_sus.to_excel(writer, index=False, sheet_name="Suspeitas")
        if not df_pend.empty:
            df_pend.to_excel(writer, index=False, sheet_name="Pendencias")

    print(f"\n✅ Planilha gerada: {XLSX_SAIDA}")
    print(f"✅ CSV gerado: {CSV_SAIDA}")
    print(f"ℹ️  Socket OK: {len(df_socket)} | Suspeitas: {len(df_sus)} | Pendências: {len(df_pend)}")

if __name__ == "__main__":
    asyncio.run(main())
