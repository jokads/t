# JOKA Trading Bot - Startup Script (Windows PowerShell)
# Inicia automaticamente o trading_bot_core.py e dashboard_server.py

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          JOKA TRADING BOT - STARTUP SCRIPT" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar se Python está instalado
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python não encontrado!" -ForegroundColor Red
    Write-Host "  Instale Python 3 e tente novamente" -ForegroundColor Yellow
    exit 1
}

# Verificar se estamos no diretório correto
if (-not (Test-Path "backend")) {
    Write-Host "✗ Diretório 'backend' não encontrado!" -ForegroundColor Red
    Write-Host "  Execute este script a partir da raiz do projeto bot-mt5" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Diretório correto" -ForegroundColor Green

# Criar ambiente virtual se não existir
if (-not (Test-Path "venv")) {
    Write-Host "ℹ Criando ambiente virtual..." -ForegroundColor Cyan
    python -m venv venv
    Write-Host "✓ Ambiente virtual criado" -ForegroundColor Green
}

# Ativar ambiente virtual
Write-Host "ℹ Ativando ambiente virtual..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

# Instalar dependências
if (Test-Path "backend\requirements.txt") {
    Write-Host "ℹ Instalando dependências..." -ForegroundColor Cyan
    pip install -q -r backend\requirements.txt
    Write-Host "✓ Dependências instaladas" -ForegroundColor Green
}

# Verificar se .env existe
if (-not (Test-Path "backend\.env")) {
    Write-Host "⚠ Ficheiro .env não encontrado" -ForegroundColor Yellow
    if (Test-Path "backend\.env.example") {
        Write-Host "ℹ Copiando .env.example para .env..." -ForegroundColor Cyan
        Copy-Item "backend\.env.example" "backend\.env"
        Write-Host "✓ Ficheiro .env criado" -ForegroundColor Green
        Write-Host "⚠ Configure o ficheiro backend\.env antes de continuar" -ForegroundColor Yellow
    }
}

# Iniciar dashboard
Write-Host ""
Write-Host "ℹ A iniciar dashboard_server.py..." -ForegroundColor Cyan
$dashboardProcess = Start-Process -FilePath "python" -ArgumentList "backend\dashboard_server.py" -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 3

if ($dashboardProcess -and !$dashboardProcess.HasExited) {
    Write-Host "✓ Dashboard iniciado com sucesso (PID: $($dashboardProcess.Id))" -ForegroundColor Green
    Write-Host "ℹ Dashboard disponível em: http://localhost:5000" -ForegroundColor Cyan
} else {
    Write-Host "✗ Falha ao iniciar dashboard" -ForegroundColor Red
    exit 1
}

# Iniciar trading bot (opcional - descomente se necessário)
# Write-Host ""
# Write-Host "ℹ A iniciar trading_bot_core.py..." -ForegroundColor Cyan
# $botProcess = Start-Process -FilePath "python" -ArgumentList "trading_bot_core.py" -PassThru -WindowStyle Hidden
# Start-Sleep -Seconds 2
# if ($botProcess -and !$botProcess.HasExited) {
#     Write-Host "✓ Trading bot iniciado com sucesso (PID: $($botProcess.Id))" -ForegroundColor Green
# } else {
#     Write-Host "✗ Falha ao iniciar trading bot" -ForegroundColor Red
# }

# Abrir navegador
Write-Host "ℹ A abrir dashboard no navegador..." -ForegroundColor Cyan
Start-Sleep -Seconds 1
Start-Process "http://localhost:5000"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          SISTEMA INICIADO COM SUCESSO" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "✓ Dashboard PID: $($dashboardProcess.Id)" -ForegroundColor Green
# if ($botProcess) {
#     Write-Host "✓ Trading Bot PID: $($botProcess.Id)" -ForegroundColor Green
# }
Write-Host ""
Write-Host "Pressione Ctrl+C para parar todos os processos" -ForegroundColor Yellow
Write-Host ""

# Manter script ativo
try {
    while ($true) {
        Start-Sleep -Seconds 1
        
        # Verificar se dashboard ainda está ativo
        if ($dashboardProcess.HasExited) {
            Write-Host "⚠ Dashboard terminou inesperadamente" -ForegroundColor Yellow
            break
        }
    }
} finally {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "          A ENCERRAR SISTEMA" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
    
    if ($dashboardProcess -and !$dashboardProcess.HasExited) {
        Write-Host "ℹ A terminar dashboard (PID: $($dashboardProcess.Id))..." -ForegroundColor Cyan
        Stop-Process -Id $dashboardProcess.Id -Force
    }
    
    # if ($botProcess -and !$botProcess.HasExited) {
    #     Write-Host "ℹ A terminar trading bot (PID: $($botProcess.Id))..." -ForegroundColor Cyan
    #     Stop-Process -Id $botProcess.Id -Force
    # }
    
    Write-Host "✓ Sistema encerrado com sucesso!" -ForegroundColor Green
}
