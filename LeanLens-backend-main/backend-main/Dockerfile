# PFE (LeanLens) : Dockerfile modernisé.
# Amont : python:3.9-slim (aujourd'hui = trixie) + `apt-key` + repo mssql
# ubuntu-20.04 — tous trois cassés en 2026 (apt-key supprimé de Debian 12+,
# bullseye-security 404, msodbcsql17 absent de trixie).
# Ici : base bookworm LTS + repo Microsoft debian/12 via keyring signé.
# pymssql/pyodbc restent installés (imports module-level dans OrderView /
# DatabaseConnections) même si le connecteur ERP n'est pas utilisé par le PFE.
FROM python:3.9-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    musl-dev \
    sudo \
    unixodbc-dev \
    curl \
    gnupg \
    ca-certificates

RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | \
      gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
      -o /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y \
      msodbcsql17 freetds-dev freetds-bin iputils-ping && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY ./requirements.txt .
RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt

COPY . .

EXPOSE 8000

RUN chmod +x /usr/src/app/entrypoint.sh

CMD ./entrypoint.sh
