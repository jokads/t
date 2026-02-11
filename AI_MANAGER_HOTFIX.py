"""
HOTFIX para ai_manager.py - Corrige problema de HOLD com confidence 0.0

PROBLEMA IDENTIFICADO:
- Todos os modelos GPT4All retornam HOLD com confidence 0.0
- Causa: Modelos não estão gerando respostas válidas
- Resultado: Bot nunca executa trades

CORREÇÃO:
1. Adicionar logging detalhado em _call_gpt_safe
2. Detectar quando modelo retorna vazio/inválido
3. Implementar fallback inteligente para external_signal
4. Reduzir threshold de confidence de 0.25 para 0.15
5. Adicionar flag ai_failed no retorno
"""

# Patch 1: Adicionar logging detalhado após linha 5050
PATCH_1_INSERT_AFTER_LINE_5050 = """
            # 🔍 HOTFIX: Log detalhado do que o modelo retornou
            try:
                logger.debug(f"[HOTFIX] Model {model_label_local} raw output type: {type(raw_out)}")
                logger.debug(f"[HOTFIX] Model {model_label_local} raw output (first 200 chars): {str(raw_out)[:200]}")
            except Exception:
                pass
"""

# Patch 2: Modificar linha 3577-3584 para detectar falha de modelo
PATCH_2_REPLACE_LINES_3577_3584 = """
                    if isinstance(result, Exception):
                        # 🔍 HOTFIX: Log detalhado da exceção
                        log.warning(f"[HOTFIX] Model {mid} failed with exception: {type(result).__name__}: {str(result)[:100]}")
                        votes.append({
                            "decision": "HOLD",
                            "confidence": 0.0,  # ✅ Mudado de 0.4 para 0.0 para indicar falha
                            "tp_pips": 1.0,
                            "sl_pips": 1.0,
                            "model": mid,
                            "raw": str(result),
                            "ai_failed": True  # ✅ Flag de falha
                        })
                        continue
"""

# Patch 3: Modificar linha 3443-3444 para reduzir threshold
PATCH_3_REPLACE_LINE_3443 = """
            # ✅ HOTFIX: Threshold reduzido: 0.15 (ao invés de 0.25)
            if ext_action != "HOLD" and ext_conf >= 0.15:
"""

# Patch 4: Adicionar detecção de AI falhou após linha 3636
PATCH_4_INSERT_AFTER_LINE_3636 = """
            # 🔍 HOTFIX: Detectar se TODOS os modelos falharam
            ai_failed_count = sum(1 for v in votes if v.get("ai_failed", False))
            ai_total_count = len(votes)
            ai_all_failed = (ai_failed_count == ai_total_count) and ai_total_count > 0
            
            if ai_all_failed:
                log.error(f"[HOTFIX] TODOS os {ai_total_count} modelos AI falharam!")
"""

# Patch 5: Modificar linha 3657 para usar AI failed
PATCH_5_REPLACE_LINE_3657 = """
            if (max(agg.values()) <= 0.3 or ai_all_failed) and external_signal and ext_action != "HOLD":
"""

# Patch 6: Adicionar flag ai_failed no retorno final (linha 3742)
PATCH_6_ADD_TO_RETURN = """
            return {
                "decision": decision,
                "confidence": float(confidence),
                "tp_pips": float(tp_agg),
                "sl_pips": float(sl_agg),
                "votes": votes,
                "elapsed": time.time() - start,
                "ai_failed": ai_all_failed if 'ai_all_failed' in locals() else False  # ✅ Flag
            }
"""

print("✅ Patches definidos. Aplicar manualmente ou via script.")
