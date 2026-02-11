# 🔧 Instrumentação para Runtime Error Reporting

Este guia mostra como adicionar captura automática de erros runtime ao seu bot MT5 para enviar erros em tempo real ao dashboard.

---

## 📋 Snippet para `trading_bot_core.py`

Adicione este código ao início do seu `trading_bot_core.py`:

```python
import sys
import traceback
import requests
from functools import wraps
from datetime import datetime

# Configuração do Dashboard
DASHBOARD_URL = "http://localhost:5000"
DASHBOARD_TOKEN = "seu_token_aqui"  # Mesmo token do BOT_PUSH_TOKEN

def report_error_to_dashboard(file_path, line_number, error_type, message, stack_trace, local_vars=None):
    """Envia erro runtime para o dashboard"""
    try:
        payload = {
            'file': file_path,
            'line': line_number,
            'error_type': error_type,
            'message': message,
            'stack_trace': stack_trace,
            'locals': local_vars or {}
        }
        
        headers = {
            'Authorization': f'Bearer {DASHBOARD_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            f'{DASHBOARD_URL}/api/diagnostics/runtime_error',
            json=payload,
            headers=headers,
            timeout=5
        )
        
        if response.ok:
            print(f"✅ Erro reportado ao dashboard: {file_path}:{line_number}")
        else:
            print(f"⚠️ Falha ao reportar erro: {response.status_code}")
    
    except Exception as e:
        print(f"❌ Erro ao reportar para dashboard: {e}")

def catch_and_report(func):
    """Decorator para capturar e reportar exceções"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Obter informações do erro
            exc_type, exc_value, exc_traceback = sys.exc_info()
            
            # Extrair detalhes
            tb = traceback.extract_tb(exc_traceback)
            last_frame = tb[-1]
            
            file_path = last_frame.filename
            line_number = last_frame.lineno
            error_type = exc_type.__name__
            message = str(exc_value)
            stack_trace = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            
            # Obter variáveis locais (limitado para evitar dados sensíveis)
            local_vars = {}
            if exc_traceback.tb_frame.f_locals:
                for key, value in list(exc_traceback.tb_frame.f_locals.items())[:10]:
                    try:
                        local_vars[key] = str(value)[:100]  # Limitar tamanho
                    except:
                        local_vars[key] = '<não serializável>'
            
            # Reportar ao dashboard
            report_error_to_dashboard(
                file_path=file_path,
                line_number=line_number,
                error_type=error_type,
                message=message,
                stack_trace=stack_trace,
                local_vars=local_vars
            )
            
            # Re-raise para não quebrar o fluxo
            raise
    
    return wrapper

# Handler global de exceções não capturadas
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Captura exceções não tratadas"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Extrair detalhes
    tb = traceback.extract_tb(exc_traceback)
    last_frame = tb[-1] if tb else None
    
    if last_frame:
        file_path = last_frame.filename
        line_number = last_frame.lineno
        error_type = exc_type.__name__
        message = str(exc_value)
        stack_trace = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Reportar
        report_error_to_dashboard(
            file_path=file_path,
            line_number=line_number,
            error_type=error_type,
            message=message,
            stack_trace=stack_trace
        )
    
    # Chamar handler padrão
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Instalar handler global
sys.excepthook = global_exception_handler

print("✅ Runtime error reporting ativado")
```

---

## 🎯 Como Usar

### 1. Decorar Funções Críticas

Use o decorator `@catch_and_report` nas funções principais:

```python
@catch_and_report
def execute_strategy(strategy_name, symbol, timeframe):
    """Executar estratégia de trading"""
    # Seu código aqui
    pass

@catch_and_report
def process_signal(signal):
    """Processar sinal de trading"""
    # Seu código aqui
    pass

@catch_and_report
def main_loop():
    """Loop principal do bot"""
    while True:
        # Seu código aqui
        pass
```

### 2. Reportar Erros Manualmente

Para erros específicos que você quer reportar:

```python
try:
    # Código que pode falhar
    result = risky_operation()
except Exception as e:
    # Reportar manualmente
    report_error_to_dashboard(
        file_path=__file__,
        line_number=sys._getframe().f_lineno,
        error_type=type(e).__name__,
        message=str(e),
        stack_trace=traceback.format_exc(),
        local_vars={'result': str(result)}
    )
    # Tratar erro
    handle_error(e)
```

---

## 📦 Snippet para `ai_manager.py`

Adicione ao início do `ai_manager.py`:

```python
import sys
import traceback
import requests

DASHBOARD_URL = "http://localhost:5000"
DASHBOARD_TOKEN = "seu_token_aqui"

def report_ai_error(model_name, error_type, message, stack_trace):
    """Reportar erro de IA ao dashboard"""
    try:
        payload = {
            'file': 'ai_manager.py',
            'line': 0,
            'error_type': f'AI_{error_type}',
            'message': f'[{model_name}] {message}',
            'stack_trace': stack_trace,
            'locals': {'model': model_name}
        }
        
        headers = {
            'Authorization': f'Bearer {DASHBOARD_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        requests.post(
            f'{DASHBOARD_URL}/api/diagnostics/runtime_error',
            json=payload,
            headers=headers,
            timeout=5
        )
    except:
        pass

# Usar em métodos de IA
def load_model(self, model_name):
    try:
        # Carregar modelo
        pass
    except Exception as e:
        report_ai_error(
            model_name=model_name,
            error_type='LOAD_ERROR',
            message=str(e),
            stack_trace=traceback.format_exc()
        )
        raise
```

---

## 📦 Snippet para Estratégias

Adicione ao início de cada ficheiro em `strategies/*.py`:

```python
import sys
import traceback
import requests

DASHBOARD_URL = "http://localhost:5000"
DASHBOARD_TOKEN = "seu_token_aqui"

def report_strategy_error(strategy_name, error_type, message, stack_trace):
    """Reportar erro de estratégia ao dashboard"""
    try:
        payload = {
            'file': f'strategies/{strategy_name}.py',
            'line': 0,
            'error_type': f'STRATEGY_{error_type}',
            'message': f'[{strategy_name}] {message}',
            'stack_trace': stack_trace
        }
        
        headers = {
            'Authorization': f'Bearer {DASHBOARD_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        requests.post(
            f'{DASHBOARD_URL}/api/diagnostics/runtime_error',
            json=payload,
            headers=headers,
            timeout=5
        )
    except:
        pass

# Exemplo de uso
class AdaptiveMLStrategy:
    def execute(self, symbol, timeframe):
        try:
            # Lógica da estratégia
            pass
        except Exception as e:
            report_strategy_error(
                strategy_name='adaptive_ml',
                error_type='EXECUTION_ERROR',
                message=str(e),
                stack_trace=traceback.format_exc()
            )
            raise
```

---

## 🔔 Notificações em Tempo Real

Quando um erro é reportado:

1. ✅ **Dashboard recebe** o erro instantaneamente
2. 🔴 **Notificação visual** aparece na UI
3. 📱 **Alerta Telegram** (se configurado)
4. 📝 **Log de auditoria** registra o evento
5. 🤖 **IA pode analisar** automaticamente

---

## 🎯 Exemplo Completo

```python
# trading_bot_core.py

import sys
import traceback
import requests
from functools import wraps

# ... (código de instrumentação acima) ...

@catch_and_report
def main():
    """Função principal do bot"""
    print("🚀 Iniciando Trading Bot...")
    
    # Inicializar componentes
    mt5 = MT5Communication()
    ai = AIManager()
    strategies = StrategyEngine()
    
    # Loop principal
    while True:
        try:
            # Obter dados do mercado
            data = mt5.get_market_data()
            
            # Executar estratégias
            signals = strategies.execute_all(data)
            
            # Processar sinais
            for signal in signals:
                process_signal(signal)
            
            time.sleep(1)
        
        except KeyboardInterrupt:
            print("⏹️ Bot interrompido pelo usuário")
            break
        
        except Exception as e:
            # Erro será automaticamente reportado pelo decorator
            print(f"❌ Erro no loop principal: {e}")
            time.sleep(5)  # Aguardar antes de tentar novamente

if __name__ == '__main__':
    main()
```

---

## 🛡️ Segurança

### ⚠️ Dados Sensíveis

**NUNCA** envie ao dashboard:
- ❌ Passwords
- ❌ API keys
- ❌ Tokens
- ❌ Dados de conta completos

### ✅ Filtrar Variáveis Locais

```python
SENSITIVE_KEYS = ['password', 'api_key', 'token', 'secret']

def filter_sensitive_data(local_vars):
    """Remover dados sensíveis"""
    filtered = {}
    for key, value in local_vars.items():
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            filtered[key] = '<REDACTED>'
        else:
            filtered[key] = str(value)[:100]
    return filtered
```

---

## 📊 Visualização no Dashboard

Após instrumentar o código, você verá no dashboard:

1. **Página Diagnóstico** (`/diagnostics`)
   - Lista de erros em tempo real
   - Ficheiro:linha:coluna exatos
   - Stack trace completo
   - Variáveis locais

2. **Análise com IA**
   - Clique em "Analisar com IA"
   - IA explica o problema
   - Sugere correção
   - Gera patch

3. **Aplicar Correção**
   - Testar patch em sandbox
   - Aplicar com segurança
   - Backup automático
   - Audit log

---

## 🚀 Próximos Passos

1. ✅ Adicionar instrumentação ao `trading_bot_core.py`
2. ✅ Adicionar aos ficheiros críticos (`ai_manager.py`, estratégias)
3. ✅ Configurar `DASHBOARD_TOKEN` no `.env`
4. ✅ Testar reportando um erro intencional
5. ✅ Verificar no dashboard se o erro aparece
6. ✅ Usar IA para analisar e corrigir

---

## 🔧 Troubleshooting

### Erro não aparece no dashboard?

1. Verificar se `dashboard_server.py` está rodando
2. Verificar se `DASHBOARD_TOKEN` está correto
3. Verificar logs do backend: `backend/logs/dashboard.log`
4. Testar endpoint manualmente:

```bash
curl -X POST http://localhost:5000/api/diagnostics/runtime_error \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file": "test.py",
    "line": 42,
    "error_type": "TestError",
    "message": "Teste de erro",
    "stack_trace": "Traceback...",
    "locals": {}
  }'
```

### Muitos erros sendo reportados?

Adicione rate limiting:

```python
import time
from collections import defaultdict

error_timestamps = defaultdict(list)
MAX_ERRORS_PER_MINUTE = 10

def should_report_error(error_key):
    """Rate limit de erros"""
    now = time.time()
    timestamps = error_timestamps[error_key]
    
    # Remover timestamps antigos (> 1 minuto)
    timestamps[:] = [t for t in timestamps if now - t < 60]
    
    if len(timestamps) >= MAX_ERRORS_PER_MINUTE:
        return False
    
    timestamps.append(now)
    return True
```

---

**🎯 Com esta instrumentação, você terá controlo total sobre erros runtime e poderá corrigi-los rapidamente com ajuda da IA!**
