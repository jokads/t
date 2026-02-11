#!/bin/bash

# JOKA Trading Bot - Startup Script (Linux/Mac)
# Inicia automaticamente o trading_bot_core.py e dashboard_server.py

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}          JOKA TRADING BOT - STARTUP SCRIPT${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 não encontrado!${NC}"
    echo -e "${YELLOW}  Instale Python 3 e tente novamente${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python 3 encontrado${NC}"

# Verificar se estamos no diretório correto
if [ ! -d "backend" ]; then
    echo -e "${RED}✗ Diretório 'backend' não encontrado!${NC}"
    echo -e "${YELLOW}  Execute este script a partir da raiz do projeto bot-mt5${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Diretório correto${NC}"

# Criar ambiente virtual se não existir
if [ ! -d "venv" ]; then
    echo -e "${CYAN}ℹ Criando ambiente virtual...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Ambiente virtual criado${NC}"
fi

# Ativar ambiente virtual
echo -e "${CYAN}ℹ Ativando ambiente virtual...${NC}"
source venv/bin/activate

# Instalar dependências
if [ -f "backend/requirements.txt" ]; then
    echo -e "${CYAN}ℹ Instalando dependências...${NC}"
    pip install -q -r backend/requirements.txt
    echo -e "${GREEN}✓ Dependências instaladas${NC}"
fi

# Verificar se .env existe
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}⚠ Ficheiro .env não encontrado${NC}"
    if [ -f "backend/.env.example" ]; then
        echo -e "${CYAN}ℹ Copiando .env.example para .env...${NC}"
        cp backend/.env.example backend/.env
        echo -e "${GREEN}✓ Ficheiro .env criado${NC}"
        echo -e "${YELLOW}⚠ Configure o ficheiro backend/.env antes de continuar${NC}"
    fi
fi

# Função para limpar processos ao sair
cleanup() {
    echo ""
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${CYAN}          A ENCERRAR SISTEMA${NC}"
    echo -e "${CYAN}============================================================${NC}"
    echo ""
    
    if [ ! -z "$DASHBOARD_PID" ]; then
        echo -e "${CYAN}ℹ A terminar dashboard (PID: $DASHBOARD_PID)...${NC}"
        kill $DASHBOARD_PID 2>/dev/null
    fi
    
    if [ ! -z "$BOT_PID" ]; then
        echo -e "${CYAN}ℹ A terminar trading bot (PID: $BOT_PID)...${NC}"
        kill $BOT_PID 2>/dev/null
    fi
    
    echo -e "${GREEN}✓ Sistema encerrado com sucesso!${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Iniciar dashboard
echo ""
echo -e "${CYAN}ℹ A iniciar dashboard_server.py...${NC}"
cd backend
python3 dashboard_server.py &
DASHBOARD_PID=$!
cd ..

sleep 3

if ps -p $DASHBOARD_PID > /dev/null; then
    echo -e "${GREEN}✓ Dashboard iniciado com sucesso (PID: $DASHBOARD_PID)${NC}"
    echo -e "${CYAN}ℹ Dashboard disponível em: http://localhost:5000${NC}"
else
    echo -e "${RED}✗ Falha ao iniciar dashboard${NC}"
    exit 1
fi

# Iniciar trading bot (opcional - descomente se necessário)
# echo ""
# echo -e "${CYAN}ℹ A iniciar trading_bot_core.py...${NC}"
# python3 trading_bot_core.py &
# BOT_PID=$!
# sleep 2
# if ps -p $BOT_PID > /dev/null; then
#     echo -e "${GREEN}✓ Trading bot iniciado com sucesso (PID: $BOT_PID)${NC}"
# else
#     echo -e "${RED}✗ Falha ao iniciar trading bot${NC}"
# fi

# Abrir navegador (Linux)
if command -v xdg-open &> /dev/null; then
    echo -e "${CYAN}ℹ A abrir dashboard no navegador...${NC}"
    sleep 1
    xdg-open http://localhost:5000 &
fi

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${GREEN}          SISTEMA INICIADO COM SUCESSO${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""
echo -e "${GREEN}✓ Dashboard PID: $DASHBOARD_PID${NC}"
if [ ! -z "$BOT_PID" ]; then
    echo -e "${GREEN}✓ Trading Bot PID: $BOT_PID${NC}"
fi
echo ""
echo -e "${YELLOW}Pressione Ctrl+C para parar todos os processos${NC}"
echo ""

# Manter script ativo
wait
