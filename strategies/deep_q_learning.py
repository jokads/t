#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JokaMazKiBu Trading Bot - Deep Q-Learning Strategy v4.0 (refactor)
Features:
- TensorFlow / PyTorch / NumPy fallback
- Double DQN target computation
- Soft target updates (tau)
- Prioritized-ish replay (sampling by abs(td)+eps)
- Online feature normalization (mean/std per feature)
- Adaptive epsilon and lr schedules
- Checkpoint save/load (weights + metadata)
- Robust logging and safe fallbacks
Author: Assistant -> JokaMazKiBu Team
Date: 2025-12-24
"""
from __future__ import annotations

import os
import json
import time
import socket
import math
from gymnasium import spaces
import random
import logging
import pickle
from collections import deque
from typing import Any, Dict, List, Tuple, Optional

import numpy as np
import tensorflow as tf  # ou torch, conforme seu backend
import pandas as pd

from strategies.models import TradeSignal, TradeDirection, OrderType
from strategies.technical_indicators import TechnicalIndicatorsHardcore
from datetime import datetime, timezone

from ai_manager import AIManager
from strategies.models import Signal, TradeDirection
import uuid
from datetime import datetime, timezone

# =========================================================
# OPTIONAL BACKENDS (DEVEM EXISTIR ANTES DE QUALQUER USO)
# =========================================================
_torch = None
_tf = None
_keras = None

try:
    import torch
    import torch.nn as nn  # noqa
    import torch.optim as optim  # noqa
    _torch = torch
except Exception:
    _torch = None

try:
    import tensorflow as tf  # noqa
    try:
        _keras = tf.keras
    except Exception:
        from tensorflow import keras as _keras  # type: ignore
    _tf = tf
except Exception:
    _tf = None
    _keras = None

# deep learning backends
try:
    import tensorflow as tf  # sempre disponível se tensorflow estiver instalado
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

observation_space = spaces.Box(
    low=np.array([0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32),
    high=np.array([np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf], dtype=np.float32),
    shape=(8,),
    dtype=np.float32
)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except Exception:
    PYTORCH_AVAILABLE = False

# logging
logger = logging.getLogger("deep_q_learning")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)


def _validate_positive_int(value, name: str) -> int:
    """
    Garante que value é um inteiro positivo.
    Se for float inteiro ex: 3.0 -> 3
    Lança ValueError caso inválido.
    """
    import numbers
    if isinstance(value, numbers.Integral):
        if value > 0:
            return int(value)
        else:
            raise ValueError(f"{name} deve ser > 0, recebeu {value}")
    elif isinstance(value, numbers.Real):
        if value > 0 and value.is_integer():
            return int(value)
        else:
            raise ValueError(f"{name} deve ser inteiro positivo, recebeu {value}")
    else:
        try:
            iv = int(value)
            if iv > 0:
                return iv
            else:
                raise ValueError(f"{name} deve ser > 0, recebeu {value}")
        except Exception:
            raise ValueError(f"{name} inválido: {value}")

class StrategyDataCollector:
    """
    Coleta sinais, estados e rewards de todas as strategies ativas.
    Mantém histórico para backtesting offline e aprendizado contínuo.
    """
    def __init__(self):
        self.data: Dict[str, List[Dict[str, Any]]] = {}

    def record(self, strategy_name: str, state: np.ndarray, action: int, reward: float, info: Dict[str, Any]):
        if strategy_name not in self.data:
            self.data[strategy_name] = []
        self.data[strategy_name].append({
            "state": state.copy(),
            "action": int(action),
            "reward": float(reward),
            "info": info.copy(),
            "timestamp": time.time()
        })

    def get_history(self, strategy_name: str) -> List[Dict[str, Any]]:
        return self.data.get(strategy_name, [])

    def clear_history(self, strategy_name: Optional[str] = None):
        if strategy_name:
            self.data[strategy_name] = []
        else:
            self.data.clear()

class _Box:
    def __init__(self, low, high, shape, dtype):
        self.low = low
        self.high = high
        self.shape = shape
        self.dtype = dtype

class _Discrete:
    def __init__(self, n):
        self.n = n


class BacktestEngine:
    """
    Executa backtest simultâneo de múltiplas strategies usando dados históricos.
    Atualiza ReplayBuffer do DQNAgent de cada strategy.
    """
    def __init__(self, strategy_wrappers: Dict[str, DeepQLearningStrategy]):
        self.strategies = strategy_wrappers
        self.collector = StrategyDataCollector()

    def run(self, df: pd.DataFrame, max_steps: int = 500):
        """
        Executa backtest para todas as estratégias registradas.

        Args:
            df (pd.DataFrame): histórico completo OHLC
            max_steps (int): número máximo de passos por episódio
        """
        for name, strategy in self.strategies.items():
            # Prepara a estratégia e seu ambiente
            strategy.prepare(df)
            env = strategy.env
            agent = strategy.agent

            # Reset do ambiente para iniciar o episódio
            state = env.reset()
            done = False
            steps = 0

            # Loop do episódio
            while not done and steps < max_steps:
                # Obter ação do agente a partir do estado atual
                action = agent.act(state)

                # Executar ação no ambiente
                next_state, reward, done, info = env.step(action)

                # Armazenar experiência para aprendizado
                agent.store(state, action, reward, next_state, done)

                # Registrar dados do episódio
                self.collector.record(name, state, action, reward, info)

                # Avançar para o próximo estado
                state = next_state
                steps += 1

            # Aprendizado pós-episódio
            agent.learn(n_steps=10)

class MultiIAAdaptiveTrainer:
    """
    Treina o DQNAgent de cada strategy com feedback das 7 IAs.
    Ajusta hiperparâmetros dinamicamente e fortalece sinais confiáveis.
    """
    def __init__(self, strategies: Dict[str, DeepQLearningStrategy]):
        self.strategies = strategies

    def reinforce_with_ai(self, df: pd.DataFrame, timeout: float = 2.0):
        """
        Para cada strategy, obtém sinais do DQN e valida/adapta pelo AIManager.
        Atualiza replay buffer com rewards ajustados pelo consenso das 7 IAs.
        """
        for name, strategy in self.strategies.items():
            env = strategy.env
            agent = strategy.agent
            state = env.reset()
            done = False

            while not done:
                action = agent.act(state)
                next_state, reward, done, info = env.step(action)

                # build signal
                last_price = float(df["close"].iloc[env.current_step-1])
                pred = {"action": ["HOLD","BUY","SELL"][action], "confidence": 0.5}
                signal = strategy._build_signal_from_dqn(pred, last_price, df)

                # validar com AIManager
                ai_resp = strategy.ai_manager.validate_and_adjust_signal(signal.to_dict(), timeout=timeout)
                # reforço adaptativo: ajusta reward baseado no consenso
                adj_reward = reward * (ai_resp.get("approved", 0) + 0.5)
                agent.store(state, action, adj_reward, next_state, done)

                state = next_state
            agent.learn(n_steps=20)

import threading

class OnlineLearningScheduler:
    """
    Executa treino e backtest contínuo em paralelo ao trading real.
    """
    def __init__(self, trainer: MultiIAAdaptiveTrainer, interval: float = 60.0):
        self.trainer = trainer
        self.interval = interval
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.running = False

    def start(self):
        self.running = True
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join(timeout=2.0)

    def _run_loop(self):
        """
        Loop contínuo e robusto que aplica reforço de IA para cada estratégia registrada.
        Cuida de:
        - validações de presença de trainer/strategies/env/agent
        - compatibilidade Gym vs Gymnasium (reset/step signatures)
        - preprocess seguro (usa normalizer do agent se disponível)
        - uso seguro de act_inference / act
        - tratamento de exceções por estratégia sem quebrar o loop geral
        - limitador de passos por episódio para evitar loops infinitos
        - chamada incremental de learn e atualização de soft target

        Requisitos esperados no objeto `self`:
        - self.running: flag booleana
        - self.interval: segundos entre ciclos do loop externo
        - self.trainer: objeto com .strategies (dict-like)
        """
        logger = getattr(self, "logger", logging.getLogger("DeepQLoop"))

        # utilitário local para preprocess seguro
        def _safe_preprocess(raw_state, strategy):
            """
            Tenta normalizar/extrair features do estado usando o agent.normalizer se disponível.
            Se nada disponível, transforma para numpy float32 1-D.
            """
            try:
                agent = getattr(strategy, "agent", None)
                if agent is not None and hasattr(agent, "normalizer"):
                    arr = np.asarray(raw_state, dtype=np.float32)
                    # garante forma 1-D
                    if arr.ndim > 1 and arr.shape[0] == 1:
                        arr = arr.reshape(-1)
                    try:
                        # normalizer pode aceitar (n, dim)
                        agent.normalizer.update(arr.reshape(1, -1))
                        return agent.normalizer.normalize(arr.reshape(-1,))
                    except Exception:
                        # fallback simples
                        return arr.reshape(-1,)
                # fallback geral
                return np.asarray(raw_state, dtype=np.float32).reshape(-1,)
            except Exception as e:
                logger.debug("Preprocess fallback failed: %s", e, exc_info=True)
                try:
                    return np.asarray(raw_state, dtype=np.float32).reshape(-1,)
                except Exception:
                    return raw_state

        # utilitário para extrair (next_state, reward, done, info) compatível com gym/gymnasium/custom
        def _unpack_step_result(res):
            """
            Accepts:
            - (obs, reward, done, info)
            - (obs, reward, terminated, truncated, info)  -> gymnasium
            - any custom tuple where reward numeric and last element is info dict
            Returns (next_state, reward, done, info_dict)
            """
            try:
                if res is None:
                    return None, 0.0, True, {}
                if isinstance(res, tuple) or isinstance(res, list):
                    if len(res) == 4:
                        obs, reward, done, info = res
                        return obs, float(reward), bool(done), info or {}
                    if len(res) == 5:
                        obs, reward, terminated, truncated, info = res
                        done = bool(terminated) or bool(truncated)
                        return obs, float(reward), done, info or {}
                    # fallback: try to heuristically pick
                    obs = res[0]
                    # find first numeric element as reward
                    reward = 0.0
                    done = False
                    info = {}
                    for v in res[1:]:
                        if isinstance(v, (int, float)):
                            reward = float(v)
                            continue
                        if isinstance(v, dict):
                            info = v
                            continue
                        if isinstance(v, (bool,)):
                            done = bool(v)
                    return obs, reward, done, info
                # if single object returned, assume terminal
                return res, 0.0, True, {}
            except Exception as e:
                logger.debug("_unpack_step_result failed: %s", e, exc_info=True)
                return res, 0.0, True, {}

        # segurança: se trainer inválido, dorme e volta (não crasha)
        if not hasattr(self, "trainer") or self.trainer is None:
            logger.warning("_run_loop: self.trainer não encontrado — entrando em sleep")
            while getattr(self, "running", False):
                time.sleep(getattr(self, "interval", 1.0))
            return

        # loop principal
        while getattr(self, "running", False):
            loop_start = time.time()
            try:
                strategies = getattr(self.trainer, "strategies", {}) or {}
                # iterar sobre cópia da lista para evitar problemas de mutação durante iteração
                for name, strategy in list(strategies.items()):
                    try:
                        # validações básicas
                        if strategy is None:
                            continue
                        env = getattr(strategy, "env", None)
                        agent = getattr(strategy, "agent", None)
                        if env is None or agent is None:
                            logger.debug("Strategy '%s' sem env/agent — pulando", name)
                            continue

                        # Preparar episódio (reset). gym/gymnasium podem devolver (obs, info)
                        try:
                            reset_res = env.reset()
                        except TypeError:
                            # algumas implementações esperam kwargs
                            reset_res = env.reset()
                        # desempacotar reset (gym returns obs OR (obs, info))
                        if isinstance(reset_res, tuple) and len(reset_res) >= 1:
                            state = reset_res[0]
                        else:
                            state = reset_res

                        # determinar máximo de steps por episódio (defensivo)
                        max_steps = getattr(env, "spec", None) and getattr(env.spec, "max_episode_steps", None)
                        if max_steps is None:
                            max_steps = getattr(env, "max_steps", None)
                        max_steps = int(max_steps) if max_steps is not None else 1000

                        step_count = 0
                        done = False

                        # loop do episódio
                        while (not done) and step_count < max_steps and getattr(self, "running", False):
                            # preprocess seguro
                            state_proc = _safe_preprocess(state, strategy)

                            # escolher ação via interface segura (preferir act_inference)
                            action = None
                            try:
                                if hasattr(agent, "act_inference"):
                                    action = agent.act_inference(state_proc)
                                elif hasattr(agent, "act"):
                                    # act geralmente espera np array 1D
                                    action = agent.act(state_proc)
                                elif hasattr(agent, "predict"):
                                    action = agent.predict(state_proc)
                                else:
                                    # fallback random if action_size known
                                    a_size = getattr(agent, "action_size", None) or getattr(agent, "n_actions", None)
                                    if a_size:
                                        action = int(np.random.randint(0, int(a_size)))
                                    else:
                                        action = 0
                            except Exception as e:
                                logger.debug("agent action error (%s): %s", name, e, exc_info=True)
                                # fallback seguro
                                try:
                                    a_size = getattr(agent, "action_size", None) or getattr(agent, "n_actions", None)
                                    action = int(np.random.randint(0, int(a_size))) if a_size else 0
                                except Exception:
                                    action = 0

                            # executar ação, compatível com gym/gymnasium/custom
                            try:
                                step_res = env.step(action)
                            except TypeError:
                                step_res = env.step(action)
                            next_state, reward, done, info = _unpack_step_result(step_res)

                            # armazena a experiência; garantimos que os arrays tenham shape coerente
                            try:
                                # se agent espera np arrays, convert
                                s_store = state_proc
                                ns_store = _safe_preprocess(next_state, strategy)
                            except Exception:
                                s_store = state
                                ns_store = next_state

                            try:
                                # agent.store(signature: state, action, reward, next_state, done)
                                if hasattr(agent, "store"):
                                    agent.store(s_store, action, float(reward), ns_store, bool(done))
                            except Exception as e:
                                logger.debug("store() falhou para '%s': %s", name, e, exc_info=True)

                            # aprendizado incremental: chamamos learn periodicamente dentro do episódio
                            try:
                                # muitas implementações aceitam n_steps; usamos valor pequeno
                                if hasattr(agent, "learn"):
                                    agent.learn(n_steps=1)
                            except Exception as e:
                                logger.debug("learn() falhou para '%s': %s", name, e, exc_info=True)

                            # pequenas tarefas pós-step: logging/collector
                            try:
                                if hasattr(self, "collector") and hasattr(self.collector, "record"):
                                    # grava o estado bruto para análise
                                    self.collector.record(name, s_store, action, float(reward), info or {})
                            except Exception:
                                pass

                            # avançar estado
                            state = next_state
                            step_count += 1

                        # fim episódio: aprendizado extra e soft update
                        try:
                            if hasattr(agent, "learn"):
                                agent.learn(n_steps=5)
                            if hasattr(agent, "soft_update"):
                                agent.soft_update()
                        except Exception as e:
                            logger.debug("learn/soft_update pós-episódio falhou para '%s': %s", name, e, exc_info=True)

                    except Exception as strat_e:
                        logger.exception("Erro dentro da estratégia '%s' no loop de reforço: %s", name, strat_e)

            except Exception as e:
                logger.exception("_run_loop erro inesperado: %s", e)

            # pausa entre iterações externas — ajusta o tempo para manter intervalo estável
            try:
                elapsed = time.time() - loop_start
                sleep_for = max(0.0, float(getattr(self, "interval", 1.0)) - elapsed)
                if sleep_for > 0:
                    time.sleep(sleep_for)
            except Exception:
                time.sleep(getattr(self, "interval", 1.0))




        # -------------------------
        # Replay Buffer (prioritized-ish)
        # -------------------------
class ReplayBuffer:
    """
    ReplayBuffer robusto e thread-safe com suporte a prioridades (PER-like).
    API:
      - store(state, action, reward, next_state, done, priority=None)
      - push(...) alias para store
      - sample(batch_size, beta=0.4) ->
          (states, actions, rewards, next_states, dones, indices, weights)
      - update_priorities(indices, priorities)
      - clear(), is_empty(), __len__()
    Observações:
      - Se nenhuma prioridade foi fornecida, faz amostragem uniforme.
      - Quando batch_size > n, devolve até n amostras sem repetição.
    """
    def __init__(self, capacity: int = 20000, alpha: float = 0.6, eps: float = 1e-6, seed: Optional[int] = None):
        from collections import deque
        import threading

        self.capacity = max(1, int(capacity))
        self.alpha = float(alpha)
        self.eps = float(eps)

        self.buffer = deque(maxlen=self.capacity)       # armazenará tuplas (s,a,r,ns,done)
        self.priorities = deque(maxlen=self.capacity)   # prioridade por posição (float)
        self._lock = threading.Lock()

        # RNG reproducível opcional
        self._rng = np.random.default_rng(seed)

    # alias compat
    push = lambda self, *args, **kwargs: self.store(*args, **kwargs)

    def store(self, state: Any, action: Any, reward: float, next_state: Any, done: bool, priority: Optional[float] = None):
        """
        Adiciona experiência. Se priority for None, usa reward absoluto (ou eps).
        Mantém prioridade com exponent alpha.
        """
        with self._lock:
            self.buffer.append((state, action, float(reward), next_state, bool(done)))
            if priority is None:
                pr = (abs(float(reward)) + self.eps) ** self.alpha
            else:
                pr = (abs(float(priority)) + self.eps) ** self.alpha
            self.priorities.append(float(pr))

    def __len__(self) -> int:
        with self._lock:
            return len(self.buffer)

    def is_empty(self) -> bool:
        return len(self) == 0

    def clear(self) -> None:
        with self._lock:
            self.buffer.clear()
            self.priorities.clear()

    def _get_probs(self) -> np.ndarray:
        """
        Retorna array de probabilidades normalizadas.
        Se não houver prioridades (vazias), devolve uniformes.
        """
        with self._lock:
            n = len(self.priorities)
            if n == 0:
                return np.array([], dtype=np.float64)
            probs = np.array(self.priorities, dtype=np.float64)
        total = probs.sum()
        if total <= 0 or not np.isfinite(total):
            # fallback para uniforme se prioridades inválidas
            probs = np.ones_like(probs, dtype=np.float64)
            total = probs.sum()
        probs = probs / (total + 1e-12)
        return probs

    def sample(self, batch_size: int, beta: float = 0.4) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[int], np.ndarray]:
        """
        Amostra uma minibatch.
        Retorna (states, actions, rewards, next_states, dones, indices, weights)
        - weights: importance-sampling weights normalizados (max=1).
        """
        batch_size = int(batch_size)
        beta = float(beta)

        with self._lock:
            n = len(self.buffer)
            if n == 0:
                # devolve arrays vazios compatíveis
                return (np.empty((0,)), np.empty((0,)), np.empty((0,)),
                        np.empty((0,)), np.empty((0,), dtype=bool),
                        [], np.empty((0,)))

            probs = self._get_probs()
            # se probs vazia (fallback), usa uniforme
            if probs.size == 0:
                probs = np.ones(n, dtype=np.float64) / float(n)

            k = min(batch_size, n)
            # escolha sem substituição
            try:
                idxs = self._rng.choice(n, size=k, replace=False, p=probs)
            except Exception:
                # em casos raros (p com NaNs) fallback para uniforme
                idxs = self._rng.choice(n, size=k, replace=False)

            samples = [self.buffer[int(i)] for i in idxs]

        # unzip batch
        states, actions, rewards, next_states, dones = zip(*samples)

        # converter para arrays onde possível (manter dtype float32 para numerics)
        try:
            states_arr = np.asarray(states, dtype=np.float32)
        except Exception:
            states_arr = np.array(states, dtype=object)

        actions_arr = np.asarray(actions)
        rewards_arr = np.asarray(rewards, dtype=np.float32)
        try:
            next_states_arr = np.asarray(next_states, dtype=np.float32)
        except Exception:
            next_states_arr = np.array(next_states, dtype=object)
        dones_arr = np.asarray(dones, dtype=bool)

        # importance-sampling weights
        # w_i = (N * p_i)^{-beta} normalized by max(w)
        probs_for_idxs = probs[idxs]
        weights = (len(probs) * probs_for_idxs) ** (-beta)
        # proteger contra zeros / inf
        weights = np.asarray(weights, dtype=np.float32)
        w_max = weights.max() if weights.size > 0 else 1.0
        if w_max <= 0 or not np.isfinite(w_max):
            w_max = 1.0
        weights = weights / (w_max + 1e-12)

        return states_arr, actions_arr, rewards_arr, next_states_arr, dones_arr, list(map(int, idxs)), weights

    def update_priorities(self, indices: List[int], priorities: List[float]) -> None:
        """
        Atualiza prioridades (uso pós-batch para TD errors).
        indices e priorities devem ter mesmo comprimento.
        """
        if not indices:
            return
        with self._lock:
            for i, p in zip(indices, priorities):
                if 0 <= int(i) < len(self.priorities):
                    self.priorities[int(i)] = (abs(float(p)) + self.eps) ** self.alpha


# -------------------------
# Normalizer: running mean/std (per feature)
# -------------------------
class RunningNormalizer:
    """
    Normalizador online por-feature baseado em Welford (estável).
    - Mantém mean e M2 (soma dos quadrados das diferenças) por feature.
    - update(x): x pode ser (size,) ou (batch, size)
    - normalize(x): normaliza e retorna float32. Mantém clipping para evitar outliers extremos.
    - Thread-safe.
    """

    def __init__(self, size: int, eps: float = 1e-8, clip: float = 5.0):
        self.size = int(size)
        self.eps = float(eps)
        self.clip = float(clip)

        # estatísticas em float64 para estabilidade numérica
        self.count = 0  # número total de observações
        self.mean = np.zeros(self.size, dtype=np.float64)
        self.M2 = np.zeros(self.size, dtype=np.float64)  # soma acumulada de squared diffs

        self._lock = threading.Lock()

    def reset(self) -> None:
        """Reinicia estatísticas."""
        with self._lock:
            self.count = 0
            self.mean.fill(0.0)
            self.M2.fill(0.0)

    def update(self, x: Any) -> None:
        """
        Atualiza mean/M2 com observações em x.
        x pode ser:
          - 1D array-like com tamanho == self.size
          - 2D array-like (batch, size)
        Qualquer forma extraível será reshaped para (batch, size).
        """
        arr = np.asarray(x, dtype=np.float64)
        if arr.size == 0:
            return

        # normalizar a forma para (batch, size)
        if arr.ndim == 1:
            batch = arr.reshape(1, -1)
        elif arr.ndim == 2:
            batch = arr
        else:
            # tenta flatten por observação
            batch = arr.reshape(arr.shape[0], -1)

        # se as features não coincidirem com size, tenta broadcast/trim/pad defensivo
        if batch.shape[1] != self.size:
            # se for maior, trunca; se menor, pad com zeros (fallback defensivo)
            if batch.shape[1] > self.size:
                batch = batch[:, : self.size]
            else:
                pad_width = self.size - batch.shape[1]
                batch = np.pad(batch, ((0, 0), (0, pad_width)), mode="constant", constant_values=0.0)

        with self._lock:
            for row in batch:
                self.count += 1
                delta = row - self.mean
                self.mean += delta / self.count
                delta2 = row - self.mean
                self.M2 += delta * delta2
            # nota: var = M2 / count  (população). Para amostral, usar count-1 quando count>1.

    def _variance(self) -> np.ndarray:
        """Retorna a variância populacional (M2 / count). Protege count==0."""
        with self._lock:
            if self.count <= 0:
                return np.ones(self.size, dtype=np.float64)
            return self.M2 / float(max(1, self.count))

    def normalize(self, x: Any) -> np.ndarray:
        """
        Normaliza x usando estatísticas correntes.
        - Retorna np.float32 com mesma forma que x (1D -> 1D; batch -> batch).
        - Se estatísticas ainda vazias (count==0), devolve x convertidos para float32.
        """
        arr = np.asarray(x, dtype=np.float64)
        if arr.size == 0:
            return arr.astype(np.float32)

        var = self._variance()
        std = np.sqrt(var + self.eps).astype(np.float64)

        # prepara mean/std para broadcast
        with self._lock:
            mean = self.mean.copy()

        # shape handling
        if arr.ndim == 1:
            if arr.shape[0] != self.size:
                # defensivo: trunca ou pad
                if arr.shape[0] > self.size:
                    arr_proc = arr[: self.size]
                else:
                    arr_proc = np.pad(arr, (0, self.size - arr.shape[0]), mode="constant", constant_values=0.0)
            else:
                arr_proc = arr
            normed = (arr_proc - mean) / std
            normed = np.clip(normed, -self.clip, self.clip)
            return normed.astype(np.float32)
        else:
            # arr é batch
            if arr.shape[1] != self.size:
                if arr.shape[1] > self.size:
                    arr_proc = arr[:, : self.size]
                else:
                    pad_w = self.size - arr.shape[1]
                    arr_proc = np.pad(arr, ((0, 0), (0, pad_w)), mode="constant", constant_values=0.0)
            else:
                arr_proc = arr
            normed = (arr_proc - mean) / std
            normed = np.clip(normed, -self.clip, self.clip)
            return normed.astype(np.float32)

    # utilitários para debug / checkpoint
    def as_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "size": self.size,
                "eps": self.eps,
                "clip": self.clip,
                "count": int(self.count),
                "mean": self.mean.tolist(),
                "M2": self.M2.tolist(),
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunningNormalizer":
        inst = cls(int(data["size"]), eps=float(data.get("eps", 1e-8)), clip=float(data.get("clip", 5.0)))
        with inst._lock:
            inst.count = int(data.get("count", 0))
            inst.mean = np.asarray(data.get("mean", np.zeros(inst.size)), dtype=np.float64)
            inst.M2 = np.asarray(data.get("M2", np.zeros(inst.size)), dtype=np.float64)
        return inst

class DQNAgent:
    __strategy_ignore__ = True
    """
    DQNAgent robusto — detecta backend (torch/keras/numpy), aceita fallbacks e
    integra com ReplayBuffer e RunningNormalizer do projeto.

    Parâmetros principais:
    - state_size (int): dimensão do estado (obrigatório)
    - action_size (int|None): dimensão do espaço de ações (se None, tenta inferir; fallback=2)
    - prioritized (bool): se usar buffer priorizado (depende do ReplayBuffer)
    """

    def __init__(
        self,
        state_size: Optional[Any] = None,
        action_size: Optional[int] = None,
        lr: float = 1e-3,
        gamma: float = 0.99,
        batch_size: int = 64,
        buffer_size: int = 20_000,
        tau: float = 0.005,
        prioritized: bool = True,
        symbol: Optional[str] = None,
        timeframe: Optional[int] = None,
        seed: Optional[int] = None,
        **kwargs,
    ):
        self.logger = logging.getLogger(f"{__name__}.DQNAgent")

        # seed
        if seed is None:
            seed = int(os.environ.get("DQN_SEED", "0"))
        self.seed = int(seed)
        np.random.seed(self.seed)
        if _torch:
            try:
                _torch.manual_seed(self.seed)
                if _torch.cuda.is_available():
                    _torch.cuda.manual_seed_all(self.seed)
            except Exception:
                pass

        # -------------------------
        # RESOLVE STATE_SIZE (sempre; não depende de _torch)
        # -------------------------
        state_shape = None
        resolved_state = None
        try:
            # int simples
            if isinstance(state_size, int):
                resolved_state = int(state_size)
                state_shape = (resolved_state,)

            elif isinstance(state_size, (list, tuple)):
                shape = tuple(int(x) for x in state_size)
                state_shape = shape
                prod = 1
                for d in shape:
                    prod *= max(1, int(d))
                resolved_state = prod

            elif isinstance(state_size, np.ndarray):
                resolved_state = int(state_size.size)
                state_shape = tuple(int(x) for x in state_size.shape)

            elif "pd" in globals() and isinstance(state_size, pd.DataFrame):
                resolved_state = int(state_size.shape[1])
                state_shape = (resolved_state,)

            else:
                # tenta inferir do env passado em kwargs
                env = kwargs.get("env") or kwargs.get("environment")
                if env is not None:
                    try:
                        if hasattr(env, "observation_space"):
                            sp = getattr(env, "observation_space")
                            if hasattr(sp, "shape") and sp.shape is not None:
                                shp = tuple(int(x) for x in sp.shape)
                                state_shape = shp
                                prod = 1
                                for d in shp:
                                    prod *= max(1, int(d))
                                resolved_state = prod
                            elif hasattr(sp, "n"):
                                resolved_state = int(sp.n)
                                state_shape = (resolved_state,)
                        elif hasattr(env, "state_size"):
                            resolved_state = int(getattr(env, "state_size"))
                            state_shape = (resolved_state,)
                        elif hasattr(env, "df") and isinstance(getattr(env, "df"), pd.DataFrame):
                            resolved_state = int(env.df.shape[1])
                            state_shape = (resolved_state,)
                    except Exception:
                        resolved_state = None
        except Exception:
            resolved_state = None

        if resolved_state is None:
            self.logger.warning(
                "state_size inválido/indeterminado. Usando fallback state_size=1. "
                "Recomendo passar state_size explícito (int) ou env/action_space."
            )
            resolved_state = 1
            state_shape = (1,)

        try:
            self.state_size = self._validate_positive_int(resolved_state, "state_size")
        except Exception:
            self.state_size = max(1, int(resolved_state))

        self.state_shape = tuple(state_shape) if state_shape is not None else (self.state_size,)
        self.state_ndim = len(self.state_shape)
        self.input_dim = int(np.prod(self.state_shape))

        self.logger.debug(
            "DQNAgent state_size normalized: state_size=%s state_shape=%s input_dim=%d",
            self.state_size, self.state_shape, self.input_dim
        )

        # -------------------------
        # action_size (tal como tinhas)
        # -------------------------
        resolved_action = None
        try:
            if action_size is not None:
                resolved_action = int(action_size)
        except Exception:
            resolved_action = None

        if resolved_action is None:
            env = kwargs.get("env") or kwargs.get("environment")
            if env is not None:
                try:
                    if hasattr(env, "action_space"):
                        sp = getattr(env, "action_space")
                        if hasattr(sp, "n"):
                            resolved_action = int(sp.n)
                except Exception:
                    resolved_action = None

        if resolved_action is None:
            resolved_action = 2
            self.logger.warning("action_size não fornecido — fallback para 2 (ex: buy/sell).")

        self.action_size = int(resolved_action)

        # hiperparams
        self.lr = float(lr)
        self.gamma = float(gamma)
        self.batch_size = int(batch_size)
        self.tau = float(tau)
        self.prioritized = bool(prioritized)

        self.epsilon = 0.15
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995

        self.trade_log = []
        self.steps = 0
        self.symbol = symbol
        self.timeframe = timeframe

        # replay
        try:
            if self.prioritized:
                self.replay = ReplayBuffer(capacity=buffer_size)
            else:
                try:
                    self.replay = ReplayBuffer(capacity=buffer_size, alpha=0.0)
                except TypeError:
                    self.replay = ReplayBuffer(capacity=buffer_size)
        except Exception as e:
            self.logger.exception("ReplayBuffer falhou — usando stub: %s", e)
            class _ReplayStub:
                def __init__(self):
                    self._buf = []
                def store(self, *args):
                    self._buf.append(args)
                def sample(self, batch_size):
                    return [], [], [], [], []
                def __len__(self):
                    return len(self._buf)
            self.replay = _ReplayStub()

        # normalizer
        try:
            self.normalizer = RunningNormalizer(self.input_dim)
        except Exception as e:
            self.logger.warning("RunningNormalizer indisponível (%s) — usando passthrough.", e)
            class _NormStub:
                def __init__(self, *_): pass
                def normalize(self, x): return x
                def update(self, x): return x
            self.normalizer = _NormStub()


        # ===============================
        # Hiperparâmetros
        # ===============================
        self.lr = float(lr)
        self.gamma = float(gamma)
        self.batch_size = int(batch_size)
        self.tau = float(tau)
        self.prioritized = bool(prioritized)

        # exploração
        self.epsilon = 0.15
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995

        # bookkeeping
        self.trade_log = []
        self.steps = 0
        self.symbol = symbol
        self.timeframe = timeframe

        # ===============================
        # Replay Buffer (robusto)
        # ===============================
        try:
            if self.prioritized:
                self.replay = ReplayBuffer(capacity=buffer_size)
            else:
                try:
                    self.replay = ReplayBuffer(capacity=buffer_size, alpha=0.0)
                except TypeError:
                    self.replay = ReplayBuffer(capacity=buffer_size)
        except Exception as e:
            self.logger.exception("ReplayBuffer falhou — usando stub: %s", e)

            class _ReplayStub:
                def __init__(self):
                    self._buf = []

                def store(self, *args):
                    self._buf.append(args)

                def sample(self, batch_size):
                    return [], [], [], [], []

                def __len__(self):
                    return len(self._buf)

            self.replay = _ReplayStub()

        # ===============================
        # Normalizador (seguro)
        # ===============================
        try:
            self.normalizer = RunningNormalizer(self.input_dim)
        except Exception as e:
            self.logger.warning(
                "RunningNormalizer indisponível (%s) — usando passthrough.", e
            )

            class _NormStub:
                def __init__(self, *_): pass
                def normalize(self, x): return x
                def update(self, x): return x

            self.normalizer = _NormStub()

        # ===============================
        # Backend selection
        # ===============================
        self.framework = None
        self.device = "cpu"
        self._q_network = None
        self._target_network = None

        # ---- Torch (prioritário)
        if _torch is not None:
            try:
                self.framework = "torch"
                self.device = (
                    _torch.device("cuda")
                    if _torch.cuda.is_available()
                    else _torch.device("cpu")
                )
                self._build_torch()
                self.logger.info("DQNAgent usando backend PyTorch (%s)", self.device)
            except Exception as e:
                self.logger.exception("Falha no backend Torch: %s", e)
                self.framework = None

        # ---- Keras
        if self.framework is None and _keras is not None:
            try:
                self.framework = "keras"
                self.device = "cpu"
                self._build_keras()
                self.logger.info("DQNAgent usando backend Keras")
            except Exception as e:
                self.logger.exception("Falha no backend Keras: %s", e)
                self.framework = None

        # ---- NumPy (fallback final)
        if self.framework is None:
            self.framework = "numpy"
            self.device = "cpu"
            self._build_numpy()
            self.logger.warning("DQNAgent usando backend NumPy (fallback)")

        # ===============================
        # Log final
        # ===============================
        self.logger.info(
            "DQNAgent inicializado | state=%d action=%d framework=%s device=%s",
            self.state_size,
            self.action_size,
            self.framework,
            self.device,
        )
    
    def act(self, state):
        raw_out = self.model.predict(state)
        action = self._sanitize_dqn_output(raw_out)
        return action
    
    # -------------------------
    # Validation / helpers
    # -------------------------
    def prepare(self, state_size: int, action_size: int):
        """
        Inicializa o agente quando o environment já conhece o state/action space.
        """
        if self._q_network is not None:
            return  # já inicializado

        self.state_size = int(state_size)
        self.action_size = int(action_size)

        self.normalizer = RunningNormalizer(self.state_size)

        self.logger.info(
            "Inicializando DQNAgent | state_size=%d action_size=%d",
            self.state_size, self.action_size
        )

        self._build_model()

        if self._q_network is None:
            raise RuntimeError("DQNAgent inicializado sem Q-network")

    def _validate_positive_int(self, v: Any, name: str, optional: bool = False) -> Optional[int]:
        """Valida que v é um inteiro positivo. Se optional=True, retorna None em vez de raise."""
        # tenta usar função global se existir (compat com teu projeto)
        try:
            global _validate_positive_int  # type: ignore
            if callable(_validate_positive_int):
                return _validate_positive_int(v, name)
        except Exception:
            pass
        if v is None:
            if optional:
                return None
            raise ValueError(f"{name} obrigatório")
        try:
            iv = int(v)
            if iv <= 0:
                raise ValueError()
            return iv
        except Exception:
            if optional:
                return None
            raise ValueError(f"{name} inválido: {v}")

    def _infer_action_size_from_env(self, env) -> Optional[int]:
        try:
            if hasattr(env, "action_space"):
                return self._infer_action_size_from_space(env.action_space)
        except Exception:
            pass
        try:
            # se env tiver df com colunas que definem ações
            if hasattr(env, "df"):
                # heurística: 3 ações (buy/sell/hold) se não for claro
                return 3
        except Exception:
            pass
        return None

    def _infer_action_size_from_space(self, action_space) -> Optional[int]:
        try:
            if hasattr(action_space, "n"):
                return int(action_space.n)
            if hasattr(action_space, "shape") and action_space.shape is not None:
                prod = 1
                for s in action_space.shape:
                    prod *= int(s)
                return prod if prod > 0 else None
        except Exception:
            pass
        return None

    # -------------------------
    # Model builders
    # -------------------------
    def _build_torch(self):
        """
        Constrói um modelo PyTorch MLP + optimizer de forma robusta.
        Garante:
        - imports explícitos
        - device consistente
        - _q_network nunca None
        - framework definido corretamente
        """
        if _torch is None:
            raise RuntimeError("PyTorch não disponível (_torch is None)")

        import torch
        import torch.nn as nn
        import torch.optim as optim
        import torch.nn.functional as F

        # -----------------------------
        # Device seguro
        # -----------------------------
        if not hasattr(self, "device") or self.device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        in_dim = int(self.state_size)
        out_dim = int(self.action_size)

        if in_dim <= 0 or out_dim <= 0:
            raise ValueError(f"Dimensões inválidas: state_size={in_dim}, action_size={out_dim}")

        # -----------------------------
        # Modelo MLP
        # -----------------------------
        class MLP(nn.Module):
            def __init__(self, in_dim: int, out_dim: int):
                super().__init__()
                h1 = max(64, in_dim * 2)
                h2 = max(64, in_dim)

                self.fc1 = nn.Linear(in_dim, h1)
                self.fc2 = nn.Linear(h1, h2)
                self.fc3 = nn.Linear(h2, out_dim)

                # inicialização estável
                nn.init.kaiming_uniform_(self.fc1.weight, nonlinearity="relu")
                nn.init.kaiming_uniform_(self.fc2.weight, nonlinearity="relu")
                nn.init.xavier_uniform_(self.fc3.weight)

            def forward(self, x):
                x = F.relu(self.fc1(x))
                x = F.relu(self.fc2(x))
                return self.fc3(x)

        # -----------------------------
        # Criar rede e optimizer
        # -----------------------------
        self._q_network = MLP(in_dim, out_dim).to(self.device)

        self._optimizer = optim.Adam(
            self._q_network.parameters(),
            lr=float(getattr(self, "lr", 1e-3))
        )

        # flags internas
        self.framework = "torch"
        self._use_torch = True

        # sanity-check (evita NoneType object is not callable)
        self._q_network.eval()
        with torch.no_grad():
            dummy = torch.zeros((1, in_dim), device=self.device)
            _ = self._q_network(dummy)

        self.logger.info(
            "Torch Q-network criado | state_size=%s action_size=%s device=%s",
            in_dim, out_dim, self.device
        )


    def _clone_torch(self, model):
        """Retorna uma cópia de um modelo Torch com parâmetros iguais."""
        import copy
        m = copy.deepcopy(model)
        m.to(self.device)
        return m

    def _build_keras(self):
        """
        Constrói modelo DQN com Keras de forma 100% segura.

        - Não usa imports diretos de tensorflow.keras (evita erro do Pylance)
        - Funciona apenas se _tf e _keras estiverem disponíveis
        - Cria Q-network e Target-network
        - Loss robusta (Huber se existir)
        """

        if _tf is None or _keras is None:
            raise RuntimeError("TensorFlow/Keras não disponível neste ambiente")

        keras_mod = _keras
        layers = keras_mod.layers
        models = keras_mod.models
        optimizers = keras_mod.optimizers

        # ---- input shape seguro ----
        if isinstance(self.state_size, int):
            input_shape = (self.state_size,)
        else:
            input_shape = tuple(int(x) for x in self.state_size)

        # ---- heurística robusta para hidden layers ----
        hidden1 = max(64, int(input_shape[0] * 2))
        hidden2 = max(64, int(input_shape[0]))

        # ---- Q-Network ----
        inp = layers.Input(shape=input_shape, name="state")
        x = layers.Dense(hidden1, activation="relu", kernel_initializer="he_normal")(inp)
        x = layers.Dense(hidden2, activation="relu", kernel_initializer="he_normal")(x)
        out = layers.Dense(int(self.action_size), activation="linear", name="q_values")(x)

        q_model = models.Model(inputs=inp, outputs=out, name="dqn_q_network")

        # ---- Loss (Huber > MSE para RL) ----
        try:
            loss = keras_mod.losses.Huber()
        except Exception:
            loss = "mse"

        # ---- Compile ----
        try:
            optimizer = optimizers.Adam(learning_rate=float(self.lr))
            q_model.compile(optimizer=optimizer, loss=loss)
        except Exception as e:
            self.logger.exception("Erro ao compilar modelo Keras: %s", e)
            raise RuntimeError("Falha ao compilar Q-network Keras") from e

        self._q_network = q_model
        self.framework = "keras"

        # ---- Target Network ----
        try:
            target = models.clone_model(q_model)
            try:
                target.compile(
                    optimizer=optimizers.Adam(learning_rate=float(self.lr)),
                    loss=loss
                )
            except Exception:
                pass  # compile não é obrigatório para target

            target.set_weights(q_model.get_weights())
            self._target_network = target
        except Exception:
            self.logger.warning("Target network não pôde ser criada (continuando sem).")
            self._target_network = None


        # função wrapper de predict que normaliza entradas e trata 1D -> batch
        def _keras_predict(state_batch):
            import numpy as _np
            # garante array float32 com shape (batch, features)
            arr = _np.asarray(state_batch, dtype=_np.float32)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)

            # obtém a instância do modelo (segura: usa self._q_network)
            model = getattr(self, "_q_network", None)
            if model is None:
                raise RuntimeError("Keras model não inicializado em self._q_network")

            # tenta predict -> fallback para call(...).numpy()
            try:
                preds = model.predict(arr, verbose=0)
            except Exception:
                try:
                    preds = model(arr, training=False).numpy()
                except Exception as e:
                    # log detalhado para debugging (não interrompe stack sem contexto)
                    self.logger.exception("Erro ao executar forward Keras: %s", e)
                    raise RuntimeError("Falha na inferência Keras") from e

            # normaliza formato de saída para numpy float32 (batch, action_size)
            preds = _np.asarray(preds, dtype=_np.float32)
            if preds.ndim == 1:
                preds = preds.reshape(1, -1)
            return preds

        self._keras_predict = _keras_predict

        # informação de debug
        self.logger.info(
            "Keras model criado: state_size=%s action_size=%s hidden=[%s,%s]",
            input_shape, self.action_size, hidden1, hidden2
        )


    def _build_numpy(self):
        """
        Fallback: aproximação linear simples para Q-values.
        Inicializa pesos e bias de forma estável usando Xavier/Glorot.
        """
        self.framework = "numpy"

        # Inicialização Xavier/Glorot para camada linear
        limit = np.sqrt(6.0 / (self.state_size + self.action_size))
        self._W = np.random.uniform(-limit, limit, (self.state_size, self.action_size)).astype(np.float32)
        
        # Bias inicializado como zeros
        self._b = np.zeros((self.action_size,), dtype=np.float32)


    # -------------------------
    # Act / store / learn
    # -------------------------
    def act(self, state: Any, greedy: bool = False) -> int:
        """
        Seleciona ação por epsilon-greedy.
        - state: array-like shape (state_size,)
        - greedy: força greedy (sem exploração)
        """
        s = np.asarray(state, dtype=np.float32)
        s = s.reshape(-1)  # flatten
        s = self.normalizer.normalize(s) if hasattr(self.normalizer, "normalize") else s

        # decai epsilon ao longo do tempo se não greedy
        if not greedy:
            eps = self.epsilon
        else:
            eps = 0.0

        # amostragem aleatória
        if np.random.rand() < eps:
            return int(np.random.randint(0, self.action_size))

        # predição do Q
        qvals = self._predict_q(s)
        # escolher argmax - se várias ações com mesmo q, escolhe aleatoriamente entre eles
        max_actions = np.flatnonzero(qvals == qvals.max())
        return int(np.random.choice(max_actions))

    def _predict_q(self, state_np: np.ndarray) -> np.ndarray:
        """
        Retorna um array (action_size,) com Q-values segundo o backend.
        Robustez:
        - aceita entradas 1D ou 2D (usa apenas a primeira linha / reshape(1,-1))
        - tenta PyTorch > Keras > NumPy
        - em caso de erro faz fallback e retorna zeros (não lança)
        - sempre retorna np.float32 e tamanho self.action_size
        """
        try:
            s = np.asarray(state_np, dtype=np.float32)
        except Exception:
            self.logger.exception("_predict_q: entrada inválida, retornando zeros")
            return np.zeros((int(getattr(self, "action_size", 1)),), dtype=np.float32)

        # garantir batch shape (1, features)
        if s.ndim == 1:
            s = s.reshape(1, -1)
        elif s.ndim > 2:
            s = s.reshape(1, -1)

        # resultado default (em caso de erro)
        action_size = int(getattr(self, "action_size", 1))
        try:
            # ------------------------
            # PyTorch backend
            # ------------------------
            if self.framework == "torch" and _torch is not None and getattr(self, "_q_network", None) is not None:
                try:
                    self._q_network.eval()
                    with _torch.no_grad():
                        x = _torch.from_numpy(s).float().to(self.device)
                        out_t = self._q_network(x)
                        # alguns modelos retornam (batch, out) ou tensor; garantir numpy
                        if isinstance(out_t, tuple) or isinstance(out_t, list):
                            out_t = out_t[0]
                        out = out_t.cpu().numpy().reshape(-1)
                    out = np.asarray(out, dtype=np.float32)
                    # garantir tamanho
                    if out.size != action_size:
                        out = np.resize(out, (action_size,))
                    return out
                except Exception as e:
                    self.logger.exception("_predict_q: erro PyTorch -> fallback: %s", e)

            # ------------------------
            # Keras / TensorFlow backend
            # ------------------------
            if self.framework == "keras" and _keras is not None and getattr(self, "_q_network", None) is not None:
                try:
                    # usa helper se disponível (definido em _build_keras)
                    predictor = getattr(self, "_keras_predict", None)
                    if callable(predictor):
                        preds = predictor(s)
                    else:
                        # tentativa direta (compatível com tf.keras.Model)
                        preds = self._q_network.predict(s, verbose=0)
                    preds = np.asarray(preds, dtype=np.float32).reshape(-1)
                    if preds.size != action_size:
                        preds = np.resize(preds, (action_size,))
                    return preds
                except Exception as e:
                    self.logger.exception("_predict_q: erro Keras -> fallback: %s", e)

            # ------------------------
            # NumPy fallback
            # ------------------------
            # espera-se _W: (state_size, action_size) e _b: (action_size,)
            if hasattr(self, "_W") and hasattr(self, "_b"):
                try:
                    out = (s.dot(self._W) + self._b).reshape(-1)
                    out = np.asarray(out, dtype=np.float32)
                    if out.size != action_size:
                        out = np.resize(out, (action_size,))
                    return out
                except Exception as e:
                    self.logger.exception("_predict_q: erro NumPy linear -> %s", e)

        except Exception as e:
            self.logger.exception("_predict_q erro inesperado: %s", e)

        # Se chegamos aqui: não foi possível calcular — devolve vetor neutro (zeros)
        self.logger.warning("_predict_q: retornando zeros como fallback (action_size=%s)", action_size)
        return np.zeros((action_size,), dtype=np.float32)

    def store(self, state, action, reward, next_state, done):
        """Armazena experiência no replay buffer; atualiza normalizer."""
        try:
            self.normalizer.update(state)
        except Exception:
            pass
        try:
            self.replay.store(state, action, reward, next_state, done)
        except Exception:
            # tenta assinatura alternativa (lista de tuplas)
            try:
                self.replay.store((state, action, reward, next_state, done))
            except Exception as e:
                self.logger.exception("Falha ao armazenar experiência: %s", e)

    def sample_batch(self, batch_size: int):
        """
        Uniformiza a amostragem: suporta duas assinaturas de ReplayBuffer:
        - (states, actions, rewards, next_states, dones)
        - (states, actions, rewards, next_states, dones, idxs, is_weights)
        Retorna dict com arrays e, opcionalmente, idxs/is_weights.
        """
        got = self.replay.sample(batch_size)
        # heurística para detectar estrutura
        if got is None:
            return None
        # Se retorna tuple de 5
        if isinstance(got, tuple) and (len(got) == 5 or len(got) == 7):
            if len(got) == 5:
                s, a, r, ns, d = got
                return dict(states=np.asarray(s), actions=np.asarray(a), rewards=np.asarray(r),
                            next_states=np.asarray(ns), dones=np.asarray(d))
            if len(got) == 7:
                s, a, r, ns, d, idxs, is_weights = got
                return dict(states=np.asarray(s), actions=np.asarray(a), rewards=np.asarray(r),
                            next_states=np.asarray(ns), dones=np.asarray(d),
                            idxs=np.asarray(idxs), is_weights=np.asarray(is_weights))
        # else tenta interpretar arrays
        try:
            arr = np.array(got)
            return dict(states=arr)
        except Exception:
            return None

    def learn(self, n_steps: int = 1):
        """
        Realiza aprendizado por minibatches. Implementação adaptativa conforme backend.
        - usa Double DQN simples (usando target network quando disponível)
        """
        if len(self.replay) == 0:
            return

        for _ in range(max(1, n_steps)):
            batch = self.sample_batch(self.batch_size)
            if not batch:
                return

            states = batch["states"]
            actions = batch["actions"]
            rewards = batch["rewards"]
            next_states = batch["next_states"]
            dones = batch["dones"]

            # normalize states
            try:
                states = np.asarray([self.normalizer.normalize(s) for s in states])
                next_states = np.asarray([self.normalizer.normalize(s) for s in next_states])
            except Exception:
                pass

            if self.framework == "torch" and _torch:
                self._learn_torch(states, actions, rewards, next_states, dones)
            elif self.framework == "keras" and _keras:
                self._learn_keras(states, actions, rewards, next_states, dones)
            else:
                self._learn_numpy(states, actions, rewards, next_states, dones)

            # update epsilon & steps
            self.steps += 1
            if self.epsilon > self.epsilon_min:
                self.epsilon *= self.epsilon_decay
                self.epsilon = max(self.epsilon, self.epsilon_min)

    # -------------------------
    # Learning implementations
    # -------------------------
    def _learn_torch(self, states, actions, rewards, next_states, dones):
        import torch.nn.functional as F
        device = self.device
        q_net = self._q_network
        target = self._target_model if self._target_model is not None else q_net
        q_net.train()

        states_t = _torch.from_numpy(states).float().to(device)
        next_states_t = _torch.from_numpy(next_states).float().to(device)
        actions_t = _torch.from_numpy(actions).long().to(device)
        rewards_t = _torch.from_numpy(rewards).float().to(device)
        dones_t = _torch.from_numpy(dones.astype(np.uint8)).float().to(device)

        # current Q
        q_values = q_net(states_t)
        q_a = q_values.gather(1, actions_t.unsqueeze(1)).squeeze(1)

        # Double DQN: choose actions with online network, evaluate with target
        with _torch.no_grad():
            next_q_online = q_net(next_states_t)
            next_actions = next_q_online.argmax(dim=1, keepdim=True)
            next_q_target = target(next_states_t)
            next_q_val = next_q_target.gather(1, next_actions).squeeze(1)
            target_q = rewards_t + (1.0 - dones_t) * (self.gamma * next_q_val)

        loss = F.mse_loss(q_a, target_q)
        self._optimizer.zero_grad()
        loss.backward()
        # gradient clipping
        _torch.nn.utils.clip_grad_norm_(q_net.parameters(), max_norm=10.0)
        self._optimizer.step()

        # soft update target
        if self._target_model is not None:
            self._soft_update_torch(self._target_model, self._q_network, self.tau)

    def _soft_update_torch(self, target, source, tau):
        for t_p, s_p in zip(target.parameters(), source.parameters()):
            t_p.data.copy_(t_p.data * (1.0 - tau) + s_p.data * tau)

    def _learn_keras(self, states, actions, rewards, next_states, dones):
        # Implementação simples: calcula alvos e treina com fit
        q_next = self._target_model.predict(next_states, verbose=0) if self._target_model else self._q_network.predict(next_states, verbose=0)
        q_next_online = self._q_network.predict(next_states, verbose=0)
        # double dqn select
        next_actions = np.argmax(q_next_online, axis=1)
        next_q = q_next[np.arange(len(next_actions)), next_actions]
        targets = self._q_network.predict(states, verbose=0)
        for i in range(len(states)):
            targets[i, actions[i]] = rewards[i] + (0.0 if dones[i] else self.gamma * next_q[i])
        # treina
        self._q_network.fit(states, targets, epochs=1, verbose=0, batch_size=len(states))

        # soft update target weights
        if self._target_model:
            w_src = np.array(self._q_network.get_weights(), dtype=object)
            w_tgt = np.array(self._target_model.get_weights(), dtype=object)
            new_w = [(1 - self.tau) * wt + self.tau * ws for wt, ws in zip(w_tgt, w_src)]
            self._target_model.set_weights(new_w)

    def _learn_numpy(self, states, actions, rewards, next_states, dones):
        # Q-learning tabular-like update for linear approximator weights (very rough)
        lr = self.lr
        for i in range(len(states)):
            s = np.asarray(states[i]).reshape(1, -1)
            ns = np.asarray(next_states[i]).reshape(1, -1)
            q = s.dot(self._W) + self._b
            q_next = ns.dot(self._W) + self._b
            target = rewards[i] + (0.0 if dones[i] else self.gamma * np.max(q_next))
            a = int(actions[i])
            td = target - q[0, a]
            # gradient step on weights/bias
            self._W[:, a] += lr * td * s.reshape(-1)
            self._b[a] += lr * td

    # -------------------------
    # Utilities: save/load/soft_update/reset
    # -------------------------
    def save(self, path: str):
        """Salva pesos/estado mínimo para reiniciar o agente depois."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = dict(
            framework=self.framework,
            state_size=self.state_size,
            action_size=self.action_size,
            steps=self.steps,
            epsilon=self.epsilon,
        )
        try:
            if self.framework == "torch" and _torch:
                data["torch_state"] = self._q_network.state_dict()
            elif self.framework == "keras" and _keras:
                data["keras_weights"] = self._q_network.get_weights()
            else:
                data["W"] = self._W
                data["b"] = self._b
            with open(path, "wb") as f:
                pickle.dump(data, f)
            self.logger.info("Agente salvo em %s", path)
        except Exception as e:
            self.logger.exception("Falha ao salvar agente: %s", e)
            raise

    def load(self, path: str):
        """Carrega pesos/estado guardado por save()."""
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            fw = data.get("framework")
            if fw != self.framework:
                self.logger.warning("Framework salvo (%s) difere do atual (%s). Tenta adaptar.", fw, self.framework)
            self.steps = data.get("steps", self.steps)
            self.epsilon = data.get("epsilon", self.epsilon)
            if self.framework == "torch" and _torch and "torch_state" in data:
                self._q_network.load_state_dict(data["torch_state"])
            elif self.framework == "keras" and _keras and "keras_weights" in data:
                self._q_network.set_weights(data["keras_weights"])
            else:
                if "W" in data and "b" in data:
                    self._W = data["W"]
                    self._b = data["b"]
            self.logger.info("Agente carregado de %s", path)
        except Exception as e:
            self.logger.exception("Falha ao carregar agente: %s", e)
            raise

    def soft_update(self, tau: Optional[float] = None):
        """Força soft update do target network agora."""
        tau = self.tau if tau is None else float(tau)
        if self.framework == "torch" and self._target_model is not None:
            self._soft_update_torch(self._target_model, self._q_network, tau)
        elif self.framework == "keras" and self._target_model is not None:
            w_src = self._q_network.get_weights()
            w_tgt = self._target_model.get_weights()
            new_w = [(1 - tau) * wt + tau * ws for wt, ws in zip(w_tgt, w_src)]
            self._target_model.set_weights(new_w)
        else:
            # numpy fallback: nada a fazer (weights são únicos)
            pass

    def reset(self):
        """Reseta algumas variáveis internas (epsilon opcional)."""
        self.steps = 0
        self.epsilon = 0.15

    def update_normalizer(self, x):
        """Exposição para atualizar o normalizador externamente."""
        try:
            self.normalizer.update(x)
        except Exception:
            pass
    # -------------------------
    # Model builders
    # -------------------------
    def act_inference(self, state) -> int:
        """
        Método seguro de inferência (SEM treino).
        Tenta várias assinaturas comuns (act/predict) e normaliza o retorno para um inteiro de ação.
        Garante que NUNCA levante exceção para o chamador — sempre retorna uma ação válida (int).
        """
        import logging
        try:
            import numpy as _np
        except Exception:
            _np = None

        logger = getattr(self, "logger", logging.getLogger("DQNAgent"))

        def _to_np(x):
            # converte estado para numpy 1D/2D conforme necessário
            try:
                if _np is None:
                    return x
                if isinstance(x, _np.ndarray):
                    return x
                if isinstance(x, (list, tuple)):
                    arr = _np.array(x)
                    # se for 0-d, keep
                    return arr
                # se for pandas Series/DataFrame
                try:
                    import pandas as _pd
                    if isinstance(x, _pd.Series):
                        return x.to_numpy()
                    if isinstance(x, _pd.DataFrame):
                        return x.to_numpy()
                except Exception:
                    pass
                return _np.array(x)
            except Exception:
                return x

        def _clamp_action(a: int) -> int:
            """Se tivermos info sobre action_size ou action_space, clamp para esse range."""
            try:
                max_a = None
                if hasattr(self, "action_size"):
                    max_a = int(getattr(self, "action_size"))
                elif hasattr(self, "n_actions"):
                    max_a = int(getattr(self, "n_actions"))
                elif hasattr(self, "action_space") and hasattr(self.action_space, "n"):
                    max_a = int(self.action_space.n)
                if max_a is not None and max_a > 0:
                    if a < 0:
                        return 0
                    if a >= max_a:
                        return max_a - 1
                return int(a)
            except Exception:
                try:
                    return int(a)
                except Exception:
                    return 0

        def _interpret(res):
            """Normaliza vários tipos de resultado para um inteiro de ação ou None."""
            try:
                if res is None:
                    return None
                # int-ish
                if isinstance(res, (int,)):
                    return _clamp_action(res)
                if isinstance(res, float):
                    # se for probabilidade/score, round
                    return _clamp_action(int(round(res)))
                # numpy arrays
                if _np is not None and isinstance(res, _np.ndarray):
                    # se escalar
                    if res.size == 1:
                        try:
                            return _clamp_action(int(res.item()))
                        except Exception:
                            pass
                    # se for vetor de logits/probs -> argmax
                    try:
                        idx = int(_np.argmax(res))
                        return _clamp_action(idx)
                    except Exception:
                        pass
                # list/tuple: se primeiro elemento for ação ou vetor de scores
                if isinstance(res, (list, tuple)):
                    if len(res) == 0:
                        return None
                    first = res[0]
                    # caso comum: (action, info)
                    if isinstance(first, (int, float)):
                        return _clamp_action(int(first))
                    # caso comum: (probs_array, )
                    try:
                        # tenta interpretar primeiro elemento recursivamente
                        return _interpret(first)
                    except Exception:
                        pass
                # dict: aceita {'action': x} ou {'a': x}
                if isinstance(res, dict):
                    for key in ("action", "act", "a"):
                        if key in res:
                            return _interpret(res[key])
                    # por vezes o retorno é {'probs': [...]} ou {'logits': [...]}
                    for key in ("probs", "probas", "logits", "policy"):
                        if key in res:
                            return _interpret(res[key])
                    # se dict tem keys numéricas -> tente pegar primeira
                    vals = list(res.values())
                    if vals:
                        return _interpret(vals[0])
                # string que representa número
                if isinstance(res, str):
                    try:
                        return _clamp_action(int(res))
                    except Exception:
                        try:
                            return _clamp_action(int(float(res)))
                        except Exception:
                            return None
            except Exception as e:
                logger.debug("DQN interpret error: %s", e, exc_info=True)
            return None

        # ---------- tentativa de chamadas em ordem segura ----------
        state_np = _to_np(state)

        call_candidates = []

        # prioridade 1: self.act with simple arg (no kwargs)
        if hasattr(self, "act") and callable(getattr(self, "act")):
            call_candidates.append(lambda: self.act(state_np))
            # tentativas com kwargs em ordens não-fatais — serão capturadas se assinatura não aceitar
            call_candidates.append(lambda: self.act(state_np, training=False))
            call_candidates.append(lambda: self.act(state_np, training=False, deterministic=True))
            call_candidates.append(lambda: self.act(state_np, deterministic=True))
            call_candidates.append(lambda: self.act(state_np, explore=False))
        # prioridade 2: predict variants
        if hasattr(self, "predict") and callable(getattr(self, "predict")):
            call_candidates.append(lambda: self.predict(state_np))
            if _np is not None:
                call_candidates.append(lambda: self.predict(_np.expand_dims(state_np, 0)))
        # prioridade 3: model.predict if available (Keras/TensorFlow style)
        model_obj = getattr(self, "model", None)
        if model_obj is not None and hasattr(model_obj, "predict"):
            if _np is not None:
                call_candidates.append(lambda: model_obj.predict(_np.expand_dims(state_np, 0)))
            else:
                call_candidates.append(lambda: model_obj.predict(state_np))

        last_exc = None
        for fn in call_candidates:
            try:
                res = fn()
                action = _interpret(res)
                if action is not None:
                    return int(action)
            except TypeError as te:
                # assinatura incompatível; tenta próximo sem log de erro ruidoso
                last_exc = te
                continue
            except Exception as e:
                last_exc = e
                logger.debug("DQN inference candidate failed: %s", e, exc_info=True)
                continue

        # última tentativa: chamar act with raw state (in case wrappers expect lists)
        try:
            if hasattr(self, "act") and callable(getattr(self, "act")):
                try:
                    res = self.act(state)
                    action = _interpret(res)
                    if action is not None:
                        return int(action)
                except Exception:
                    pass
        except Exception:
            pass

        # log do último erro para depuração leve, sem quebrar runtime
        if last_exc is not None:
            logger.debug("DQN inference all candidates failed, last error: %s", last_exc, exc_info=True)

        # fallback absoluto
        return 0  # HOLD

    
    def save_full(self, path_prefix: str):
        """
        Salva completamente o agente:
        - Pesos do modelo (self.save)
        - Replay buffer
        - Normalizador de estados
        - Metadata (epsilon, steps)
        
        Recursos avançados:
        - Logging detalhado
        - Criação automática de diretório
        - Salvamento atômico
        - Protocol pickle mais recente
        """
        import os
        import pickle
        import logging
        import tempfile
        logger = getattr(self, "logger", logging.getLogger("DQNAgent"))

        try:
            # garante que o diretório existe
            directory = os.path.dirname(path_prefix)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.debug("Criado diretório: %s", directory)
        except Exception as e:
            logger.warning("Falha ao criar diretório para save_full: %s", e)

        # ---------- 1) Salvar pesos / modelo ----------
        try:
            self.save(path_prefix)
            logger.debug("Modelo salvo em: %s", path_prefix)
        except Exception as e:
            logger.warning("Falha ao salvar modelo com self.save: %s", e)

        # ---------- 2) Salvar replay buffer ----------
        replay_path = path_prefix + "_replay.pkl"
        try:
            with tempfile.NamedTemporaryFile("wb", delete=False) as tmp:
                pickle.dump(self.replay, tmp, protocol=pickle.HIGHEST_PROTOCOL)
                tmp_path = tmp.name
            os.replace(tmp_path, replay_path)
            logger.debug("Replay buffer salvo em: %s", replay_path)
        except Exception as e:
            logger.warning("Falha ao salvar replay buffer: %s", e)

        # ---------- 3) Salvar normalizer ----------
        normalizer_path = path_prefix + "_normalizer.pkl"
        try:
            with tempfile.NamedTemporaryFile("wb", delete=False) as tmp:
                pickle.dump(self.normalizer, tmp, protocol=pickle.HIGHEST_PROTOCOL)
                tmp_path = tmp.name
            os.replace(tmp_path, normalizer_path)
            logger.debug("Normalizer salvo em: %s", normalizer_path)
        except Exception as e:
            logger.warning("Falha ao salvar normalizer: %s", e)

        # ---------- 4) Salvar meta ----------
        meta_path = path_prefix + "_meta.pkl"
        meta = {"epsilon": self.epsilon, "steps": self.steps}
        try:
            with tempfile.NamedTemporaryFile("wb", delete=False) as tmp:
                pickle.dump(meta, tmp, protocol=pickle.HIGHEST_PROTOCOL)
                tmp_path = tmp.name
            os.replace(tmp_path, meta_path)
            logger.debug("Meta salvo em: %s", meta_path)
        except Exception as e:
            logger.warning("Falha ao salvar meta: %s", e)

    
    def _build_model(self):
        import logging

        logger = getattr(self, "logger", logging.getLogger("DQNAgent"))

        self.framework = None
        self.device = "cpu"
        self._q_network = None
        self._target_network = None

        # ==================================================
        # 1️⃣ PyTorch (prioridade máxima – mais estável em prod)
        # ==================================================
        if _torch is not None:
            try:
                self.framework = "torch"
                self.device = (
                    _torch.device("cuda")
                    if _torch.cuda.is_available()
                    else _torch.device("cpu")
                )
                self._build_torch()
                logger.info("DQNAgent usando backend PyTorch (%s)", self.device)
                return
            except Exception as e:
                logger.exception("Falha ao iniciar backend PyTorch: %s", e)
                self.framework = None

        # ==================================================
        # 2️⃣ TensorFlow / Keras (fallback controlado)
        # ==================================================
        if _keras is not None:
            try:
                self.framework = "keras"
                self.device = "cpu"
                self._build_keras()
                logger.info("DQNAgent usando backend TensorFlow/Keras")
                return
            except Exception as e:
                logger.exception("Falha ao iniciar backend Keras: %s", e)
                self.framework = None

        # ==================================================
        # 3️⃣ NumPy (fallback FINAL – nunca falha)
        # ==================================================
        try:
            self.framework = "numpy"
            self.device = "cpu"
            self._build_numpy()
            logger.warning("DQNAgent usando backend NumPy (fallback final)")
        except Exception as e:
            logger.critical("Falha total ao iniciar DQNAgent: %s", e)
            raise RuntimeError(
                "Nenhum backend disponível para DQNAgent (Torch/Keras/NumPy)"
            ) from e
    
    def log_trade(self, info: Dict[str, Any]):
        import json
        import os

        self.trade_log.append(info)

        log_file = "trades_log.json"

        try:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if not isinstance(existing, list):
                        existing = []
            else:
                existing = []

            existing.append(info)

            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.warning("Falha ao persistir trade_log: %s", e)
            
    # -------- TensorFlow model --------
    def _build_tf(self):
        # usando tf.keras explicitamente
        inputs = tf.keras.Input(shape=(self.state_size,), name="state")
        x = tf.keras.layers.Dense(256, activation="relu")(inputs)
        x = tf.keras.layers.Dense(128, activation="relu")(x)
        x = tf.keras.layers.Dense(64, activation="relu")(x)
        outputs = tf.keras.layers.Dense(self.action_size, activation="linear")(x)

        self.q_net = tf.keras.Model(inputs=inputs, outputs=outputs)
        self.q_net.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=self.lr), loss="mse")

        # target network
        self.target_net = tf.keras.models.clone_model(self.q_net)
        self.target_net.set_weights(self.q_net.get_weights())

    # -------- PyTorch model --------
    def _build_torch(self):
        """
        Constrói uma rede MLP Torch robusta e cria optimizer + target network.
        Esta versão:
        - importa torch localmente (evita erros do linter/ambiente)
        - valida state_size/action_size
        - escolhe device corretamente
        - inicializa pesos (kaiming/xavier)
        - cria aliases compatíveis (_q_network/_target_network/_optimizer)
        - faz sanity check com forward dummy
        """
        # verifica disponibilidade
        if _torch is None:
            raise RuntimeError("PyTorch não disponível (_torch is None)")

        import torch
        import torch.nn as nn
        import torch.optim as optim
        import torch.nn.functional as F

        # garante device coerente
        if not hasattr(self, "device") or self.device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            # converter string/device se necessário
            try:
                self.device = torch.device(self.device) if isinstance(self.device, str) else self.device
            except Exception:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        in_dim = int(self.state_size)
        out_dim = int(self.action_size)
        if in_dim <= 0 or out_dim <= 0:
            raise ValueError(f"Dimensões inválidas: state_size={in_dim}, action_size={out_dim}")

        # define arquitetura MLP
        class Net(nn.Module):
            def __init__(self, s: int, a: int):
                super().__init__()
                h1 = max(256, s * 2)  # podes ajustar heurística
                h2 = max(128, s)
                self.net = nn.Sequential(
                    nn.Linear(s, 256),
                    nn.ReLU(),
                    nn.Linear(256, 128),
                    nn.ReLU(),
                    nn.Linear(128, 64),
                    nn.ReLU(),
                    nn.Linear(64, a)
                )
                # inicialização robusta dos pesos
                for m in self.net:
                    if isinstance(m, nn.Linear):
                        nn.init.kaiming_uniform_(m.weight, nonlinearity="relu")
                        if m.bias is not None:
                            nn.init.zeros_(m.bias)

            def forward(self, x):
                return self.net(x)

        # cria redes e otimizer
        q_net = Net(in_dim, out_dim).to(self.device)
        target_net = Net(in_dim, out_dim).to(self.device)
        # copia pesos com no_grad
        with torch.no_grad():
            target_net.load_state_dict(q_net.state_dict())

        optimizer = optim.Adam(q_net.parameters(), lr=float(getattr(self, "lr", 1e-3)))

        # freeze target params (não devem gradientes)
        for p in target_net.parameters():
            p.requires_grad = False

        # atributos usados por outros trechos do código
        # define ambos nomes para compatibilidade: tua versão (q_net) e a usada por predict/_predict_q (_q_network)
        self.q_net = q_net
        self.target_net = target_net
        self.optimizer = optimizer

        # aliases compatíveis (muitos pontos do projecto usam underscore names)
        self._q_network = self.q_net
        self._target_network = self.target_net
        self._optimizer = self.optimizer

        # marca framework e faz sanity-check forward
        self.framework = "torch"
        try:
            self._q_network.eval()
            with torch.no_grad():
                dummy = torch.zeros((1, in_dim), dtype=torch.float32, device=self.device)
                out = self._q_network(dummy)
                # garante shape esperado
                assert out is not None and out.shape[-1] == out_dim
        except Exception as e:
            # cleanup parcial e raise claro
            self.logger.exception("Sanity-check da Q-network falhou: %s", e)
            raise RuntimeError("Falha ao construir/validar Q-network Torch") from e

        self.logger.info("Torch Q-network criada | state=%s action=%s device=%s", in_dim, out_dim, self.device)

    # -------- NumPy fallback --------
    def _build_numpy(self):
        """
        Constrói pesos e biases para MLP simples (3 hidden layers + output)
        usando NumPy, com inicialização Xavier/Glorot para estabilidade.
        """

        def glorot_init(in_dim, out_dim):
            limit = np.sqrt(6.0 / (in_dim + out_dim))
            return np.random.uniform(-limit, limit, size=(in_dim, out_dim)).astype(np.float32)

        # Camadas ocultas
        self.w1 = glorot_init(self.state_size, 256)
        self.b1 = np.zeros(256, dtype=np.float32)

        self.w2 = glorot_init(256, 128)
        self.b2 = np.zeros(128, dtype=np.float32)

        self.w3 = glorot_init(128, 64)
        self.b3 = np.zeros(64, dtype=np.float32)

        # Camada de saída (ações)
        self.w4 = glorot_init(64, self.action_size)
        self.b4 = np.zeros(self.action_size, dtype=np.float32)

    # -------------------------
    # Forward / predict
    # -------------------------
    def _q_values(self, states: np.ndarray) -> np.ndarray:
        """Return q-values for array of states (n, state_size)"""
        if self.framework == "tensorflow":
            return self.q_net.predict(states, verbose=0)
        if self.framework == "pytorch":
            with torch.no_grad():
                t = torch.FloatTensor(states).to(self.device)
                out = self.q_net(t).cpu().numpy()
                return out
        # numpy forward
        x = np.asarray(states, dtype=np.float32)
        x = x.dot(self.w1) + self.b1
        x = np.maximum(x, 0)
        x = x.dot(self.w2) + self.b2
        x = np.maximum(x, 0)
        x = x.dot(self.w3) + self.b3
        x = np.maximum(x, 0)
        out = x.dot(self.w4) + self.b4
        return out

    def act(self, state: np.ndarray, greedy: bool = False) -> int:
        """Epsilon-greedy action selection"""
        self.steps += 1
        state = np.asarray(state, dtype=np.float32)
        self.normalizer.update(state.reshape(1, -1))
        norm = self.normalizer.normalize(state)
        if (not greedy) and (random.random() < self.epsilon):
            return random.randrange(self.action_size)
        q = self._q_values(norm.reshape(1, -1))[0]
        return int(np.argmax(q))

    # -------------------------
    # Store & learn
    # -------------------------
    def store(self, state, action, reward, next_state, done):
        self.replay.push(state, action, reward, next_state, done)

    def soft_update(self):
        if self.framework == "numpy":
            # implement basic target weights
            if not hasattr(self, 'target_w4'):
                self.target_w1, self.target_b1 = self.w1.copy(), self.b1.copy()
                self.target_w2, self.target_b2 = self.w2.copy(), self.b2.copy()
                self.target_w3, self.target_b3 = self.w3.copy(), self.b3.copy()
                self.target_w4, self.target_b4 = self.w4.copy(), self.b4.copy()
            else:
                tau = self.tau
                self.target_w1 = tau*self.w1 + (1-tau)*self.target_w1
                self.target_b1 = tau*self.b1 + (1-tau)*self.target_b1
                self.target_w2 = tau*self.w2 + (1-tau)*self.target_w2
                self.target_b2 = tau*self.b2 + (1-tau)*self.target_b2
                self.target_w3 = tau*self.w3 + (1-tau)*self.target_w3
                self.target_b3 = tau*self.b3 + (1-tau)*self.target_b3
                self.target_w4 = tau*self.w4 + (1-tau)*self.target_w4
                self.target_b4 = tau*self.b4 + (1-tau)*self.target_b4

    def learn(self, n_steps: int = 1):
        """Performs learning updates"""
        if len(self.replay) < max(1, self.batch_size // 4):
            return

        for _ in range(n_steps):
            batch, indices, weights = self.replay.sample(self.batch_size, beta=self.beta)
            if not batch:
                return
            states = np.vstack([b[0].reshape(1, -1) for b in batch]).astype(np.float32).squeeze()
            actions = np.array([b[1] for b in batch], dtype=np.int32)
            rewards = np.array([b[2] for b in batch], dtype=np.float32)
            next_states = np.vstack([b[3].reshape(1, -1) for b in batch]).astype(np.float32).squeeze()
            dones = np.array([b[4] for b in batch], dtype=np.bool_)

            # normalize
            self.normalizer.update(states)
            self.normalizer.update(next_states)
            s_norm = self.normalizer.normalize(states)
            ns_norm = self.normalizer.normalize(next_states)

            if self.framework == "tensorflow":
                self._learn_tf(s_norm, actions, rewards, ns_norm, dones, indices, weights)
            elif self.framework == "pytorch":
                self._learn_torch(s_norm, actions, rewards, ns_norm, dones, indices, weights)
            else:
                self._learn_numpy(s_norm, actions, rewards, ns_norm, dones, indices, weights)

            # update beta and epsilon schedules
            self.beta = min(1.0, self.beta + self.beta_increment)
            if self.epsilon > self.epsilon_min:
                self.epsilon *= self.epsilon_decay

            # soft update
            self.soft_update()

    # -------------------------
    # Learning TF
    # -------------------------
    def _learn_tf(self, s, actions, rewards, ns, dones, indices, weights):
        # Double DQN target: action selection by q_net, evaluation by target_net
        q_next = self.q_net.predict(ns, verbose=0)
        next_actions = np.argmax(q_next, axis=1)
        q_next_target = self.target_net.predict(ns, verbose=0)
        # compute targets
        q_target = self.q_net.predict(s, verbose=0)
        targets = q_target.copy()
        td_errors = []
        for i in range(len(s)):
            if dones[i]:
                target_val = rewards[i]
            else:
                target_val = rewards[i] + self.gamma * q_next_target[i, next_actions[i]]
            td = target_val - q_target[i, actions[i]]
            td_errors.append(td)
            targets[i, actions[i]] = target_val
        # train with sample weights = importance weights
        try:
            self.q_net.fit(s, targets, sample_weight=weights, epochs=1, verbose=0)
        except Exception:
            # fallback train without sample weights
            self.q_net.fit(s, targets, epochs=1, verbose=0)
        # update priorities
        self.replay.update_priorities(indices, [abs(float(x)) for x in td_errors])

    # -------------------------
    # Learning PyTorch
    # -------------------------
    def _learn_torch(self, s, actions, rewards, ns, dones, indices, weights):
        s_t = torch.FloatTensor(s).to(self.device)
        ns_t = torch.FloatTensor(ns).to(self.device)
        actions_t = torch.LongTensor(actions).to(self.device)
        rewards_t = torch.FloatTensor(rewards).to(self.device)
        dones_t = torch.BoolTensor(dones).to(self.device)
        weights_t = torch.FloatTensor(weights).to(self.device)

        # Double DQN
        q_next = self.q_net(ns_t)
        next_actions = torch.argmax(q_next, dim=1)
        q_next_target = self.target_net(ns_t)
        q_next_vals = q_next_target.gather(1, next_actions.unsqueeze(1)).squeeze()

        q_vals = self.q_net(s_t).gather(1, actions_t.unsqueeze(1)).squeeze()
        target = rewards_t + self.gamma * q_next_vals * (~dones_t).float()
        loss = (weights_t * F.mse_loss(q_vals, target.detach(), reduction="none")).mean()

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        # update priorities by absolute TD
        td_errors = (target.detach() - q_vals).abs().cpu().numpy().tolist()
        self.replay.update_priorities(indices, td_errors)

    # -------------------------
    # Learning NumPy fallback
    # -------------------------
    def _learn_numpy(self, s, actions, rewards, ns, dones, indices, weights):
        # naive bootstrap update on last layer only (very simplified)
        q_s = self._q_values(s)
        q_ns = self._q_values(ns)
        td_errors = []
        for i in range(len(s)):
            if dones[i]:
                target = rewards[i]
            else:
                # double selection: pick argmax on q_s_next, evaluate by q_ns
                a_star = int(np.argmax(self._q_values(ns[i].reshape(1, -1))[0]))
                target = rewards[i] + self.gamma * q_ns[i, a_star]
            td = target - q_s[i, actions[i]]
            td_errors.append(td)
            # simple gradient step on final layer via delta into last layer representation
            # backprop approximated by using hidden activations from forward pass (we re-compute)
            # Forward pass to hidden layer
            x = np.maximum(0, s[i].dot(self.w1) + self.b1)
            x = np.maximum(0, x.dot(self.w2) + self.b2)
            x = np.maximum(0, x.dot(self.w3) + self.b3)
            grad_out = np.zeros_like(self.w4)
            lr = self.lr * (weights[i] if weights is not None else 1.0)
            # update w4 and b4 for action column
            self.w4[:, actions[i]] += lr * td * x
            self.b4[actions[i]] += lr * td
        self.replay.update_priorities(indices, [abs(float(x)) for x in td_errors])

    # -------------------------
    # Save / load
    # -------------------------
    def save(self, path_prefix: str):
        meta = {
            "framework": self.framework,
            "state_size": self.state_size,
            "action_size": self.action_size,
            "lr": self.lr,
            "gamma": self.gamma,
            "epsilon": self.epsilon,
            "tau": self.tau
        }
        os.makedirs(os.path.dirname(path_prefix) or ".", exist_ok=True)
        # backend-specific weights
        try:
            if self.framework == "tensorflow":
                self.q_net.save_weights(path_prefix + "_tf_weights.h5")
                self.target_net.save_weights(path_prefix + "_tf_target.h5")
            elif self.framework == "pytorch":
                torch.save(self.q_net.state_dict(), path_prefix + "_pt_weights.pth")
                torch.save(self.target_net.state_dict(), path_prefix + "_pt_target.pth")
            else:
                np.savez(path_prefix + "_np_weights.npz",
                         w1=self.w1, b1=self.b1, w2=self.w2, b2=self.b2,
                         w3=self.w3, b3=self.b3, w4=self.w4, b4=self.b4)
            with open(path_prefix + "_meta.json", "w") as f:
                json.dump(meta, f)
            logger.info("Agent saved to %s*", path_prefix)
        except Exception as e:
            logger.exception("Failed to save agent: %s", e)

    def load(self, path_prefix: str) -> bool:
        try:
            if self.framework == "tensorflow":
                self.q_net.load_weights(path_prefix + "_tf_weights.h5")
                self.target_net.load_weights(path_prefix + "_tf_target.h5")
            elif self.framework == "pytorch":
                self.q_net.load_state_dict(torch.load(path_prefix + "_pt_weights.pth"))
                self.target_net.load_state_dict(torch.load(path_prefix + "_pt_target.pth"))
            else:
                arr = np.load(path_prefix + "_np_weights.npz")
                self.w1 = arr["w1"]; self.b1 = arr["b1"]
                self.w2 = arr["w2"]; self.b2 = arr["b2"]
                self.w3 = arr["w3"]; self.b3 = arr["b3"]
                self.w4 = arr["w4"]; self.b4 = arr["b4"]
            logger.info("Agent loaded from %s*", path_prefix)
            return True
        except Exception as e:
            logger.exception("Failed to load agent: %s", e)
            return False


class TradingEnv:
    """
    Lightweight trading environment for DQN training.
    Provides state vector, step/reward accounting, trade closing, and position sizing heuristics.
    """

    def __init__(self, df: pd.DataFrame, initial_balance: float = 10000.0, state_size: int = 50):
        import numpy as np
        from typing import List, Dict, Any

        self.df = df.reset_index(drop=True).copy()
        self.initial_balance = float(initial_balance)
        self.current_step = 0
        self.max_steps = max(1, len(self.df) - 1)

        # trading state
        self.state_size = self._validate_positive_int(state_size, "state_size")
        self.balance = float(initial_balance)
        self.position = 0  # -1 short, 0 flat, 1 long
        self.position_size = 0.0
        self.entry_price = 0.0
        self.unrealized = 0.0
        self.realized = 0.0

        # prepare features
        self._prepare_features()
        self.feature_cols = [c for c in self.df.columns if c.endswith("_norm")]
        if not self.feature_cols:
            raise ValueError("No normalized feature columns found in df. Ensure your df has *_norm columns.")

        # position config
        self.max_position_pct = 0.05  # % of balance per trade
        self.transaction_cost = 0.00005  # proportion per trade

        # trade log
        self.trade_log: List[Dict[str, Any]] = []

        # initialize observation and action spaces
        sample_state = self._get_state()
        self.observation_space = _Box(
            low=-np.inf,
            high=np.inf,
            shape=(len(sample_state),),
            dtype=np.float32
        )
        self.action_space = _Discrete(3)  # 0=SELL, 1=HOLD, 2=BUY

    # ----------------------------
    # Helpers
    # ----------------------------
    def _validate_positive_int(self, value, name: str) -> int:
        try:
            iv = int(value)
            if iv <= 0:
                raise ValueError(f"{name} must be positive, got {value}")
            return iv
        except Exception as e:
            raise ValueError(f"Invalid {name}: {value}") from e

    def _prepare_features(self):
        """
        Prepare normalized features for the environment.
        Example: normalize close, volume, indicators, etc.
        """
        for col in self.df.columns:
            if np.issubdtype(self.df[col].dtype, np.number):
                norm_col = f"{col}_norm"
                max_val = self.df[col].max()
                min_val = self.df[col].min()
                range_val = max_val - min_val if max_val != min_val else 1.0
                self.df[norm_col] = (self.df[col] - min_val) / range_val

    def _get_state(self):
        """
        Returns current state vector for DQN.
        Concatenates last `state_size` normalized feature values + position info.
        """
        start_idx = max(0, self.current_step - self.state_size + 1)
        end_idx = self.current_step + 1
        features = self.df[self.feature_cols].iloc[start_idx:end_idx].values

        # pad if needed
        if features.shape[0] < self.state_size:
            pad = np.zeros((self.state_size - features.shape[0], features.shape[1]), dtype=np.float32)
            features = np.vstack([pad, features])

        # flatten and append position info
        state = features.flatten()
        state = np.concatenate([state, [self.position, self.balance / self.initial_balance]])
        return state.astype(np.float32)

    def _prepare_features(self):
        df = self.df
        if "volume" not in df.columns:
            df["volume"] = 0.15

        # ensure columns exist
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")
        # add technical features (robust, safe)
        df["sma_10"] = df["close"].rolling(10, min_periods=1).mean()
        df["sma_20"] = df["close"].rolling(20, min_periods=1).mean()
        delta = df["close"].diff().fillna(0.0)
        gain = delta.clip(lower=0).rolling(14, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).rolling(14, min_periods=1).mean()
        rs = gain / (loss.replace(0, np.nan)).fillna(0.0)
        df["rsi"] = 100 - (100 / (1 + rs)).fillna(50)
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = (ema12 - ema26).fillna(0.0)
        sma20 = df["close"].rolling(20, min_periods=1).mean()
        std20 = df["close"].rolling(20, min_periods=1).std().fillna(0.0)
        df["bb_upper"] = sma20 + 2 * std20
        df["bb_lower"] = sma20 - 2 * std20
        # atr
        high = df.get("high", df["close"])
        low = df.get("low", df["close"])
        prev = df["close"].shift(1).fillna(df["close"])
        tr = np.maximum(high - low, np.maximum((high - prev).abs(), (low - prev).abs()))
        df["atr"] = tr.rolling(14, min_periods=1).mean().fillna(0.0)
        df["momentum"] = df["close"] - df["close"].shift(10).fillna(0.0)
        # fillna
        df.ffill(inplace=True)
        df.bfill(inplace=True)

        df.fillna(0.0, inplace=True)
        # normalize columns into *_norm using rolling mean/std to be robust
        norm_cols = ["close", "sma_10", "sma_20", "rsi", "macd", "bb_upper", "bb_lower", "atr", "momentum"]
        for c in norm_cols:
            mean = df[c].rolling(100, min_periods=1).mean()
            std = df[c].rolling(100, min_periods=1).std().replace(0, 1.0)
            df[f"{c}_norm"] = ((df[c] - mean) / std).fillna(0.0)
        self.df = df

    def reset(self, random_start: bool = True):
        self.current_step = random.randint(self.state_size, max(self.state_size, self.max_steps - 1)) if random_start else self.state_size
        self.balance = self.initial_balance
        self.position = 0
        self.position_size = 0.0
        self.entry_price = 0.0
        self.unrealized = 0.0
        self.realized = 0.0
        self.trade_log = []
        return self._get_state()

    def _get_state(self) -> np.ndarray:
        i = self.current_step
        start = max(0, i - self.state_size + 1)
        rows = self.df.iloc[start:i + 1]
        # gather norm cols
        cols = [c for c in self.df.columns if c.endswith("_norm")]
        arr = rows[cols].values
        # pad if needed (state_size x features)
        if arr.shape[0] < self.state_size:
            pad = np.zeros((self.state_size - arr.shape[0], arr.shape[1]), dtype=np.float32)
            arr = np.vstack([pad, arr])
        # flatten
        flat = arr.flatten()
        # add portfolio info
        meta = np.array([
            self.position,
            self.position_size,
            (self.balance - self.initial_balance) / (self.initial_balance + 1e-9),
            self.realized / (self.initial_balance + 1e-9)
        ], dtype=np.float32)
        return np.concatenate([flat, meta]).astype(np.float32)

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        action: 0 hold, 1 buy, 2 sell
        returns: next_state, reward, done, info
        """
        price = float(self.df["close"].iat[self.current_step])
        reward = 0.0
        done = False

        # execute action
        if action == 1:  # buy
            if self.position <= 0:
                # close short if any
                if self.position == -1:
                    reward += self._close(price)
                # open long
                self._open(1, price)
                reward += 0.001
        elif action == 2:  # sell
            if self.position >= 0:
                if self.position == 1:
                    reward += self._close(price)
                self._open(-1, price)
                reward += 0.001
        else:
            # small reward for holding profitable position
            if self.position == 0:
                reward -= 0.001  # penaliza ficar parado
            else:
                pnl = self._unrealized(price)
                reward += np.tanh(pnl / (self.initial_balance * 0.01))

        # advance
        self.current_step += 1
        if self.current_step >= self.max_steps:
            done = True
            # close any open position
            if self.position != 0:
                reward += self._close(price)

        # compute info
        state = self._get_state()
        total_value = self.balance + self._unrealized(price)
        info = {"balance": self.balance, "position": self.position, "unrealized": self._unrealized(price), "total_value": total_value}
        # reward shaping: small penalty for large drawdown
        if total_value < self.initial_balance * 0.9:
            reward -= 0.05
        return state, float(reward), done, info

    def _open(self, direction: int, price: float):
        # use portion of balance
        alloc = max(1e-6, self.balance * self.max_position_pct)
        position_value = alloc
        position_size = position_value / (price + 1e-12)
        cost = position_value * self.transaction_cost
        self.balance -= cost
        self.position = direction
        self.position_size = position_size
        self.entry_price = price

    def _close(self, price: float) -> float:
        if self.position == 0:
            return 0.0

        if self.position == 1:
            pnl = (price - self.entry_price) * self.position_size
        else:
            pnl = (self.entry_price - price) * self.position_size

        cost = abs(self.position_size * price) * self.transaction_cost
        net = pnl - cost

        self.balance += net
        self.realized += net

        self.trade_log.append({
            "entry": self.entry_price,
            "exit": price,
            "pos": self.position,
            "size": self.position_size,
            "pnl": net,
            "time": self.current_step
        })

        self.position = 0
        self.position_size = 0.0
        self.entry_price = 0.0

        return net


    def _unrealized(self, price: float) -> float:
        if self.position == 0:
            return 0.0
        if self.position == 1:
            return (price - self.entry_price) * self.position_size
        return (self.entry_price - price) * self.position_size


# -------------------------
# Strategy wrapper
# -------------------------
class DeepQLearningStrategy:
    def __init__(self, symbol: str = "EURUSD", timeframe: int = 15, checkpoint_dir: str = "./dqn_checkpoints"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        self.agent: Optional[DQNAgent] = None
        self.env: Optional[TradingEnv] = None
        self.ai_manager = AIManager()

        # training config
        self.config = {
            "initial_balance": 10000.0,
            "episodes": 300,
            "max_steps_per_episode": 500,
            "buffer_size": 20000,
            "batch_size": 64,
            "lr": 1e-3,
            "gamma": 0.99,
            "tau": 0.005,
            "state_size": 30 * 10,  # rough default: state window * features (will adapt)
            "save_every": 50
        }

        self.logger = logger
        self.is_trained = False
        self.training_stats: Dict[str, Any] = {}
    def act(self, state):
        raw_out = self.model.predict(state)
        action = self._sanitize_dqn_output(raw_out)
        return action
    def prepare(self, df: pd.DataFrame):
        df2 = df.copy().reset_index(drop=True)
        if "close" not in df2.columns:
            raise ValueError("Data must contain 'close'")
        # create environment and agent based on df
        state_window = min(50, max(10, int(len(df2) / 10)))
        env = TradingEnv(df2, initial_balance=self.config["initial_balance"], state_size=state_window)
        # state length computed from env state
        sample_state = env.reset(random_start=False)
        state_size = len(sample_state)
        self.env = env
        self.agent = DQNAgent(
            state_size=state_size,
            action_size=3,
            lr=self.config["lr"],
            gamma=self.config["gamma"],
            batch_size=self.config["batch_size"],
            buffer_size=self.config["buffer_size"],
            tau=self.config["tau"],
            prioritized=True
        )
        self.logger.info("Prepared env and agent: state_size=%d", state_size)
 
    def train(self, df: pd.DataFrame, episodes: Optional[int] = None) -> Dict[str, Any]:
        episodes = int(episodes or self.config["episodes"])
        self.prepare(df)
        assert self.env and self.agent
        best_reward = -1e9
        rewards = []

        for ep in range(1, episodes + 1):
            state = self.env.reset()
            total_reward = 0.0
            steps = 0
            done = False
            max_steps = min(self.config["max_steps_per_episode"], self.env.max_steps - 1)

            while not done and steps < max_steps:
                action = self.agent.act(state)
                next_state, reward, done, info = self.env.step(action)
                self.agent.store(state, action, reward, next_state, done)
                self.agent.learn(n_steps=1)
                state = next_state
                total_reward += reward
                steps += 1

            rewards.append(total_reward)
            avg_recent = float(np.mean(rewards[-50:])) if rewards else float(total_reward)
            if total_reward > best_reward:
                best_reward = total_reward
            # logging
            if ep % 5 == 0 or ep == 1:
                self.logger.info("Episode %d/%d reward=%.4f avg50=%.4f epsilon=%.3f", ep, episodes, total_reward, avg_recent, self.agent.epsilon)
            # checkpoint
            if ep % self.config["save_every"] == 0:
                path = os.path.join(self.checkpoint_dir, f"dqn_{self.symbol}_{ep}")
                self.agent.save(path)

        self.is_trained = True
        self.training_stats = {
            "episodes": episodes,
            "best_reward": float(best_reward),
            "avg_reward": float(np.mean(rewards)) if rewards else 0.0,
            "last_rewards": rewards[-10:],
            "total_trades": len(self.env.trade_log) if self.env else 0
        }
        # final save
        final_path = os.path.join(self.checkpoint_dir, f"dqn_{self.symbol}_final")
        self.agent.save(final_path)
        return {"success": True, **self.training_stats}
    
    def act_inference(self, state: "np.ndarray") -> int:
        """
        Inferência segura SEM treino.
        - Não altera normalizer (usa cópia para transform/normalize).
        - Suporta agent._q_values, agent.act, agent.predict, model.predict (vários formatos de retorno).
        - Normaliza/flatten conforme necessário e garante retorno int válido (clamp).
        - Nunca lança exceção — devolve 0 (HOLD) como fallback absoluto.
        """

        logger = getattr(self, "logger", logging.getLogger("DQNAgent"))

        # ------------------------------
        # Helpers
        # ------------------------------
        def _clamp_action(a: int) -> int:
            """Garante que a ação está no range válido [0, action_size-1]."""
            try:
                max_a = getattr(self, "action_size", None)
                if max_a is None:
                    max_a = getattr(self, "n_actions", None)
                if max_a is None and hasattr(self, "action_space") and hasattr(self.action_space, "n"):
                    max_a = self.action_space.n
                if max_a is not None and max_a > 0:
                    return max(0, min(int(a), int(max_a) - 1))
                return int(a)
            except Exception:
                try:
                    return int(a)
                except Exception:
                    return 0

        def _ensure_2d(arr: np.ndarray) -> np.ndarray:
            """Garante que o estado está 2D (batch_size=1)."""
            a = np.asarray(arr, dtype=float)
            if a.ndim == 0:
                return a.reshape(1, -1)
            if a.ndim == 1:
                return a.reshape(1, -1)
            if a.ndim > 2:
                return a.reshape(1, -1)
            return a

        def _interpret_action(res) -> int:
            """Normaliza múltiplos tipos de retorno para ação inteira."""
            try:
                if res is None:
                    return None
                if isinstance(res, (int, np.integer)):
                    return _clamp_action(res)
                if isinstance(res, (float, np.floating)):
                    return _clamp_action(int(round(res)))
                if isinstance(res, np.ndarray):
                    if res.size == 1:
                        return _clamp_action(int(res.item()))
                    return _clamp_action(int(np.argmax(res)))
                if isinstance(res, (list, tuple)):
                    if not res:
                        return None
                    # tenta interpretar primeiro elemento
                    first = res[0]
                    if isinstance(first, (int, float, np.integer, np.floating)):
                        return _clamp_action(int(first))
                    try:
                        arr = np.asarray(first)
                        if arr.size > 0:
                            return _clamp_action(int(np.argmax(arr)))
                    except Exception:
                        pass
                    if len(res) > 1:
                        return _interpret_action(res[1])
                if isinstance(res, dict):
                    for k in ("action", "act", "a"):
                        if k in res:
                            return _interpret_action(res[k])
                    for k in ("probs", "probas", "logits", "policy"):
                        if k in res:
                            return _interpret_action(res[k])
                    # fallback: pegar primeiro valor
                    vals = list(res.values())
                    if vals:
                        return _interpret_action(vals[0])
                if isinstance(res, str):
                    try:
                        return _clamp_action(int(res))
                    except Exception:
                        try:
                            return _clamp_action(int(float(res)))
                        except Exception:
                            return None
            except Exception as e:
                logger.debug("DQN interpret error: %s", e, exc_info=True)
            return None

        # ------------------------------
        # Início da inferência
        # ------------------------------
        try:
            state_arr = np.asarray(state)
            state_in = _ensure_2d(state_arr)

            # ---------- 1) Tentar Q-values diretos ----------
            try:
                if hasattr(self, "_q_values") and callable(getattr(self, "_q_values")):
                    norm = state_in
                    normalizer = getattr(self, "normalizer", None)
                    if normalizer is not None:
                        # tenta transform ou normalize sem alterar estado
                        try:
                            if hasattr(normalizer, "transform"):
                                norm = normalizer.transform(state_in.copy())
                            elif hasattr(normalizer, "normalize"):
                                norm = normalizer.normalize(state_in.copy())
                        except Exception:
                            norm = state_in
                    norm = _ensure_2d(norm)
                    qv = np.asarray(self._q_values(norm))
                    if qv.ndim == 2:
                        qv = qv[0]
                    action = _interpret_action(qv)
                    if action is not None:
                        return int(action)
            except Exception as e:
                logger.debug("agent._q_values failed: %s", e, exc_info=True)

            # ---------- 2) Tentar agent.act / agent.predict ----------
            candidates = []
            if hasattr(self, "act") and callable(getattr(self, "act")):
                candidates += [
                    lambda: self.act(state_in),
                    lambda: self.act(state_in, training=False),
                    lambda: self.act(state_in, deterministic=True),
                    lambda: self.act(state_in, explore=False)
                ]
            if hasattr(self, "predict") and callable(getattr(self, "predict")):
                candidates += [
                    lambda: self.predict(state_in),
                    lambda: self.predict(state_in[0])
                ]
            model_obj = getattr(self, "model", None)
            if model_obj is not None and hasattr(model_obj, "predict"):
                candidates += [
                    lambda: model_obj.predict(state_in),
                    lambda: model_obj.predict(state_in[0:1])
                ]

            last_exc = None
            for fn in candidates:
                try:
                    res = fn()
                    action = _interpret_action(res)
                    if action is not None:
                        return int(action)
                except Exception as e:
                    last_exc = e
                    logger.debug("DQN candidate call failed: %s", e, exc_info=True)
                    continue

            # ---------- 3) Última tentativa: flattened ----------
            try:
                if hasattr(self, "act"):
                    flat = state_in.flatten()
                    try:
                        res = self.act(flat)
                    except TypeError:
                        res = self.act(flat, training=False)
                    action = _interpret_action(res)
                    if action is not None:
                        return int(action)
            except Exception:
                pass

            if last_exc is not None:
                logger.debug("act_inference all candidates failed, last error: %s", last_exc, exc_info=True)

        except Exception as e:
            logger.exception("Unexpected error in act_inference: %s", e)

        # fallback absoluto
        return 0

    def predict(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Gera previsão via DQN + validação AIManager.
        Retorno compatível com TradingBot core (produção).
        """
        import numpy as np
        from datetime import datetime, timezone

        # ---------- sanity checks ----------
        if df is None or not isinstance(df, pd.DataFrame) or len(df) < 10:
            return {"result": "hold_or_invalid", "reason": "df_empty_or_too_short"}

        # ensure agent/env ready
        if not getattr(self, "agent", None) or not getattr(self, "env", None):
            try:
                self.prepare(df)
            except Exception:
                pass

        if not getattr(self, "agent", None) or not getattr(self, "env", None):
            return {"result": "hold_or_invalid", "reason": "dqn_not_ready"}

        df = df.copy().reset_index(drop=True)

        if len(df) <= getattr(self, "env").state_size:
            return {"result": "hold_or_invalid", "reason": "insufficient_market_data"}

        # ---------- build temporary env and state ----------
        try:
            temp_env = TradingEnv(
                df=df,
                initial_balance=float(self.config.get("initial_balance", 100.0)) if isinstance(self.config, dict) else float(getattr(self.config, "initial_balance", 100.0)),
                state_size=getattr(self.env, "state_size", 1),
            )
        except Exception:
            # fallback minimal env wrapper (must provide _get_state and current_step)
            temp_env = getattr(self, "env", None)
            if temp_env is None:
                return {"result": "hold_or_invalid", "reason": "cannot_create_temp_env"}

        # set current_step to last available index (safe)
        try:
            temp_env.current_step = min(max(getattr(self.env, "state_size", 1), 0), len(df) - 1)
            # normally we want the last index so model sees latest state:
            temp_env.current_step = len(df) - 1
        except Exception:
            temp_env.current_step = len(df) - 1

        # get state
        try:
            state = temp_env._get_state()
        except Exception as e:
            try:
                # try alternative method name
                state = temp_env.get_state()
            except Exception:
                self.logger and getattr(self, "logger").debug("predict: _get_state failed: %s", e)
                return {"result": "hold_or_invalid", "reason": "state_fetch_failed"}

        if state is None:
            return {"result": "hold_or_invalid", "reason": "state_is_none"}

        try:
            state = np.asarray(state, dtype=np.float32)
        except Exception:
            return {"result": "hold_or_invalid", "reason": "state_cast_failed"}

        if np.any(np.isnan(state)) or np.any(np.isinf(state)):
            return {"result": "hold_or_invalid", "reason": "invalid_state_vector"}

        # ---------- normalize ----------
        try:
            normalizer = getattr(self.agent, "normalizer", None)
            if normalizer and hasattr(normalizer, "normalize"):
                norm_state = normalizer.normalize(state)
            else:
                norm_state = state
        except Exception:
            norm_state = state

        try:
            norm_state = np.asarray(norm_state, dtype=np.float32).reshape(1, -1)
        except Exception:
            return {"result": "hold_or_invalid", "reason": "normalize_shape_failed"}

        # ---------- compute Q-values ----------
        try:
            q_values = None
            framework = getattr(self.agent, "framework", None)
            if framework == "torch":
                import torch as _torch
                with _torch.no_grad():
                    s = _torch.from_numpy(norm_state).to(getattr(self.agent, "device", "cpu"))
                    out = self.agent._q_network(s)
                    try:
                        q_values = out.cpu().numpy()[0]
                    except Exception:
                        q_values = np.asarray(out).reshape(-1)
            elif framework == "keras":
                # keras predict
                q_values = np.asarray(self.agent._q_network.predict(norm_state, verbose=0))[0]
            else:
                # numpy MLP fallback (weights expected on agent)
                z1 = np.dot(norm_state, getattr(self.agent, "w1", np.zeros((norm_state.shape[1], 32)))) + getattr(self.agent, "b1", 0)
                a1 = np.maximum(0, z1)
                q_values = (np.dot(a1, getattr(self.agent, "w2", np.zeros((a1.shape[1], 2)))) + getattr(self.agent, "b2", 0))[0]

            q_values = np.asarray(q_values, dtype=np.float64)
        except Exception as e:
            try:
                getattr(self, "logger").exception("Falha ao calcular Q-values: %s", e)
            except Exception:
                pass
            return {"result": "hold_or_invalid", "reason": "q_value_computation_failed"}

        # ---------- action selection (stable softmax) ----------
        try:
            action_id = int(np.argmax(q_values))
        except Exception:
            action_id = 0

        # stable softmax
        try:
            exp_q = np.exp(q_values - np.max(q_values))
            probs = exp_q / (np.sum(exp_q) + 1e-12)
        except Exception:
            probs = np.ones_like(q_values) / max(1, len(q_values))

        # action mapping robust: support 2 or 3 outputs
        if len(q_values) == 2:
            action_map = {0: "BUY", 1: "SELL"}
        elif len(q_values) >= 3:
            action_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
        else:
            # fallback sequential mapping
            action_map = {i: f"A{i}" for i in range(len(q_values))}

        action = action_map.get(action_id, "HOLD")
        confidence = float(probs[action_id]) if 0 <= action_id < len(probs) else float(np.max(probs))

        prediction = {
            "action": action,
            "confidence": float(confidence),
            "q_values": q_values.tolist(),
            "probabilities": probs.tolist(),
            "action_id": int(action_id),
        }

        # ---------- confidence filter ----------
        min_conf = None
        try:
            if isinstance(self.config, dict):
                min_conf = float(self.config.get("min_confidence", 0.55))
            else:
                min_conf = float(getattr(self.config, "min_confidence", 0.55))
        except Exception:
            min_conf = 0.55

        if action == "HOLD" or confidence < min_conf:
            return {
                "result": "hold_or_invalid",
                "prediction": prediction,
                "reason": "hold_or_low_confidence",
            }

        # ---------- build trade signal ----------
        # safe technical indicator instance + ATR calc
        last_price = None
        try:
            last_price = float(df["close"].iloc[temp_env.current_step])
        except Exception:
            try:
                last_price = float(df["close"].iloc[-1])
            except Exception:
                return {"result": "hold_or_invalid", "reason": "no_price"}

        # attempt to get ATR through TechnicalIndicatorsHardcore, fallback to simple atr
        try:
            tech_ind = TechnicalIndicatorsHardcore()
            atr_series = tech_ind.atr(df)
            atr_val = float(atr_series.iloc[temp_env.current_step])
            if np.isnan(atr_val) or atr_val <= 0:
                raise ValueError("bad atr")
        except Exception:
            try:
                # simple atr fallback: rolling mean of high-low
                if "high" in df.columns and "low" in df.columns:
                    atr_val = float((df["high"] - df["low"]).rolling(window=14, min_periods=1).mean().iloc[-1])
                    if np.isnan(atr_val) or atr_val <= 0:
                        atr_val = max(last_price * 0.001, 0.0001)
                else:
                    atr_val = max(last_price * 0.001, 0.0001)
            except Exception:
                atr_val = max(last_price * 0.001, 0.0001)

        # tp/sl multipliers (config can be dict or object)
        try:
            tp_mult = float(self.config.get("tp_atr_mult", 1.8)) if isinstance(self.config, dict) else float(getattr(self.config, "tp_atr_mult", 1.8))
        except Exception:
            tp_mult = 1.8
        try:
            sl_mult = float(self.config.get("sl_atr_mult", 1.2)) if isinstance(self.config, dict) else float(getattr(self.config, "sl_atr_mult", 1.2))
        except Exception:
            sl_mult = 1.2

        action_upper = str(action).upper() if action is not None else "HOLD"
        if action_upper == "BUY":
            tp = last_price + atr_val * tp_mult
            sl = last_price - atr_val * sl_mult
        elif action_upper == "SELL":
            tp = last_price - atr_val * tp_mult
            sl = last_price + atr_val * sl_mult
        else:
            tp = last_price
            sl = last_price

        # Attempt to construct TradeSignal; if that fails, return a serializable dict
        try:
            try:
                dir_enum = TradeDirection[action_upper]
            except Exception:
                try:
                    dir_enum = TradeDirection(action_upper)
                except Exception:
                    dir_enum = getattr(TradeDirection, "HOLD", None)

            signal_obj = TradeSignal(
                symbol=getattr(self, "symbol", "UNKNOWN"),
                direction=dir_enum,
                order_type=OrderType.MARKET,
                price=float(last_price),
                take_profit=float(tp),
                stop_loss=float(sl),
                confidence=float(confidence),
                timestamp=datetime.now(timezone.utc),
                reason="Deep Q Learning decision",
                meta={
                    "source": "DQN",
                    "action_id": int(action_id),
                    "q_values": q_values.tolist(),
                    "probabilities": probs.tolist(),
                    "atr": float(atr_val),
                    "framework": getattr(getattr(self, "agent", None), "framework", "unknown"),
                },
            )
            signal_serializable = signal_obj.to_dict() if hasattr(signal_obj, "to_dict") else {
                "symbol": getattr(self, "symbol", "UNKNOWN"),
                "direction": str(dir_enum) if dir_enum is not None else action_upper,
                "order_type": str(OrderType.MARKET) if hasattr(OrderType, "__str__") else "MARKET",
                "price": float(last_price),
                "take_profit": float(tp),
                "stop_loss": float(sl),
                "confidence": float(confidence),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "Deep Q Learning decision",
                "meta": {
                    "source": "DQN",
                    "action_id": int(action_id),
                    "q_values": q_values.tolist(),
                    "probabilities": probs.tolist(),
                    "atr": float(atr_val),
                    "framework": getattr(getattr(self, "agent", None), "framework", "unknown"),
                },
            }
        except Exception as e:
            # fallback to dict if TradeSignal constructor fails
            try:
                getattr(self, "logger").warning("TradeSignal object creation failed, returning dict fallback: %s", e)
            except Exception:
                pass
            signal_serializable = {
                "symbol": getattr(self, "symbol", "UNKNOWN"),
                "direction": action_upper,
                "order_type": "MARKET",
                "price": float(last_price),
                "take_profit": float(tp),
                "stop_loss": float(sl),
                "confidence": float(confidence),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "Deep Q Learning decision (fallback)",
                "meta": {
                    "source": "DQN",
                    "action_id": int(action_id),
                    "q_values": q_values.tolist(),
                    "probabilities": probs.tolist(),
                    "atr": float(atr_val),
                    "framework": getattr(getattr(self, "agent", None), "framework", "unknown"),
                },
            }
            signal_obj = None

        # ---------- AI validation (best effort) ----------
        ai_response = None
        try:
            if getattr(self, "ai_manager", None) and hasattr(self.ai_manager, "validate_and_adjust_signal"):
                ai_response = self.ai_manager.validate_and_adjust_signal(signal_serializable, timeout=2.0)
        except Exception as e:
            try:
                getattr(self, "logger").warning("AI validation failed: %s", e)
            except Exception:
                pass
            ai_response = {"ok": False, "error": str(e)}

        return {
            "result": "ok",
            "prediction": prediction,
            "signal": signal_serializable,
            "ai_response": ai_response,
        }


    def save(self, prefix: str):
        if not self.agent:
            return False
        p = os.path.join(self.checkpoint_dir, prefix)
        self.agent.save(p)
        with open(p + "_meta_strategy.json", "w") as f:
            json.dump({"symbol": self.symbol, "timeframe": self.timeframe, "config": self.config}, f)
        return True
    
    def load(self, prefix: str) -> bool:
        p = os.path.join(self.checkpoint_dir, prefix)
        if not os.path.exists(p + "_meta.json") and not os.path.exists(p + "_np_weights.npz"):
            logger.warning("No saved agent found at %s", p)
            return False
        # lazy load; create agent shell if needed
        if not self.agent:
            # need an env to determine sizes; user should prepare first
            logger.warning("Loading weights requires calling prepare(...) first with representative data")
            return False
        return self.agent.load(p)

    def send_signal(self, action_str: str, q_values: List[float]):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(("127.0.0.1", 33058))
                msg = json.dumps({"action": action_str, "q": q_values})
                s.send(msg.encode("utf-8"))
        except Exception as e:
            logger.warning("Falha ao enviar sinal: %s", e)
    
    def _build_signal_from_dqn(
        self,
        pred: Dict[str, Any],
        price: float,
        df: pd.DataFrame
    ) -> Signal:
        direction_map = {
            "BUY": TradeDirection.BUY,
            "SELL": TradeDirection.SELL,
            "HOLD": TradeDirection.HOLD,
        }

        direction = direction_map.get(pred["action"], TradeDirection.HOLD)

        atr = float(df["atr"].iloc[-1]) if "atr" in df.columns else price * 0.001

        if direction == TradeDirection.BUY:
            sl = price - atr * 1.5
            tp = price + atr * 3.0
        elif direction == TradeDirection.SELL:
            sl = price + atr * 1.5
            tp = price - atr * 3.0
        else:
            sl = price
            tp = price

        return Signal(
            uid=uuid.uuid4().hex,
            symbol=self.symbol,
            direction=direction,
            confidence=float(pred.get("confidence", 0.0)),
            entry=price,
            sl=sl,
            tp=tp,
            lot=0.01,
            strategy="DQN",
            reason="Deep Q-Learning prediction",
            source="AI_MODEL",
            timestamp=datetime.now(timezone.utc),
        )



# -------------------------
# Quick test runner (offline simulation)
# -------------------------
def _quick_test():
    # generate synthetic but realistic-ish OHLC data
    import numpy as _np
    import pandas as _pd
    rng = _pd.date_range("2023-01-01", periods=2000, freq="15min")
    _np.random.seed(42)
    p = 1.1000 + _np.cumsum(_np.random.normal(0, 0.0001, len(rng)))
    df = _pd.DataFrame({
        "open": p + _np.random.normal(0, 1e-5, len(rng)),
        "high": p + _np.abs(_np.random.normal(0, 2e-4, len(rng))),
        "low": p - _np.abs(_np.random.normal(0, 2e-4, len(rng))),
        "close": p,
        "volume": _np.random.randint(1000, 5000, len(rng))
    }, index=rng)

    strat = DeepQLearningStrategy(symbol="EURUSD")
    print("Starting quick train (this may take a while)...")
    res = strat.train(df, episodes=10)
    print("Train result:", res)
    pred = strat.predict(df)
    print("Prediction sample:", pred)


if __name__ == "__main__":
    _quick_test()
