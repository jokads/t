# 📚 RESEARCH FINDINGS - High-Frequency Trading Bot

**Data:** 2026-02-11  
**Objetivo:** Melhores práticas para bot MT5 assíncrono de baixa latência

---

## 🔗 FONTES PESQUISADAS

### 1. FastAPI + WebSockets Low-Latency

#### 📄 **10 FastAPI WebSocket Patterns for Live Dashboards**
**URL:** https://medium.com/@connect.hashblock/10-fastapi-websocket-patterns-for-live-dashboards-3e36f3080510  
**Data:** Sep 29, 2025  
**Relevância:** ⭐⭐⭐⭐⭐

**Principais Padrões Identificados:**

1. **Broadcast Hub Pattern**
   - Separar lógica de negócio do WebSocket plumbing
   - Hub central recebe eventos e distribui para clientes
   - Usar `asyncio.Queue` para cada cliente (maxsize=100)
   
   ```python
   class Hub:
       def __init__(self):
           self.clients = set()
           self.events = asyncio.Queue()
       
       async def register(self, ws: WebSocket):
           await ws.accept()
           q = asyncio.Queue(maxsize=100)
           self.clients.add((ws, q))
   ```

2. **Backpressure Handling**
   - Limitar tamanho da fila por cliente
   - Dropar mensagens antigas se fila cheia
   - Evitar bloquear produtor

3. **Delta Updates**
   - Enviar apenas mudanças, não estado completo
   - Reduz bandwidth e latência

4. **Resumable Cursors**
   - Cliente pode reconectar e retomar de onde parou
   - Usar sequence numbers

5. **Auth Pattern**
   - Validar token JWT no handshake
   - Renovar token periodicamente

6. **Fan-Out Pattern**
   - Um produtor, múltiplos consumidores
   - Usar asyncio.create_task para cada cliente

7. **Observability**
   - Métricas: conexões ativas, mensagens/s, latência
   - Logs estruturados

**Aplicação ao Bot MT5:**
- ✅ Usar Hub para distribuir sinais de trading
- ✅ Backpressure para evitar sobrecarga
- ✅ Auth JWT para EA MT5
- ✅ Métricas para monitoramento

---

#### 📄 **FastAPI Ultra: Uvicorn, uvloop & HTTP/3**
**URL:** https://medium.com/@bhagyarana80/fastapi-ultra-uvicorn-uvloop-http-3-for-blazing-apis-1b44e496606c  
**Data:** Sep 4, 2025  
**Relevância:** ⭐⭐⭐⭐

**Principais Descobertas:**

1. **uvloop Benefits**
   - 2-4x mais rápido que asyncio default
   - Reduz tail latency
   - Baseado em libuv (Node.js)
   
   ```python
   import uvloop
   uvloop.install()
   ```

2. **⚠️ Windows Limitation**
   - uvloop **NÃO funciona no Windows**
   - Apenas Linux/macOS
   - Usar condicional:
   
   ```python
   import sys
   if sys.platform != "win32":
       import uvloop
       uvloop.install()
   ```

3. **Uvicorn Configuration**
   - `--workers`: múltiplos processos
   - `--loop uvloop`: event loop otimizado
   - `--ws websockets`: WebSocket protocol
   
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000 \
       --loop uvloop --workers 4 --ws websockets
   ```

**Aplicação ao Bot MT5:**
- ✅ Usar uvloop em produção (Linux)
- ⚠️ Detectar Windows e desabilitar
- ✅ Configurar workers baseado em CPU cores

---

### 2. Pydantic v2 Performance

#### 📄 **Pydantic v2 Migration Guide** (a pesquisar)
**Status:** Pendente  
**Prioridade:** Alta

**Questões a responder:**
- Breaking changes v1 → v2?
- Performance gains?
- Compatibilidade com FastAPI atual?

---

### 3. llama.cpp / GGUF Worker Pool

#### 📄 **llama-cpp-python Official Documentation**
**URL:** https://llama-cpp-python.readthedocs.io/  
**Data:** 2026  
**Relevância:** ⭐⭐⭐⭐⭐

**Principais Descobertas:**

1. **High-Level API**
   ```python
   from llama_cpp import Llama
   
   llm = Llama(
       model_path="./models/model.gguf",
       n_gpu_layers=-1,  # GPU acceleration
       n_ctx=2048,       # context window
   )
   
   output = llm(
       "Q: Analyze market...",
       max_tokens=32,
       stop=["\n"],
       echo=False
   )
   ```

2. **JSON Schema Mode** (CRÍTICO para trading)
   ```python
   llm.create_chat_completion(
       messages=[...],
       response_format={
           "type": "json_object",
           "schema": {
               "type": "object",
               "properties": {
                   "action": {"type": "string"},
                   "confidence": {"type": "number"}
               },
               "required": ["action", "confidence"]
           }
       }
   )
   ```

3. **Worker Pool Pattern** (a implementar)
   - Carregar modelo uma vez por processo
   - Comunicar via `multiprocessing.Queue`
   - Timeout via `asyncio.wait_for`
   - Evitar memory leaks com processo dedicado

**Aplicação ao Bot MT5:**
- ✅ Usar JSON Schema para validar respostas
- ✅ Processo dedicado por modelo (evita GIL)
- ✅ Queue para comunicação async-safe
- ✅ Timeout configurável (8s quick, 30s deep)

---

### 4. MQL5 Socket/WebSocket EA

#### 📄 **Working with sockets in MQL**
**URL:** https://www.mql5.com/en/articles/2599  
**Data:** Jul 20, 2016  
**Relevância:** ⭐⭐⭐⭐

**Principais Descobertas:**

1. **TCP Client Pattern (MQL5)**
   ```mql5
   // 1. Initialize
   WSAStartup(MAKEWORD(2,2), wsaData);
   
   // 2. Create socket
   SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
   
   // 3. Set non-blocking
   ioctlsocket(sock, FIONBIO, &nonBlocking);
   
   // 4. Connect
   connect(sock, serverAddr, sizeof(serverAddr));
   
   // 5. Send/Receive
   send(sock, buffer, len, 0);
   recv(sock, buffer, len, 0);
   
   // 6. Close
   closesocket(sock);
   WSACleanup();
   ```

2. **Message Format** (proposta)
   ```json
   // EA → Python
   {
     "type": "signal.request",
     "timestamp": "2026-02-11T20:30:00Z",
     "auth_token": "jwt_token_here",
     "payload": {
       "symbol": "EURUSD",
       "timeframe": "M5",
       "price": 1.0870,
       "account_id": "12345"
     }
   }
   
   // Python → EA
   {
     "type": "signal.response",
     "timestamp": "2026-02-11T20:30:01Z",
     "payload": {
       "action": "BUY",
       "lot": 0.01,
       "stop_loss": 1.0850,
       "take_profit": 1.0900,
       "confidence": 0.75
     }
   }
   ```

3. **Heartbeat Pattern**
   - EA envia ping a cada 30s
   - Python responde pong
   - Se timeout > 60s, reconectar

**Aplicação ao Bot MT5:**
- ✅ Usar TCP socket (não WebSocket) para simplicidade
- ✅ Non-blocking mode para não travar EA
- ✅ JSON messages validadas com pydantic
- ✅ Heartbeat para detectar conexões mortas

---

### 5. Circuit-Breaker Asyncio

#### 📄 **Python Circuit Breaker Patterns** (a pesquisar)
**Status:** Pendente  
**Prioridade:** Média

**Opções:**
- Biblioteca `aiobreaker`
- Implementação custom
- Integração com timeout

---

### 6. Token Bucket Rate Limiter

#### 📄 **Asyncio Rate Limiter Examples** (a pesquisar)
**Status:** Pendente  
**Prioridade:** Média

**Requisitos:**
- Por (account_id, symbol)
- Configurável (default: 60 orders/min)
- Async-safe

---

## 📊 DECISÕES TÉCNICAS PRELIMINARES

### ✅ Confirmadas

1. **FastAPI + Uvicorn + uvloop** (Linux only)
2. **WebSocket Hub Pattern** para distribuição de sinais
3. **Backpressure** com Queue maxsize
4. **JWT Auth** para EA MT5
5. **Structured Logging** (JSON)

### ⚠️ A Confirmar

1. **Pydantic v1 vs v2** (verificar compatibilidade)
2. **llama.cpp worker pattern** (multiprocessing vs subprocess)
3. **MQL5 WebSocket format** (encontrar exemplo EA)
4. **Circuit-breaker library** (aiobreaker vs custom)

---

## 🚀 PRÓXIMOS PASSOS DE PESQUISA

1. ✅ FastAPI WebSocket patterns
2. ✅ uvloop benefits & limitations
3. ✅ Pydantic v2 migration (docs lidas)
4. ✅ llama.cpp worker pool (API documentada)
5. ✅ MQL5 socket examples (padrão TCP identificado)
6. ⏳ Circuit-breaker patterns (baixa prioridade)
7. ⏳ Token bucket rate limiter (baixa prioridade)

---

**Última atualização:** 2026-02-11 20:30 GMT+1
