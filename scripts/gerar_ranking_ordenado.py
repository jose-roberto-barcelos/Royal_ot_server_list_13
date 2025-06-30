import pandas as pd
from pathlib import Path

# Caminhos de entrada e saída
entrada = Path("resultado_validado.csv")
saida = Path("ranking_final.csv")

# Verifica se o arquivo de entrada existe
if not entrada.exists():
    print("❌ Arquivo 'resultado_validado.csv' não encontrado.")
    exit()

# Carrega o CSV original
df = pd.read_csv(entrada)

# Remove linhas nulas ou divisórias (como '=== VIA SOCKET ===')
df = df[df["Servidor"].notnull() & ~df["Servidor"].astype(str).str.contains("===|^\s*$", na=False)]

# Converte coluna 'Jogadores Online' para número
df["Jogadores Online"] = pd.to_numeric(df["Jogadores Online"], errors="coerce").fillna(0).astype(int)

# Prioriza origem: Socket = 0, HTML = 1, outros = 2
df["Origem_Prioridade"] = df["Origem"].astype(str).str.lower().map({"socket": 0, "html": 1}).fillna(2)

# Ordena: Socket primeiro, depois por jogadores decrescentes
df_ordenado = df.sort_values(by=["Origem_Prioridade", "Jogadores Online"], ascending=[True, False])

# Remove coluna auxiliar
df_ordenado.drop(columns=["Origem_Prioridade"], inplace=True)

# Salva o novo ranking
df_ordenado.to_csv(saida, index=False)

print("✅ Arquivo 'ranking_final.csv' gerado com sucesso.")
