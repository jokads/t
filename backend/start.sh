#!/bin/bash

# JOKA Trading Bot - Script de Inicialização (Linux/Mac)

echo "🚀 JOKA Trading Bot - Inicialização"
echo "===================================="

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 não encontrado. Por favor, instale Python 3.8+${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python encontrado: $(python3 --version)${NC}"

# Criar diretórios
echo ""
echo "📁 Criando diretórios..."
mkdir -p data
mkdir -p models/gpt4all
mkdir -p logs

# Verificar .env
if [ ! -f backend/.env ]; then
    echo -e "${YELLOW}⚠️  Ficheiro .env não encontrado. Criando a partir de .env.example...${NC}"
    cp backend/.env.example backend/.env
    echo -e "${GREEN}✅ Ficheiro .env criado. Por favor, configure as variáveis necessárias.${NC}"
fi

# Criar virtual environment
if [ ! -d "venv" ]; then
    echo ""
    echo "🔧 Criando ambiente virtual Python..."
    python3 -m venv venv
    echo -e "${GREEN}✅ Ambiente virtual criado${NC}"
fi

# Ativar virtual environment
echo ""
echo "🔌 Ativando ambiente virtual..."
source venv/bin/activate

# Instalar dependências
echo ""
echo "📦 Instalando dependências Python..."
pip install --upgrade pip
pip install -r backend/requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Erro ao instalar dependências${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Dependências instaladas${NC}"

# Iniciar dashboard server
echo ""
echo "🌐 Iniciando Dashboard Server..."
cd backend
python3 dashboard_server.py &
DASHBOARD_PID=$!
cd ..

echo -e "${GREEN}✅ Dashboard Server iniciado (PID: $DASHBOARD_PID)${NC}"
echo ""
echo "📊 Dashboard disponível em: http://localhost:5000"
echo ""
echo "🔐 Credenciais de acesso:"
echo "   Utilizador: joka"
echo "   Password: ThugParadise616#"
echo ""
echo "💡 Para testar a integração, execute em outro terminal:"
echo "   python3 backend/simulate_bot.py"
echo ""
echo "🛑 Para parar o servidor, pressione Ctrl+C"
echo ""

# Aguardar
wait $DASHBOARD_PID
