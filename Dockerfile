# Imagem base oficial do Playwright (já inclui Chromium e libs do SO)
FROM mcr.microsoft.com/playwright/python:1.52.0

# Cria diretório da app e define workdir
WORKDIR /app

# Copia e instala dependências Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala Flask e Gunicorn
RUN pip install flask gunicorn

# Copia o código e scripts
COPY backend/ .
COPY run_all.sh .
COPY app.py .

# Permissões e exposição de porta
RUN chmod +x run_all.sh
EXPOSE 8080

# Inicia o servidor HTTP com Gunicorn, que dispara seus scripts
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
