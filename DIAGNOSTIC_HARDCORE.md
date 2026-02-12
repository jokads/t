# DIAGNOSTIC HARDCORE - Bot MT5 Trading

## PROBLEMAS CRÍTICOS IDENTIFICADOS

### 1. WEBSOCKET HANDSHAKE ERRORS (CRÍTICO)
**Frequência:** Contínua (a cada 1-2 segundos)
**Impacto:** Polui logs, pode causar memory leaks

**Erros:**
```
AssertionError: assert isinstance(response, Response)
ValueError: unsupported HTTP method; expected GET; got POST
websockets.exceptions.InvalidMessage: did not receive a valid HTTP request
websockets.exceptions.ConnectionClosedError: no close frame received or sent
```

**Causa Raiz:**
- `process_request` callback retorna formato inválido
- Cliente (browser/tool) faz POST/HTTP em vez de WebSocket GET
- Falta try/except robusto no handshake
- Logs não são suprimidos

**Solução:**
1. Melhorar `process_request` para retornar `None` ou tuple válido
2. Adicionar try/except em `_ws_main` para suprimir erros esperados
3. Adicionar `open_timeout=10` no `websockets.serve`
4. Logar apenas DEBUG para handshake errors

---

### 2. AI RETORNA HOLD 100% (CRÍTICO)
**Frequência:** SEMPRE (100% dos casos)
**Impacto:** Bot NUNCA executa trades

**Logs:**
```
AIManager vote_trade returned: {'decision': 'HOLD', 'confidence': 0.0, ...}
All 6 models: {'model': 'gpt0-5', 'decision': 'HOLD', 'confidence': 0.0}
EURUSD: AI decision=HOLD conf=0.00 tp=1.0 sl=1.0
EURUSD: decision is HOLD -> skipping
```

**Causa Raiz:**
1. Modelos GPT4All não estão carregados corretamente
2. Prompt está mal formatado
3. Parsing de resposta falha
4. Todos modelos retornam confidence=0.0
5. Bot depende 100% da AI (sem fallback)

**Solução:**
1. Adicionar fallback para estratégias técnicas quando AI falha
2. Detectar quando TODOS modelos retornam HOLD (0.0)
3. Usar estratégias (SuperTrend, EMA, RSI) como decisão primária
4. AI apenas valida/ajusta (não bloqueia)
5. Adicionar modo `AI_OPTIONAL=true`

---

### 3. ESTRATÉGIAS NÃO GERAM SINAIS
**Frequência:** Sempre
**Impacto:** Buffer de sinais vazio

**Logs:**
```
run_strategies_cycle concluído — 0 sinais enfileirados neste ciclo | buffer_total=0
Skipping non-live strategy: BacktestEngine
Skipping non-live strategy: StrategyEngine
```

**Causa Raiz:**
- Apenas AdaptiveMLStrategy está ativa
- AdaptiveMLStrategy não gera sinais (depende de AI)
- SuperTrend, EMA, RSI não estão sendo executadas

**Solução:**
1. Ativar estratégias técnicas (SuperTrend, EMA Crossover, RSI)
2. Criar `HybridStrategy` que combina múltiplas estratégias
3. Adicionar `FallbackStrategy` rule-based (EMA + RSI + Bollinger)
4. Garantir que pelo menos 1 estratégia técnica sempre roda

---

### 4. UNDEFINED VARIABLES (MÉDIO)
**Impacto:** Potenciais crashes

**Possíveis erros (não visíveis nos logs mas detectáveis por linter):**
- `mt5` vs `mt5_comm` confusion
- `item` vs `external_signal` undefined
- `out` vs `response` naming inconsistency

**Solução:**
1. Scan completo com Pylance/mypy
2. Corrigir todas referências undefined
3. Adicionar type hints

---

## ARQUITETURA PROPOSTA (HARDCORE MODE)

### Fluxo de Decisão ROBUSTO

```
1. Estratégias Técnicas (PRIMÁRIAS)
   ├─ SuperTrend (trend following)
   ├─ EMA Crossover (momentum)
   ├─ RSI Oversold/Overbought (reversal)
   ├─ Bollinger Bands (volatility)
   └─ ICT Concepts (smart money)
   
2. Votação de Estratégias
   ├─ Cada estratégia vota: BUY/SELL/HOLD
   ├─ Peso por estratégia (configurável)
   ├─ Decisão por maioria ponderada
   └─ Confidence agregada
   
3. AI Validation (OPCIONAL)
   ├─ Se AI disponível: valida decisão
   ├─ Se AI concorda: aumenta confidence
   ├─ Se AI discorda: reduz confidence
   └─ Se AI falha: ignora e usa estratégias
   
4. Risk Manager
   ├─ Valida exposição
   ├─ Ajusta volume
   ├─ Verifica max drawdown
   └─ Aprova/rejeita trade
   
5. Execução
   ├─ Se approved: executa via MT5
   ├─ Se rejected: loga motivo
   └─ Atualiza métricas
```

### Configuração via .env

```bash
# AI Configuration
USE_AI=true                    # true|false
AI_MODE=validation             # validation|primary|disabled
AI_TIMEOUT=10                  # seconds
AI_MIN_CONFIDENCE=0.30         # 0.0-1.0

# Strategy Configuration
STRATEGY_MODE=hybrid           # hybrid|technical|ai_only
STRATEGY_WEIGHTS=supertrend:0.3,ema:0.2,rsi:0.2,bollinger:0.15,ict:0.15

# Fallback Configuration
FALLBACK_ENABLED=true
FALLBACK_STRATEGY=ema_rsi      # ema_rsi|supertrend|conservative

# WebSocket Configuration
USE_DASHBOARD=false            # Disable dashboard WebSocket
MT5_SOCKET_PORT=9090
MT5_SOCKET_HOST=127.0.0.1

# Execution Configuration
DRY_RUN=false
AUTO_INIT_MT5=true
MIN_CONFIDENCE=0.40            # Minimum confidence to execute
```

---

## PRIORIDADES DE CORREÇÃO

### P0 (CRÍTICO - Bloqueia bot)
1. ✅ Suprimir WebSocket handshake errors
2. ✅ Implementar fallback de estratégias técnicas
3. ✅ Remover dependência 100% de AI
4. ✅ Ativar SuperTrend + EMA + RSI

### P1 (ALTO - Melhora robustez)
5. ✅ Criar HybridStrategy com votação
6. ✅ Adicionar .env.example
7. ✅ Corrigir undefined variables
8. ✅ Adicionar testes unitários

### P2 (MÉDIO - Qualidade)
9. ✅ Adicionar GitHub Actions CI
10. ✅ Adicionar type hints
11. ✅ Melhorar logging estruturado
12. ✅ Documentar README

---

## ESTRATÉGIAS A IMPLEMENTAR

### 1. FallbackStrategy (Rule-Based)
```python
class FallbackStrategy:
    """Estratégia conservadora quando AI falha"""
    
    def analyze(self, symbol, data):
        # EMA 20/50 crossover
        ema_signal = self._ema_crossover(data)
        
        # RSI oversold/overbought
        rsi_signal = self._rsi_extreme(data)
        
        # Bollinger Bands squeeze
        bb_signal = self._bollinger_squeeze(data)
        
        # Combine signals
        if all([ema_signal == 'BUY', rsi_signal != 'SELL', bb_signal != 'SELL']):
            return {'decision': 'BUY', 'confidence': 0.65}
        elif all([ema_signal == 'SELL', rsi_signal != 'BUY', bb_signal != 'BUY']):
            return {'decision': 'SELL', 'confidence': 0.65}
        else:
            return {'decision': 'HOLD', 'confidence': 0.5}
```

### 2. HybridStrategy (Votação)
```python
class HybridStrategy:
    """Combina múltiplas estratégias com votação ponderada"""
    
    def __init__(self):
        self.strategies = {
            'supertrend': (SuperTrendStrategy(), 0.30),
            'ema': (EMACrossoverStrategy(), 0.20),
            'rsi': (RSIStrategy(), 0.20),
            'bollinger': (BollingerStrategy(), 0.15),
            'ict': (ICTStrategy(), 0.15)
        }
    
    def analyze(self, symbol, data):
        votes = []
        for name, (strategy, weight) in self.strategies.items():
            result = strategy.analyze(symbol, data)
            votes.append({
                'strategy': name,
                'decision': result['decision'],
                'confidence': result['confidence'],
                'weight': weight
            })
        
        # Weighted voting
        buy_score = sum(v['confidence'] * v['weight'] for v in votes if v['decision'] == 'BUY')
        sell_score = sum(v['confidence'] * v['weight'] for v in votes if v['decision'] == 'SELL')
        
        if buy_score > sell_score and buy_score > 0.40:
            return {'decision': 'BUY', 'confidence': buy_score}
        elif sell_score > buy_score and sell_score > 0.40:
            return {'decision': 'SELL', 'confidence': sell_score}
        else:
            return {'decision': 'HOLD', 'confidence': max(buy_score, sell_score)}
```

---

## MÉTRICAS ESPERADAS (APÓS CORREÇÃO)

| Métrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Taxa de HOLD | 100% | 10-20% | ⬇️ 80% |
| Trades/dia | 0 | 30-50 | 🚀 +∞ |
| WebSocket errors | 100/min | 0 | ⬇️ 100% |
| AI dependency | 100% | 0-30% | ⬇️ 70% |
| Estratégias ativas | 1 | 5+ | 🚀 +400% |
| Confidence médio | 0.0 | 0.50-0.70 | 🚀 +∞ |

---

**STATUS:** DIAGNÓSTICO COMPLETO - INICIANDO CORREÇÕES HARDCORE
