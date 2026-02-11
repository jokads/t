# 🔐 JOKA Trading Bot - Guia de Segurança de Produção

## ⚠️ ATENÇÃO: LEIA ANTES DE USAR EM PRODUÇÃO

Este documento contém informações **CRÍTICAS** para operar o sistema com dinheiro real.

---

## 🚨 CHECKLIST PRÉ-PRODUÇÃO (OBRIGATÓRIO)

### 1. Credenciais e Tokens

- [ ] **Alterar password padrão** (`ThugParadise616#`)
- [ ] **Regenerar `DASHBOARD_SECRET_KEY`** (usar 64+ caracteres aleatórios)
- [ ] **Regenerar `JWT_SECRET`** (usar 64+ caracteres aleatórios)
- [ ] **Regenerar `BOT_PUSH_TOKEN`** (usar 64+ caracteres aleatórios)
- [ ] **Configurar `TELEGRAM_TOKEN`** (obter do @BotFather)
- [ ] **Configurar `TELEGRAM_CHAT_ID`** (obter do @userinfobot)
- [ ] **Configurar `NEWS_API_KEY`** (obter em newsapi.org)

### 2. Limites de Trading

- [ ] **Definir `MAX_LOT_SIZE`** (volume máximo por ordem)
- [ ] **Definir `MAX_RISK_PER_TRADE`** (% máximo de risco por trade)
- [ ] **Definir `MAX_DAILY_LOSS`** (perda máxima diária em $)
- [ ] **Definir `MAX_CONCURRENT_POSITIONS`** (posições simultâneas)
- [ ] **Definir `MAX_DRAWDOWN_PERCENT`** (drawdown máximo permitido)

### 3. Configurações de Segurança

- [ ] **Ativar HTTPS** (`HTTPS_ENABLED=True`)
- [ ] **Configurar firewall** (permitir apenas IPs confiáveis)
- [ ] **Ativar rate limiting** (`RATE_LIMIT_ENABLED=True`)
- [ ] **Configurar backup automático** (`AUTO_SNAPSHOT_ENABLED=True`)
- [ ] **Testar Watchdog** (verificar restart automático)

### 4. Testes Obrigatórios

- [ ] **Testar Kill Switch** (emergency stop)
- [ ] **Testar alternância SAFE ↔ LIVE**
- [ ] **Testar validação de ordens** (ordem inválida deve ser rejeitada)
- [ ] **Testar alertas Telegram** (enviar mensagem de teste)
- [ ] **Testar rollback** (criar snapshot e restaurar)
- [ ] **Verificar integridade de logs** (hash deve validar)

### 5. Monitorização

- [ ] **Configurar alertas de erro** (Telegram + Email)
- [ ] **Configurar alertas de drawdown** (notificar se > 80% do limite)
- [ ] **Configurar alertas de notícias** (alto impacto)
- [ ] **Verificar logs diariamente** (auditoria)
- [ ] **Backup semanal** (exportar logs e snapshots)

---

## 🛡️ CAMADAS DE PROTEÇÃO

### 1. Kill Switch (Emergency Stop)

**O que faz:**
- Fecha **TODAS** as posições abertas
- Bloqueia **TODAS** as novas ordens
- Desativa **TODAS** as estratégias
- Envia alerta crítico no Telegram
- Muda automaticamente para modo SAFE

**Quando usar:**
- Erro crítico no bot
- Notícia de alto impacto inesperada
- Comportamento anormal do mercado
- Perda acelerada
- Qualquer situação de pânico

**Como ativar:**
1. Ir para `/security`
2. Clicar em "🚨 ATIVAR EMERGENCY STOP"
3. Inserir password
4. Inserir motivo
5. Confirmar

**Cooldown:** 60 segundos entre ativações

---

### 2. Modo SAFE vs LIVE

#### Modo SAFE (Simulação)
- ✅ **Todas as ordens são BLOQUEADAS**
- ✅ Bot continua a analisar mercado
- ✅ Estratégias continuam a gerar sinais
- ✅ Nenhuma ordem chega ao MT5
- ✅ Ideal para testar novas estratégias

#### Modo LIVE (Trading Real)
- ⚠️ **Ordens são ENVIADAS ao MT5**
- ⚠️ **Dinheiro real em risco**
- ⚠️ Requer confirmação dupla
- ⚠️ Cooldown de 60 segundos

**Como alternar:**
1. Ir para `/security`
2. Clicar no modo desejado (SAFE ou LIVE)
3. Inserir password
4. Digitar confirmação: `CONFIRMO_SAFE` ou `CONFIRMO_LIVE`
5. Confirmar

**⚠️ NUNCA mude para LIVE sem completar o checklist!**

---

### 3. Validação de Ordens

**Todas as ordens passam por validação ANTES do MT5:**

#### Validações Automáticas:
- ✅ Volume dentro do limite (`MAX_LOT_SIZE`)
- ✅ Risco dentro do limite (`MAX_RISK_PER_TRADE`)
- ✅ Drawdown diário não excedido (`MAX_DAILY_LOSS`)
- ✅ SL/TP válidos
- ✅ Símbolo válido
- ✅ Tipo de ordem válido (BUY/SELL)
- ✅ Sem notícias de alto impacto em curso
- ✅ Sistema não em modo SAFE
- ✅ Emergency stop não ativo

#### Se ordem for rejeitada:
- ❌ Ordem **NÃO** é enviada ao MT5
- 📝 Motivo é registado no log
- 🔔 Notificação no dashboard
- 📱 Alerta opcional no Telegram

---

### 4. Watchdog Automático

**Monitoriza continuamente:**
- 🤖 Bot freeze (bot travado)
- 🔌 MT5 socket desconectado
- 💾 Memória alta (> 80%)
- 🧠 IA travada
- ⏱️ Latência alta

**Ações automáticas:**
- 🔄 Restart do bot (se freeze)
- 🟡 Mudança para SAFE (se MT5 down)
- 📱 Alertas Telegram
- 📊 Broadcast para UI

**Configuração:**
```env
WATCHDOG_ENABLED=True
WATCHDOG_CHECK_INTERVAL=10
WATCHDOG_AUTO_RESTART=True
WATCHDOG_AUTO_SAFE_MODE=True
```

---

### 5. Auditoria Imutável

**Todas as ações críticas são registadas com hash de integridade:**

#### Ações registadas:
- 🚨 Emergency stop
- 🔄 Mudança de modo (SAFE ↔ LIVE)
- 💾 Criação de snapshots
- ⏮️ Rollbacks
- 🔑 Mudança de credenciais
- 🤖 Aplicação de patches IA
- ⚙️ Mudanças de configuração

#### Verificação de integridade:
1. Ir para `/audit`
2. Selecionar ação
3. Clicar em "Verificar"
4. Sistema recalcula hash
5. Compara com hash armazenado

**Se hash não coincidir = LOG FOI ALTERADO! 🚨**

---

### 6. Snapshots e Rollback

**Criar snapshot antes de:**
- Aplicar patch de IA
- Editar estratégias
- Mudar configurações críticas
- Atualizar código

**Como criar snapshot:**
1. Ir para `/audit`
2. Clicar em "Criar Snapshot"
3. Snapshot é criado automaticamente

**Como fazer rollback:**
1. Ir para `/audit`
2. Tab "Snapshots"
3. Selecionar snapshot
4. Clicar em "Rollback"
5. Inserir password
6. Confirmar

**⚠️ Rollback restaura:**
- Configurações
- Estratégias
- Modo operacional
- Paths

---

## 🤖 IA COM LIMITES

### Restrições de Segurança:

#### ❌ IA NÃO PODE:
- Alterar `trading_bot_core.py`
- Enviar ordens diretas ao MT5
- Mudar modo SAFE/LIVE
- Desativar validações
- Alterar limites de risco

#### ✅ IA SÓ PODE:
- Sugerir correções de código
- Gerar patches revisáveis
- Propor configurações
- Analisar erros
- Otimizar estratégias

### Configurações:
```env
AI_MAX_SUGGESTIONS_PER_HOUR=10
AI_CONFIDENCE_THRESHOLD=0.7
AI_AUTO_APPLY=False
```

**⚠️ NUNCA ative `AI_AUTO_APPLY=True` em produção!**

---

## 📊 MONITORIZAÇÃO CONTÍNUA

### Verificações Diárias:

#### 1. Manhã (antes do mercado abrir):
- [ ] Verificar status do sistema (`/security`)
- [ ] Verificar checklist de produção (`/security`)
- [ ] Verificar logs de erro (`/system-control`)
- [ ] Verificar drawdown acumulado
- [ ] Verificar conexão MT5

#### 2. Durante o trading:
- [ ] Monitorizar posições abertas
- [ ] Verificar alertas Telegram
- [ ] Verificar watchdog status
- [ ] Verificar validações rejeitadas

#### 3. Final do dia:
- [ ] Exportar logs de auditoria
- [ ] Criar snapshot diário
- [ ] Verificar performance
- [ ] Analisar trades rejeitados
- [ ] Backup de dados

---

## 🚨 PROCEDIMENTOS DE EMERGÊNCIA

### Cenário 1: Bot Travado
1. Verificar Watchdog (`/security`)
2. Se não restart automático, usar `/system-control` → Restart Bot
3. Verificar logs para causa
4. Se persistir, ativar Emergency Stop

### Cenário 2: Perda Acelerada
1. **ATIVAR EMERGENCY STOP IMEDIATAMENTE**
2. Analisar posições fechadas
3. Verificar logs de estratégias
4. Identificar causa
5. Corrigir antes de reativar

### Cenário 3: MT5 Desconectado
1. Watchdog muda automaticamente para SAFE
2. Verificar conexão MT5
3. Reiniciar MT5 se necessário
4. Testar conexão
5. Voltar para LIVE apenas se estável

### Cenário 4: Notícia de Alto Impacto
1. Sistema bloqueia ordens automaticamente
2. Aguardar volatilidade diminuir
3. Analisar impacto nas posições abertas
4. Considerar fechar posições manualmente
5. Reativar após mercado estabilizar

### Cenário 5: Erro Crítico de Código
1. Ativar Emergency Stop
2. Ir para `/diagnostics`
3. Escanear projeto
4. Enviar para IA analisar
5. Aplicar correção
6. Testar em SAFE
7. Criar snapshot
8. Voltar para LIVE

---

## 🔒 HARDENING DE SEGURANÇA

### 1. Servidor

```bash
# Firewall (permitir apenas IPs confiáveis)
sudo ufw allow from YOUR_IP to any port 5000
sudo ufw enable

# Fail2ban (proteção brute-force)
sudo apt install fail2ban
sudo systemctl enable fail2ban

# HTTPS (usar certificado SSL)
# Configurar nginx como reverse proxy com SSL
```

### 2. Aplicação

```env
# Rate limiting agressivo
RATE_LIMIT_PER_MINUTE=30
RATE_LIMIT_PER_HOUR=500

# Sessões únicas
SESSION_TIMEOUT=3600

# CSRF protection
CSRF_ENABLED=True

# Logout automático
AUTO_LOGOUT_MINUTES=30
```

### 3. Database

```bash
# Permissões restritas
chmod 600 data/dashboard.db

# Backup automático
crontab -e
# Adicionar: 0 */6 * * * cp data/dashboard.db backups/dashboard_$(date +\%Y\%m\%d_\%H\%M\%S).db
```

### 4. Logs

```bash
# Rotação de logs
sudo apt install logrotate

# Configurar em /etc/logrotate.d/joka-bot
/path/to/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 user group
}
```

---

## 📱 ALERTAS TELEGRAM

### Configurar Bot:
1. Falar com @BotFather no Telegram
2. Criar novo bot: `/newbot`
3. Copiar token
4. Adicionar ao `.env`: `TELEGRAM_TOKEN=...`

### Obter Chat ID:
1. Falar com @userinfobot
2. Copiar ID
3. Adicionar ao `.env`: `TELEGRAM_CHAT_ID=...`

### Testar:
1. Ir para `/integrations`
2. Tab "Telegram"
3. Clicar em "Enviar Teste"
4. Verificar mensagem recebida

### Tipos de Alertas:
- 🟢 **Trades**: Abertura/fecho de posições
- 🟡 **Risco**: Drawdown, limites atingidos
- 🔴 **Erros**: Erros críticos, bot down
- 📰 **Notícias**: Alto impacto

---

## 📈 MÉTRICAS DE PERFORMANCE

### KPIs a Monitorizar:

#### Trading:
- Win rate
- Profit factor
- Drawdown máximo
- Sharpe ratio
- Ordens rejeitadas / aprovadas

#### Sistema:
- Uptime do bot
- Latência média
- Uso de memória
- Erros por hora
- Restarts automáticos

#### Segurança:
- Tentativas de login falhadas
- Ações críticas por dia
- Validações rejeitadas
- Emergency stops ativados
- Integridade de logs

---

## ✅ CHECKLIST FINAL

Antes de mudar para modo LIVE:

- [ ] Todas as credenciais alteradas
- [ ] Todos os limites configurados
- [ ] HTTPS ativado
- [ ] Firewall configurado
- [ ] Telegram funcionando
- [ ] Kill switch testado
- [ ] Validação de ordens testada
- [ ] Watchdog testado
- [ ] Snapshots funcionando
- [ ] Rollback testado
- [ ] Logs de auditoria verificados
- [ ] Backup automático ativo
- [ ] Monitorização configurada
- [ ] Procedimentos de emergência revistos
- [ ] Testado em SAFE por 1 semana mínimo

---

## 📞 SUPORTE

Em caso de dúvidas ou problemas:

1. Verificar logs: `/system-control` → System Logs
2. Verificar diagnóstico: `/diagnostics`
3. Consultar auditoria: `/audit`
4. Contactar suporte técnico

---

## ⚖️ DISCLAIMER

**ATENÇÃO:**
- Trading envolve risco de perda de capital
- Este sistema é uma ferramenta, não uma garantia de lucro
- Teste extensivamente em SAFE antes de usar LIVE
- Nunca arrisque mais do que pode perder
- Monitorize constantemente o sistema
- Mantenha sempre o controlo manual

**O utilizador é 100% responsável pelas decisões de trading.**

---

**🔥 BOA SORTE E TRADE COM SEGURANÇA! 🔥**