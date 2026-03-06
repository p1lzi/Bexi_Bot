# Nutze ein offizielles Python-Image, das für ARM (Raspberry Pi) optimiert ist
FROM python:3.11-slim-bookworm

# Setze Umgebungsvariablen für Python
# Verhindert, dass Python .pyc Dateien schreibt und sorgt für sofortige Log-Ausgabe
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Arbeitsverzeichnis im Container
WORKDIR /app

# Installiere System-Abhängigkeiten
# Wir halten das Image klein, indem wir den Cache nach der Installation leeren
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopiere die requirements.txt zuerst (für besseres Caching der Layer)
COPY requirements.txt .

# Installiere die Python-Pakete
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere den Bot-Quellcode in den Container
COPY bot.py .

# Erstelle eine leere config.json, falls sie nicht über Volumes gemountet wird
# Das verhindert Fehler beim ersten Start
RUN echo "{}" > config.json

# Standard-Umgebungsvariablen (werden durch docker-compose überschrieben)
ENV TOKEN=""
ENV GUILD_ID=""
ENV TZ="Europe/Berlin"

# Startbefehl für den Bot
CMD ["python", "bot.py"]