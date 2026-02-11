# HOTFIX para trading_bot_core.py - Lógica de Decisão HOLD

## 🔴 PROBLEMA IDENTIFICADO

**Sintoma nos logs:**
```
EURUSD: decision is HOLD -> skipping
trade result = {'ok': False, 'result': 'hold'}
```

**Fluxo Atual (QUEBRADO):**
1. SuperTrend gera sinal BUY (confidence=0.514) ✅
2. AIManager retorna HOLD (confidence=0.0) ❌
3. Bot aceita HOLD da AI
4. Trade NÃO executado ❌

**Causa Raiz:**
- `ai_override_min_confidence = 0.65` (muito alto!)
- AI com confidence 0.0 não passa threshold
- Bot ignora sinal válido da estratégia
- Prioriza AI mesmo quando AI falha

## ✅ CORREÇÕES APLICADAS

### 1. **Reduzir ai_override_min_confidence**
- De: `0.65` (65%)
- Para: `0.30` (30%)
- Permite AI influenciar com confidence mais baixa

### 2. **Detectar quando AI falhou**
- Usar flag `ai_failed` do AIManager
- Se `ai_failed=True`, ignorar decisão da AI
- Usar decisão da estratégia

### 3. **Priorizar estratégia quando AI tem confidence muito baixa**
- Se `ai_conf < 0.20` (20%), considerar AI inválida
- Usar decisão da estratégia original

### 4. **Adicionar logging detalhado**
- Logar decisão da estratégia
- Logar decisão da AI
- Logar decisão final escolhida
- Logar motivo da escolha

## 📋 IMPLEMENTAÇÃO

### Patch 1: Reduzir threshold (linha 1674)
```python
# ✅ HOTFIX: Reduzir threshold de 0.65 para 0.30
ai_min_conf = float(getattr(self, "ai_override_min_confidence", 0.30))
```

### Patch 2: Detectar AI failed (linha 1676)
```python
# 🔍 HOTFIX: Detectar se AI falhou
ai_failed = ai_res.get("ai_failed", False)
ai_very_low_conf = ai_conf < 0.20

# Se AI falhou OU confidence muito baixa, usar estratégia
if ai_failed or ai_very_low_conf:
    self.logger.warning(
        f"{symbol}: AI falhou ou confidence muito baixa "
        f"(conf={ai_conf:.2f}, failed={ai_failed}). "
        f"Usando decisão da estratégia: {strategy_decision}"
    )
    decision = strategy_decision
elif ai_decision_str in ("BUY", "SELL") and ai_conf >= ai_min_conf:
    decision = ai_decision_str
    self.logger.info("%s: AI override ACTIVE -> %s (conf=%.2f)", symbol, decision, ai_conf)
elif decision == "HOLD" and dq_decision_str in ("BUY", "SELL"):
    decision = dq_decision_str
    self.logger.info("%s: Deep Q override -> %s", symbol, decision)
```

### Patch 3: Adicionar logging detalhado (linha 1630)
```python
# 🔍 HOTFIX: Log detalhado das decisões
self.logger.info(
    f"[HOTFIX] {symbol} decisions: "
    f"strategy={strategy_decision}, "
    f"ai={ai_decision_str}(conf={ai_conf:.2f}), "
    f"dq={dq_decision_str}"
)
```

### Patch 4: Modificar validação HOLD (linha 1691)
```python
# 🔍 HOTFIX: Só rejeitar HOLD se estratégia também for HOLD
if decision not in ("BUY", "SELL"):
    # Se estratégia tinha sinal válido mas AI forçou HOLD, logar WARNING
    if strategy_decision in ("BUY", "SELL"):
        self.logger.warning(
            f"{symbol}: Estratégia tinha {strategy_decision} mas decisão final é HOLD. "
            f"AI conf={ai_conf:.2f}, failed={ai_res.get('ai_failed', False)}"
        )
    self.logger.debug("%s: decision is HOLD -> skipping", symbol)
    return {"ok": False, "result": "hold"}
```

## 🎯 RESULTADO ESPERADO

### Fluxo Correto (APÓS HOTFIX)
```
1. SuperTrend gera BUY (conf=0.514) ✅
2. AIManager retorna HOLD (conf=0.0, ai_failed=True) ❌
3. Bot detecta ai_failed=True
4. Bot usa decisão da estratégia (BUY) ✅
5. Trade executado ✅
```

### Cenários de Decisão

| Estratégia | AI Decision | AI Conf | AI Failed | Decisão Final | Motivo |
|------------|-------------|---------|-----------|---------------|--------|
| BUY | HOLD | 0.0 | True | **BUY** | AI falhou, usa estratégia |
| BUY | SELL | 0.15 | False | **BUY** | AI conf < 0.20, usa estratégia |
| BUY | SELL | 0.35 | False | **SELL** | AI conf >= 0.30, usa AI |
| BUY | BUY | 0.50 | False | **BUY** | AI concorda |
| HOLD | BUY | 0.40 | False | **BUY** | Estratégia HOLD, usa AI |
| HOLD | HOLD | 0.0 | True | **HOLD** | Ambos HOLD |

## 📝 NOTAS

### Thresholds Configuráveis
```python
# Em __init__ ou config
self.ai_override_min_confidence = 0.30  # AI precisa >= 30% para override
self.ai_very_low_threshold = 0.20       # < 20% considera AI inválida
```

### Variáveis de Ambiente
```bash
# Opcional: configurar via env
export AI_OVERRIDE_MIN_CONFIDENCE=0.30
export AI_VERY_LOW_THRESHOLD=0.20
```

### Compatibilidade
- ✅ Funciona com AIManager antigo (sem flag ai_failed)
- ✅ Funciona com AIManager novo (com flag ai_failed)
- ✅ Backward compatible

## 🔍 DEBUG

Para debug, adicionar no início do método:
```python
self.logger.debug(
    f"[DEBUG] {symbol} ai_res keys: {list(ai_res.keys()) if isinstance(ai_res, dict) else type(ai_res)}"
)
```

Verificar se `ai_failed` está presente na resposta do AIManager.
