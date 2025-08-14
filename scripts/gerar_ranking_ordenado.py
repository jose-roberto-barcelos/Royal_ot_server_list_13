# scripts/gerar_ranking_ordenado.py
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

IN_ARQ  = Path("resultado_validado.csv")
OUT_ARQ = Path("ranking_final.csv")

COLS = ["Servidor","Versão","Jogadores Online","Origem","Observação"]

def to_int(v):
    try:
        if pd.isna(v): return 0
        s = str(v).strip().replace(",", ".")
        if s == "": return 0
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

    # Carrega como texto pra não bagunçar nada
    df = pd.read_csv(IN_ARQ, dtype=str, encoding="utf-8")

    # Garante as colunas obrigatórias
    for c in COLS:
        if c not in df.columns:
            print(f"❌ Coluna ausente no CSV de entrada: {c}")
            sys.exit(1)

    # Remove linhas vazias/separadores
    df = df[
        df["Servidor"].notnull() &
        ~df["Servidor"].astype(str).str.contains(r"===|^\s*$", na=False, regex=True)
    ]

    # Normaliza tipos/valores esperados
    df["Jogadores Online"] = df["Jogadores Online"].apply(to_int).astype(int)

    # 🔧 EVITA “COLUNA ANDAR”: nunca deixe Versão vazia
    df["Versão"] = df["Versão"].fillna("-")
    df["Versão"] = df["Versão"].astype(str).apply(lambda s: s if s.strip() != "" else "-")

    # (hardening opcional)
    df["Origem"] = df["Origem"].fillna("Pendência")
    df["Observação"] = df["Observação"].fillna("")

    # Prioridade de origem
    df["_prio"] = df["Origem"].apply(origem_prio).astype(int)

    # Ordena: prioridade (menor melhor), online desc, servidor asc
    df_ord = df.sort_values(
        by=["_prio", "Jogadores Online", "Servidor"],
        ascending=[True, False, True]
    ).drop(columns=["_prio"])

    # 🔒 Força ORDEM EXATA de colunas antes de salvar
    df_ord = df_ord[COLS]

    # CSV final (com cabeçalho), mantendo seu timestamp na 1ª linha
    csv_text = df_ord.to_csv(index=False, lineterminator="\n", encoding="utf-8")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    with open(OUT_ARQ, "w", encoding="utf-8", newline="") as f:
        f.write(f"# Gerado em: {timestamp}\n")
        f.write(csv_text)

    print("✅ Arquivo 'ranking_final.csv' gerado com sucesso.")

if __name__ == "__main__":
    main()
