# JOKA Trading Bot - Script de Inicialização (Windows)

Write-Host "🚀 JOKA Trading Bot - Inicialização" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Verificar Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "❌ Python não encontrado. Por favor, instale Python 3.8+" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Python encontrado: $(python --version)" -ForegroundColor Green

# Criar diretórios
Write-Host ""
Write-Host "📁 Criando diretórios..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path data | Out-Null
New-Item -ItemType Directory -Force -Path models\gpt4all | Out-Null
New-Item -ItemType Directory -Force -Path logs | Out-Null

# Verificar .env
if (-not (Test-Path backend\.env)) {
    Write-Host "⚠️  Ficheiro .env não encontrado. Criando a partir de .env.example..." -ForegroundColor Yellow
    Copy-Item backend\.env.example backend\.env
    Write-Host "✅ Ficheiro .env criado. Por favor, configure as variáveis necessárias." -ForegroundColor Green
}

# Criar virtual environment
if (-not (Test-Path venv)) {
    Write-Host ""
    Write-Host "🔧 Criando ambiente virtual Python..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "✅ Ambiente virtual criado" -ForegroundColor Green
}

# Ativar virtual environment
Write-Host ""
Write-Host "🔌 Ativando ambiente virtual..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Instalar dependências
Write-Host ""
Write-Host "📦 Instalando dependências Python..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erro ao instalar dependências" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Dependências instaladas" -ForegroundColor Green

# Iniciar dashboard server
Write-Host ""
Write-Host "🌐 Iniciando Dashboard Server..." -ForegroundColor Yellow
$dashboardProcess = Start-Process python -ArgumentList "backend\dashboard_server.py" -PassThru -NoNewWindow

Write-Host "✅ Dashboard Server iniciado (PID: $($dashboardProcess.Id))" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Dashboard disponível em: http://localhost:5000" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔐 Credenciais de acesso:" -ForegroundColor Cyan
Write-Host "   Utilizador: joka" -ForegroundColor White
Write-Host "   Password: ThugParadise616#" -ForegroundColor White
Write-Host ""
Write-Host "💡 Para testar a integração, execute em outro terminal:" -ForegroundColor Yellow
Write-Host "   python backend\simulate_bot.py" -ForegroundColor White
Write-Host ""
Write-Host "🛑 Para parar o servidor, pressione Ctrl+C" -ForegroundColor Yellow
Write-Host ""

# Aguardar
try {
    Wait-Process -Id $dashboardProcess.Id
}
catch {
    Write-Host "Servidor encerrado" -ForegroundColor Yellow
}
