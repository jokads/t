# adaptive_ml.py — Adaptive ML Strategy (Hardcore / Production-ready)
from __future__ import annotations

import time
import logging
import json
import math
import threading
from typing import Dict, Any, Optional, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import RandomizedSearchCV
from sklearn.calibration import CalibratedClassifierCV
import joblib

logger = logging.getLogger("AdaptiveMLStrategy")
logger.setLevel(logging.INFO)


class AdaptiveMLStrategy:
    """
    Adaptive Machine Learning Strategy - Production-grade

    Principais responsabilidades:
    - Construir features a partir de OHLCV
    - Treinar um classificador (BUY / HOLD / SELL) com labels adaptativos baseados em ATR
    - Expor API para registrar informações de outras strategies (meta-features)
    - Produzir `signal_intent` compatível com RiskManager/MT5
    """

    NAME = "adaptive_ml"

    def __init__(self, symbol: str, config: Optional[Dict[str, Any]] = None):
        self.symbol = symbol

        default_cfg = {
            "lookback": 300,
            "min_samples": 400,
            "confidence_threshold": 0.60,
            "edge_threshold": 0.0015,
            "retrain_interval": 3600,  # segundos entre re-treinos
            "horizon": 5,  # candles à frente para avaliar label
            "label_atr_mult": 0.5,  # threshold = ATR * label_atr_mult
            "model": dict(
                n_estimators=200,
                max_depth=12,
                min_samples_leaf=4,
                n_jobs=-1,
                random_state=42
            ),
            "use_calibration": True,
            "persistence_path": None,  # caminho para salvar modelo (joblib)
            "enable_hypersearch": False,
            "hypersearch_params": {
                "n_iter": 10,
                "param_distributions": {
                    "n_estimators": [100, 200, 300],
                    "max_depth": [6, 10, 12, 16],
                    "min_samples_leaf": [1, 2, 4, 8],
                }
            }
        }
        self.cfg = {**default_cfg, **(config or {})}

        # modelos e utilitários
        self.model: Optional[RandomForestClassifier] = None
        self.calibrator: Optional[CalibratedClassifierCV] = None
        self.scaler: Optional[StandardScaler] = None
        self.features: List[str] = []
        self.last_train_ts: float = 0.0
        self.is_trained: bool = False
        self._lock = threading.RLock()

        # armazenamento de informações vindas de outras strategies
        # ex: {"supertrend": {"vote":"BUY","conf":0.6}, ...}
        self.strategy_signals: Dict[str, Dict[str, Any]] = {}

        # caches
        self._last_feature_vector: Optional[np.ndarray] = None
        self._last_pred_proba: Optional[np.ndarray] = None

        # tentar carregar modelo se caminho definido
        try:
            if self.cfg["persistence_path"]:
                self._load_model(self.cfg["persistence_path"])
        except Exception as e:
            logger.debug("[%s] no persistence loaded: %s", self.NAME, e)

    # ---------------------------
    # Helpers de indicadores
    # ---------------------------
    @staticmethod
    def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(n).mean()

    @staticmethod
    def _ema(df: pd.DataFrame, span: int) -> pd.Series:
        return df["close"].ewm(span=span, adjust=False).mean()

    # ---------------------------
    # FEATURE ENGINEERING
    # ---------------------------
    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Constrói um DataFrame com features estáveis e previsíveis.
        Mantém índices iguais ao df de entrada e remove NA ao final.
        """
        d = df.copy()
        # basic returns
        d["ret_1"] = d["close"].pct_change(1)
        d["ret_5"] = d["close"].pct_change(5)
        d["logret_1"] = np.log(d["close"] / d["close"].shift(1)).replace([np.inf, -np.inf], 0).fillna(0)

        # vol/variabilidade
        d["vol_20"] = d["ret_1"].rolling(20).std().fillna(method="backfill")
        d["vol_50"] = d["ret_1"].rolling(50).std().fillna(method="backfill")

        # EMAs / trend
        d["ema_12"] = self._ema(d, 12)
        d["ema_26"] = self._ema(d, 26)
        d["ema_diff"] = d["ema_12"] - d["ema_26"]
        d["ema_cross"] = (d["ema_12"] > d["ema_26"]).astype(int)

        # momentum
        d["mom_10"] = d["close"] - d["close"].shift(10)
        d["mom_20"] = d["close"] - d["close"].shift(20)

        # RSI
        delta = d["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        roll_gain = gain.rolling(14).mean()
        roll_loss = loss.rolling(14).mean() + 1e-9
        rs = roll_gain / roll_loss
        d["rsi"] = 100 - (100 / (1 + rs))

        # ATR and normalized returns by ATR
        d["atr14"] = self._atr(d, 14).fillna(method="backfill")
        d["ret_over_atr_1"] = d["ret_1"] / (d["atr14"] / d["close"].replace(0, np.nan))
        d["ret_over_atr_5"] = d["ret_5"] / (d["atr14"] / d["close"].replace(0, np.nan))

        # volume / liquidity proxies if exist
        if "volume" in d.columns:
            d["vol_ratio_20"] = d["volume"] / (d["volume"].rolling(20).mean() + 1e-9)

        # meta-features from other strategies (registered externally)
        # flatten strategy_signals into numeric columns
        for sname, info in self.strategy_signals.items():
            # ex: info={"vote":"BUY","conf":0.6}
            try:
                col_vote = f"meta_{sname}_vote"
                col_conf = f"meta_{sname}_conf"
                vote_val = 0
                if info.get("vote") in ("BUY", "LONG", 1):
                    vote_val = 1
                elif info.get("vote") in ("SELL", "SHORT", -1):
                    vote_val = -1
                # broadcast last value across index
                d[col_vote] = vote_val
                d[col_conf] = float(info.get("conf", 0.0))
            except Exception:
                continue

        # final cleaning
        d = d.replace([np.inf, -np.inf], np.nan)
        d = d.dropna()
        return d

    # ---------------------------
    # LABELS
    # ---------------------------
    def _build_labels(self, df: pd.DataFrame, horizon: Optional[int] = None) -> np.ndarray:
        """
        Gera labels -1/0/+1 usando ATR-based threshold.
        - horizon: quantos candles a frente
        - threshold = atr * cfg["label_atr_mult"]
        """
        h = int(horizon or self.cfg["horizon"])
        atr = self._atr(df, 14)
        future_close = df["close"].shift(-h)
        future_ret = (future_close / df["close"]) - 1.0

        # threshold em termos de percent (uso ATR/price)
        thr = (atr / df["close"]) * float(self.cfg["label_atr_mult"])

        y = np.zeros(len(df), dtype=int)
        y[future_ret > thr] = 1
        y[future_ret < -thr] = -1
        # for last rows where future is NaN, remain 0 (will be dropped later)
        return y

    # ---------------------------
    # TRAIN / PERSIST
    # ---------------------------
    def _should_train(self) -> bool:
        return (time.time() - self.last_train_ts) >= float(self.cfg["retrain_interval"])

    def fit_from_history(self, df: pd.DataFrame, force: bool = False) -> bool:
        """
        Treina / re-treina o modelo com o histórico provido.
        Retorna True se treinou.
        """
        with self._lock:
            try:
                df = df.copy()
                if len(df) < int(self.cfg["min_samples"]):
                    logger.warning("[%s] not enough rows for training: %d", self.NAME, len(df))
                    return False

                if not force and not self._should_train() and self.is_trained:
                    logger.debug("[%s] skipping train (not time yet)", self.NAME)
                    return False

                df_feat = self._build_features(df)
                if len(df_feat) < int(self.cfg["min_samples"]):
                    logger.warning("[%s] after feature build not enough samples: %d", self.NAME, len(df_feat))
                    return False

                y = self._build_labels(df_feat)
                # align and drop rows with labels NaN (last rows)
                df_feat = df_feat.iloc[:-self.cfg["horizon"]] if self.cfg["horizon"] > 0 else df_feat
                y = y[: len(df_feat)]

                # drop rows where label==0 (HOLD) optionally keep for class balance
                # We'll train multiclass (-1,0,1) but may choose to drop HOLD depending on config
                X = df_feat.copy()
                # remove columns that shouldn't train
                for col in ["open", "high", "low", "close", "time"]:
                    if col in X.columns:
                        X = X.drop(columns=[col], errors="ignore")

                # store features names
                self.features = list(X.columns)

                # scale
                self.scaler = StandardScaler()
                X_scaled = self.scaler.fit_transform(X.values)

                # sample weighting: weight by volatility (higher vol -> more weight)
                sample_weight = np.maximum(0.5, (X["vol_20"].values / (np.nanmedian(X["vol_20"].values) + 1e-9)))
                sample_weight = np.nan_to_num(sample_weight, posinf=1.0, neginf=1.0)
                sample_weight = sample_weight.clip(0.1, 5.0)

                # model init
                base_model = RandomForestClassifier(**self.cfg["model"])

                # optional hypersearch (expensive)
                if self.cfg.get("enable_hypersearch", False):
                    params = self.cfg["hypersearch_params"]
                    rs = RandomizedSearchCV(base_model, params["param_distributions"],
                                            n_iter=params.get("n_iter", 10),
                                            n_jobs=-1, cv=3, verbose=0, random_state=42)
                    rs.fit(X_scaled, y, sample_weight=sample_weight)
                    base_model = rs.best_estimator_
                    logger.info("[%s] hypersearch finished, best_params=%s", self.NAME, getattr(rs, "best_params_", {}))

                # fit
                base_model.fit(X_scaled, y, sample_weight=sample_weight)

                # optional calibration for better probabilities
                if self.cfg.get("use_calibration", True):
                    try:
                        cal = CalibratedClassifierCV(base_model, cv=3)
                        cal.fit(X_scaled, y, sample_weight=sample_weight)
                        self.calibrator = cal
                        self.model = cal
                    except Exception:
                        logger.warning("[%s] probability calibration failed — using raw model", self.NAME)
                        self.model = base_model
                else:
                    self.model = base_model

                self.is_trained = True
                self.last_train_ts = time.time()

                # persist if path provided
                if self.cfg.get("persistence_path"):
                    try:
                        self._save_model(self.cfg["persistence_path"])
                    except Exception as e:
                        logger.warning("[%s] failed to persist model: %s", self.NAME, e)

                logger.info("[%s] model trained (samples=%d classes=%s)", self.NAME, len(X_scaled),
                            np.unique(y).tolist())
                return True

            except Exception as e:
                logger.exception("[%s] train failed: %s", self.NAME, e)
                return False

    def _save_model(self, path: str):
        meta = {
            "features": self.features,
            "cfg": self.cfg,
            "last_train_ts": self.last_train_ts
        }
        joblib.dump({"model": self.model, "scaler": self.scaler, "meta": meta}, path)
        logger.info("[%s] model persisted to %s", self.NAME, path)

    def _load_model(self, path: str):
        data = joblib.load(path)
        self.model = data.get("model")
        self.scaler = data.get("scaler")
        meta = data.get("meta", {})
        self.features = meta.get("features", self.features)
        self.last_train_ts = meta.get("last_train_ts", self.last_train_ts)
        self.is_trained = True if self.model is not None else False
        logger.info("[%s] model loaded from %s", self.NAME, path)

    # ---------------------------
    # Strategy integration API
    # ---------------------------
    def register_strategy_info(self, strategy_name: str, info: Dict[str, Any]) -> None:
        """
        Permite que outras strategies registrem votes/confidence/context
        Ex: register_strategy_info('supertrend', {'vote':'BUY','conf':0.6})
        Esses valores serão injetados como meta-features na próxima chamada de build_features.
        """
        with self._lock:
            self.strategy_signals[strategy_name] = info.copy()
            logger.debug("[%s] registered external info from %s: %s", self.NAME, strategy_name, info)

    def clear_registered_strategy_info(self):
        with self._lock:
            self.strategy_signals.clear()

    # ---------------------------
    # PREDICTION / SIGNAL
    # ---------------------------
    def _get_last_feature_vector(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """
        Retorna 2D array (1, n_features) pronto para scaler/model.
        """
        with self._lock:
            df_feat = self._build_features(df)
            if df_feat.empty:
                return None
            X = df_feat[self.features].iloc[-1:].values if set(self.features).issubset(df_feat.columns) else None
            if X is None:
                logger.debug("[%s] feature mismatch: model has %d features but data has %d",
                             self.NAME, len(self.features), len(df_feat.columns))
                return None
            # guard NaN
            if np.isnan(X).any():
                logger.debug("[%s] NaN in last feature row", self.NAME)
                return None
            return X

    def predict_proba(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        with self._lock:
            if not self.is_trained or self.model is None or self.scaler is None:
                logger.debug("[%s] predict_proba skipped — model not trained", self.NAME)
                return None
            X = self._get_last_feature_vector(df)
            if X is None:
                return None
            Xs = self.scaler.transform(X)
            try:
                proba = np.asarray(self.model.predict_proba(Xs))[0]
                self._last_feature_vector = Xs
                self._last_pred_proba = proba
                return proba
            except Exception as e:
                logger.exception("[%s] predict_proba failed: %s", self.NAME, e)
                return None

    def _estimate_tp_sl_from_atr(self, df: pd.DataFrame, side: str) -> Tuple[float, float]:
        """
        Sugere TP/SL (em pips — aproximado) baseado em ATR.
        Retorna (tp_pips, sl_pips) ambos em pips (aprox: price*percent -> pips depende de broker).
        """
        try:
            atr = float(self._atr(df, 14).iloc[-1])
            price = float(df["close"].iloc[-1])
            # usar multipliers conservadores
            sl_price_dist = atr * 1.0
            tp_price_dist = atr * 1.5
            if side == "SELL":
                sl = price + sl_price_dist
                tp = price - tp_price_dist
            else:
                sl = price - sl_price_dist
                tp = price + tp_price_dist
            # Convert to pips approximation using price decimal (not exact, broker-dep)
            # We'll return price differences (absolute) — RiskManager / MT5 should convert to pips properly.
            sl_pips = abs(sl - price)
            tp_pips = abs(tp - price)
            return float(round(tp_pips, 6)), float(round(sl_pips, 6))
        except Exception:
            return 0.0, 0.0

    def generate(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Gera signal_intent dict:
        {
            "symbol": self.symbol,
            "side": "BUY"/"SELL",
            "confidence": 0.0-1.0,
            "edge": float,
            "strategy": self.NAME,
            "context": {...},
            "tp_pips": float,
            "sl_pips": float,
            "risk": fraction_of_balance (suggested)
        }
        """
        try:
            if df is None or len(df) < int(self.cfg["lookback"]):
                logger.debug("[%s] insufficient history for generate", self.NAME)
                return None

            # ensure trained
            if not self.is_trained or self._should_train():
                trained = self.fit_from_history(df)
                if not trained and not self.is_trained:
                    return None

            proba = self.predict_proba(df)
            if proba is None:
                return None

            # model.classes_ should give labels (-1,0,1) — but confirm
            classes = getattr(self.model, "classes_", np.array([0, 1, -1]))
            best_idx = int(np.argmax(proba))
            best_label = classes[best_idx] if len(classes) > best_idx else None
            conf = float(np.max(proba))
            edge = self._estimate_edge(proba)

            # filter by thresholds
            if conf < float(self.cfg["confidence_threshold"]) or edge < float(self.cfg["edge_threshold"]):
                logger.debug("[%s] low confidence/edge conf=%.3f edge=%.6f", self.NAME, conf, edge)
                return None

            side = "BUY" if best_label == 1 else "SELL" if best_label == -1 else None
            if side is None:
                return None

            # gather context info for logging / risk manager
            ctx = {}
            last_row = df.iloc[-1]
            ctx["close"] = float(last_row["close"])
            ctx["vol_20"] = float(last_row.get("vol_20", np.nan))
            ctx["rsi"] = float(last_row.get("rsi", np.nan))
            ctx["ema_diff"] = float(last_row.get("ema_diff", np.nan))

            tp_pips, sl_pips = self._estimate_tp_sl_from_atr(df, side)

            signal_intent = {
                "symbol": self.symbol,
                "side": side,
                "confidence": round(conf, 4),
                "edge": round(edge, 6),
                "strategy": self.NAME,
                "context": ctx,
                "tp_pips": float(round(tp_pips, 6)),
                "sl_pips": float(round(sl_pips, 6)),
                "risk": 0.01  # sugestão padrão 1% — RiskManager pode ajustar
            }

            logger.info("[%s] generated signal: %s", self.NAME, signal_intent)
            return signal_intent

        except Exception as e:
            logger.exception("[%s] generate failed: %s", self.NAME, e)
            return None

    # ---------------------------
    # UTILIDADES / EXPLAINABILITY
    # ---------------------------
    def _estimate_edge(self, proba: np.ndarray) -> float:
        # edge = prob(best) - mean(random)
        if proba is None or len(proba) == 0:
            return 0.0
        return float(np.max(proba) - (1.0 / len(proba)))

    def get_feature_importances(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """
        Retorna lista (feature,importance) ordenada.
        """
        with self._lock:
            if not self.is_trained or self.model is None:
                return []
            try:
                # se calibrator envolvido, extrair estimator_
                est = getattr(self.model, "estimator", None) or getattr(self.model, "base_estimator", None) or self.model
                importances = getattr(est, "feature_importances_", None)
                if importances is None:
                    return []
                feats = list(self.features)
                pairs = sorted(zip(feats, importances), key=lambda x: x[1], reverse=True)
                return pairs[:top_n]
            except Exception:
                return []

    def explain_last_prediction(self) -> Dict[str, Any]:
        """
        Retorna proba e contribuições aproximadas (feature importances * feature value)
        Não é uma explicação SHAP real, mas dá intuição.
        """
        with self._lock:
            if self._last_feature_vector is None or self._last_pred_proba is None or not self.features:
                return {}
            try:
                fi = dict(self.get_feature_importances(top_n=len(self.features)))
                fv = self._last_feature_vector.flatten()
                approx = {}
                for i, name in enumerate(self.features):
                    approx[name] = float(fv[i] * fi.get(name, 0.0))
                return {
                    "proba": self._last_pred_proba.tolist(),
                    "feature_contrib": approx
                }
            except Exception as e:
                logger.debug("[%s] explain failed: %s", self.NAME, e)
                return {}

