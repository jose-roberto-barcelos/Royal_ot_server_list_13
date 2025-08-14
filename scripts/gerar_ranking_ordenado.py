# scripts/gerar_ranking_ordenado.py
# Lê resultado_validado.csv e gera ranking_final.csv
# - Prioriza Origem: Socket > HTML > outros
# - Ordena por Jogadores Online (desc) e Servidor (asc)
# - Força colunas e posições: Servidor, Versão, Jogadores Online, Origem, Observação
# - Mantém a 1ª linha com timestamp "# Gerado em: ..."

from pathlib import Path
from datetime import datetime
import csv

IN_ARQ  = Path("resultado_validado.csv")
OUT_ARQ = Path("ranking_final.csv")

COLS = ["Servidor", "Versão", "Jogadores Online", "Origem", "Observação"]

def to_int(v):
    try:
        s = str(v).strip().replace(",", ".")
        if not s:
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
        raise SystemExit(1)

    # Lê o CSV de entrada como texto cru
    rows = []
    with IN_ARQ.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        # sanity check de colunas
        for c in COLS:
            if c not in r.fieldnames:
                print(f"❌ Coluna ausente no CSV de entrada: {c}")
                raise SystemExit(1)
        for row in r:
            serv = (row.get("Servidor") or "").strip()
            if not serv or serv == "===":
                continue

            versao = (row.get("Versão") or "").strip()
            if versao == "":
                versao = "-"                    # evita front “remover vazio” e deslocar colunas

            online = to_int(row.get("Jogadores Online", 0))
            origem = (row.get("Origem") or "").strip() or "Pendência"
            observ = (row.get("Observação") or "").strip()

            rows.append({
                "Servidor": serv,
                "Versão": versao,
                "Jogadores Online": online,
                "Origem": origem,
                "Observação": observ,
            })

    # Ordenação: prioridade de origem, depois online desc, depois servidor asc
    rows.sort(key=lambda r: (origem_prio(r["Origem"]), -r["Jogadores Online"], r["Servidor"]))

    # Escreve o CSV final manualmente (garantindo a ORDEM das colunas)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with OUT_ARQ.open("w", encoding="utf-8", newline="") as f:
        f.write(f"# Gerado em: {timestamp}\n")  # 1ª linha de timestamp
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS)
        for r in rows:
            w.writerow([r["Servidor"], r["Versão"], r["Jogadores Online"], r["Origem"], r["Observação"]])

    print("✅ Arquivo 'ranking_final.csv' gerado com sucesso.")

if __name__ == "__main__":
    main()
