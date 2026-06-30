# Imagen ligera de Python
FROM python:3.11-slim

# ffmpeg: necesario para que yt-dlp procese audio/thumbnails
# curl: usado por el HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements primero para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la app
# (el contexto de build aquí es SOLO esta carpeta del repo, no el NAS entero)
COPY . .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
