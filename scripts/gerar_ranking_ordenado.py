# scripts/gerar_ranking_ordenado.py
# Lê resultado_validado.csv e gera ranking_final.csv (e public/ranking_final.csv)
# Ordem final FIXA: Servidor, Versão, Jogadores Online, Origem, Observação
# Prioriza Origem: Socket > HTML > outros. Ordena por Jogadores desc e Servidor asc.

from pathlib import Path
from datetime import datetime
import csv

IN_ARQ  = Path("resultado_validado.csv")
OUT_ARQ = Path("ranking_final.csv")
OUT_ARQ_PUBLIC = Path("public/ranking_final.csv")

COLS_IN  = ["Servidor", "Versão", "Jogadores Online", "Origem", "Observação"]   # do coletor
COLS_OUT = ["Servidor", "Versão", "Jogadores Online", "Origem", "Observação"]   # ordem que o site espera

def to_int(v):
    try:
        s = str(v).strip().replace(",", ".")
        if not s: return 0
        return int(float(s))
    except:
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
        for c in COLS_IN:
            if c not in r.fieldnames:
                print(f"❌ Coluna ausente no CSV de entrada: {c}")
                raise SystemExit(1)
        for row in r:
            serv = (row.get("Servidor") or "").strip()
            if not serv or serv == "===":
                continue
            versao = (row.get("Versão") or "").strip() or "-"  # impede coluna “andar”
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

def salvar_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        f.write(f"# Gerado em: {ts}\n")     # 1ª linha de timestamp (mantém seu formato)
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS_OUT)                # cabeçalho na ordem esperada
        for r in rows:
            w.writerow([r["Servidor"], r["Versão"], r["Jogadores Online"], r["Origem"], r["Observação"]])

def preview(path: Path, n=5):
    try:
        with path.open("r", encoding="utf-8") as f:
            print(f"\n# Preview {path} (até {n} linhas):")
            for i, ln in enumerate(f):
                print(ln.rstrip("\n"))
                if i >= n: break
    except Exception as e:
        print(f"⚠️ Preview falhou: {e}")

def main():
    rows = ler_entrada()
    # Ordena por prioridade de origem, depois jogadores (desc) e servidor (asc)
    rows.sort(key=lambda r: (origem_prio(r["Origem"]), -r["Jogadores Online"], r["Servidor"]))

    # Salva nas duas rotas (raiz e /public)
    salvar_csv(OUT_ARQ, rows)
    salvar_csv(OUT_ARQ_PUBLIC, rows)

    # Mostra as primeiras linhas no log pra validar a ordem
    preview(OUT_ARQ, n=6)
    preview(OUT_ARQ_PUBLIC, n=6)

    print("\n✅ ranking_final.csv e public/ranking_final.csv gerados (ordem: Servidor, Versão, Jogadores Online, Origem, Observação).")

if __name__ == "__main__":
    main()
