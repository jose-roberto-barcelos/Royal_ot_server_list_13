#!/bin/sh

# Vai para a pasta do backend
cd backend || exit 1

# Executa coleta e ranking
# (certifique-se de já ter instalado requests, pandas e playwright)
python coleta_validada_pronto.py
python gerar_ranking_ordenado.py
