# bot_mt5 - High-Frequency Trading Bot for MetaTrader 5

**Versão:** 2.0.0-refactor  
**Status:** 🚧 Refactor em progresso (branch `refactor/hf-mt5-bot`)

---

## 📋 Visão Geral

Sistema de trading automatizado de **alta frequência** para MetaTrader 5, com:

- ✅ **Arquitetura assíncrona** (100% `async/await`)
- ✅ **AI worker pool** (processos dedicados, sem GIL)
- ✅ **Socket MT5** com reconexão automática
- ✅ **Rate limiting** (token bucket)
- ✅ **Logging estruturado** (JSON)
- ✅ **Pydantic v2** validation
- ✅ **Docker** + **CI/CD**

---

## 🏗️ Arquitetura

```
bot_mt5/
├── ai_manager/          # AI worker pool (multiprocessing)
│   ├── manager.py       # Async interface, circuit-breaker
│   └── worker.py        # Process worker (llama.cpp/gpt4all)
├── core/                # Trading orchestrator
│   └── orchestrator.py  # generate_and_validate_signals()
├── mt5_comm/            # MT5 communication
│   └── client.py        # Socket client com reconexão
├── schemas/             # Pydantic models
│   └── messages.py      # SignalCreate, OrderExecute, etc
└── utils/               # Config, logging, rate limiter
    ├── config.py
    ├── logging.py
    └── rate_limiter.py
```

---

## 🚀 Quick Start

### 1. Pré-requisitos

- Python 3.11+
- Docker + Docker Compose (opcional)
- Modelos GGUF (llama.cpp) ou GPT4All

### 2. Instalação

```bash
# Clone o repositório
git clone https://github.com/jokads/t.git
cd t

# Checkout branch refactor
git checkout refactor/hf-mt5-bot

# Instalar dependências
pip install -r requirements-refactor.txt

# (Opcional) Instalar AI models
pip install llama-cpp-python gpt4all
```

### 3. Configuração

Criar ficheiro `.env`:

```bash
# AI Configuration
AI_MODEL_PATHS=./models:/home/user/models/gpt4all
AI_POOL_SIZE=2
AI_TIMEOUT_QUICK=8.0
AI_TIMEOUT_DEEP=30.0

# MT5 Configuration
MT5_HOST=0.0.0.0
MT5_PORT=8765
MT5_PROTOCOL=socket

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_OPM=60
RATE_LIMIT_BURST=10

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
# SENTRY_DSN=https://...  # Opcional

# Performance
USE_UVLOOP=true  # auto-detect Windows
USE_ORJSON=true
```

### 4. Colocar Modelos

```bash
# Criar diretório
mkdir -p models

# Baixar modelo GGUF (exemplo)
# wget https://huggingface.co/.../model.gguf -O models/mistral-7b.gguf

# Ou usar GPT4All
# python3 -c "from gpt4all import GPT4All; GPT4All('mistral-7b-instruct-v0.1.Q4_0.gguf')"
```

### 5. Executar

**Opção A: Python direto**
```bash
python3 -m bot_mt5.main
```

**Opção B: Docker Compose**
```bash
docker-compose -f docker-compose-refactor.yml up -d
docker-compose -f docker-compose-refactor.yml logs -f bot_mt5
```

---

## 🧪 Testes

```bash
# Executar todos os testes
pytest tests/ -v

# Com coverage
pytest tests/ --cov=bot_mt5 --cov-report=html

# Apenas schemas
pytest tests/test_schemas.py -v

# Apenas rate limiter
pytest tests/test_rate_limiter.py -v

# Apenas orchestrator
pytest tests/test_orchestrator.py -v
```

**Resultados esperados:**
```
tests/test_schemas.py ................ (16 passed)
tests/test_rate_limiter.py .......... (10 passed)
tests/test_orchestrator.py ........ (8 passed)
============================== 34 passed in 2.5s ==============================
```

---

## 📊 Performance

### Comparação vs Código Antigo

| Métrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| **Linhas de código** | 10713 | ~2500 | **-77%** |
| **Latência AI** | 5-40s (bloqueante) | 0.1-8s (async) | **-80%** |
| **Timeout MT5** | Indefinido | 5s configurável | ✅ |
| **Reconexão** | Manual | Automática | ✅ |
| **Validação** | Nenhuma | Pydantic v2 | ✅ |
| **Rate limiting** | Nenhum | Token bucket | ✅ |

### Latências Esperadas

- **Enrich market data:** ~10-50ms
- **AI decision (quick):** 100-8000ms (timeout 8s)
- **Risk validation:** ~1-5ms
- **MT5 execution:** 50-500ms (timeout 5s)
- **Total pipeline:** 200-10000ms (timeout 15s)

---

## 🔧 Desenvolvimento

### Code Quality

```bash
# Format code
black bot_mt5/ tests/

# Lint
flake8 bot_mt5/ tests/ --max-line-length=120

# Type check
mypy bot_mt5/ --ignore-missing-imports
```

### Estrutura de Commits

Este refactor usa **commits atômicos**:

```
132dc664 - refactor(project): create modular bot_mt5 structure
ed680f23 - feat(ai_manager): implement async AI manager with worker pool
df73e7d5 - feat(core,mt5_comm): implement async orchestrator and MT5 client
5ffb1eb8 - feat(utils): add rate limiter, structured logging
721f46b1 - test: add comprehensive unit and integration tests
1c4f1ddc - ci: add Docker and GitHub Actions CI/CD
```

---

## 📖 Documentação Adicional

- **[DIAGNOSTIC_REPORT.md](DIAGNOSTIC_REPORT.md)** - Diagnóstico completo do código antigo
- **[RESEARCH_FINDINGS.md](RESEARCH_FINDINGS.md)** - Pesquisa de melhores práticas
- **[CHANGELOG.md](CHANGELOG.md)** - Changelog detalhado

---

## 🐛 Troubleshooting

### Problema: "No models found"

**Solução:** Verificar `AI_MODEL_PATHS` e colocar ficheiros `.gguf` no diretório.

```bash
export AI_MODEL_PATHS="./models:/home/user/models"
ls -lh models/*.gguf
```

### Problema: "Connection refused" (MT5)

**Solução:** Verificar se EA está conectado e porta está correta.

```bash
# Verificar porta
netstat -tuln | grep 8765

# Testar conexão
telnet localhost 8765
```

### Problema: "Rate limit exceeded"

**Solução:** Ajustar `RATE_LIMIT_OPM` ou desativar.

```bash
export RATE_LIMIT_ENABLED=false
# ou
export RATE_LIMIT_OPM=120  # 120 orders/min
```

---

## 🤝 Contribuir

1. Fork o repositório
2. Criar branch (`git checkout -b feature/nova-feature`)
3. Commit com mensagem descritiva
4. Push para branch (`git push origin feature/nova-feature`)
5. Abrir Pull Request

**Convenções:**
- Commits: `type(scope): message` (conventional commits)
- Code style: Black + Flake8
- Tests: Pytest com coverage > 80%

---

## 📄 Licença

[Adicionar licença aqui]

---

## 👥 Autores

- **Manus AI** - Refactor e otimização
- **jokads** - Código original

---

## 🔗 Links Úteis

- [Pydantic v2 Docs](https://docs.pydantic.dev/latest/)
- [llama-cpp-python](https://llama-cpp-python.readthedocs.io/)
- [MQL5 Socket Docs](https://www.mql5.com/en/articles/2599)
- [FastAPI WebSocket Patterns](https://medium.com/@connect.hashblock/10-fastapi-websocket-patterns-for-live-dashboards-3e36f3080510)
