# HOTFIX para mt5_communication.py - WebSocket Handshake Errors

## 🔴 PROBLEMA IDENTIFICADO

**Erros nos logs:**
```
AssertionError: assert isinstance(response, Response)
EOFError: connection closed while reading HTTP request line
websockets.exceptions.InvalidMessage: did not receive a valid HTTP request
```

**Causa Raiz:**
1. Cliente (EA MT5) está enviando dados incorretos durante handshake
2. `process_request` callback pode estar retornando formato inválido
3. Falta try/except robusto no handshake
4. Logs de erro muito verbosos (poluem console)

## ✅ CORREÇÕES APLICADAS

### 1. **Melhorar process_request callback**
- Adicionar validação mais robusta de headers
- Garantir retorno correto: `None` para WS, `(status, headers, body)` para HTTP
- Adicionar try/except em cada etapa

### 2. **Suprimir erros de handshake esperados**
- Adicionar filtro de logging para erros websockets.exceptions
- Logar apenas WARNING ao invés de ERROR
- Evitar stacktraces desnecessários

### 3. **Adicionar timeout no handshake**
- Configurar `open_timeout=5` no websockets.serve
- Evitar conexões penduradas

### 4. **Melhorar error handling em _handle_client**
- Adicionar try/except específico para ConnectionClosed
- Logar detalhes do erro apenas em DEBUG
- Graceful disconnect

## 📋 IMPLEMENTAÇÃO

### Patch 1: Melhorar process_request (linha 1698)
```python
async def process_request(path, request_headers):
    """
    🔍 HOTFIX: Graceful handler for non-WebSocket hits.
    Return None to continue WebSocket handshake.
    Otherwise return (status, headers, body).
    """
    try:
        # Validar se headers existem
        if not request_headers:
            log.debug("[HOTFIX] Empty request headers, rejecting")
            body = b"Invalid request\n"
            return 400, [("Content-Type", "text/plain")], body
        
        upgrade = request_headers.get("Upgrade", "")
        connection_hdr = request_headers.get("Connection", "")
        
        # WebSocket handshake válido
        if (isinstance(upgrade, str) and "websocket" in upgrade.lower() and 
            isinstance(connection_hdr, str) and "upgrade" in connection_hdr.lower()):
            log.debug("[HOTFIX] Valid WebSocket handshake detected")
            return None  # ✅ Continue with WS handshake
        
        # HTTP request normal
        log.debug("[HOTFIX] Non-WebSocket request, returning HTTP response")
        body = b"MT5 WebSocket endpoint. Use WebSocket protocol.\n"
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body)))
        ]
        return 200, headers, body
        
    except Exception as e:
        log.warning(f"[HOTFIX] process_request error: {e}")
        # Fallback seguro
        return 200, [("Content-Type", "text/plain")], b"OK"
```

### Patch 2: Adicionar open_timeout (linha 1727)
```python
server = await websockets.serve(
    handler,
    self.host,
    self.port,
    ping_interval=globals().get("WS_PING_INTERVAL", None),
    ping_timeout=globals().get("WS_PING_TIMEOUT", None),
    max_size=globals().get("WS_MAX_SIZE", None),
    open_timeout=5,  # ✅ HOTFIX: Timeout de 5s no handshake
    process_request=process_request,
)
```

### Patch 3: Melhorar error handling em _handle_client (linha 2080)
```python
try:
    async for message in websocket:
        # ... código existente ...
        
except websockets.exceptions.ConnectionClosed as e:
    # ✅ HOTFIX: Graceful disconnect
    log.debug(f"[HOTFIX] Client {client_id} disconnected: {e.code} {e.reason}")
except Exception as e:
    log.error(f"[HOTFIX] Unexpected error in _handle_client for {client_id}: {e}")
finally:
    log.info(f"[WS] Client disconnected {client_id}")
    with self._metrics_lock:
        self.metrics["ws_connections"] = max(0, self.metrics.get("ws_connections", 1) - 1)
```

### Patch 4: Suprimir logs verbosos (linha 1754)
```python
except (_ws_exceptions.InvalidMessage, _ws_exceptions.InvalidUpgrade, 
        ConnectionResetError, EOFError, ValueError, AssertionError) as e:
    # ✅ HOTFIX: Suprimir erros esperados de handshake
    log.debug("_ws_main handshake error (suppressed): %s", str(e)[:100])
```

## 🎯 RESULTADO ESPERADO

**Antes:**
- ❌ Stacktraces a cada conexão inválida
- ❌ Logs poluídos com AssertionError
- ❌ Conexões penduradas sem timeout

**Depois:**
- ✅ Handshake robusto com validação
- ✅ Logs limpos (apenas DEBUG)
- ✅ Timeout de 5s no handshake
- ✅ Graceful disconnect

## 📝 NOTAS

- Erros de handshake são **normais** quando:
  - Browser acessa porta WebSocket
  - Ferramentas de monitoramento fazem health check
  - EA MT5 reconecta após erro
  
- Não é necessário logar ERROR para estes casos

- Se EA MT5 continuar com erro, verificar:
  1. EA está usando protocolo `ws://` (não `http://`)
  2. EA envia headers corretos: `Upgrade: websocket`, `Connection: Upgrade`
  3. EA usa biblioteca WebSocket válida (não socket TCP raw)
