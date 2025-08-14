# scripts/gerar_ranking_ordenado.py
from pathlib import Path
from datetime import datetime
import csv

IN_ARQ  = Path("resultado_validado.csv")
OUT_ARQ = Path("ranking_final.csv")
OUT_ARQ_PUBLIC = Path("public/ranking_final.csv")

# HOTFIX: ordem que o SEU front está usando (por posição, não por header)
COLS_IN   = ["Servidor", "Versão", "Jogadores Online", "Origem", "Observação"]   # como vem do coletor
COLS_OUT  = ["Servidor", "Jogadores Online", "Versão", "Origem", "Observação"]   # como o front está lendo

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
        for c in COLS_IN:
            if c not in r.fieldnames:
                print(f"❌ Coluna ausente no CSV de entrada: {c}")
                raise SystemExit(1)
        for row in r:
            serv = (row.get("Servidor") or "").strip()
            if not serv or serv == "===":
                continue
            versao = (row.get("Versão") or "").strip() or "-"
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
        f.write(f"# Gerado em: {ts}\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS_OUT)  # cabeçalho conforme o front está mapeando por posição
        for r in rows:
            # NOTE: aqui escrevemos NA ORDEM que o front espera
            w.writerow([r["Servidor"], r["Jogadores Online"], r["Versão"], r["Origem"], r["Observação"]])

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
    # prioridade: Socket > HTML > outros; depois Jogadores desc; depois Servidor asc
    rows.sort(key=lambda r: (origem_prio(r["Origem"]), -r["Jogadores Online"], r["Servidor"]))

    salvar_csv(OUT_ARQ, rows)
    salvar_csv(OUT_ARQ_PUBLIC, rows)

    preview(OUT_ARQ)
    preview(OUT_ARQ_PUBLIC)

    print("\n✅ ranking_final.csv e public/ranking_final.csv gerados (ordem compatível com o front).")

if __name__ == "__main__":
    main()
