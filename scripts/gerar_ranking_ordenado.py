# scripts/gerar_ranking_ordenado.py
# Lê resultado_validado.csv e gera ranking_final.csv
# Regras:
#  - prioriza Origem=Socket, depois HTML, depois outros
#  - ordena por Jogadores Online (desc) e, em empate, por Servidor (asc)
#  - força a ORDEM DE COLUNAS: Servidor, Versão, Jogadores Online, Origem, Observação
#  - escreve timestamp na 1a linha começando com "# "

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

IN_ARQ  = Path("resultado_validado.csv")
OUT_ARQ = Path("ranking_final.csv")

def to_int(v):
    try:
        if pd.isna(v):
            return 0
        s = str(v).strip().replace(",", ".")
        if s == "":
            return 0
        return int(float(s))
    except Exception:
        return 0

def origem_prio(v: str) -> int:
    v = (v or "").strip().lower()
    if v == "socket": return 0
    if v == "html":   return 1
    return 2

def main():
    if not IN_ARQ.exists():
        print("❌ Arquivo 'resultado_validado.csv' não encontrado.")
        sys.exit(1)

    # carrega como texto pra não bagunçar colunas
    df = pd.read_csv(IN_ARQ, dtype=str, encoding="utf-8")

    # garante colunas obrigatórias
    cols = ["Servidor", "Versão", "Jogadores Online", "Origem", "Observação"]
    for c in cols:
        if c not in df.columns:
            print(f"❌ Coluna ausente no CSV de entrada: {c}")
            sys.exit(1)

    # remove linhas vazias/de separador
    df = df[
        df["Servidor"].notnull() &
        ~df["Servidor"].astype(str).str.contains(r"===|^\s*$", na=False, regex=True)
    ]

    # normaliza 'Jogadores Online' para inteiro
    df["Jogadores Online"] = df["Jogadores Online"].apply(to_int).astype(int)

    # prioridade de origem
    df["_prio"] = df["Origem"].apply(origem_prio).astype(int)

    # ordena: prioridade (menor melhor), online desc, servidor asc
    df_ord = df.sort_values(
        by=["_prio", "Jogadores Online", "Servidor"],
        ascending=[True, False, True]
    ).drop(columns=["_prio"])

    # 🔧 força ORDEM EXATA de colunas antes de salvar
    df_ord = df_ord[cols]

    # monta CSV em memória (com cabeçalho)
    csv_text = df_ord.to_csv(index=False, lineterminator="\n", encoding="utf-8")

    # escreve com timestamp na 1ª linha (mantém seu formato atual)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(OUT_ARQ, "w", encoding="utf-8", newline="") as f:
        f.write(f"# Gerado em: {timestamp}\n")
        f.write(csv_text)

    print("✅ Arquivo 'ranking_final.csv' gerado com sucesso.")

if __name__ == "__main__":
    main()
