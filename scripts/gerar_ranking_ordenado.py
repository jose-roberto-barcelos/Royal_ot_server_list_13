# scripts/gerar_ranking_ordenado.py
# Lê resultado_validado.csv e gera ranking_final.csv (e public/ranking_final.csv)
# - Prioriza Origem: Socket > HTML > outros
# - Ordena por Jogadores Online (desc) e Servidor (asc)
# - Força colunas/p posições: Servidor, Versão, Jogadores Online, Origem, Observação
# - Preenche Versão vazia com '-' para evitar “coluna andar” no front
# - Imprime preview no log

from pathlib import Path
from datetime import datetime
import csv

IN_ARQ  = Path("resultado_validado.csv")
OUT_ARQ = Path("ranking_final.csv")
OUT_ARQ_PUBLIC = Path("public/ranking_final.csv")

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

def ler_entrada():
    if not IN_ARQ.exists():
        print("❌ Arquivo 'resultado_validado.csv' não encontrado.")
        raise SystemExit(1)
    rows = []
    with IN_ARQ.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        # sanity check
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
                versao = "-"  # evita coluna “andar” no front
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
    return rows

def salvar_csv(caminho: Path, rows):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as f:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        f.write(f"# Gerado em: {ts}\n")              # 1ª linha de timestamp
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS)                              # cabeçalho
        for r in rows:
            w.writerow([r["Servidor"], r["Versão"], r["Jogadores Online"], r["Origem"], r["Observação"]])

def preview(caminho: Path, n=5):
    try:
        with caminho.open("r", encoding="utf-8") as f:
            print(f"\n# Preview de {caminho} (até {n} linhas):")
            for i, ln in enumerate(f):
                print(ln.rstrip("\n"))
                if i >= n: break
    except Exception as e:
        print(f"⚠️ Não consegui pré-visualizar {caminho}: {e}")

def main():
    rows = ler_entrada()
    # ordena: origem (melhor primeiro), online desc, servidor asc
    rows.sort(key=lambda r: (origem_prio(r["Origem"]), -r["Jogadores Online"], r["Servidor"]))

    # salva em AMBOS os caminhos (raiz e public/)
    salvar_csv(OUT_ARQ, rows)
    salvar_csv(OUT_ARQ_PUBLIC, rows)

    # previews no log (confirma 2ª coluna = Versão e 3ª = Jogadores)
    preview(OUT_ARQ)
    preview(OUT_ARQ_PUBLIC)

    print("\n✅ ranking_final.csv e public/ranking_final.csv gerados com sucesso.")

if __name__ == "__main__":
    main()
