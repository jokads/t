FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Criar diretórios
RUN mkdir -p data models/gpt4all logs

# Variáveis de ambiente
ENV DASHBOARD_HOST=0.0.0.0
ENV DASHBOARD_PORT=5000
ENV PYTHONUNBUFFERED=1

# Expor porta
EXPOSE 5000

# Comando de inicialização
CMD ["python", "dashboard_server.py"]
