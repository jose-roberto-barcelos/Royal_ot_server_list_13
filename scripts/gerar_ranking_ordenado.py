import pandas as pd
from pathlib import Path
from datetime import datetime

# Caminhos de entrada e saída
entrada = Path("resultado_validado.csv")
saida = Path("ranking_final.csv")

# Verifica se o arquivo de entrada existe
if not entrada.exists():
    print("❌ Arquivo 'resultado_validado.csv' não encontrado.")
    exit()

# Gera timestamp UTC para inclusão no CSV
timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

# Carrega o CSV original em DataFrame (ignora linhas de separação)
df = pd.read_csv(entrada)
df = df[df["Servidor"].notnull() & ~df["Servidor"].astype(str).str.contains("===|^\\s*$", na=False)]

# Converte coluna 'Jogadores Online' para inteiro
df["Jogadores Online"] = pd.to_numeric(df["Jogadores Online"], errors="coerce").fillna(0).astype(int)

# Define prioridade: Socket = 0, HTML = 1, outros = 2
df["Origem_Prioridade"] = (
    df["Origem"].str.lower().map({"socket": 0, "html": 1}).fillna(2)
)

# Ordena: primeiro por Origem_Prioridade, depois por jogadores decrescentes
df_ordenado = df.sort_values(
    by=["Origem_Prioridade", "Jogadores Online"],
    ascending=[True, False]
).drop(columns=["Origem_Prioridade"])

# Salva o novo ranking com timestamp como comentário na primeira linha
with open(saida, 'w', encoding='utf-8', newline='') as f:
    f.write(f"# Gerado em: {timestamp}\n")
    df_ordenado.to_csv(f, index=False)

print("✅ Arquivo 'ranking_final.csv' gerado com sucesso.")
