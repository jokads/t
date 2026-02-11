# 🚀 GUIA COMPLETO DE PRODUÇÃO - BOT MT5

## ✅ O QUE FOI CORRIGIDO

### **1. Configuração da API**
- ✅ Detecção automática de ambiente (dev/produção)
- ✅ Logging detalhado de todas as requisições
- ✅ Tratamento de erros melhorado
- ✅ Verificação de saúde do backend
- ✅ Retry automático em caso de falha

### **2. CORS no Backend**
- ✅ Preflight requests (OPTIONS) configurados
- ✅ Headers corretos para todas as origens
- ✅ Credentials habilitados
- ✅ Logging de todas as requisições

### **3. Dashboard Frontend**
- ✅ Banner de erro quando backend está offline
- ✅ Botão de retry manual
- ✅ Indicador de carregamento
- ✅ Logs detalhados no console do browser
- ✅ Estados de loading adequados

### **4. Variáveis de Ambiente**
- ✅ `.env` configurado com todas as variáveis
- ✅ `BOT_BASE_PATH` para detecção de caminhos
- ✅ `DASHBOARD_HOST` e `DASHBOARD_PORT` configuráveis
- ✅ `VITE_API_BASE_URL` para produção

---

## 🎯 COMO USAR AGORA

### **PASSO 1: Configurar Variáveis de Ambiente**

Edite o ficheiro `.env` na raiz do projeto (`C:/bot-mt5/.env`):

```env
# ✅ CAMINHO RAIZ DO PROJETO (MUITO IMPORTANTE!)
BOT_BASE_PATH=C:/bot-mt5

# ✅ CONFIGURAÇÃO DO SERVIDOR
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=5000

# ✅ CREDENCIAIS
BOT_USERNAME=joka
BOT_PASSWORD=ThugParadise616#

# ✅ MT5 SOCKET
MT5_SOCKET_HOST=127.0.0.1
MT5_SOCKET_PORT=9090

# ✅ MODELOS AI
GPT4ALL_MODELS_DIR=C:/bot-mt5/models/gpt4all

# ✅ FRONTEND API
VITE_API_BASE_URL=http://127.0.0.1:5000
```

---

### **PASSO 2: Instalar Dependências**

```bash
cd C:\bot-mt5
npm install
```

---

### **PASSO 3: Build do Frontend**

```bash
npm run build
```

**Resultado esperado:**
```
✓ built in xxxms
out/index.html created
out/assets/... created
```

---

### **PASSO 4: Iniciar o Sistema**

```bash
python trading_bot_core.py
```

**Isto inicia TUDO automaticamente:**
- ✅ Bot de trading
- ✅ Dashboard backend (porta 5000)
- ✅ MT5 socket connection (porta 9090)
- ✅ Atualização em tempo real

---

### **PASSO 5: Aceder ao Dashboard**

Abra o navegador:
```
http://localhost:5000
```

**Login:**
```
Utilizador: joka
Password: ThugParadise616#
```

---

## 🔍 COMO VERIFICAR SE ESTÁ TUDO A FUNCIONAR

### **1. Verificar Backend**

Abra o browser console (F12) e vá ao dashboard. Deve ver logs assim:

```
🔧 API Config: { isDev: false, API_BASE: "http://127.0.0.1:5000", mode: "production" }
🔍 Verificando backend...
🏥 Health check: http://127.0.0.1:5000/api/health
✅ Backend healthy: { status: "healthy", bot_connected: true, ... }
📊 Buscando dados em tempo real...
📡 API Request: { endpoint: "/api/mt5/account", url: "http://127.0.0.1:5000/api/mt5/account", ... }
✅ API Response: { endpoint: "/api/mt5/account", status: 200, ok: true }
```

### **2. Verificar MT5 Connection**

No dashboard, deve ver:
- 🟢 **MT5: Online** (ponto verde a piscar)
- 🟢 **Bot: Ativo** (ponto verde a piscar)
- **Estratégias: X** (número de estratégias ativas)
- **Margem: XXXX%** (nível de margem MT5)

### **3. Verificar Dados da Conta**

Os cards principais devem mostrar:
- **Balance**: Valor real do MT5
- **Equity**: Equity em tempo real
- **Margem Livre**: Margem disponível
- **Profit/Loss**: Lucro/prejuízo atual

---

## 🛠️ RESOLUÇÃO DE PROBLEMAS

### ❌ **"Backend Offline" no Dashboard**

**Possíveis causas:**

1. **Bot não está a correr**
   ```bash
   cd C:\bot-mt5
   python trading_bot_core.py
   ```

2. **Porta 5000 ocupada**
   ```bash
   # Windows
   netstat -ano | findstr :5000
   
   # Se encontrar processo, mate-o:
   taskkill /PID <PID> /F
   ```

3. **Firewall a bloquear**
   - Adicione exceção para Python
   - Adicione exceção para porta 5000

4. **BOT_BASE_PATH errado**
   - Verifique `.env`: `BOT_BASE_PATH=C:/bot-mt5`
   - Use barras normais `/`, não `\`

---

### ❌ **"Erro na requisição API" no Console**

**Solução:**

1. **Verificar se backend está a correr**
   ```bash
   curl http://127.0.0.1:5000/api/health
   ```
   
   Deve retornar:
   ```json
   {
     "status": "healthy",
     "bot_connected": true,
     "mt5_socket_connected": true
   }
   ```

2. **Verificar logs do backend**
   ```bash
   tail -f logs/dashboard_server.log
   ```

3. **Limpar cache do browser**
   - F12 → Application → Clear Storage
   - Reload (Ctrl+R)

---

### ❌ **"MT5: Offline" mas bot está a correr**

**Solução:**

1. **Verificar MT5 Socket**
   ```bash
   netstat -ano | findstr :9090
   ```

2. **Verificar se MT5 está aberto**
   - Abra MetaTrader 5
   - Vá a Tools → Options → Expert Advisors
   - Ative "Allow automated trading"

3. **Reiniciar o bot**
   ```bash
   # Parar (Ctrl+C)
   # Iniciar novamente
   python trading_bot_core.py
   ```

---

### ❌ **Frontend não carrega (página em branco)**

**Solução:**

1. **Verificar se build foi feito**
   ```bash
   dir out\index.html
   # ou
   ls out/index.html
   ```

2. **Fazer build manualmente**
   ```bash
   cd C:\bot-mt5
   npm install
   npm run build
   ```

3. **Verificar logs do backend**
   Deve ver:
   ```
   ✅ Frontend já está buildado
   📊 Dashboard Web: http://0.0.0.0:5000
   ```

---

## 📊 MONITORIZAÇÃO EM PRODUÇÃO

### **1. Logs do Sistema**

```bash
# Backend
tail -f logs/dashboard_server.log

# Bot principal
tail -f logs/trading_bot_runtime.log

# Erros
tail -f logs/error.log
```

### **2. Health Checks Automáticos**

```bash
# Criar script de monitorização (monitor.sh)
#!/bin/bash
while true; do
  STATUS=$(curl -s http://127.0.0.1:5000/api/health | jq -r '.status')
  if [ "$STATUS" != "healthy" ]; then
    echo "❌ Backend não está saudável!"
    # Enviar notificação aqui
  else
    echo "✅ Sistema OK"
  fi
  sleep 60
done
```

### **3. Alertas de Erro**

Configure no Telegram ou email para receber alertas:
- Backend offline
- MT5 desconectado
- Estratégias com erro
- Margem baixa

---

## 🔥 CHECKLIST FINAL DE PRODUÇÃO

Antes de colocar em produção real:

- [ ] ✅ `.env` configurado com valores corretos
- [ ] ✅ `BOT_BASE_PATH` correto
- [ ] ✅ Frontend buildado (`npm run build`)
- [ ] ✅ Backend inicia sem erros
- [ ] ✅ MT5 conectado (porta 9090)
- [ ] ✅ Dashboard acessível em http://localhost:5000
- [ ] ✅ Login funciona
- [ ] ✅ Dados da conta aparecem
- [ ] ✅ Posições são mostradas
- [ ] ✅ Logs aparecem no dashboard
- [ ] ✅ Estratégias carregadas
- [ ] ✅ Modelos AI carregados
- [ ] ✅ DRY_RUN testado primeiro
- [ ] ✅ Backups configurados
- [ ] ✅ Monitorização ativa

---

## 🚀 PRÓXIMOS PASSOS

1. **Testar em modo DRY_RUN**
   ```env
   DRY_RUN=true
   ```

2. **Monitorizar durante 24h**
   - Verificar logs
   - Verificar performance
   - Verificar memória

3. **Ajustar parâmetros**
   - Confiança mínima
   - Volume de trading
   - Stop loss / Take profit

4. **Activar modo REAL**
   ```env
   DRY_RUN=false
   ```

5. **Monitorizar 24/7**
   - Alertas configurados
   - Backups automáticos
   - Health checks ativos

---

## 💡 DICAS IMPORTANTES

1. **Sempre testar em DRY_RUN primeiro**
2. **Fazer backup da BD antes de alterações**
3. **Monitorizar logs regularmente**
4. **Ajustar confiança mínima conforme performance**
5. **Nunca correr várias instâncias ao mesmo tempo**
6. **Verificar margem antes de aumentar volume**
7. **Ter sempre plano B (stop loss manual)**

---

## 📞 SUPORTE

Se continuar com problemas:

1. **Verificar logs:**
   - `logs/dashboard_server.log`
   - `logs/trading_bot_runtime.log`

2. **Testar API manualmente:**
   ```bash
   curl http://127.0.0.1:5000/api/health
   curl http://127.0.0.1:5000/api/mt5/status
   ```

3. **Verificar console do browser (F12)**
   - Ver mensagens de erro
   - Verificar network tab
   - Ver logs da API

---

**💪 ESTÁ TUDO PRONTO! BOA SORTE COM O TRADING! 🚀**
