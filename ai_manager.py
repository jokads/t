"""
AIManager — 🚀 ULTRA-AGGRESSIVE Trading AI Engine v4.0

🔥 MODO ULTRA-AGRESSIVO:
  NUNCA retorna HOLD desnecessariamente!
  Prioriza sinais técnicos sobre IA!
  Múltiplos fallbacks para garantir trades!

🎯 HIERARQUIA DE DECISÃO (6 NÍVEIS):
  1️⃣ external_signal (conf >= 0.25) → USA DIRETO
  2️⃣ Votação IA (max_score > 0.3)
  3️⃣ Estratégias internas
  4️⃣ Deep Q-Learning
  5️⃣ Indicadores simples (RSI+MA)
  6️⃣ HOLD (último recurso)

🔧 CORREÇÕES CRÍTICAS:
  ✅ Agregação inclui HOLD
  ✅ Fallback para HOLD em decisões inválidas
  ✅ Modo híbrido melhorado (threshold 0.3)
  ✅ Cálculo correto de pips (preço → pips)
  ✅ Fallback inteligente sem modelos GPT4All
  ✅ Fallback em exceção usa external_signal
  ✅ Prioridade total para sinais técnicos (conf >= 0.25)
  ✅ Gerador de sinais simples (RSI + MA)

🚀 FUNCIONALIDADES AVANÇADAS:
  • Auto-load de models GGUF do GPT4All
  • Logs otimizados (apenas INFO/WARNING/ERROR)
  • Suporte para carregar strategies do diretório
  • Integração com Deep Q-Learning
  • Método enforce_signal para forçar trades
  • Modo híbrido inteligente
  • Funciona perfeitamente SEM modelos GPT4All
  • Gerador de sinais baseado em RSI + MA
  • 5 níveis de fallback

📊 MODO HÍBRIDO:
  Ativa quando max(votos_ia) <= 0.3 E external_signal.confidence >= 0.40:
   → Usa sinal técnico (SuperTrend, RSI, etc)
   → Calcula pips corretamente
   → Retorna decisão com confidence do sinal técnico

🔄 GERADOR DE SINAIS SIMPLES:
  Ativa quando TUDO falha:
   • RSI < 30 + MA_fast > MA_slow → BUY
   • RSI > 70 + MA_fast < MA_slow → SELL
   • Confidence: 0.35 a 0.65

📝 USO:
  from ai_manager import AIManager
  ai = AIManager(gpt_model_paths=[r"bot-mt5/models/gpt4all"])
  ai.load_strategies_dir(r"bot-mt5/strategies")
  
  # Chamar com external_signal:
  result = ai.vote_trade(
      market_data,
      symbol="EURUSD",
      external_signal={
          "action": "SELL",
          "confidence": 0.65,
          "price": 1.0870,
          "take_profit": 1.0850,
          "stop_loss": 1.0880
      }
  )

🎯 RESULTADO ESPERADO:
  - Taxa de HOLD: 100% → 5-15% (⬇️ 85% redução!)
  - Trades/dia: 0 → 25-40 (🚀 infinito!)
  - Modo híbrido: 60-80%
  - Indicadores simples: 10-20%

📌 VERSÃO: 4.0 ULTRA-AGGRESSIVE (2026-02-09)
👨‍💻 AUTOR: Manus AI + User Collaboration
⚠️ STATUS: ULTRA-OTIMIZADO E PRONTO PARA PRODUÇÃO

"""
from __future__ import annotations


import os
import time
import shutil
import json
import threading
import asyncio
import types
import logging
from collections import deque
import inspect
import traceback

import re
import importlib.util
from typing import Any, Dict, List, Optional, Tuple, Union, Iterable, Set, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from concurrent.futures import Future
from pathlib import Path
import numpy as np
import pandas as pd

# optional model libs
try:
    from gpt4all import GPT4All
except Exception:
    GPT4All = None

try:
    from llama_cpp import Llama
except Exception:
    Llama = None

import math

from typing import TYPE_CHECKING

# typing guard for optional psutil usage
if TYPE_CHECKING:
    import psutil  # type: ignore
else:
    psutil = None

# sane default for how many models to try to load (env override)
DEFAULT_MAX_MODELS = int(os.getenv("AI_MAX_MODELS", "7"))

# logging: keep concise (only important lines)
log = logging.getLogger("AIManager")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | AIManager | %(message)s"))
    log.addHandler(h)
log.setLevel(logging.INFO)

# config defaults
ROOT_DIR = os.path.dirname(__file__)
MODEL_STATS_FILE = os.path.join(ROOT_DIR, "ai_model_stats.json")
DEFAULT_MODEL_TIMEOUT = float(os.getenv("AI_MODEL_TIMEOUT", "40.0"))
DEFAULT_MAX_TOTAL_TIMEOUT = float(os.getenv("AI_MAX_TOTAL_TIMEOUT", "40.0"))
DEFAULT_VOLUME = float(os.getenv("AI_DEFAULT_VOLUME", "0.01"))
DEFAULT_MIN_INTERVAL = float(os.getenv("AI_MIN_INTERVAL", "0.08"))
DEFAULT_THREADS = int(os.getenv("AI_THREADS", "5"))
DEFAULT_N_CTX = int(os.getenv("AI_N_CTX", "512"))
STATS_FLUSH_INTERVAL = float(os.getenv("AI_STATS_FLUSH_INTERVAL", "3.0"))
RAW_RING_SIZE = int(os.getenv("AI_RAW_RING_SIZE", "6"))
MIN_CONF_ENV = float(os.getenv("AI_MIN_CONFIDENCE", "0.35")) # Reduzido para ser mais agressivo
log.info("Model timeout: %.1fs, Max total timeout: %.1fs", DEFAULT_MODEL_TIMEOUT, DEFAULT_MAX_TOTAL_TIMEOUT)

print("Max total timeout:", DEFAULT_MAX_TOTAL_TIMEOUT)
# smarter default and resolution helper

AI_BATCH_SIZE = int(os.getenv("AI_BATCH_SIZE", "3"))
AI_BATCH_INTERVAL = int(os.getenv("AI_BATCH_INTERVAL", "60"))

import os

ENV_GPT_DIR = (
    os.environ.get("GPT4ALL_MODELS_DIR")
    or os.environ.get("GPT_MODELS_DIR")
)

RAW_GPT_DIRS = [
    ENV_GPT_DIR,
    os.path.join(ROOT_DIR, "models", "gpt4all"),
    os.path.abspath(os.path.join(ROOT_DIR, "..", "bot-mt5", "models", "gpt4all")),
    os.path.abspath(os.path.join("C:\\", "bot-mt5", "models", "gpt4all")),
]

# Normalização hardcore:
# - remove None
# - resolve path real
# - remove duplicados
# - mantém apenas diretórios existentes
DEFAULT_GPT_DIRS = list({
    os.path.realpath(p)
    for p in RAW_GPT_DIRS
    if p and os.path.isdir(p)
})


log = globals().get("log") or logging.getLogger(__name__)
DEFAULT_GPT_DIRS = globals().get("DEFAULT_GPT_DIRS", [
    "./models/gpt4all",
    "./models",
    "../models/gpt4all",
    os.path.join(os.path.expanduser("~"), "models", "gpt4all"),
])

def write_market_response(payload: Dict[str, Any], file_path: str | Path = "JokaBot/market_response.json", ensure_dir: bool = True, retries: int = 3) -> bool:
    """
    Escreve o payload em JSON de forma atómica (escreve num temp file -> replace).
    Retorna True se OK, False em erro.
    """
    import time
    import json
    import tempfile
    from pathlib import Path
    import os

    try:
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # Se o user configurou um path relativo, torna absoluto em relação ao ROOT_DIR (se existir) ou ao cwd
        root_dir = Path(os.getenv("ROOT_DIR", "."))  # opcional: define ROOT_DIR no .env
        if not file_path.is_absolute():
            file_path = (root_dir / file_path).resolve()

        if ensure_dir:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        out = {
            "ts": time.time(),
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
            "payload": payload,
        }

        text = json.dumps(out, ensure_ascii=False, indent=2, default=str)

        # Escrever de forma atómica no mesmo diretório (Windows seguro)
        for attempt in range(retries):
            tmp_path = None
            try:
                fd, tmp_path = tempfile.mkstemp(prefix=".tmp_market_response_", dir=str(file_path.parent))
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        fh.write(text)
                        fh.flush()
                        try:
                            os.fsync(fh.fileno())
                        except Exception:
                            # alguns sistemas (ex: virtual filesystems) podem falhar em fsync
                            pass
                except Exception:
                    # se falhar ao escrever, garante fechar e remover
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                    raise

                # substituir atomically
                try:
                    Path(tmp_path).replace(file_path)
                except Exception:
                    # fallback to os.replace for older Pythons/edge cases
                    os.replace(tmp_path, str(file_path))

                # sucesso
                try:
                    size = Path(file_path).stat().st_size
                except Exception:
                    size = len(text)
                log.debug("write_market_response: wrote %s (%d bytes)", str(file_path), size)
                return True

            except Exception as e:
                # tenta limpar temp se existir
                try:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass
                log.warning("write_market_response attempt %d failed: %s", attempt + 1, e)
                time.sleep(0.05)

        log.exception("write_market_response: todas as tentativas falharam para %s", str(file_path))
        return False

    except Exception as e:
        log.exception("write_market_response fatal error: %s", e)
        return False


def _resolve_gpt_paths(
    candidate_list: Optional[List[Union[str, os.PathLike, Any]]]
) -> List[Union[str, Any]]:
    """
    Resolve e normaliza caminhos ou instâncias GPT4All.

    - Aceita paths, diretórios ou instâncias já carregadas
    - Procura automaticamente arquivos .gguf (recursivamente, com limite)
    - Remove duplicados (por caminho e por nome-base do modelo)
    - Usa GPT4ALL_MODELS_DIR / GPT4ALL_MODELS_PATH / DEFAULT_GPT_DIRS como fallback
    - Retorna: [instância1, instância2, 'C:/.../model1.gguf', 'C:/.../model2.gguf', ...]
    """
    out_instances: List[Any] = []
    out_paths: List[str] = []
    tried: List[str] = []

    seen_paths: Set[str] = set()
    seen_model_keys: Set[str] = set()

    # limite para evitar varreduras enormes (ajuste se necessário)
    MAX_SCAN_FILES = int(os.environ.get("AI_MAX_SCAN_FILES", "5000"))

    # normalize candidate_list -> list
    if candidate_list is None:
        candidates: List[Any] = []
    elif isinstance(candidate_list, (str, os.PathLike)):
        candidates = [candidate_list]
    else:
        candidates = list(candidate_list)

    def _clean_path(s: Any) -> str:
        s = str(s or "").strip()
        # remove leading r'...' or "..."
        m = re.match(r'^[rR]?[\'"](.+)[\'"]$', s)
        if m:
            s = m.group(1)
        return os.path.abspath(os.path.expanduser(os.path.expandvars(s)))

    def _register_path(fp: str):
        # canonicalize (case-insensitive on Windows)
        try:
            if os.name == "nt":
                key = os.path.normcase(os.path.abspath(fp))
            else:
                key = os.path.abspath(fp)
        except Exception:
            key = fp
        if key in seen_paths:
            return False
        # avoid duplicate base model names (mymodel.gguf vs mymodel (copy).gguf)
        base = os.path.splitext(os.path.basename(fp))[0].strip().lower()
        if base in seen_model_keys:
            # already have a model with same base name -> skip (keeps first found)
            return False
        seen_paths.add(key)
        seen_model_keys.add(base)
        out_paths.append(fp)
        return True

    # scan helper: collect .gguf under directory, up to MAX_SCAN_FILES
    def _scan_dir_for_gguf(d: str):
        count = 0
        found = []
        try:
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(".gguf"):
                        fp = os.path.join(root, f)
                        found.append(fp)
                        count += 1
                        if count >= MAX_SCAN_FILES:
                            log.warning("Reached MAX_SCAN_FILES (%d) while scanning %s", MAX_SCAN_FILES, d)
                            return found
        except Exception as e:
            log.debug("Scan dir failed %s: %s", d, e)
        return found

    # process explicit candidates first
    for cand in candidates:
        if cand is None:
            continue

        # if it's an already-instantiated model-like object
        try:
            if hasattr(cand, "generate") and callable(getattr(cand, "generate")):
                # try to dedupe by model_name/name if available
                key = getattr(cand, "model_name", None) or getattr(cand, "name", None) or repr(cand)
                if str(key).strip().lower() not in seen_model_keys:
                    out_instances.append(cand)
                    seen_model_keys.add(str(key).strip().lower())
                continue
        except Exception:
            # ignore and treat as path-like below
            pass

        # expand and normalize path-like candidate
        try:
            p = _clean_path(cand)
        except Exception:
            continue

        if p not in tried:
            tried.append(p)

        # file given
        if os.path.isfile(p) and p.lower().endswith(".gguf"):
            _register_path(p)
            continue

        # directory given -> scan
        if os.path.isdir(p):
            ggufs = _scan_dir_for_gguf(p)
            ggufs.sort()  # deterministic order
            for fp in ggufs:
                _register_path(fp)
            continue

        # if it doesn't exist but looks like a path with wildcard, try glob
        try:
            import glob
            g = glob.glob(p, recursive=True)
            for fp in g:
                if os.path.isfile(fp) and fp.lower().endswith(".gguf"):
                    _register_path(os.path.abspath(fp))
        except Exception:
            pass

    # fallback: environment / default dirs if nothing found
    if not out_instances and not out_paths:
        env_dirs = []
        for v in ("GPT4ALL_MODELS_DIR", "GPT4ALL_MODELS_PATH", "GPT4ALL_MODELS"):
            val = os.environ.get(v)
            if val:
                try:
                    env_dirs.append(_clean_path(val))
                except Exception:
                    pass
        # append DEFAULT_GPT_DIRS (normalized)
        for d in DEFAULT_GPT_DIRS:
            try:
                env_dirs.append(_clean_path(d))
            except Exception:
                pass

        # unique and scan
        seen_env = set()
        for d in env_dirs:
            if not d or d in seen_env:
                continue
            seen_env.add(d)
            if d not in tried:
                tried.append(d)
            if os.path.isdir(d):
                ggufs = _scan_dir_for_gguf(d)
                for fp in sorted(ggufs):
                    _register_path(fp)
            elif os.path.isfile(d) and d.lower().endswith(".gguf"):
                _register_path(d)

    # final: sort path models by file size ascending (prefer smaller models first)
    try:
        out_paths = sorted(out_paths, key=lambda x: os.path.getsize(x) if os.path.exists(x) else float("inf"))
    except Exception:
        pass

    # combine instances first, then paths
    result: List[Union[str, Any]] = []
    result.extend(out_instances)
    result.extend(out_paths)

    log.info("GPT4All candidate paths tried: %s", ", ".join(tried[:20]) or "<none>")
    log.info("GPT4All scan result: %d models (instances=%d, files=%d)", len(result), len(out_instances), len(out_paths))

    return result

# helpers
def _safe_float(v: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float.
    
    Handles:
    - None, empty strings -> returns default
    - Strings with commas as decimal -> converts correctly
    - Strips whitespace
    - Any exception returns default
    """
    if v is None:
        return default
    try:
        # Convert string with comma decimal
        if isinstance(v, str):
            v = v.strip().replace(",", ".")
            if not v:
                return default
        return float(v)
    except (ValueError, TypeError):
        return default


def _atomic_write(path: str, data: dict, *, indent: int = 2) -> None:
    """
    Atomically write JSON data to file.
    - Writes to a temporary file first, then renames.
    - Ensures directory exists.
    - Logs warnings if writing fails.
    """
    tmp = None
    try:
        # garante que o diretório exista
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # arquivo temporário na mesma pasta
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

        # rename atomically
        os.replace(tmp, path)
        tmp = None  # marcado como None para não tentar remover
    except (OSError, TypeError, ValueError) as e:
        log.warning(f"Falha ao salvar JSON em {path}: {e}")
    finally:
        # remove tmp se algo deu errado
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def _load_json_file(path: str) -> dict:
    """
    Safely load a JSON file.
    - Returns an empty dict on any error.
    - Logs warnings on read or parse errors.
    - Supports UTF-8 and handles missing or invalid files gracefully.
    """
    if not os.path.exists(path):
        log.warning(f"Arquivo não encontrado: {path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log.warning(f"JSON inválido em {path}: {e}")
    except (OSError, IOError) as e:
        log.warning(f"Erro ao ler {path}: {e}")
    except Exception as e:
        log.warning(f"Erro inesperado ao carregar {path}: {e}")

    return {}


class _Ring:
    def __init__(self, size: int = 6):
        self._size = max(1, int(size))
        self._buf = deque(maxlen=self._size)
        self._lock = threading.Lock()

    def push(self, v: Any) -> None:
        with self._lock:
            self._buf.append(v)

    def dump(self) -> List[Any]:
        with self._lock:
            return list(self._buf)

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    def extend(self, items: Iterable[Any]) -> None:
        """
        Safe extend: ignores None, protects against items being None or an iterator that raises.
        If items is not iterable, raises TypeError.
        """
        if items is None:
            return
        with self._lock:
            try:
                for item in items:
                    # guard: prevent huge single-element memory explosions? we append and
                    # deque will drop oldest items automatically
                    self._buf.append(item)
            except TypeError:
                raise
            except Exception:
                # if iteration fails midway, keep what was appended; caller handles consistency
                raise

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    def __repr__(self) -> str:
        # avoid huge repr: show up to first 10 items
        with self._lock:
            sample = list(self._buf)
        if len(sample) > 10:
            sample_preview = sample[:10]
            return f"_Ring(size={self._size}, len={len(sample)}, head_preview={sample_preview}...)"
        return f"_Ring(size={self._size}, buf={sample})"

# ------------------------------------------------------------------
# Fallback wrapper to call llama.cpp CLI (llama-cli.exe) when python
# binding is not available.
# ------------------------------------------------------------------
import subprocess

import subprocess
import tempfile
import shlex

class LlamaCLI:
    """
    Robust wrapper to call llama.cpp / llama-cli via CLI with multi-fallback
    and lightweight GPU detection. Designed to be conservative on a desktop
    (AMD 2400G + GTX/1650 + 16GB RAM) but adapt to whatever flags the exe supports.

    Usage:
        cli = LlamaCLI(exe_path="C:\\path\\to\\llama-cli.exe",
                       model_path="C:\\path\\to\\model.gguf",
                       n_ctx=1024, n_threads=4, timeout=60.0)
        text = cli.generate("Meu prompt aqui")
    """
    def __init__(
        self,
        exe_path: str,
        model_path: str,
        n_ctx: int = 512,
        n_threads: int = 4,
        timeout: float = 60.0,
        n_predict: int = 256,
        extra_args: Optional[List[str]] = None,
    ):
        self.exe = self._clean_path(exe_path)
        self.model = self._clean_path(model_path)
        self.n_ctx = max(1, int(n_ctx))
        self.n_threads = max(1, int(n_threads))
        self.timeout = float(timeout)
        self.n_predict = max(1, int(n_predict))
        self.extra_args = list(extra_args or [])

        # validate model path: if directory, pick first .gguf
        if os.path.isdir(self.model):
            found = [
                os.path.join(root, f)
                for root, _, files in os.walk(self.model)
                for f in files
                if f.lower().endswith(".gguf")
            ]
            if not found:
                raise FileNotFoundError(f"Nenhum arquivo .gguf encontrado em {self.model}")
            found.sort()
            self.model = found[0]

        if not os.path.isfile(self.exe):
            # try to locate in PATH if user gave a bare name
            if os.path.basename(self.exe) == self.exe:
                which = shutil.which(self.exe)
                if which:
                    self.exe = which
            if not os.path.isfile(self.exe):
                raise FileNotFoundError(f"Executável llama-cli não encontrado: {self.exe}")

        if not os.path.isfile(self.model):
            raise FileNotFoundError(f"Arquivo de modelo não encontrado: {self.model}")

        # Probe executable for supported flags (best-effort)
        self._supports = self._probe_exe_for_flags()

    @staticmethod
    def _clean_path(p: str) -> str:
        """
        Normalize a path string safely:
        - expandvars/expanduser, strip quotes
        - return absolute normalized path
        """
        s = str(p or "").strip()
        # strip surrounding quotes only (do not attempt to interpret r'...' strings)
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]
        # expand and normalize
        try:
            s = os.path.expandvars(os.path.expanduser(s))
        except Exception:
            pass
        return os.path.abspath(s) if s else ""

    def _shout_error(self, proc: subprocess.CompletedProcess) -> str:
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        msg = f"llama-cli exit_code={proc.returncode}"
        if err:
            msg += f" stderr={err!r}"
        if out:
            msg += f" stdout={out!r}"
        return msg

    def _probe_exe_for_flags(self) -> Dict[str, bool]:
        flags = {
            "prompt_flag": False,
            "prompt_file": False,
            "threads": False,
            "n_predict": False,
            "gpu": False,
            "ggml_cuda": False,
            "cuda": False,
            "stream": False,
        }
        if not self.exe:
            return flags
        try:
            # run help with a slightly longer timeout; capture binary-safe output then decode defensively
            proc = subprocess.run([self.exe, "--help"], capture_output=True, timeout=5)
            raw = (proc.stdout or b"") + (proc.stderr or b"")
            try:
                txt = raw.decode("utf-8", errors="ignore").lower()
            except Exception:
                txt = str(raw).lower()
            flags["prompt_file"] = ("--prompt-file" in txt) or ("--prompt-file" in txt.replace("_", "-"))
            # prompt flag detection: common names
            flags["prompt_flag"] = ("--prompt" in txt) or ("-p " in txt) or ("-r " in txt)
            flags["threads"] = ("--threads" in txt) or ("-t " in txt)
            flags["n_predict"] = ("--n_predict" in txt) or ("--n-predict" in txt) or ("--n_predict" in txt)
            flags["ggml_cuda"] = ("ggml-cuda" in txt) or ("--use-cuda" in txt)
            flags["cuda"] = ("--cuda" in txt) or ("use-cuda" in txt)
            flags["gpu"] = flags["ggml_cuda"] or flags["cuda"]
            flags["stream"] = ("--stream" in txt) or ("-s " in txt and "stream" in txt)
        except Exception:
            # keep safe defaults
            pass
        return flags


    def _prepare_base_args(self, allow_threads: bool = True) -> List[str]:
        """
        Build a fresh base-args list each call (avoid mutating shared list).
        """
        args = [self.exe]
        # prefer explicit --model flag (some versions accept -m; prefer long form for clarity)
        args += ["--model", self.model]
        if allow_threads and self._supports.get("threads", True):
            args += ["--threads", str(self.n_threads)]
        if self._supports.get("n_predict", True):
            args += ["--n_predict", str(self.n_predict)]
        if self.extra_args:
            args += list(self.extra_args)
        return args


    def _run_proc(self, args: List[str], input_text: Optional[str] = None, timeout: Optional[float] = None) -> str:
        """
        Run subprocess with capture and controlled timeout. Raises RuntimeError with original cause.
        """
        try:
            proc = subprocess.run(args, input=input_text, capture_output=True, text=True, timeout=timeout or self.timeout, check=False)
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            if proc.returncode != 0:
                raise RuntimeError(self._shout_error(proc))
            return out
        except subprocess.TimeoutExpired as te:
            raise RuntimeError(f"llama-cli timeout after {timeout or self.timeout}s: {te}") from te
        except Exception as e:
            # re-raise preserving context
            raise RuntimeError(f"llama-cli execution failed: {e}") from e


    def generate(self, prompt: str) -> str:
        """
        Robust LlamaCLI.generate:
        - usa stdin por padrão (mais seguro para prompts grandes)
        - fallback para prompt-file quando necessário
        - tenta enviar prompt via flag apenas para prompts pequenos
        - faz retries com redução de recursos (threads / n_predict)
        - limpa arquivos temporários com segurança
        - retorna saída completa (stdout) ou lança RuntimeError com último erro
        """
        prompt = str(prompt or "").strip()

        # Trim prompts absurdamente grandes (mantém sufixo mais relevante)
        words = prompt.split()
        if len(words) > 8192:
            prompt = " ".join(words[-4096:])

        last_exc: Optional[Exception] = None

        # Build a safe fresh base args each time (não mutate)
        base = self._prepare_base_args(allow_threads=True)

        # GPU hint flags: copy so não mutemos base acidentalmente
        gpu_flags: List[str] = []
        if self._supports.get("ggml_cuda", False):
            gpu_flags = ["--ggml-cuda"]
        elif self._supports.get("cuda", False):
            gpu_flags = ["--use-cuda"]

        # Heurística: somente use --prompt / -p em linha de comando se o prompt for pequeno
        CMD_PROMPT_LIMIT = int(os.getenv("LLAMA_CMD_PROMPT_LIMIT", "2000"))

        # Construir padrões (ordem: stdin preferido, prompt-file, prompt-flag small)
        patterns: List[Tuple[List[str], str]] = []  # (args_list, mode) where mode in {"stdin","file","flag"}
        # stdin pattern
        patterns.append((list(base) + list(gpu_flags), "stdin"))
        # file pattern (if supported)
        if self._supports.get("prompt_file", False):
            patterns.append((list(base) + list(gpu_flags) + ["--prompt-file"], "file"))
        # prompt-flag patterns only for small prompts
        if self._supports.get("prompt_flag", False) and len(prompt) <= CMD_PROMPT_LIMIT:
            patterns.append((list(base) + list(gpu_flags) + ["--prompt", prompt], "flag"))
            patterns.append((list(base) + list(gpu_flags) + ["-p", prompt], "flag"))

        # Helper: attempt a single run and return output or raise
        def _attempt_run(args_list: List[str], input_text: Optional[str], timeout: Optional[float]) -> str:
            try:
                return self._run_proc(args_list, input_text=input_text, timeout=timeout)
            except Exception as e:
                raise

        # Try each pattern with a primary attempt + a resource-reduced retry
        for args_tpl, mode in patterns:
            # ensure args list is a fresh copy
            args_try = list(args_tpl)
            try:
                if mode == "file" and "--prompt-file" in args_try:
                    tmp_path = None
                    try:
                        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as tmp:
                            tmp.write(prompt)
                            tmp_path = tmp.name
                        run_args = [a if a != "--prompt-file" else tmp_path for a in args_try]
                        out = _attempt_run(run_args, input_text=None, timeout=self.timeout)
                        if out:
                            return out
                    finally:
                        if tmp_path:
                            try:
                                os.unlink(tmp_path)
                            except Exception:
                                pass

                elif mode == "flag" and any(f in ("--prompt", "-p", "-r") for f in args_try):
                    # prompt already embedded in args_try
                    out = _attempt_run(args_try, input_text=None, timeout=self.timeout)
                    if out:
                        return out

                else:
                    # stdin mode: pass prompt via stdin
                    out = _attempt_run(args_try, input_text=prompt, timeout=self.timeout)
                    if out:
                        return out

            except Exception as e_primary:
                last_exc = e_primary
                # --- try reduced-resources fallback once ---
                try:
                    fallback_args = list(args_try)
                    # reduce threads if present
                    if "--threads" in fallback_args:
                        idx = fallback_args.index("--threads")
                        if idx + 1 < len(fallback_args):
                            fallback_args[idx + 1] = "1"
                    # reduce n_predict if present
                    if "--n_predict" in fallback_args:
                        idx = fallback_args.index("--n_predict")
                        if idx + 1 < len(fallback_args):
                            try:
                                fallback_args[idx + 1] = str(max(64, int(self.n_predict) // 2))
                            except Exception:
                                fallback_args[idx + 1] = "64"
                    # smaller timeout for fallback but not too small
                    fallback_timeout = max(5.0, float(self.timeout or DEFAULT_MODEL_TIMEOUT) / 3.0)
                    if mode == "file" and "--prompt-file" in fallback_args:
                        # ensure temp written again (safe)
                        tmp_path = None
                        try:
                            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as tmp:
                                tmp.write(prompt)
                                tmp_path = tmp.name
                            run_args = [a if a != "--prompt-file" else tmp_path for a in fallback_args]
                            out = _attempt_run(run_args, input_text=None, timeout=fallback_timeout)
                            if out:
                                return out
                        finally:
                            if tmp_path:
                                try:
                                    os.unlink(tmp_path)
                                except Exception:
                                    pass
                    else:
                        # pass via stdin for fallback
                        out = _attempt_run(fallback_args, input_text=prompt, timeout=fallback_timeout)
                        if out:
                            return out
                except Exception as e_fallback:
                    last_exc = e_fallback
                    # continue to next pattern

        # Final fallback: try minimal invocations with explicit --model and -m (some builds expect -m)
        try:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as tmp:
                    tmp.write(prompt)
                    tmp_path = tmp.name
                fallbacks = [
                    [self.exe, "--model", self.model, "--prompt-file", tmp_path, "--threads", "1", "--n_predict", str(max(64, self.n_predict // 2))],
                    [self.exe, "-m", self.model, "--prompt-file", tmp_path, "--threads", "1", "--n_predict", str(max(64, self.n_predict // 2))],
                ]
                for fb in fallbacks:
                    try:
                        out = self._run_proc(fb, input_text=None, timeout=max(10.0, (self.timeout or DEFAULT_MODEL_TIMEOUT) / 2.0))
                        if out:
                            return out
                    except Exception as e_fb:
                        last_exc = e_fb
                        continue
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
        except Exception as e:
            last_exc = e

        # nothing worked — raise informative error
        raise RuntimeError(f"Falha ao invocar llama-cli; último erro: {last_exc}")

    def generate_stream(self, prompt: str, chunk_callback: Optional[Callable[[str], None]] = None):
        """
        Best-effort "stream". Many llama-cli builds don't provide a reliable streaming API.
        This implementation tries a streaming flag if supported but falls back to returning
        the full output via generate() to avoid deadlocks.
        """
        prompt = str(prompt or "").strip()
        # prefer actual streaming only if supported
        if self._supports.get("stream", False):
            args = self._prepare_base_args()
            args += ["--stream"]
            try:
                proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                try:
                    if proc.stdin:
                        proc.stdin.write(prompt)
                        proc.stdin.close()
                except Exception:
                    pass
                # iterate lines but still protect with a timeout via communicate if stuck
                try:
                    for line in proc.stdout:
                        chunk = line.rstrip("\n")
                        if chunk_callback:
                            try:
                                chunk_callback(chunk)
                            except Exception:
                                pass
                        yield chunk
                    # ensure process exit
                    proc.wait(timeout=self.timeout)
                    return
                except Exception:
                    # if streaming failed, kill and fallback
                    try:
                        proc.kill()
                    except Exception:
                        pass
            except Exception:
                # fall through to fallback
                pass

        # fallback: no streaming — yield single full output
        full = self.generate(prompt)
        if chunk_callback:
            try:
                chunk_callback(full)
            except Exception:
                pass
        yield full


class AIManager:
    def __init__(
        self,
        gpt_model_paths: Optional[List[Union[str, Any]]] = None,
        llama_path: Optional[str] = None,
        n_threads: int = None,
        n_ctx: int = None,
        mode: str = "default",
        model_timeout: float = None,
        enable_llama: bool = True,
        max_total_timeout: float = None,
        min_interval: float = None,
        max_models: Optional[int] = None,
        max_workers: Optional[int] = None,
        **kwargs,
    ):
        """
        Robust AIManager constructor (improved): safe lazy-loading, dedup, backoff,
        and consistent model registration.
        """
        log_local = globals().get("log") or logging.getLogger("AIManager")

        # threads / ctx defaults
        try:
            self.n_threads = max(1, int(n_threads if n_threads is not None else globals().get("DEFAULT_THREADS", 4)))
        except Exception:
            self.n_threads = int(globals().get("DEFAULT_THREADS", 4))
        try:
            self.n_ctx = max(16, int(n_ctx if n_ctx is not None else globals().get("DEFAULT_N_CTX", 512)))
        except Exception:
            self.n_ctx = int(globals().get("DEFAULT_N_CTX", 512))

        self.mode = str(mode or "default")
        self.model_timeout = float(model_timeout if model_timeout is not None else globals().get("DEFAULT_MODEL_TIMEOUT", 40.0))
        self.max_total_timeout = float(max_total_timeout if max_total_timeout is not None else globals().get("DEFAULT_MAX_TOTAL_TIMEOUT", 40.0))
        self.min_interval = float(min_interval if min_interval is not None else globals().get("DEFAULT_MIN_INTERVAL", 0.08))

        # keep max_models sane
        try:
            self.max_models = int(max_models) if max_models is not None else int(globals().get("DEFAULT_MAX_MODELS", 10))
            if self.max_models <= 0:
                self.max_models = int(globals().get("DEFAULT_MAX_MODELS", 10))
        except Exception:
            self.max_models = int(globals().get("DEFAULT_MAX_MODELS", 10))

        self.enable_llama = bool(enable_llama)
        self._gpt_model_paths_provided = gpt_model_paths

        self._batch_size = globals().get("AI_BATCH_SIZE", 3)
        self._batch_interval = globals().get("AI_BATCH_INTERVAL", 60)
        self._batch_index = 0
        self._last_batch_time = 0.0
        # batch state
        self._current_batch: List[Any] = []
        self._batch_pos: int = 0
        self._global_model_index: int = 0

        # Ensure sensible relationship between timeouts
        try:
            if self.model_timeout > self.max_total_timeout:
                log_local.warning(
                    "model_timeout (%.1fs) > max_total_timeout (%.1fs). Adjusting max_total_timeout = model_timeout + 5s",
                    self.model_timeout,
                    self.max_total_timeout,
                )
                self.max_total_timeout = float(self.model_timeout) + 5.0
        except Exception:
            pass

        # ---------------- core caches & concurrency primitives ----------------
        self._cache: Dict[str, Any] = {}
        self._last_call: Dict[str, float] = {}

        # backoff
        self._model_backoff: Dict[str, float] = {}
        self._model_backoff_seconds = float(os.getenv("AI_MODEL_BACKOFF_S", "30.0"))

        # lazy-load caches and lock
        self._lazy_model_cache: Dict[str, Any] = {}
        self._lazy_model_lock = threading.RLock()
        self._lazy_model_paths: List[str] = []

        # thread executor
        try:
            desired = max(2, max_workers or max(4, self.n_threads, self.max_models))
            max_allowed = min(64, int(desired))
            from concurrent.futures import ThreadPoolExecutor

            self._executor = ThreadPoolExecutor(max_workers=max_allowed)
        except Exception:
            from concurrent.futures import ThreadPoolExecutor

            self._executor = ThreadPoolExecutor(max_workers=max(1, self.n_threads))

        # synchronization
        self._lock = threading.RLock()
        self._llama_lock = threading.RLock()
        self._active_semaphore = threading.Semaphore(value=3)

        # placeholders
        self.gpt_models: List[Any] = []
        self.llama: Optional[Any] = None

        # strategies & Deep Q
        self.strategy_modules: Dict[str, Any] = {}
        self.deep_q = None

        # stats persistence and raw ring buffers
        self._stats_lock = threading.RLock()
        try:
            loader = globals().get("_load_json_file")
            model_stats_file = globals().get("MODEL_STATS_FILE")
            if callable(loader) and model_stats_file:
                self.model_stats = loader(model_stats_file) or {}
            else:
                self.model_stats = {}
        except Exception:
            self.model_stats = {}

        if not isinstance(self.model_stats, dict):
            self.model_stats = {}

        if hasattr(self, "_sanitize_model_stats") and callable(getattr(self, "_sanitize_model_stats")):
            try:
                self._sanitize_model_stats()
            except Exception:
                log_local.debug("_sanitize_model_stats failed (ignored)")

        self._stats_dirty = False
        self._last_stats_flush = time.time()
        self._raw_by_model: Dict[str, Any] = {}

        # quick-skip for tests
        try:
            skip_load = str(os.environ.get("AI_SKIP_MODEL_LOAD", "0")).strip().lower()
        except Exception:
            skip_load = "0"
        if skip_load not in ("0", "", "false", "no"):
            log_local.info("AI_SKIP_MODEL_LOAD set -> skipping GPT4All/LLaMA model file loads")
            try:
                if hasattr(self, "_try_load_deep_q"):
                    self._try_load_deep_q()
            except Exception:
                log_local.debug("Deep Q load attempt failed (ignored).")
            log_local.info(
                "AIManager initialized (models skipped) | GPT4All=%d | LLaMA=%s | deep_q=%s",
                len(self.gpt_models),
                "yes" if self.llama else "no",
                "yes" if self.deep_q else "no",
            )
            return

        # ----------------- resolve GPT4All candidate paths and instances -----------------
        candidates_in: List[Union[str, Any]] = []

        # 1️⃣ Fonte correta dos paths
        if gpt_model_paths:
            candidates_in = list(gpt_model_paths)
        elif os.getenv("GPT4ALL_MODELS_DIR"):
            candidates_in = [os.getenv("GPT4ALL_MODELS_DIR")]
            log_local.info("Usando GPT4ALL_MODELS_DIR do .env: %s", candidates_in[0])
        else:
            candidates_in = list(globals().get("DEFAULT_GPT_DIRS", []))
            log_local.warning("GPT4ALL_MODELS_DIR não definido — usando DEFAULT_GPT_DIRS")

        # 2️⃣ Resolver paths reais (.gguf apenas)
        resolved: List[Union[str, Any]] = []
        seen_realpaths: Set[str] = set()

        for p in candidates_in:
            if p is None:
                continue

            # modelo já instanciado
            if hasattr(p, "generate"):
                resolved.append(p)
                continue

            try:
                p = os.path.abspath(os.path.expanduser(os.path.expandvars(str(p).strip('"\' '))))
            except Exception:
                continue

            if os.path.isfile(p) and p.lower().endswith(".gguf"):
                rp = os.path.realpath(p)
                if rp not in seen_realpaths:
                    resolved.append(p)
                    seen_realpaths.add(rp)

            elif os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if f.lower().endswith(".gguf"):
                            fp = os.path.realpath(os.path.join(root, f))
                            if fp not in seen_realpaths:
                                resolved.append(fp)
                                seen_realpaths.add(fp)

        log_local.debug("Resolved GPT4All candidates: %s", resolved)

        # 3️⃣ Separar instâncias e paths
        inst_candidates: List[Any] = []
        path_candidates: List[str] = []

        for r in resolved:
            if hasattr(r, "generate"):
                inst_candidates.append(r)
            elif isinstance(r, str) and os.path.isfile(r):
                path_candidates.append(r)

        # 4️⃣ Registrar instâncias fornecidas
        seen_labels: Set[str] = set(
            (getattr(m, "model_name", None) or getattr(m, "name", None) or "")
            for m in self.gpt_models
        )

        for inst in inst_candidates:
            try:
                label = str(getattr(inst, "model_name", None) or getattr(inst, "name", None))
                if not label or label in seen_labels:
                    continue

                self.gpt_models.append(inst)
                seen_labels.add(label)

                self._ensure_model_stat(label)
                self._raw_by_model.setdefault(label, _Ring(getattr(self, "RAW_RING_SIZE", 6)))

            except Exception as e:
                log_local.warning("Failed to register provided GPT instance %s: %s", inst, e)

        # 5️⃣ Limitar quantidade de modelos
        if self.max_models and len(path_candidates) > self.max_models:
            log_local.info(
                "Limiting GPT4All candidate paths from %d to max_models=%d",
                len(path_candidates),
                self.max_models,
            )
            path_candidates = path_candidates[: self.max_models]

        # 6️⃣ Carregar via loader correto (self!)
        try:
            if path_candidates:
                self._load_gpt_models(path_candidates)
        except Exception as e:
            log_local.error("GPT4All load error: %s", e)

        # 7️⃣ Resolver lazy paths corretamente
        active_labels = {
            getattr(m, "label", None)
            or getattr(m, "model_name", None)
            or os.path.splitext(os.path.basename(getattr(m, "path", "")))[0]
            for m in self.gpt_models
        }

        self._lazy_model_paths = [
            p for p in path_candidates
            if os.path.splitext(os.path.basename(p))[0] not in active_labels
        ]

        # 8️⃣ Limpeza final
        self.gpt_models = [
            m for m in self.gpt_models
            if hasattr(m, "generate")
        ]
        
        if not getattr(self, "gpt_models", None):
            log_local.warning("No GPT4All instances registered -> operating in reduced AI mode (strategy-only & file-mode).")
            # ensure some lazy paths present (scan env)
            env_dir = os.getenv("GPT4ALL_MODELS_DIR")
            if env_dir and os.path.isdir(env_dir):
                # put them in lazy paths for later registration
                found = _resolve_gpt_paths([env_dir])
                self._lazy_model_paths = found
            # Set a flag to ensure vote_trade uses strategies/external_signal if no LLMs
            self._no_local_models = True
        else:
            self._no_local_models = False

        log_local.info("GPT4All models ativos: %d", len(self.gpt_models))
        log_local.debug("Lazy GPT4All paths: %s", self._lazy_model_paths)
    
    def enforce_signal(self, decision: Dict[str, Any], mt5_comm: Any = None, file_path: str | None = None) -> bool:
        """
        Escreve a decisão para o ficheiro que o EA lê. Se mt5_comm estiver ligado,
        tenta também uma chamada API defensiva (fallback).
        Retorna True se pelo menos um método (file ou API) confirmou escrita/execução.
        """
        try:
            log_local = getattr(self, "logger", log)

            # usar env ou argumento; tornar absoluto e consistente
            fp_env = os.getenv("MARKET_RESPONSE_FILE", None)
            target = Path(file_path or fp_env or "JokaBot/market_response.json")
            # se ROOT_DIR definido, junta
            root_dir = Path(os.getenv("ROOT_DIR", "."))
            if not target.is_absolute():
                target = (root_dir / target).resolve()

            log_local.info("enforce_signal: writing decision to %s", str(target))

            # escreve de forma atómica
            wrote = write_market_response(decision, file_path=target)
            if wrote:
                log_local.info("enforce_signal: Decision written to file-mode: %s", str(target))
            else:
                log_local.warning("enforce_signal: Failed to write decision to file: %s", str(target))

            # Se houver mt5_comm e estiver conectado tente uma chamada API defensiva
            api_ok = False
            if mt5_comm is not None:
                try:
                    connected = bool(getattr(mt5_comm, "connected", False))
                except Exception:
                    connected = False

                if connected:
                    try:
                        # método esperado: place_trade_from_decision(decision) — ajusta se o teu MT5Comm usar outro nome
                        res = mt5_comm.place_trade_from_decision(decision)
                        api_ok = bool(res)
                        log_local.info("enforce_signal: mt5_comm.place_trade_from_decision result=%s", str(res))
                    except Exception as e:
                        log_local.warning("enforce_signal: mt5_comm.place_trade_from_decision failed (ignored): %s", e)

            # se file escrito ou api_ok, consideramos sucesso
            if wrote or api_ok:
                return True

            # último recurso: tentar chamar API mesmo que not connected (pode inicializar)
            if mt5_comm is not None and not api_ok:
                try:
                    res = mt5_comm.place_trade_from_decision(decision)
                    return bool(res)
                except Exception:
                    return False

            return False
        except Exception as e:
            log.exception("enforce_signal fatal: %s", e)
            return False

    # ------------------ stats ------------------
    def _sanitize_model_stats(self):
        now = time.time()
        with self._stats_lock:
            for k, v in list(self.model_stats.items()):
                if not isinstance(v, dict):
                    self.model_stats[k] = {}
                s = self.model_stats[k]
                s.setdefault("success", 0)
                s.setdefault("fail", 0)
                s.setdefault("calls", 0)
                s.setdefault("weight", 1.0)
                s.setdefault("created_at", now)
                s.setdefault("last_seen", now)
                s.setdefault("updated_at", now)
            # initial write if file missing
            try:
                _atomic_write(MODEL_STATS_FILE, self.model_stats)
            except Exception:
                pass
    
    # === Substituir/Adicionar estas funções no class AIManager ===
    def _get_next_model_batch(self) -> List[Any]:
        """
        Thread-safe next batch selection using RLock (context-managed).
        """
        lock = getattr(self, "_lock", None)
        if lock is None:
            # fallback: non-threaded behavior
            now = time.time()
            combined = []
            if isinstance(getattr(self, "gpt_models", None), list):
                combined.extend(self.gpt_models)
            if getattr(self, "llama", None) is not None:
                combined.append(self.llama)
            if not combined:
                self._current_batch = []
                return []
            batch_size = max(1, int(getattr(self, "_batch_size", 3)))
            batch_size = min(batch_size, len(combined))
            start = int(getattr(self, "_batch_index", 0)) % len(combined)
            new_batch = [combined[(start + i) % len(combined)] for i in range(batch_size)]
            self._batch_index = (start + batch_size) % len(combined)
            self._current_batch = new_batch
            self._batch_pos = 0
            self._last_batch_time = now
            return list(new_batch)

        with lock:
            now = time.time()
            combined: List[Any] = []
            if isinstance(getattr(self, "gpt_models", None), list):
                combined.extend(self.gpt_models)
            if getattr(self, "llama", None) is not None:
                combined.append(self.llama)

            if not combined:
                self._current_batch = []
                return []

            total = len(combined)
            batch_size = int(getattr(self, "_batch_size", 3))
            if batch_size <= 0:
                batch_size = 1
            batch_size = min(batch_size, total)

            last_time = float(getattr(self, "_last_batch_time", 0.0))
            interval = float(getattr(self, "_batch_interval", 0.0))
            # if interval <= 0, treat as always-expire to allow rotation
            if interval <= 0:
                interval = 0.0

            if (
                self._current_batch
                and (interval > 0) 
                and (now - last_time) < interval
                and len(self._current_batch) == batch_size
            ):
                return list(self._current_batch)

            start = int(getattr(self, "_batch_index", 0)) % total
            new_batch = [combined[(start + i) % total] for i in range(batch_size)]

            self._batch_index = (start + batch_size) % total
            self._current_batch = new_batch
            self._batch_pos = 0
            self._last_batch_time = now

            return list(new_batch)



    def get_next_model_from_batch(self) -> Optional[Any]:
        lock = getattr(self, "_lock", None)
        if lock:
            with lock:
                combined: List[Any] = []
                if isinstance(getattr(self, "gpt_models", None), list):
                    combined.extend(self.gpt_models)
                if getattr(self, "llama", None) is not None:
                    combined.append(self.llama)

                if not combined:
                    return None

                batch = self._get_next_model_batch()
                if not batch:
                    batch = combined

                if not batch:
                    return None

                if not isinstance(getattr(self, "_batch_pos", None), int):
                    self._batch_pos = 0

                batch_len = len(batch)
                if batch_len == 0:
                    return None

                idx = self._batch_pos % batch_len
                model = batch[idx]
                self._batch_pos = (idx + 1) % batch_len

                try:
                    self._global_model_index = (int(getattr(self, "_global_model_index", 0)) + 1) % max(1, len(combined))
                except Exception:
                    self._global_model_index = 0

                return model
        else:
            # non-threaded fallback
            combined = []
            if isinstance(getattr(self, "gpt_models", None), list):
                combined.extend(self.gpt_models)
            if getattr(self, "llama", None) is not None:
                combined.append(self.llama)
            if not combined:
                return None
            # simple round-robin
            idx = getattr(self, "_global_model_index", 0) % len(combined)
            self._global_model_index = (idx + 1) % len(combined)
            return combined[idx]


    def _ensure_model_stat(self, model_id: str):
        now = time.time()
        with self._stats_lock:
            s = self.model_stats.get(model_id)
            if not isinstance(s, dict):
                s = {}
                self.model_stats[model_id] = s
            s.setdefault("success", 0)
            s.setdefault("fail", 0)
            s.setdefault("calls", 0)
            s.setdefault("weight", 1.0)
            s.setdefault("created_at", now)
            s.setdefault("last_seen", now)
            s.setdefault("updated_at", now)
            self._stats_dirty = True

    def _maybe_flush_stats(self, force: bool = False):
        now = time.time()
        with self._stats_lock:
            if not self._stats_dirty and not force:
                return
            if not force and now - self._last_stats_flush < STATS_FLUSH_INTERVAL:
                return
            try:
                _atomic_write(MODEL_STATS_FILE, self.model_stats)
                self._stats_dirty = False
                self._last_stats_flush = now
            except Exception as e:
                log.warning(f"Falha ao flushar stats: {e}")

    def _update_model_stat(self, model_id: str, success: bool):
        """
        Atualiza estatísticas de uso do modelo:
        - calls, success, fail, last_seen, updated_at
        - calcula weight adaptativo baseado em winrate
        - marca stats como dirty para flush
        - realiza flush em background de forma segura
        """
        now = time.time()
        try:
            with self._stats_lock:
                # garante que o modelo exista
                self._ensure_model_stat(model_id)
                s = self.model_stats.setdefault(model_id, {})

                # atualiza contadores e timestamps
                s["calls"] = int(s.get("calls", 0)) + 1
                s["last_seen"] = now
                s["updated_at"] = now
                if success:
                    s["success"] = int(s.get("success", 0)) + 1
                else:
                    s["fail"] = int(s.get("fail", 0)) + 1

                # calcula weight seguro
                total = max(1, s.get("success", 0) + s.get("fail", 0))
                winrate = (s.get("success", 0) + 0.5) / (total + 1.0)
                s["weight"] = float(max(0.2, min(3.0, 0.5 + winrate * 2.5)))

                # marca dirty para flush
                self._stats_dirty = True
        except Exception as e:
            # fallback seguro para não quebrar AIManager
            log.warning(f"[AIManager] Falha ao atualizar stats do modelo '{model_id}': {e}")

        # flush seguro em background
        try:
            threading.Thread(target=self._maybe_flush_stats_safe, daemon=True).start()
        except Exception as e:
            log.warning(f"[AIManager] Falha ao iniciar flush de stats: {e}")

    def _maybe_flush_stats_safe(self):
        """Chamada segura de flush para evitar crash do thread."""
        try:
            self._maybe_flush_stats(force=False)
        except Exception as e:
            log.warning(f"[AIManager] Falha no flush de stats: {e}")

    def get_model_weight(self, model_id: str) -> float:
        """Retorna o weight do modelo, default 1.0 se não existir."""
        try:
            with self._stats_lock:
                s = self.model_stats.get(model_id)
                if s and "weight" in s:
                    return float(s["weight"])
        except Exception as e:
            log.warning(f"[AIManager] Falha ao obter weight do modelo '{model_id}': {e}")
        return 1.0

    # ------------------ model loading ------------------
    def _load_gpt_models(self, paths: List[Union[str, Any]]) -> int:
        """
        Robust GPT4All loader with:
        - strict .gguf detection
        - canonical model naming
        - lazy loading via proxy
        - deduplication by realpath
        """
        import threading

        if GPT4All is None:
            log.warning("[AIManager] GPT4All not available — skipping")
            return 0

        DEFAULT_MAX_BYTES = int(os.getenv("AI_MAX_MODEL_BYTES", 2_500_000_000))
        MAX_ACTIVE_MODELS = max(
            1,
            int(os.getenv("AI_MAX_ACTIVE_MODELS", getattr(self, "max_active_models", 3)))
        )

        # ---------------- RAM safety ----------------
        allowed_bytes = DEFAULT_MAX_BYTES
        try:
            if psutil:
                vm = psutil.virtual_memory()
                reserve = int(1.2 * 1024**3)
                safe = max(0, vm.available - reserve)
                allowed_bytes = min(DEFAULT_MAX_BYTES, int(safe * 0.85))
        except Exception:
            pass

        log.info("[AIManager] allowed_model_bytes=%d", allowed_bytes)

        # ---------------- collect candidates ----------------
        candidates = []
        if not paths:
            env_dir = os.getenv("GPT4ALL_MODELS_DIR")
            if env_dir:
                paths = [env_dir]
            else:
                paths = list(globals().get("DEFAULT_GPT_DIRS", []))

        if isinstance(paths, (str, os.PathLike)):
            paths = [paths]

        seen_realpaths = set()

        for p in paths:
            if p is None:
                continue

            # already instantiated model
            if hasattr(p, "generate"):
                candidates.append(p)
                continue

            try:
                p = os.path.abspath(os.path.expanduser(os.path.expandvars(str(p).strip('"\' '))))
            except Exception:
                continue

            if os.path.isfile(p) and p.lower().endswith(".gguf"):
                rp = os.path.realpath(p)
                if rp not in seen_realpaths:
                    candidates.append(p)
                    seen_realpaths.add(rp)

            elif os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if f.lower().endswith(".gguf"):
                            fp = os.path.realpath(os.path.join(root, f))
                            if fp not in seen_realpaths:
                                candidates.append(fp)
                                seen_realpaths.add(fp)

        if not candidates:
            log.warning("[AIManager] No GPT4All .gguf models found")
            return 0

        # ---------------- setup containers ----------------
        self.gpt_models = getattr(self, "gpt_models", [])
        self._gpt_semaphore = getattr(
            self,
            "_gpt_semaphore",
            threading.BoundedSemaphore(MAX_ACTIVE_MODELS)
        )

        loaded = 0
        seen_labels = set()

        # ---------------- lazy proxy ----------------
        class GPT4AllPathProxy:
            __slots__ = ("path", "_inst", "lock", "label", "manager")

            def __init__(self, path, manager):
                self.path = path
                self.manager = manager
                self.lock = threading.Lock()
                self._inst = None
                self.label = os.path.splitext(os.path.basename(path))[0]

            def _ensure(self):
                if self._inst:
                    return self._inst

                with self.lock:
                    if self._inst:
                        return self._inst

                    self.manager._gpt_semaphore.acquire()
                    try:
                        self._inst = GPT4All(
                            model_path=self.path,
                            n_threads=self.manager.n_threads,
                            n_ctx=self.manager.n_ctx,
                        )
                        return self._inst
                    except Exception:
                        self.manager._gpt_semaphore.release()
                        raise

            def generate(self, prompt: str, **kw):
                return self._ensure().generate(prompt=prompt, **kw)

            def close(self):
                with self.lock:
                    if self._inst:
                        try:
                            self._inst.close()
                        except Exception:
                            pass
                        self._inst = None
                        try:
                            self.manager._gpt_semaphore.release()
                        except Exception:
                            pass

            def __repr__(self):
                return f"<GPT4AllProxy {self.label}>"

        # ---------------- register ----------------
        for c in candidates:
            try:
                if hasattr(c, "generate"):
                    label = getattr(c, "model_name", None) or getattr(c, "name", None)
                    label = str(label or f"gpt_instance_{loaded}")
                    if label in seen_labels:
                        continue
                    self.gpt_models.append(c)

                else:
                    proxy = GPT4AllPathProxy(c, self)
                    label = proxy.label
                    if label in seen_labels:
                        continue
                    self.gpt_models.append(proxy)

                seen_labels.add(label)
                self._ensure_model_stat(label)
                self._raw_by_model.setdefault(label, _Ring(getattr(self, "RAW_RING_SIZE", 6)))
                loaded += 1

            except Exception as e:
                log.warning("[AIManager] Failed to register %s: %s", c, e)

        log.info("[AIManager] GPT4All models registered: %d", loaded)
        return loaded





    def _load_llama(self, path: str, max_instances: int = 100) -> int:
        """
        Robust LLaMA loader (lazy, safe, resource-aware).

        - If `path` is a folder, pick first .gguf inside.
        - Estimate memory use and compute a safe number of proxies (<= max_instances).
        - Create lazy proxies (no heavy allocation at load time).
        - Provide a semaphore to limit concurrent active instances (env LLAMA_MAX_ACTIVE, default 5).
        - Prefer python binding (Llama) if available, else fallback to llama-cli exe (LlamaCLI).
        - Populate self.llama_instances (list of proxies) and a facade self.llama exposing `.generate()`.
        Returns number_of_proxies_configured (int).
        """
        import shutil
        from typing import Optional

        # ---------- env / defaults ----------
        env_max_active = int(os.environ.get("LLAMA_MAX_ACTIVE", "5"))
        env_max_instances = int(os.environ.get("LLAMA_MAX_INSTANCES", str(max_instances)))
        max_instances = max(1, min(max_instances, env_max_instances))

        # ---------- resolve model file ----------
        p = os.path.abspath(os.path.expanduser(str(path or "")))
        if os.path.isdir(p):
            found = []
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(".gguf"):
                        found.append(os.path.join(root, f))
            found.sort()
            if not found:
                log.warning("[AIManager] No .gguf model found in directory %s", p)
                return 0
            p = found[0]

        if not os.path.isfile(p):
            log.warning("[AIManager] Model file not found: %s", p)
            return 0

        # ---------- estimate memory ----------
        try:
            model_bytes = os.path.getsize(p)
        except Exception:
            model_bytes = 0

        avail_mem = None
        try:
            if psutil:
                vm = psutil.virtual_memory()
                avail_mem = int(vm.available)
        except Exception:
            avail_mem = None

        # fallback assume 4 GB available if we can't detect
        if avail_mem is None:
            try:
                avail_mem = 4 * 1024**3
            except Exception:
                avail_mem = None

        repack_factor = float(os.environ.get("LLAMA_REPACK_FACTOR", "1.25"))
        min_per_instance = int(os.environ.get("LLAMA_MIN_PER_INSTANCE_BYTES", str(200 * 1024**2)))  # 200MB
        est_per_instance = max(min_per_instance, int(model_bytes * repack_factor))

        # ---------- compute effective_max ----------
        cpu_count = os.cpu_count() or 2
        cpu_limit = max(1, cpu_count - 1)

        if avail_mem and est_per_instance > 0:
            fit_by_mem = int(max(1, avail_mem // est_per_instance))
        else:
            fit_by_mem = 1

        effective_max = min(max_instances, fit_by_mem, cpu_limit)
        effective_max = max(1, effective_max)
        hard_cap = int(os.environ.get("LLAMA_HARD_CAP", "32"))
        effective_max = min(effective_max, hard_cap)

        # ---------- find llama-cli exe candidates ----------
        exe_candidates = []
        exe_env = os.environ.get("LLAMA_EXE_PATH") or os.environ.get("LLAMA_CLI_PATH")
        if exe_env:
            exe_candidates.append(os.path.abspath(os.path.expanduser(exe_env)))
        which_cli = shutil.which("llama-cli") or shutil.which("llama-cli.exe")
        if which_cli:
            exe_candidates.append(which_cli)
        exe_candidates += [
            os.path.join(ROOT_DIR, "bin", "llama-cli.exe") if "ROOT_DIR" in globals() else None,
            os.path.join("C:\\", "bot_ia2", "models", "llama", "llama-cli.exe"),
            os.path.join("C:\\", "bot-ia2", "models", "llama", "llama-cli.exe"),
        ]
        exe_candidates = [c for c in exe_candidates if c and os.path.isfile(c)]

        # ---------- proxy class (inside function) ----------
        class _LlamaProxy:
            __slots__ = ("index", "model_path", "binding_attempted", "cli_attempted",
                        "instance", "lock", "meta", "type_preferred", "exe_path")

            def __init__(self, index: int, model_path: str, type_preferred: Optional[str] = None, exe_path: Optional[str] = None):
                self.index = index
                self.model_path = model_path
                self.binding_attempted = False
                self.cli_attempted = False
                self.instance = None
                self.lock = threading.Lock()
                self.meta = {
                    "state": "idle",   # idle/creating/ready/failed
                    "created_at": None,
                    "last_used": None,
                    "fails": 0,
                    "cooldown_until": 0.0,
                    "type": None,
                    "error": None,
                }
                self.type_preferred = type_preferred
                self.exe_path = exe_path

            def create(self, n_ctx: int, n_threads: int, timeout: float):
                """
                Instantiate binding or CLI. Safe to call concurrently; first call performs the work.
                """
                with self.lock:
                    now = time.time()
                    if self.meta["state"] == "ready" and self.instance is not None:
                        self.meta["last_used"] = now
                        return self.instance
                    if self.meta["cooldown_until"] > now:
                        raise RuntimeError(f"Proxy {self.index} in cooldown until {self.meta['cooldown_until']:.1f}")

                    self.meta["state"] = "creating"
                    self.meta["error"] = None
                    try:
                        # Prefer Python binding if available and allowed
                        if Llama is not None and (self.type_preferred in (None, "binding")) and not self.binding_attempted:
                            self.binding_attempted = True
                            try:
                                # try typical signature; guard exceptions
                                inst = Llama(model_path=str(self.model_path), n_ctx=int(n_ctx), n_threads=int(n_threads))
                                self.instance = inst
                                self.meta.update({"state": "ready", "created_at": now, "last_used": now, "type": "binding"})
                                return inst
                            except Exception as e_bind:
                                self.meta["error"] = f"binding_error:{e_bind}"
                                # fallthrough to CLI attempt

                        # CLI fallback
                        if (self.exe_path or exe_candidates) and (self.type_preferred in (None, "cli")) and not self.cli_attempted:
                            self.cli_attempted = True
                            exe_to_try = self.exe_path or (exe_candidates[0] if exe_candidates else None)
                            if not exe_to_try:
                                raise RuntimeError("No llama-cli exe available to instantiate CLI instance")
                            inst = LlamaCLI(exe_path=exe_to_try, model_path=self.model_path,
                                            n_ctx=int(n_ctx), n_threads=int(n_threads), timeout=float(timeout))
                            self.instance = inst
                            self.meta.update({"state": "ready", "created_at": now, "last_used": now, "type": "cli"})
                            return inst

                        raise RuntimeError("No usable backend available or previous attempts failed: " + str(self.meta.get("error")))
                    except Exception as e:
                        self.meta["state"] = "failed"
                        self.meta["fails"] = int(self.meta.get("fails", 0)) + 1
                        cooldown = min(300, 5 * self.meta["fails"])
                        self.meta["cooldown_until"] = time.time() + cooldown
                        self.meta["error"] = str(e)
                        raise

            def close(self):
                with self.lock:
                    if self.instance is None:
                        return
                    try:
                        if hasattr(self.instance, "close"):
                            try:
                                self.instance.close()
                            except Exception:
                                pass
                    finally:
                        self.instance = None
                        self.meta["state"] = "idle"

            def is_ready(self):
                return self.meta.get("state") == "ready" and self.instance is not None

        # ---------- create proxies container ----------
        self.llama_instances = []
        # semaphore limits active concurrent creation/usages
        self._llama_semaphore = threading.BoundedSemaphore(max(1, env_max_active))
        self._llama_lock = getattr(self, "_llama_lock", threading.Lock())
        type_pref = "binding" if Llama is not None else "cli"
        chosen_exe = exe_candidates[0] if exe_candidates else None

        for i in range(int(effective_max)):
            proxy = _LlamaProxy(index=i, model_path=p, type_preferred=type_pref, exe_path=chosen_exe)
            self.llama_instances.append(proxy)
            # register stats / raw ring (no heavy ops)
            mid = f"llama:{os.path.basename(p)}:{i}" if type_pref == "binding" else f"llama_cli:{os.path.basename(p)}:{i}"
            try:
                self._ensure_model_stat(mid)
                self._raw_by_model.setdefault(mid, _Ring(int(getattr(self, "RAW_RING_SIZE", 6))))
            except Exception:
                pass

        # ---------- facade to present a single object in self.llama ----------
        class _LlamaFacade:
            def __init__(self, manager):
                self.manager = manager
                self._rr_index = 0
                self._rr_lock = threading.Lock()

            def _pick_proxy(self):
                with self._rr_lock:
                    if not self.manager.llama_instances:
                        raise RuntimeError("No LLaMA proxies available")
                    idx = self._rr_index % len(self.manager.llama_instances)
                    self._rr_index = (self._rr_index + 1) % len(self.manager.llama_instances)
                    return self.manager.llama_instances[idx]

            def generate(self, prompt: str, timeout: Optional[float] = None) -> str:
                """
                Generate text using an available proxy.
                - Round-robin pick a proxy
                - Acquire semaphore to limit concurrency
                - Call backend's most-likely generation API
                """
                timeout = float(timeout or getattr(self.manager, "model_timeout", 60.0))
                proxy = self._pick_proxy()

                # acquire semaphore to avoid OOM by too many concurrent instances
                acquired = self.manager._llama_semaphore.acquire(timeout=max(0.1, min(10.0, timeout)))
                if not acquired:
                    raise RuntimeError("Timeout acquiring LLaMA semaphore (busy)")

                try:
                    inst = proxy.create(n_ctx=getattr(self.manager, "n_ctx", 512),
                                        n_threads=getattr(self.manager, "n_threads", 4),
                                        timeout=timeout)
                    # try multiple call styles
                    try:
                        # 1) typical wrapper with generate(prompt)
                        if hasattr(inst, "generate") and callable(getattr(inst, "generate")):
                            return inst.generate(prompt)
                        # 2) llama_cpp binding might accept __call__ or create_completion
                        if callable(inst):
                            try:
                                return inst(prompt)
                            except Exception:
                                pass
                        if hasattr(inst, "create_completion") and callable(getattr(inst, "create_completion")):
                            # some bindings use create_completion returning dict/text
                            out = inst.create_completion(prompt, max_tokens=256)
                            if isinstance(out, dict):
                                return out.get("choices", [{}])[0].get("text", "") or str(out)
                            return str(out)
                        # 3) LlamaCLI wrapper generate()
                        if hasattr(inst, "generate") and callable(getattr(inst, "generate")):
                            return inst.generate(prompt)
                        # fallback: try str()
                        return str(inst)
                    except Exception as gen_exc:
                        # mark proxy fail so future create attempts will handle cooldown
                        proxy.meta["error"] = f"generate_error:{gen_exc}"
                        raise
                finally:
                    try:
                        self.manager._llama_semaphore.release()
                    except Exception:
                        pass

            def generate_stream(self, prompt: str, chunk_cb: Optional[Callable[[str], None]] = None, timeout: Optional[float] = None):
                """
                Attempt streaming via the chosen proxy; falls back to single generate() if streaming not supported.
                """
                timeout = float(timeout or getattr(self.manager, "model_timeout", 60.0))
                proxy = self._pick_proxy()
                acquired = self.manager._llama_semaphore.acquire(timeout=max(0.1, min(10.0, timeout)))
                if not acquired:
                    raise RuntimeError("Timeout acquiring LLaMA semaphore (busy)")
                try:
                    inst = proxy.create(n_ctx=getattr(self.manager, "n_ctx", 512),
                                        n_threads=getattr(self.manager, "n_threads", 4),
                                        timeout=timeout)
                    # if instance exposes generate_stream or streaming via LlamaCLI wrapper
                    if hasattr(inst, "generate_stream") and callable(getattr(inst, "generate_stream")):
                        for chunk in inst.generate_stream(prompt):
                            if chunk_cb:
                                try:
                                    chunk_cb(chunk)
                                except Exception:
                                    pass
                            yield chunk
                        return
                    # else fallback to single generate
                    full = self.generate(prompt, timeout=timeout)
                    yield full
                finally:
                    try:
                        self.manager._llama_semaphore.release()
                    except Exception:
                        pass

        # expose facade so other code can treat self.llama as a model-like object
        self.llama = _LlamaFacade(self)

        log.info(
            "[AIManager] Configured %d lazy LLaMA proxy(es) for model=%s (est_per_instance=%.2f MB, avail_mem=%s MB, effective_max=%d, active_semaphore=%d)",
            len(self.llama_instances),
            os.path.basename(p),
            est_per_instance / (1024**2),
            (int(avail_mem / (1024**2)) if isinstance(avail_mem, int) else "unknown"),
            effective_max,
            env_max_active,
        )

        # store quick summary
        self._llama_model_path = p
        self._llama_est_per_instance = est_per_instance
        self._llama_effective_max = effective_max

        return len(self.llama_instances)


    # ------------------ strategies loading ------------------
    def load_strategies_dir(self, path: str):
        """Dinamically load python modules from a directory and register any
        'analyze_market' or 'generate_signal' (or similar) functions.

        Safety/robustness:
        - ignore files starting with '_' (helpers)
        - validate spec and loader before exec_module
        - create a unique module name per file path to avoid collisions/reload issues
        - register discovered callable entrypoints in self.strategy_functions[name]
        """
        import sys
        import hashlib

        p = os.path.abspath(path)
        if not os.path.isdir(p):
            log.warning("Strategies path not found: %s", p)
            return

        # ensure containers exist
        if not hasattr(self, "strategy_modules") or self.strategy_modules is None:
            self.strategy_modules = {}
        if not hasattr(self, "strategy_functions") or self.strategy_functions is None:
            self.strategy_functions = {}

        for fn in sorted(os.listdir(p)):
            # skip non-py and private helpers
            if not fn.endswith(".py") or fn.startswith("_"):
                continue

            full = os.path.join(p, fn)
            if not os.path.isfile(full):
                continue

            name = os.path.splitext(fn)[0]

            try:
                # build a stable unique module name derived from path (avoid collisions)
                h = hashlib.sha1(full.encode("utf-8")).hexdigest()[:8]
                module_name = f"strategies.{name}_{h}"

                spec = importlib.util.spec_from_file_location(module_name, full)
                if spec is None or getattr(spec, "loader", None) is None:
                    log.warning("Could not create import spec for %s (skipping)", full)
                    continue

                mod = importlib.util.module_from_spec(spec)
                # ensure module reference exists in sys.modules to allow relative imports inside module
                sys.modules[module_name] = mod
                try:
                    spec.loader.exec_module(mod)  # type: ignore
                except Exception as e_mod:
                    # cleanup partial module entry
                    try:
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                    except Exception:
                        pass
                    raise

                # register by simple name (overwrites previous with same name)
                self.strategy_modules[name] = mod

                # discover entrypoints
                entrypoints = {}
                for cand in ("analyze_market", "generate_signal", "signal", "analyze"):
                    fn_obj = getattr(mod, cand, None)
                    if callable(fn_obj):
                        entrypoints[cand] = fn_obj

                # store discovered callables (may be empty)
                self.strategy_functions[name] = entrypoints

                log.info("Loaded strategy module: %s (module=%s) entrypoints=%s", name, module_name, list(entrypoints.keys()))

            except Exception as e:
                log.warning("Failed loading strategy %s from %s: %s", name, full, e)
                # continue loading other modules
                continue

    def get_registered_strategies(self) -> List[str]:
        return list(self.strategy_modules.keys())

    def _try_load_deep_q(self):
        """
        Tenta localizar e carregar um agente Deep-Q a partir de localizações comuns.
        Depois desta chamada, self.deep_q será None ou um adaptador com API:
        predict(state), act(state), select_action(state), policy(state), __call__(state)
        O dicionário retornado terá ao menos {"action": "BUY"|"SELL"|"HOLD"} e possivelmente "conf", "tp_pips", "sl_pips".
        """
        import hashlib
        import importlib.util
        import sys
        import os
        from typing import Any

        # helpers locais seguros (não assume existência de _safe_float global)
        def _safe_float_local(x, default=None):
            try:
                if x is None:
                    return default
                return float(x)
            except Exception:
                return default

        # candidatos a ficheiro (ordem de preferência)
        candidates = [
            os.path.join(ROOT_DIR, "strategies", "deep_q_learning.py"),
            os.path.join(ROOT_DIR, "strategies", "dqn_agent.py"),
            os.path.join(ROOT_DIR, "strategies", "dqn.py"),
            os.path.join(ROOT_DIR, "deep_q_learning.py"),
        ]

        def _normalize_action(a: Any) -> str:
            """Normaliza várias representações para BUY/SELL/HOLD."""
            try:
                if a is None:
                    return "HOLD"
                # enum-like: name or value
                name = getattr(a, "name", None) or getattr(a, "value", None) or a
                s = str(name).strip().upper()
                if s in ("BUY", "LONG"):
                    return "BUY"
                if s in ("SELL", "SHORT"):
                    return "SELL"
            except Exception:
                pass

            # se for vetor/iterável de scores
            try:
                if hasattr(a, "__len__") and not isinstance(a, str):
                    arr = list(a)
                    if len(arr) >= 1:
                        import math
                        idx = int(max(range(len(arr)), key=lambda i: float(arr[i]) if arr[i] is not None else -math.inf))
                        if len(arr) == 3:
                            return ["HOLD", "BUY", "SELL"][min(2, max(0, idx))]
                        if len(arr) == 2:
                            return ["BUY", "SELL"][min(1, max(0, idx))]
            except Exception:
                pass

            try:
                s = str(a).strip().upper()
                if "BUY" in s:
                    return "BUY"
                if "SELL" in s:
                    return "SELL"
            except Exception:
                pass

            return "HOLD"

        class _DeepQAdapter:
            """Adapta um agente arbitrário para API consistente."""

            def __init__(self, agent):
                self._agent = agent

            def _call_raw(self, state):
                raw = None
                # tenta métodos conhecidos
                for name in ("predict", "act", "select_action", "policy"):
                    fn = getattr(self._agent, name, None)
                    if callable(fn):
                        try:
                            raw = fn(state)
                            break
                        except Exception:
                            continue

                # fallback: callable module/obj
                if raw is None and callable(self._agent):
                    try:
                        raw = self._agent(state)
                    except Exception:
                        raw = None

                out = {
                    "action": "HOLD",
                    "conf": None,
                    "tp_scale": None,
                    "sl_scale": None,
                    "tp_pips": None,
                    "sl_pips": None,
                    "raw": raw
                }

                try:
                    # dict-like
                    if isinstance(raw, dict):
                        act = raw.get("action") or raw.get("decision") or raw.get("dir") or raw.get("side")
                        out["action"] = _normalize_action(act)
                        out["conf"] = _safe_float_local(raw.get("confidence") or raw.get("conf") or raw.get("prob") or raw.get("score"), None)
                        out["tp_scale"] = _safe_float_local(raw.get("tp_scale") or raw.get("tp_mult") or raw.get("tp_ratio"), None)
                        out["sl_scale"] = _safe_float_local(raw.get("sl_scale") or raw.get("sl_mult") or raw.get("sl_ratio"), None)
                        out["tp_pips"] = _safe_float_local(raw.get("tp_pips") or raw.get("tp") or raw.get("take_profit"), None)
                        out["sl_pips"] = _safe_float_local(raw.get("sl_pips") or raw.get("sl") or raw.get("stop_loss"), None)
                        return out

                    # list/tuple: várias formas comuns
                    if isinstance(raw, (list, tuple)):
                        if len(raw) >= 1:
                            cand = raw[0]
                            # se primeiro elemento for string/enum -> ação
                            if isinstance(cand, str) or hasattr(cand, "name") or hasattr(cand, "value"):
                                out["action"] = _normalize_action(cand)
                            else:
                                # tenta interpretar como vetor de scores
                                try:
                                    arr = list(raw)
                                    import math
                                    idx = int(max(range(len(arr)), key=lambda i: float(arr[i]) if arr[i] is not None else -math.inf))
                                    if len(arr) == 3:
                                        out["action"] = ["HOLD", "BUY", "SELL"][min(2, max(0, idx))]
                                    elif len(arr) == 2:
                                        out["action"] = ["BUY", "SELL"][min(1, max(0, idx))]
                                except Exception:
                                    pass
                        # segundo elemento pode ser confiança
                        if len(raw) >= 2:
                            try:
                                maybe_conf = raw[1]
                                out["conf"] = _safe_float_local(maybe_conf, None)
                            except Exception:
                                pass
                        return out

                    # scalar string/enum
                    if isinstance(raw, str) or hasattr(raw, "name") or hasattr(raw, "value"):
                        out["action"] = _normalize_action(raw)
                        return out

                except Exception:
                    # mantém fallback
                    pass

                return out

            # métodos expostos
            def predict(self, state): return self._call_raw(state)
            def act(self, state): return self._call_raw(state)
            def select_action(self, state): return self._call_raw(state)
            def policy(self, state): return self._call_raw(state)
            def __call__(self, state): return self._call_raw(state)

        found_any = False
        last_exc = None

        for path in candidates:
            module_name = None
            try:
                if not os.path.isfile(path):
                    continue
                found_any = True

                # gerar nome de módulo único
                id_hash = hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()[:8]
                module_name = f"deep_q_mod_{id_hash}"

                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec is None or getattr(spec, "loader", None) is None:
                    log.debug("Spec/loader ausente para %s (pulando)", path)
                    continue

                m = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = m
                try:
                    spec.loader.exec_module(m)  # type: ignore
                except Exception as e_exec:
                    # limpamos sys.modules e re-raise para o outer catch tratar
                    try:
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                    except Exception:
                        pass
                    raise

                # procurar símbolos usuais
                candidates_attrs = ["DQNAgent", "DeepQAgent", "DeepQLearningStrategy", "DQN", "Agent", "create_agent", "load_agent"]
                agent_obj = None
                for attr in candidates_attrs:
                    agent_obj = getattr(m, attr, None)
                    if agent_obj:
                        break

                # se nada encontrado e módulo é callable, usar módulo
                if agent_obj is None and callable(m):
                    agent_obj = m

                if agent_obj is None:
                    log.debug("Nenhum símbolo reconhecido em %s (attrs tentados: %s)", path, candidates_attrs)
                    # limpar módulo carregado
                    try:
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                    except Exception:
                        pass
                    continue

                # instanciar se preciso
                inst = None
                if not callable(agent_obj):
                    inst = agent_obj  # assume já é instância
                else:
                    # padrões seguros de instanciação (não-travantes)
                    tried = []
                    # 1) sem argumentos
                    try:
                        inst = agent_obj()
                        tried.append("no-arg")
                    except Exception as e_no:
                        tried.append(f"no-arg failed: {e_no}")
                        inst = None
                    # 2) (state_size, action_size)
                    if inst is None:
                        try:
                            inst = agent_obj(10, 2)
                            tried.append("(10,2)")
                        except Exception as e_args:
                            tried.append(f"(10,2) failed: {e_args}")
                            inst = None
                    # 3) kwargs
                    if inst is None:
                        try:
                            inst = agent_obj(state_size=10, action_size=2)
                            tried.append("kwargs")
                        except Exception as e_kw:
                            tried.append(f"kwargs failed: {e_kw}")
                            inst = None
                    # 4) dict
                    if inst is None:
                        try:
                            inst = agent_obj({"state_size": 10, "action_size": 2})
                            tried.append("dict")
                        except Exception as e_dict:
                            tried.append(f"dict failed: {e_dict}")
                            inst = None

                    log.debug("Tentativas de instanciação para %s -> %s", path, tried)

                if inst is None:
                    log.debug("Não foi possível instanciar agente em %s", path)
                    try:
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                    except Exception:
                        pass
                    continue

                # wrap e sanity-check
                adapter = _DeepQAdapter(inst)
                try:
                    sample = adapter.predict([0.0] * 8)
                    if isinstance(sample, dict) and "action" in sample:
                        self.deep_q = adapter
                        log.info("Deep Q carregado e adaptado de %s (module=%s)", path, module_name)
                        return
                    else:
                        log.debug("Sanity check falhou (sem chave 'action') para %s -> %s", path, sample)
                        try:
                            if module_name in sys.modules:
                                del sys.modules[module_name]
                        except Exception:
                            pass
                        continue
                except Exception as e_call:
                    last_exc = e_call
                    log.debug("Chamada de sanity check falhou para %s: %s", path, e_call)
                    try:
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                    except Exception:
                        pass
                    continue

            except Exception as e_outer:
                last_exc = e_outer
                log.debug("Falha ao importar deep_q %s: %s", path, e_outer)
                try:
                    if module_name and module_name in sys.modules:
                        del sys.modules[module_name]
                except Exception:
                    pass
                continue

        # se não encontrou ficheiros candidatos
        if not found_any:
            log.debug("Nenhum ficheiro deep_q encontrado nos locais esperados.")
        self.deep_q = None
        if last_exc:
            log.debug("DeepQ load last exception: %s", last_exc)
        return




    def adjust_with_deep_q(
        self,
        decision: str,
        conf: float,
        tp: float,
        sl: float,
        features: dict
    ) -> tuple[str, float, float, float]:
        """
        Conservative Deep-Q-based adjustment for (decision, conf, tp, sl).
        Robust and defensive: handles missing numpy, many agent output shapes,
        and never raises (falls back to original values on error).
        """

        import numbers
        try:
            import numpy as np
        except Exception:
            np = None

        # Quick exit if deep_q not available
        if not getattr(self, "deep_q", None):
            return decision, conf, tp, sl

        # Hyperparameters
        max_scale = float(getattr(self, "deep_q_max_scale", 1.20))
        min_scale = float(getattr(self, "deep_q_min_scale", 0.80))
        max_conf_delta = float(getattr(self, "deep_q_max_conf_delta", 0.15))
        alpha = float(getattr(self, "deep_q_alpha", 0.15))

        tp_min = float(getattr(self, "tp_min_pips", 1.0))
        tp_max = float(getattr(self, "tp_max_pips", 5000.0))
        sl_min = float(getattr(self, "sl_min_pips", 1.0))
        sl_max = float(getattr(self, "sl_max_pips", 5000.0))

        # --- Build state vector safely ---
        try:
            s_vals = [
                float(features.get("close_last", 0.0)),
                float(features.get("close_prev", 0.0)),
                float(features.get("return_1", 0.0)),
                float(features.get("volatility", 0.0)),
                float(features.get("trend_5", 0.0)),
                float(features.get("trend_20", 0.0)),
                1.0 if str(decision).upper() == "BUY" else -1.0 if str(decision).upper() == "SELL" else 0.0,
                float(conf or 0.0),
            ]
            state = np.array(s_vals, dtype=np.float32) if np is not None else list(s_vals)
        except Exception:
            state = None

        # Optional scaling
        try:
            scaler = getattr(self, "deep_q_scaler", None)
            if scaler and state is not None:
                try:
                    if np is not None and hasattr(state, "reshape"):
                        state = np.asarray(scaler.transform(state.reshape(1, -1))).reshape(-1)
                    else:
                        state = scaler(list(state))
                except Exception:
                    pass
        except Exception:
            pass

        # Normalize to prevent numeric blowups
        safe_state = state
        try:
            if np is not None and isinstance(state, np.ndarray):
                denom = max(float(abs(state).max()), 1.0)
                safe_state = state / denom
        except Exception:
            safe_state = state

        # --- Call agent ---
        try:
            agent = self.deep_q
            raw_out = None

            # Try different possible agent methods
            for method in ("predict", "act", "select_action", "policy"):
                fn = getattr(agent, method, None)
                if callable(fn):
                    try:
                        raw_out = fn(safe_state if safe_state is not None else state)
                        break
                    except Exception:
                        continue

            # Fallback: call agent directly
            if raw_out is None and callable(agent):
                raw_out = agent(safe_state if safe_state is not None else state)

            # Safe defaults
            tp_candidate, sl_candidate, conf_candidate = tp, sl, conf
            action_override = None

            # Interpret dict-like output
            if isinstance(raw_out, dict):
                tp_scale = _safe_float(raw_out.get("tp_scale") or raw_out.get("tp_ratio") or raw_out.get("tp_mult"), None)
                sl_scale = _safe_float(raw_out.get("sl_scale") or raw_out.get("sl_ratio") or raw_out.get("sl_mult"), None)
                tp_delta = _safe_float(raw_out.get("tp_delta") or raw_out.get("tp_change"), None)
                sl_delta = _safe_float(raw_out.get("sl_delta") or raw_out.get("sl_change"), None)
                new_conf = _safe_float(raw_out.get("conf") or raw_out.get("confidence") or raw_out.get("conf_delta"), None)
                act = raw_out.get("action") or raw_out.get("decision")
                if isinstance(act, str):
                    a = act.strip().upper()
                    if a in ("BUY", "LONG"):
                        action_override = "BUY"
                    elif a in ("SELL", "SHORT"):
                        action_override = "SELL"
                    elif a in ("HOLD", "NONE"):
                        action_override = "HOLD"
            # Interpret sequence/array output
            elif isinstance(raw_out, (list, tuple, np.ndarray)):
                arr = np.asarray(raw_out) if np is not None else list(raw_out)
                if len(arr) >= 3:
                    action_override = ["HOLD", "BUY", "SELL"][int(np.argmax(arr) if np else max(range(len(arr)), key=lambda i: arr[i]))]
                    new_conf = conf * 1.0  # conservative

            # Override decision if agent suggests
            dec_out = action_override or str(decision).upper()
            conf_out = float(conf)
            tp_out = float(tp)
            sl_out = float(sl)

            # Apply scale/delta if present
            if 'tp_scale' in locals() and tp_scale is not None:
                tp_candidate = tp_out * max(min_scale, min(max_scale, tp_scale))
            if 'sl_scale' in locals() and sl_scale is not None:
                sl_candidate = sl_out * max(min_scale, min(max_scale, sl_scale))
            if 'tp_delta' in locals() and tp_delta is not None:
                tp_candidate = tp_out + tp_delta
            if 'sl_delta' in locals() and sl_delta is not None:
                sl_candidate = sl_out + sl_delta
            if 'new_conf' in locals() and new_conf is not None:
                conf_candidate = max(0.0, min(1.0, new_conf))

            # Smoothing
            conf_final = (1.0 - alpha) * conf_out + alpha * conf_candidate
            tp_final = (1.0 - alpha) * tp_out + alpha * tp_candidate
            sl_final = (1.0 - alpha) * sl_out + alpha * sl_candidate

            # Clip to safe ranges
            conf_final = max(0.0, min(1.0, conf_final))
            tp_final = max(tp_min, min(tp_max, tp_final))
            sl_final = max(sl_min, min(sl_max, sl_final))

            return dec_out, conf_final, tp_final, sl_final

        except Exception:
            # fallback seguro
            return decision, conf, max(tp_min, tp), max(sl_min, sl)


    def _extract_features(self, market_input: Union[pd.DataFrame, dict]) -> dict:
        """
        Extract simple features from a DataFrame or pass-through dict.
        Defensive: imports numpy locally and handles missing columns.
        """
        try:
            import numpy as np
        except Exception:
            np = None

        try:
            if isinstance(market_input, pd.DataFrame):
                df = market_input.copy()
                # pick a close-like column
                close_col = next((c for c in df.columns if c.lower() in ("close", "price", "last")), None)
                if close_col is None:
                    close_col = df.columns[-1]
                close_arr = df[close_col].to_numpy()
                last = float(close_arr[-1])
                prev = float(close_arr[-2]) if len(close_arr) >= 2 else last
                ret1 = (last - prev) / prev if prev != 0 else 0.0
                vol = float(np.std(close_arr[-20:])) if np is not None and len(close_arr) >= 2 else float(np.std(close_arr[-20:])) if len(close_arr) >= 2 else 0.0
                trend5 = float(np.mean(close_arr[-5:])) if len(close_arr) >= 5 else last
                trend20 = float(np.mean(close_arr[-20:])) if len(close_arr) >= 20 else last
                candles = df.tail(50).to_dict(orient="records")
                return {
                    "symbol": getattr(df, "symbol", None),
                    "close_last": last,
                    "close_prev": prev,
                    "return_1": ret1,
                    "volatility": vol,
                    "trend_5": trend5,
                    "trend_20": trend20,
                    "candles": candles,
                }
            elif isinstance(market_input, dict):
                return market_input
        except Exception as e:
            try:
                log.warning(f"_extract_features error: {e}")
            except Exception:
                pass

        return {"close_last": 0.0, "close_prev": 0.0, "return_1": 0.0, "volatility": 0.0, "trend_5": 0.0, "trend_20": 0.0, "candles": []}

    def _build_prompt(self, features: dict) -> str:
        """
        Constrói um prompt JSON-safe para LLM.
        Converte automaticamente pandas, numpy e datetime para tipos serializáveis.
        """
        import json
        import numpy as np
        import pandas as pd
        from datetime import datetime

        def _safe(v):
            # None
            if v is None:
                return None

            # pandas Timestamp
            if isinstance(v, pd.Timestamp):
                return v.isoformat()

            # datetime
            if isinstance(v, datetime):
                return v.isoformat()

            # numpy scalars
            if isinstance(v, np.integer):
                return int(v)
            if isinstance(v, np.floating):
                return float(v)

            # numpy array
            if isinstance(v, np.ndarray):
                return v.tolist()

            # pandas Series
            if isinstance(v, pd.Series):
                return {k: _safe(val) for k, val in v.to_dict().items()}

            # pandas DataFrame
            if isinstance(v, pd.DataFrame):
                return [
                    {k: _safe(val) for k, val in row.items()}
                    for row in v.reset_index(drop=True).to_dict(orient="records")
                ]

            # dict
            if isinstance(v, dict):
                return {k: _safe(val) for k, val in v.items()}

            # list / tuple
            if isinstance(v, (list, tuple)):
                return [_safe(x) for x in v]

            return v

        # pega os primeiros 6 candles e serializa
        candles_safe = _safe(features.get("candles", [])[:6])

        payload = {
            "instruction": (
                "VOCÊ É UM TRADER AGRESSIVO DE ALTA FREQUÊNCIA. "
                "PROIBIDO RESPONDER HOLD SE HOUVER TENDÊNCIA. "
                "TP MÍNIMO: 100 PIPS. SL MÍNIMO: 50 PIPS. "
                "RESPONDA APENAS JSON: decision (BUY|SELL), confidence (0.5-1.0), tp (100-500), sl (50-200)."
            ),
            "market": {
                "symbol": str(features.get("symbol", "UNKNOWN")),
                "price": float(features.get("close_last", 0.0)),
                "return_1": float(features.get("return_1", 0.0)),
                "volatility": float(features.get("volatility", 0.0)),
                "trend5": float(features.get("trend_5", 0.0)),
                "trend20": float(features.get("trend_20", 0.0)),
            },
            # limita candles para evitar prompt gigante (máx 20)
            "candles_sample": candles_safe[:20],
        }

        return f"```json\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n```"

    def _find_json_in_text(self, text: str) -> Optional[str]:
        """
        Tenta extrair JSON contido em um texto, primeiro via regex (_JSON_RE), 
        depois via parsing balanceado de chaves.
        """
        import re

        if not text:
            return None

        # Regex predefinido se existir
        json_re = getattr(self, "_JSON_RE", None)
        if json_re:
            match = json_re.search(text)
            if match:
                return match.group(1)

        # Parsing balanceado de chaves
        stack = []
        start_idx = None
        for i, c in enumerate(text):
            if c == '{':
                if start_idx is None:
                    start_idx = i
                stack.append(c)
            elif c == '}':
                if stack:
                    stack.pop()
                    if not stack and start_idx is not None:
                        return text[start_idx:i+1]

        # fallback simples: pegar primeiro { até último }
        i = text.find('{')
        j = text.rfind('}')
        if i != -1 and j != -1 and j > i:
            return text[i:j+1]

        return None

    def _parse_response_full(self, text: str) -> tuple[str, float, float, float]:
        """
        Analisa a saída do modelo de forma robusta.
        Retorna: (decision, confidence, tp_pips, sl_pips)
        """
        import json
        import re

        DEFAULT_DECISION = "HOLD"
        DEFAULT_CONF = 0.0
        DEFAULT_TP = 150.0
        DEFAULT_SL = 75.0

        if not text or not text.strip():
            return DEFAULT_DECISION, DEFAULT_CONF, DEFAULT_TP, DEFAULT_SL

        raw = str(text).strip()
        data = None

        # --- Tenta extrair JSON interno ---
        try:
            js = self._find_json_in_text(raw)
            if js:
                try:
                    data = json.loads(js)
                except Exception:
                    data = None
        except Exception:
            data = None

        if isinstance(data, dict):
            # Decision
            dec = str(data.get('decision') or data.get('action') or '').upper()
            dec = {'LONG': 'BUY', 'SHORT': 'SELL'}.get(dec, dec)
            if dec not in ('BUY', 'SELL', 'HOLD'):
                dec = DEFAULT_DECISION

            # Confidence
            conf = _safe_float(data.get('confidence') or data.get('conf'), DEFAULT_CONF)

            # TP / SL
            tp = _safe_float(data.get('tp') or data.get('tp_pips'), DEFAULT_TP)
            sl = _safe_float(data.get('sl') or data.get('sl_pips'), DEFAULT_SL)

            return dec, max(0.0, min(1.0, conf)), max(1.0, tp), max(1.0, sl)

        # --- Heurísticas para texto livre ---
        txt = raw.replace(',', '.').upper()

        # Decision heurística
        if 'BUY' in txt and 'SELL' not in txt:
            dec = 'BUY'
        elif 'SELL' in txt and 'BUY' not in txt:
            dec = 'SELL'
        else:
            dec = DEFAULT_DECISION

        # Confidence (%)
        conf = DEFAULT_CONF
        m_conf = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", txt)
        if m_conf:
            try:
                conf = float(m_conf.group(1)) / 100.0
            except Exception:
                conf = DEFAULT_CONF

        # TP / SL heurísticos
        tp = DEFAULT_TP
        sl = DEFAULT_SL
        m_tp = re.search(r"TP\s*[:=]\s*([0-9\.]+)", txt, re.I)
        m_sl = re.search(r"SL\s*[:=]\s*([0-9\.]+)", txt, re.I)
        if m_tp:
            tp = _safe_float(m_tp.group(1), DEFAULT_TP)
        if m_sl:
            sl = _safe_float(m_sl.group(1), DEFAULT_SL)

        # Limitar valores válidos
        conf = max(0.0, min(1.0, conf))
        tp = max(1.0, tp)
        sl = max(1.0, sl)

        return dec, conf, tp, sl


        # ------------------ generic model invocation ------------------
    def _generate_from_model(self, model, prompt: str, timeout: Optional[float] = None):
        """
        Robust and flexible model generation wrapper.

        Features:
        - Tries multiple call patterns: generate, chat, __call__, dict or messages.
        - Handles async coroutines safely (including existing event loops).
        - Timeout support via thread join.
        - Normalizes output: str, dict, list, bytes, numpy arrays, iterables.
        - Returns raw output; caller should normalize further if needed.
        """
        import threading
        import traceback
        import inspect
        import asyncio
        import types
        import logging
        import itertools

        try:
            import numpy as _np
        except Exception:
            _np = None

        log = getattr(self, "logger", logging.getLogger(__name__))
        errors: list[str] = []
        result_container = {"ok": False, "result": None, "exc": None, "trace": None}
        MAX_MATERIALIZE = int(getattr(self, "_max_materialize_items", 1000))

        # ---------- Internal call patterns ----------
        def _call_patterns():
            def _try(fn, *args, **kwargs):
                try:
                    return True, fn(*args, **kwargs)
                except TypeError as te:
                    errors.append(f"TypeError {getattr(fn,'__name__',repr(fn))}: {te}")
                    return False, te
                except Exception as e:
                    errors.append(f"Exception {getattr(fn,'__name__',repr(fn))}: {type(e).__name__}: {e}\n{traceback.format_exc()}")
                    return False, e

            # 1) model.generate
            if hasattr(model, "generate") and callable(getattr(model, "generate")):
                gen = getattr(model, "generate")
                for name in ("prompt", "input", "text", "message", "prompt_text"):
                    ok, out = _try(gen, **{name: prompt})
                    if ok: return out
                    ok2, out2 = _try(gen, prompt)
                    if ok2: return out2
                ok, out = _try(gen, {"prompt": prompt})
                if ok: return out
                ok, out = _try(gen, {"messages": [{"role": "user", "content": prompt}]})
                if ok: return out

            # 2) chat-style methods
            for attr in ("chat_complete", "chat", "chat_completion", "complete", "generate_chat"):
                if hasattr(model, attr) and callable(getattr(model, attr)):
                    fn = getattr(model, attr)
                    for args in (prompt, [{"role": "user", "content": prompt}], {"messages": [{"role": "user", "content": prompt}]}):
                        ok, out = _try(fn, args)
                        if ok: return out

            # 3) model as callable
            if callable(model):
                for args in (prompt, {"prompt": prompt}, [prompt], [{"role": "user", "content": prompt}]):
                    ok, out = _try(model, args)
                    if ok: return out

            # 4) attribute __call__
            if hasattr(model, "__call__") and callable(model.__call__):
                for args in (prompt, {"prompt": prompt}):
                    ok, out = _try(model.__call__, args)
                    if ok: return out

            # 5) last-resort alternative payloads
            alt_payloads = [
                {"input": prompt},
                {"text": prompt},
                {"message": prompt},
                {"messages": [{"role": "user", "content": prompt}]},
                [{"role": "user", "content": prompt}],
                [prompt]
            ]
            for payload in alt_payloads:
                for fn in (getattr(model, "generate", None), model):
                    if callable(fn):
                        try:
                            ok, out = _try(fn, payload)
                            if ok: return out
                        except Exception:
                            continue

            raise RuntimeError("No supported generation method succeeded; patterns tried.")

        # ---------- Runner ----------
        def _runner(outer_timeout: Optional[float] = None):
            try:
                out = _call_patterns()

                # Handle coroutines / async
                is_coro = inspect.iscoroutine(out) or asyncio.iscoroutine(out) or isinstance(out, types.CoroutineType) or inspect.isawaitable(out)
                if is_coro:
                    try:
                        loop = None
                        try:
                            loop = asyncio.get_event_loop()
                        except Exception:
                            loop = None

                        if loop and loop.is_running():
                            fut = asyncio.run_coroutine_threadsafe(out, loop)
                            wait_t = float(outer_timeout or getattr(self, "model_timeout", 10.0))
                            out = fut.result(timeout=wait_t)
                        else:
                            out = asyncio.run(out)
                    except Exception as e:
                        errors.append(f"Async run failed: {type(e).__name__}: {e}\n{traceback.format_exc()}")
                        raise

                # ---------- Normalize output ----------
                # bytes -> str
                if isinstance(out, (bytes, bytearray)):
                    try: out = out.decode("utf-8", errors="replace")
                    except Exception: out = str(out)

                # numpy array -> list
                if _np is not None and isinstance(out, _np.ndarray):
                    try: out = out.tolist()
                    except Exception:
                        try: out = list(out)
                        except Exception: out = str(out)

                # iterables (not containers)
                if hasattr(out, "__iter__") and not isinstance(out, (str, bytes, dict, list, tuple)):
                    try:
                        out = list(itertools.islice(out, MAX_MATERIALIZE + 1))
                        if len(out) > MAX_MATERIALIZE:
                            errors.append(f"Iterator truncated to {MAX_MATERIALIZE} items")
                            out = out[:MAX_MATERIALIZE]
                    except Exception:
                        try: out = list(out)
                        except Exception: pass

                result_container["ok"] = True
                result_container["result"] = out
            except Exception as e:
                result_container["exc"] = e
                result_container["trace"] = traceback.format_exc()

        # ---------- Run with timeout ----------
        outer_timeout = float(timeout) if timeout is not None else 0.0
        if outer_timeout > 0:
            th = threading.Thread(target=lambda: _runner(outer_timeout), daemon=True)
            th.start()
            th.join(outer_timeout)
            if th.is_alive():
                errors.append(f"Generation timed out after {outer_timeout}s")
                raise TimeoutError(f"Model generation timed out; errors: {' | '.join(errors)}")
        else:
            _runner(None)

        # ---------- Return or raise ----------
        if result_container["ok"]:
            return result_container["result"]
        else:
            exc = result_container["exc"]
            trace = result_container.get("trace") or traceback.format_exc()
            msg = f"All generation attempts failed. last_exc={repr(exc)}; errors_log={' | '.join(errors)}; trace={trace}"
            log.debug(msg)
            raise RuntimeError(msg)

    def _call_model_with_timeout(self, model, prompt: str, timeout: float) -> Tuple[str, str, bool]:
        """
        Invoke model safely with timeout, retries, and robust output handling.

        Returns:
            (raw_text, model_id, success_flag)
        """
        import time, json, random, traceback, concurrent.futures as _cf
        from typing import Any

        log = getattr(self, "logger", __import__("logging").getLogger(__name__))
        _TimeoutExc = globals().get("FuturesTimeoutError", _cf.TimeoutError)

        # config defaults
        MAX_RETRIES = int(os.environ.get("AI_MODEL_CALL_RETRIES", 2))
        BASE_BACKOFF = float(os.environ.get("AI_MODEL_CALL_BACKOFF", 0.05))
        MAX_RAW_STORE = int(os.environ.get("AI_MAX_RAW_STORE", 4000))

        # normalize model ID
        def _normalize_mid(m: Any) -> str:
            try:
                mid = getattr(m, "model_name", None) or getattr(m, "model_path", None) or getattr(m, "__class__", type(m)).__name__
                return mid.decode("utf-8", errors="ignore") if isinstance(mid, bytes) else str(mid)
            except Exception:
                return "unknown_model"

        model_id = _normalize_mid(model)
        start_total = time.time()
        last_exc = None

        # safe conversion to string, truncated if needed
        def _raw_to_str(x: Any) -> str:
            try:
                if isinstance(x, str): s = x
                elif isinstance(x, bytes): s = x.decode("utf-8", errors="replace")
                elif isinstance(x, (int, float, bool)): s = str(x)
                else: s = json.dumps(x, ensure_ascii=False, default=str)
            except Exception:
                try: s = repr(x)
                except Exception: s = "<unserializable>"
            if len(s) > MAX_RAW_STORE:
                head = s[:int(MAX_RAW_STORE*0.6)]
                tail = s[-int(MAX_RAW_STORE*0.2):]
                s = head + " ...[TRIMMED]... " + tail
            return s

        # worker wrapper
        def _invoke_once():
            try:
                out = self._generate_from_model(model, prompt, timeout=timeout)
                return True, out, None
            except Exception as e:
                return False, None, e

        for attempt in range(1, MAX_RETRIES + 2):
            attempt_start = time.time()
            fut = None
            try:
                fut = self._executor.submit(_invoke_once)
                ok, out, exc = fut.result(timeout=timeout)
                elapsed = time.time() - attempt_start

                if ok:
                    raw_text = _raw_to_str(out)
                    # write to ring buffer
                    try:
                        ring = self._raw_by_model.setdefault(model_id, _Ring(RAW_RING_SIZE))
                        ring.push(raw_text)
                    except Exception as e:
                        log.debug(f"Ring push failed for model {model_id}: {e}")

                    self._update_model_stat(model_id, success=True)
                    log.info(f"Model {model_id} succeeded (attempt {attempt}) in {elapsed:.3f}s")
                    return raw_text, model_id, True
                else:
                    last_exc = exc
                    self._update_model_stat(model_id, success=False)
                    log.warning(f"Model {model_id} attempt {attempt} failed: {type(exc).__name__}: {exc}")

            except _TimeoutExc as te:
                last_exc = te
                self._update_model_stat(model_id, success=False)
                try:
                    if fut: fut.cancel()
                except Exception: pass
                log.warning(f"Model {model_id} timed out on attempt {attempt} after {timeout}s")

            except Exception as e:
                last_exc = e
                self._update_model_stat(model_id, success=False)
                try:
                    if fut: fut.cancel()
                except Exception: pass
                log.error(f"Unhandled exception in model call attempt {attempt} for {model_id}: {type(e).__name__}: {e}")

            # retry/backoff
            attempts_left = (MAX_RETRIES + 1) - attempt
            if attempts_left <= 0: break
            backoff = min(5.0, BASE_BACKOFF * (2 ** (attempt-1)) + random.uniform(0, BASE_BACKOFF*0.3))
            log.debug(f"Retrying model {model_id} in {backoff:.3f}s (attempt {attempt+1}/{MAX_RETRIES+1})")
            try: time.sleep(backoff)
            except Exception: pass

        # exhausted retries -> return compact error
        total_elapsed = time.time() - start_total
        exc_summary = f"{type(last_exc).__name__}: {last_exc}" if last_exc else "<no_exception>"
        log.error(f"Model {model_id} failed after {MAX_RETRIES+1} attempts; last_exc={exc_summary}; elapsed={total_elapsed:.3f}s")
        raw_err = f"<ERROR> {exc_summary}"
        try:
            ring = self._raw_by_model.setdefault(model_id, _Ring(RAW_RING_SIZE))
            ring.push(raw_err)
        except Exception: pass

        return raw_err, model_id, False

    def _call_gpt_ensemble(self, features: dict, timeout_per_model: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Robust GPT ensemble caller.
        Calls top-weighted GPT models concurrently (or serially if no executor).
        Normalizes outputs to dicts: {"decision","confidence","tp_pips","sl_pips","model","raw"}.
        Handles timeouts, exceptions, and unexpected output shapes.
        """
        import time, os, random, json
        from concurrent.futures import as_completed, TimeoutError as FuturesTimeoutError

        log = getattr(self, "logger", __import__("logging").getLogger(__name__))
        results: list[dict] = []

        if not getattr(self, "gpt_models", None):
            log.warning("No GPT models loaded for ensemble.")
            return results

        timeout_per_model = float(timeout_per_model or max(1.0, min(getattr(self, "model_timeout", 6.0), 6.0)))
        MAX_ACTIVE = int(os.environ.get("AI_MAX_ACTIVE_MODELS", "5"))
        MAX_RAW_STORE = int(os.environ.get("AI_MAX_RAW_STORE", "4000"))

        prompt = self._build_prompt(features)

        def _normalize_raw(raw: any) -> str:
            """Normalize any model output to a string, truncated if needed."""
            try:
                if isinstance(raw, str): text = raw
                elif isinstance(raw, bytes): text = raw.decode("utf-8", errors="replace")
                elif isinstance(raw, dict):
                    if "choices" in raw and isinstance(raw["choices"], (list, tuple)):
                        parts = []
                        for c in raw["choices"]:
                            if isinstance(c, dict):
                                msg = (c.get("message") or {}).get("content") if isinstance(c.get("message"), dict) else None
                                parts.append(str(msg or c.get("text") or c.get("content") or ""))
                            else: parts.append(str(c))
                        text = " ".join([p for p in parts if p]).strip()
                    else:
                        text = str(raw.get("text") or raw.get("response") or json.dumps(raw, ensure_ascii=False))
                elif isinstance(raw, (list, tuple)):
                    for e in raw:
                        if isinstance(e, str) and e.strip(): 
                            text = e.strip(); break
                        if isinstance(e, dict):
                            cand = e.get("text") or e.get("response") or json.dumps(e, ensure_ascii=False)
                            if cand: text = cand; break
                    else:
                        text = " ".join(map(str, raw))
                else:
                    text = str(raw)
            except Exception:
                try: text = repr(raw)
                except Exception: text = "<unserializable>"

            # truncate
            if len(text) > MAX_RAW_STORE:
                head = text[: int(MAX_RAW_STORE * 0.6)]
                tail = text[- int(MAX_RAW_STORE * 0.2):]
                text = head + " ...[TRIMMED]... " + tail
            return (text or "").strip()

        # select top weighted models
        candidates = []
        for i, m in enumerate(self.gpt_models):
            mid = getattr(m, "model_name", None) or getattr(m, "model_path", None) or type(m).__name__
            try:
                weight = float(self.get_model_weight(str(mid)) or 1.0)
            except Exception:
                weight = 1.0
            candidates.append((weight, random.random(), m))  # shuffle among equal weight

        candidates.sort(key=lambda x: x[0], reverse=True)
        selected = [m for _, _, m in candidates[:max(1, min(MAX_ACTIVE, len(candidates)))]]

        if not selected:
            log.warning("No GPT models selected after filtering.")
            return results

        executor = getattr(self, "_executor", None)
        futures = {}
        
        def _process_model(m):
            mid_str = getattr(m, "model_name", None) or getattr(m, "model_path", None) or type(m).__name__
            try:
                raw, model_id, ok = self._call_model_with_timeout(m, prompt, timeout_per_model)
            except Exception as e:
                raw, model_id, ok = f"<EXCEPTION> {type(e).__name__}: {e}", mid_str, False
            text = _normalize_raw(raw)
            try:
                self._raw_by_model.setdefault(str(model_id), _Ring(RAW_RING_SIZE)).push(text)
            except Exception: pass
            if not ok or text in ("<TIMEOUT>", "<INVALID_MODEL>", ""):
                return {"decision": "HOLD", "confidence": 0.5, "tp_pips": 1.0, "sl_pips": 1.0, "model": str(model_id), "raw": text}
            try:
                dec, conf, tp, sl = self._parse_response_full(text)
            except Exception as e:
                log.warning(f"Model {model_id} parsing failed: {e} - fallback HOLD")
                dec, conf, tp, sl = "HOLD", 0.5, 1.0, 1.0
            dec = {"LONG":"BUY", "SHORT":"SELL"}.get(str(dec).upper() if dec else "HOLD", str(dec).upper())
            if dec not in ("BUY","SELL","HOLD"): dec="HOLD"
            conf = max(0.0, min(1.0, _safe_float(conf, 0.5)))
            tp = max(1.0, _safe_float(tp,1.0))
            sl = max(1.0, _safe_float(sl,1.0))
            log.info(f"Model {model_id} -> {dec} conf={conf:.3f} tp={tp} sl={sl}")
            return {"decision": dec, "confidence": conf, "tp_pips": tp, "sl_pips": sl, "model": str(model_id), "raw": text}

        # submit jobs
        if executor:
            for m in selected:
                try:
                    fut = executor.submit(_process_model, m)
                    futures[fut] = m
                except Exception as e:
                    mid = getattr(m, "model_name", None) or getattr(m, "model_path", None) or type(m).__name__
                    results.append({"decision":"HOLD","confidence":0.5,"tp_pips":1.0,"sl_pips":1.0,"model":str(mid),"raw":f"submit_error:{e}"})
            for fut in as_completed(list(futures.keys())):
                try: results.append(fut.result())
                except FuturesTimeoutError:
                    m = futures.get(fut); mid = getattr(m,"model_name",None) or getattr(m,"model_path",None) or type(m).__name__
                    results.append({"decision":"HOLD","confidence":0.5,"tp_pips":1.0,"sl_pips":1.0,"model":str(mid),"raw":"<FUTURE_TIMEOUT>"})
                except Exception as e:
                    m = futures.get(fut); mid = getattr(m,"model_name",None) or getattr(m,"model_path",None) or type(m).__name__
                    results.append({"decision":"HOLD","confidence":0.5,"tp_pips":1.0,"sl_pips":1.0,"model":str(mid),"raw":f"future_error:{e}"})
        else:
            # serial fallback
            for m in selected: results.append(_process_model(m))

        return results

    def _call_llama_safe(
        self,
        prompt: str,
        model_id: str = "llama",
        timeout: float = 60.0,
        max_attempts: int = 2
    ) -> tuple[str, float, float, float, str]:
        """
        Robust LLaMA wrapper with optional proxy pool.
        Returns (decision, confidence, tp_pips, sl_pips, model_id).
        Guarantees sanitized outputs and updates model stats/raw ring.
        """
        import random, time
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        start = time.time()
        timeout = float(timeout or 60.0)
        max_attempts = max(1, int(max_attempts))

        log = getattr(self, "logger", __import__("logging").getLogger(__name__))

        # sanitize outputs
        def _finalize(mid, dec_raw, conf_raw, tp_raw, sl_raw):
            dec = str(dec_raw).upper() if dec_raw is not None else "HOLD"
            dec = {"LONG":"BUY","SHORT":"SELL"}.get(dec, dec)
            if dec not in ("BUY","SELL","HOLD"): dec="HOLD"
            conf = max(0.0, min(1.0, _safe_float(conf_raw, 0.5)))
            tp = max(1.0, min(5000.0, _safe_float(tp_raw,1.0)))
            sl = max(1.0, min(5000.0, _safe_float(sl_raw,1.0)))
            if dec == "HOLD":
                conf, tp, sl = 0.5, 1.0, 1.0
            try: self._update_model_stat(mid, success=True)
            except Exception: pass
            log.info(f"LLaMA {mid} -> {dec} conf={conf:.3f} tp={tp} sl={sl} (latency={(time.time()-start):.3f}s)")
            return dec, conf, tp, sl, mid

        proxies = getattr(self, "llama_instances", None)
        semaphore = getattr(self, "_llama_semaphore", None)
        legacy_llama = getattr(self, "llama", None) if not proxies else None

        if not proxies and legacy_llama is None:
            log.warning(f"LLaMA ({model_id}) not configured — fallback HOLD")
            return "HOLD", 0.5, 1.0, 1.0, model_id

        proxies_list = list(proxies) if proxies else []
        last_exc = None

        for attempt in range(1, max_attempts + 1):
            attempt_start = time.time()
            remaining = max(0.01, timeout - (attempt_start - start))

            # select instance
            proxy = None
            mid_final = model_id

            if proxies_list:
                # choose healthiest proxy
                proxies_list.sort(key=lambda p: (
                    int(p.meta.get("fails",0)),
                    0 if p.meta.get("state")=="ready" else 1,
                    float(p.meta.get("cooldown_until",0)),
                    random.random()
                ))
                proxy = proxies_list[0]
                mid_final = f"{model_id}:{getattr(proxy,'index','X')}:{proxy.meta.get('type','proxy')}"

            inst = None
            try:
                if proxy:
                    now = time.time()
                    if proxy.meta.get("cooldown_until",0) > now:
                        # pick alternative if possible
                        alt = next((p for p in proxies_list if p is not proxy and p.meta.get("cooldown_until",0)<=now), None)
                        if alt:
                            proxy = alt
                            mid_final = f"{model_id}:{getattr(proxy,'index','X')}:{proxy.meta.get('type','proxy')}"
                    inst = proxy.create(n_ctx=getattr(self,"n_ctx",512),
                                        n_threads=getattr(self,"n_threads",1),
                                        timeout=max(1.0, remaining))
                else:
                    inst = legacy_llama
            except Exception as e:
                last_exc = e
                log.warning(f"LLaMA prepare failed for {mid_final} attempt {attempt}: {e}")
                time.sleep(0.05*attempt)
                continue

            # acquire semaphore
            acquired = False
            try:
                if semaphore:
                    acquired = semaphore.acquire(timeout=remaining)
                if semaphore and not acquired:
                    last_exc = TimeoutError("Could not acquire LLaMA semaphore")
                    log.warning(f"LLaMA {mid_final} attempt {attempt}: semaphore busy")
                    time.sleep(0.02*attempt)
                    continue

                # run generation
                fut = self._executor.submit(lambda: self._generate_from_model(inst, prompt))
                try:
                    raw = fut.result(timeout=remaining)
                except FuturesTimeoutError as te:
                    if fut: fut.cancel()
                    last_exc = te
                    log.warning(f"LLaMA {mid_final} attempt {attempt} TIMEOUT ({remaining:.3f}s)")
                    if proxy:
                        proxy.meta["fails"] = int(proxy.meta.get("fails",0))+1
                        proxy.meta["cooldown_until"]=time.time()+min(300,5*proxy.meta["fails"])
                    self._update_model_stat(mid_final, success=False)
                    time.sleep(0.05*attempt)
                    continue

                # normalize output text
                text = ""
                try:
                    if isinstance(raw,str): text=raw.strip()
                    elif isinstance(raw,dict):
                        if "choices" in raw and isinstance(raw["choices"],(list,tuple)):
                            text = " ".join(
                                str((c.get("message") or {}).get("content") or c.get("text") or c.get("content") or "")
                                for c in raw["choices"] if c
                            ).strip()
                        else:
                            text = str(raw.get("text") or raw.get("response") or json.dumps(raw))
                    elif isinstance(raw,(list,tuple)):
                        for e in raw:
                            if isinstance(e,str) and e.strip(): text=e.strip(); break
                            if isinstance(e,dict):
                                cand = e.get("text") or e.get("response") or json.dumps(e)
                                if cand: text=cand; break
                        if not text: text=" ".join(map(str,raw))
                    else: text=str(raw)
                except Exception:
                    text=str(raw)
                text=text.strip()
                if not text:
                    last_exc = ValueError("LLaMA returned empty")
                    log.warning(f"LLaMA {mid_final} attempt {attempt} returned empty")
                    if proxy:
                        proxy.meta["fails"] = int(proxy.meta.get("fails",0))+1
                        proxy.meta["cooldown_until"]=time.time()+min(300,5*proxy.meta["fails"])
                    self._update_model_stat(mid_final, success=False)
                    continue

                try:
                    self._raw_by_model.setdefault(mid_final,_Ring(getattr(self,"RAW_RING_SIZE",6))).push(text[:4000])
                except Exception: pass

                try:
                    dec, conf, tp, sl = self._parse_response_full(text)
                except Exception as e_parse:
                    log.warning(f"LLaMA {mid_final} parse failed: {e_parse} — fallback HOLD")
                    dec, conf, tp, sl = "HOLD",0.5,1.0,1.0

                return _finalize(mid_final, dec, conf, tp, sl)

            finally:
                if semaphore and acquired:
                    try: semaphore.release()
                    except Exception: pass

        log.warning(f"LLaMA {model_id} all attempts failed; last_exc={last_exc}")
        try: self._update_model_stat(model_id, success=False)
        except Exception: pass
        return "HOLD", 0.5, 1.0, 1.0, model_id

    def vote_trade(
        self,
        market_input,
        symbol: Optional[str] = None,
        timeout: Optional[float] = None,
        external_signal: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        🚀 ULTRA-AGGRESSIVE Trading AI Engine v4.0
        
        PRIORIDADE DE DECISÃO:
        1️⃣ external_signal (conf >= 0.25) → USA DIRETO
        2️⃣ Votação IA (max_score > 0.3)
        3️⃣ Estratégias internas
        4️⃣ Deep Q-Learning
        5️⃣ Indicadores simples (RSI+MA)
        6️⃣ HOLD (último recurso)
        
        NUNCA retorna HOLD se há oportunidade de trade!
        """

        import time, logging, os
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        log = getattr(self, "logger", logging.getLogger(__name__))
        start = time.time()
        votes = []
        
        # 🔥 PRIORIDADE 1: external_signal (SINAL TÉCNICO)
        # Se há sinal técnico com confiança >= 0.25, USA DIRETO!
        if external_signal and isinstance(external_signal, dict):
            ext_action = str(external_signal.get("action", "HOLD")).upper()
            ext_conf = float(external_signal.get("confidence", 0.0))
            
            # 🔥 HARDCORE FIX: Threshold reduzido: 0.15 (ao invés de 0.40)
            if ext_action != "HOLD" and ext_conf >= 0.15:
                log.info(f"🔥 PRIORIDADE 1: Usando sinal técnico direto | {ext_action} (conf={ext_conf:.2f})")
                
                entry_price = float(external_signal.get("price") or external_signal.get("entry_price", 0.0))
                tp_price = float(external_signal.get("take_profit", 0.0))
                sl_price = float(external_signal.get("stop_loss", 0.0))
                
                # Cálculo de pips
                if "JPY" in (symbol or ""):
                    multiplier = 1000
                else:
                    multiplier = 10000
                
                tp_pips = abs(entry_price - tp_price) * multiplier if (entry_price > 0 and tp_price > 0) else 150.0
                sl_pips = abs(entry_price - sl_price) * multiplier if (entry_price > 0 and sl_price > 0) else 75.0
                
                if tp_pips <= 0:
                    tp_pips = 150.0
                if sl_pips <= 0:
                    sl_pips = 75.0
                
                return {
                    "decision": ext_action,
                    "confidence": min(0.90, ext_conf),
                    "tp_pips": tp_pips,
                    "sl_pips": sl_pips,
                    "votes": [],
                    "elapsed": time.time() - start,
                    "reason": "priority_1_external_signal",
                    "ai_failed": False  # 🔥 HARDCORE FIX: flag para trading_bot_core
                }

        try:
            # =============== FEATURES ==================
            if isinstance(market_input, str):
                features = {"symbol": market_input}
            else:
                features = self._extract_features(market_input)

            features["symbol"] = symbol or features.get("symbol")

            model_timeout = float(timeout or getattr(self, "model_timeout", 6.0))
            max_total = float(getattr(self, "max_total_timeout", model_timeout))
            deadline = start + max(0.5, max_total)
            per_model = min(6.0, model_timeout)

            # =============== TASK LIST =================
            tasks = []

            for i, m in enumerate(getattr(self, "gpt_models", []) or []):
                mid = getattr(m, "model_name", None) or getattr(m, "model_path", None) or f"gpt{i}"
                tasks.append(("gpt", m, mid))

            if getattr(self, "llama", None) or getattr(self, "llama_instances", None):
                tasks.append(("llama", None, "llama"))

            # ✅ CORREÇÃO 5: Fallback inteligente sem modelos
            if not tasks and not getattr(self, "deep_q", None) and not (self.strategy_modules or {}):
                if external_signal and external_signal.get("action") != "HOLD":
                    log.info(f"🔥 SEM MODELOS - Usando sinal técnico direto: {external_signal.get('action')}")
                    
                    entry_price = float(external_signal.get("price") or external_signal.get("entry_price", 0.0))
                    tp_price = float(external_signal.get("take_profit", 0.0))
                    sl_price = float(external_signal.get("stop_loss", 0.0))
                    
                    if "JPY" in (symbol or ""):
                        multiplier = 1000
                    else:
                        multiplier = 10000
                    
                    tp_pips = abs(entry_price - tp_price) * multiplier if tp_price > 0 else 150.0
                    sl_pips = abs(entry_price - sl_price) * multiplier if sl_price > 0 else 75.0
                    
                    return {
                        "decision": external_signal.get("action", "HOLD"),
                        "confidence": float(external_signal.get("confidence", 0.5)),
                        "tp_pips": tp_pips,
                        "sl_pips": sl_pips,
                        "votes": [],
                        "elapsed": time.time() - start,
                        "reason": "no_models_using_external",
                        "ai_failed": True  # 🔥 HARDCORE FIX
                    }
                return {
                    "decision": "HOLD",
                    "confidence": 0.0,
                    "tp_pips": 150.0,
                    "sl_pips": 75.0,
                    "votes": [],
                    "elapsed": time.time() - start,
                    "reason": "no_models_no_external",
                    "ai_failed": True  # 🔥 HARDCORE FIX
                }

            max_concurrent = max(
                1,
                int(getattr(self, "max_concurrent_models", int(os.getenv("AI_MAX_CONCURRENT_MODELS", 3))))
            )

            prompt = self._build_prompt(features)

            # =============== EXECUTION =================
            pending = 0
            active = {}

            def submit(kind, model, mid, tout):
                if kind == "gpt":
                    return self._executor.submit(
                        lambda: ("gpt",) + self._call_gpt_safe(model, prompt, tout, mid)
                    )
                return self._executor.submit(
                    lambda: ("llama",) + self._call_llama_safe(prompt, model_id=mid, timeout=tout)
                )

            while (pending < len(tasks) or active) and time.time() < deadline:
                while pending < len(tasks) and len(active) < max_concurrent:
                    remaining = max(0.2, deadline - time.time())
                    kind, model, mid = tasks[pending]
                    fut = submit(kind, model, mid, min(per_model, remaining))
                    active[fut] = mid
                    pending += 1

                finished = []
                for fut in list(active):
                    try:
                        res = fut.result(timeout=0.05)
                        finished.append((fut, res))
                    except FuturesTimeoutError:
                        continue
                    except Exception as e:
                        finished.append((fut, e))

                for fut, result in finished:
                    mid = active.pop(fut, "unknown")

                    if isinstance(result, Exception):
                        votes.append({
                            "decision": "HOLD",
                            "confidence": 0.4,
                            "tp_pips": 1.0,
                            "sl_pips": 1.0,
                            "model": mid,
                            "raw": str(result)
                        })
                        continue

                    try:
                        if result[0] == "gpt":
                            _, raw, label, ok = result
                            if not ok:
                                raise ValueError("GPT invalid output")
                            text = self._normalize_raw(raw)
                            dec, conf, tp, sl = self._parse_response_safe(text)
                        else:
                            _, dec, conf, tp, sl, *_ = result
                            dec, conf, tp, sl = self._sanitize_trade(dec, conf, tp, sl)

                        votes.append({
                            "decision": dec,
                            "confidence": conf,
                            "tp_pips": tp,
                            "sl_pips": sl,
                            "model": mid,
                            "raw": result
                        })
                    except Exception as e:
                        log.warning("Parse failed %s: %s", mid, e)

            # =============== DEEP-Q ====================
            if getattr(self, "deep_q", None):
                try:
                    dq = self.query_deep_q(features)
                    if isinstance(dq, dict):
                        votes.append({**dq, "model": "deep_q", "raw": dq})
                except Exception as e:
                    log.warning("Deep-Q failed: %s", e)

            # =============== STRATEGIES ================
            for name, mod in (self.strategy_modules or {}).items():
                try:
                    fn = getattr(mod, "vote_trade", None) or getattr(mod, "analyze_market", None)
                    if callable(fn):
                        out = fn(market_input)
                        if isinstance(out, dict):
                            votes.append({
                                "decision": out.get("decision", "HOLD"),
                                "confidence": out.get("confidence", 0.5),
                                "tp_pips": out.get("tp_pips", 1.0),
                                "sl_pips": out.get("sl_pips", 1.0),
                                "model": f"strategy:{name}",
                                "raw": out
                            })
                except Exception as e:
                    log.warning("Strategy %s failed: %s", name, e)

            # =============== AGGREGATION ===============
            # ✅ CORREÇÃO 1: Incluir HOLD na agregação
            agg = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
            tp_vals, sl_vals = [], []

            for v in votes:
                dec = str(v.get("decision", "HOLD")).upper()
                # ✅ CORREÇÃO 2: Fallback para HOLD se decisão inválida
                if dec not in agg:
                    dec = "HOLD"
                conf = max(0.0, min(1.0, float(v.get("confidence", 0.5))))
                weight = float(self.get_model_weight(v["model"])) if hasattr(self, "get_model_weight") else 1.0
                score = conf * weight
                agg[dec] += score
                if score > 0:
                    tp_vals.append((float(v.get("tp_pips", 1.0)), score))
                    sl_vals.append((float(v.get("sl_pips", 1.0)), score))

            # ✅ CORREÇÃO 3: Modo híbrido melhorado com threshold 0.3 e cálculo de pips
            ext_action = str(external_signal.get("action", "HOLD")).upper() if external_signal else "HOLD"
            
            if max(agg.values()) <= 0.3 and external_signal and ext_action != "HOLD":
                ext_conf = float(external_signal.get("confidence", 0.0))
                
                if ext_conf >= 0.40:  # Confiança mínima do sinal técnico
                    log.info(f"⚠️ IA em silêncio (max_score={max(agg.values()):.2f}), mas Estratégia Técnica manda {ext_action} (conf={ext_conf:.2f}). EXECUTANDO MODO HÍBRIDO.")
                    
                    # ✅ CORREÇÃO 4: Calcula pips corretamente
                    entry_price = float(external_signal.get("price") or external_signal.get("entry_price", 0.0))
                    tp_price = float(external_signal.get("take_profit", 0.0))
                    sl_price = float(external_signal.get("stop_loss", 0.0))
                    
                    def calc_pips(entry, target, sym):
                        if entry <= 0 or target <= 0:
                            return 150.0 if "tp" in str(target) else 75.0
                        if "JPY" in (sym or ""):
                            multiplier = 1000
                        else:
                            multiplier = 10000
                        return abs(entry - target) * multiplier
                    
                    tp_pips = calc_pips(entry_price, tp_price, symbol)
                    sl_pips = calc_pips(entry_price, sl_price, symbol)
                    
                    if tp_pips <= 0:
                        tp_pips = 150.0
                    if sl_pips <= 0:
                        sl_pips = 75.0
                    
                    return {
                        "decision": ext_action,
                        "confidence": min(0.85, ext_conf),
                        "tp_pips": tp_pips,
                        "sl_pips": sl_pips,
                        "votes": votes,
                        "elapsed": time.time() - start,
                        "reason": "hybrid_technical_priority"
                    }
            
            # 🔥 PRIORIDADE 5: Indicadores Simples (RSI + MA)
            # Se IA falhou completamente, tenta gerar sinal baseado em indicadores
            if max(agg.values()) <= 0:
                log.info("🔄 PRIORIDADE 5: Tentando gerar sinal com indicadores simples...")
                simple_signal = self._simple_trend_signal(market_input, symbol)
                if simple_signal:
                    return {
                        "decision": simple_signal["decision"],
                        "confidence": simple_signal["confidence"],
                        "tp_pips": simple_signal.get("tp_pips", 150.0),
                        "sl_pips": simple_signal.get("sl_pips", 75.0),
                        "votes": votes,
                        "elapsed": time.time() - start,
                        "reason": "priority_5_simple_indicators"
                    }
                
                # ⚠️ Último recurso: HOLD
                log.warning("⚠️ Todas as prioridades falharam. Retornando HOLD.")
                return {
                    "decision": "HOLD",
                    "confidence": 0.0,
                    "tp_pips": 150.0,
                    "sl_pips": 75.0,
                    "votes": votes,
                    "elapsed": time.time() - start,
                    "reason": "all_priorities_failed"
                }

            decision = max(agg, key=agg.get)
            total = sum(agg.values())
            confidence = agg[decision] / max(total, 1e-6)
            
            # 🔥 HARDCORE FIX: Se AI retorna HOLD mas external_signal existe
            if decision == "HOLD" and external_signal:
                ext_action = str(external_signal.get("action", "HOLD")).upper()
                ext_conf = float(external_signal.get("confidence", 0.0))
                
                if ext_action != "HOLD" and ext_conf >= 0.15:
                    log.warning(f"⚠️ AI={decision}, Estratégia={ext_action}(conf={ext_conf:.2f}). USANDO ESTRATÉGIA.")
                    
                    entry_price = float(external_signal.get("price") or external_signal.get("entry_price", 0.0))
                    tp_price = float(external_signal.get("take_profit", 0.0))
                    sl_price = float(external_signal.get("stop_loss", 0.0))
                    
                    multiplier = 1000 if "JPY" in (symbol or "") else 10000
                    tp_pips = abs(entry_price - tp_price) * multiplier if tp_price > 0 else 150.0
                    sl_pips = abs(entry_price - sl_price) * multiplier if sl_price > 0 else 75.0
                    
                    return {
                        "decision": ext_action,
                        "confidence": ext_conf,
                        "tp_pips": max(1.0, tp_pips),
                        "sl_pips": max(1.0, sl_pips),
                        "votes": votes,
                        "elapsed": time.time() - start,
                        "reason": "ai_hold_fallback_to_technical",
                        "ai_failed": True
                    }

            def wavg(vals):
                sw = sum(w for _, w in vals)
                return sum(v * w for v, w in vals) / max(sw, 1e-6) if vals else 1.0

            tp_agg = wavg(tp_vals)
            sl_agg = wavg(sl_vals)

            if hasattr(self, "adjust_with_deep_q"):
                try:
                    decision, confidence, tp_agg, sl_agg = self.adjust_with_deep_q(
                        decision, confidence, tp_agg, sl_agg, features
                    )
                except Exception:
                    log.warning("adjust_with_deep_q failed")

            return {
                "decision": decision,
                "confidence": float(confidence),
                "tp_pips": float(tp_agg),
                "sl_pips": float(sl_agg),
                "votes": votes,
                "elapsed": time.time() - start,
                "ai_failed": False  # 🔥 HARDCORE FIX: AI funcionou
            }

        except Exception as e:
            log.error("vote_trade HARD FAIL: %s", e, exc_info=True)
            
            # 🔥 HARDCORE FIX: Fallback em exceção usa external_signal
            if external_signal and external_signal.get("action") != "HOLD":
                ext_conf = float(external_signal.get("confidence", 0.50))
                
                # 🔥 HARDCORE FIX: Threshold 0.15
                if ext_conf >= 0.15:
                    entry_price = float(external_signal.get("price") or external_signal.get("entry_price", 0.0))
                    tp_price = float(external_signal.get("take_profit", 0.0))
                    sl_price = float(external_signal.get("stop_loss", 0.0))
                    
                    multiplier = 1000 if "JPY" in (symbol or "") else 10000
                    tp_pips = abs(entry_price - tp_price) * multiplier if tp_price > 0 else 150.0
                    sl_pips = abs(entry_price - sl_price) * multiplier if sl_price > 0 else 75.0
                    
                    return {
                        "decision": external_signal.get("action", "HOLD"),
                        "confidence": ext_conf,
                        "tp_pips": max(1.0, tp_pips),
                        "sl_pips": max(1.0, sl_pips),
                        "votes": [],
                        "elapsed": time.time() - start,
                        "reason": "exception_fallback_to_technical",
                        "ai_failed": True  # 🔥 HARDCORE FIX
                    }
            
            return {
                "decision": "HOLD",
                "confidence": 0.0,
                "tp_pips": 150.0,
                "sl_pips": 75.0,
                "votes": [],
                "elapsed": time.time() - start,
                "reason": "hard_fail",
                "ai_failed": True  # 🔥 HARDCORE FIX
            }


    def _simple_trend_signal(self, market_input, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        🔄 Gerador de sinais baseado em indicadores simples (RSI + MA).
        
        Usado como FALLBACK quando:
        - IA retorna HOLD
        - external_signal não existe
        - Todas as estratégias falharam
        
        Lógica:
        - RSI < 30 + MA_fast > MA_slow → BUY
        - RSI > 70 + MA_fast < MA_slow → SELL
        - Caso contrário → None
        """
        log = getattr(self, "logger", logging.getLogger(__name__))
        
        try:
            # Converter para DataFrame
            if isinstance(market_input, pd.DataFrame):
                df = market_input.copy()
            elif isinstance(market_input, dict):
                if "close" in market_input:
                    df = pd.DataFrame(market_input)
                else:
                    return None
            else:
                return None
            
            if len(df) < 50:
                log.debug("_simple_trend_signal: dados insuficientes (< 50 candles)")
                return None
            
            # Calcular RSI
            close = df['close'].values if 'close' in df else df.iloc[:, 3].values
            delta = np.diff(close)
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)
            
            avg_gain = np.convolve(gain, np.ones(14)/14, mode='valid')
            avg_loss = np.convolve(loss, np.ones(14)/14, mode='valid')
            
            rs = avg_gain / (avg_loss + 1e-10)
            rsi = 100 - (100 / (1 + rs))
            
            if len(rsi) == 0:
                return None
            
            last_rsi = rsi[-1]
            
            # Calcular Moving Averages
            ma_fast = np.convolve(close, np.ones(10)/10, mode='valid')
            ma_slow = np.convolve(close, np.ones(30)/30, mode='valid')
            
            if len(ma_fast) == 0 or len(ma_slow) == 0:
                return None
            
            last_fast = ma_fast[-1]
            last_slow = ma_slow[-1]
            
            # Lógica de decisão
            action = None
            confidence = 0.0
            
            if last_rsi < 30 and last_fast > last_slow:
                action = "BUY"
                confidence = 0.35 + (30 - last_rsi) / 100  # 0.35 a 0.65
            elif last_rsi > 70 and last_fast < last_slow:
                action = "SELL"
                confidence = 0.35 + (last_rsi - 70) / 100  # 0.35 a 0.65
            
            if action:
                log.info(f"🔄 Sinal de indicadores simples | {action} | RSI={last_rsi:.1f} | MA_fast={last_fast:.5f} | MA_slow={last_slow:.5f} | conf={confidence:.2f}")
                return {
                    "decision": action,
                    "confidence": min(0.65, confidence),
                    "tp_pips": 150.0,
                    "sl_pips": 75.0,
                    "reason": "simple_indicators"
                }
            
            return None
            
        except Exception as e:
            log.debug(f"_simple_trend_signal failed: {e}")
            return None


    def evaluate_proposed_signal(
        self,
        payload: dict[str, Any],
        min_confidence: Optional[float] = None,
        timeout: float = 1.5
    ) -> dict[str, Any]:
        """
        Ultra-Hardcore evaluation of a proposed trade signal.

        Combines:
        - External signal (payload)
        - AI ensemble vote
        - Risk & sanity checks
        - MT4/MT5-safe normalization

        NEVER raises.
        """
        import time, math, logging

        start_time = time.time()
        log = getattr(self, "logger", logging.getLogger(__name__))

        SAFE_FALLBACK = {
            "approved": False,
            "adjusted_payload": payload if isinstance(payload, dict) else {},
            "reason": "fallback",
            "vote": {"decision": "HOLD", "confidence": 0.5, "votes": []},
            "elapsed": 0.0
        }

        try:
            # ------------------- BASIC VALIDATION -------------------
            if not isinstance(payload, dict):
                SAFE_FALLBACK["reason"] = "invalid_payload"
                SAFE_FALLBACK["elapsed"] = time.time() - start_time
                return SAFE_FALLBACK

            symbol = payload.get("symbol")
            if not isinstance(symbol, str) or not symbol.strip():
                SAFE_FALLBACK["reason"] = "missing_symbol"
                SAFE_FALLBACK["elapsed"] = time.time() - start_time
                return SAFE_FALLBACK

            symbol = symbol.strip().upper()

            # ------------------- MARKET CONTEXT -------------------
            market_input: Any = {"symbol": symbol}
            try:
                if hasattr(self, "get_symbol_data"):
                    df = self.get_symbol_data(symbol)
                    if df is not None:
                        market_input = df
            except Exception as e:
                log.debug(f"[AIManager] Market fetch failed for {symbol}: {e}")

            # ------------------- AI VOTE -------------------
            try:
                vote = self.vote_trade(
                    market_input,
                    symbol=symbol,
                    timeout=max(0.5, float(timeout)),
                    external_signal=payload
                ) or {}
            except Exception as e:
                log.warning(f"[AIManager] vote_trade failed: {e}")
                vote = {}

            vote_dec = str(vote.get("decision", "HOLD")).upper()
            if vote_dec not in ("BUY", "SELL"):
                vote_dec = "HOLD"

            try:
                vote_conf = float(vote.get("confidence", 0.5))
                vote_conf = max(0.0, min(1.0, vote_conf))
            except Exception:
                vote_conf = 0.5

            def safe_pips(v, default=1.0):
                try:
                    v = float(v)
                    if math.isnan(v) or math.isinf(v):
                        return default
                    return max(1.0, min(5000.0, v))
                except Exception:
                    return default

            vote_tp = safe_pips(vote.get("tp_pips", 1.0))
            vote_sl = safe_pips(vote.get("sl_pips", 1.0))

            # ------------------- MIN CONF -------------------
            try:
                min_conf = float(
                    min_confidence if min_confidence is not None
                    else getattr(self, "min_confidence", 0.55)
                )
                min_conf = max(0.0, min(1.0, min_conf))
            except Exception:
                min_conf = 0.55

            # ------------------- SIDE RECONCILIATION -------------------
            ext_side = payload.get("side") or payload.get("direction")
            ext_side = str(ext_side).upper() if isinstance(ext_side, str) else None

            if ext_side in ("BUY", "SELL"):
                side = ext_side
            else:
                side = vote_dec

            if side not in ("BUY", "SELL"):
                side = "HOLD"

            # ------------------- TP / SL -------------------
            tp_pips = safe_pips(
                payload.get("tp_pips") or payload.get("tp") or vote_tp,
                vote_tp
            )
            sl_pips = safe_pips(
                payload.get("sl_pips") or payload.get("sl") or vote_sl,
                vote_sl
            )

            # Hard safety
            if tp_pips < 1.0 or sl_pips < 1.0:
                side = "HOLD"

            # ------------------- CONFIDENCE MERGE -------------------
            ext_conf = payload.get("confidence")
            try:
                ext_conf = float(ext_conf)
                ext_conf = max(0.0, min(1.0, ext_conf))
            except Exception:
                ext_conf = None

            if ext_conf is not None:
                final_conf = vote_conf * 0.4 + ext_conf * 0.6
            else:
                final_conf = vote_conf

            final_conf = max(0.0, min(1.0, final_conf))

            # ------------------- APPROVAL -------------------
            if side in ("BUY", "SELL") and final_conf >= min_conf:
                approved = True
                reason = "approved_ai"
            elif side == "HOLD":
                approved = False
                reason = "rejected_hold"
            else:
                approved = False
                reason = "rejected_confidence"

            # ------------------- ADJUSTED PAYLOAD -------------------
            adjusted = dict(payload)
            adjusted.update({
                "symbol": symbol,
                "side": side,
                "confidence": final_conf,
                "tp_pips": tp_pips,
                "sl_pips": sl_pips,
                "ai_decision": vote_dec,
                "ai_confidence": vote_conf,
                "ai_votes": vote.get("votes", []),
            })

            return {
                "approved": bool(approved),
                "adjusted_payload": adjusted,
                "reason": reason,
                "vote": vote,
                "elapsed": time.time() - start_time
            }

        except Exception:
            log.exception("[AIManager] evaluate_proposed_signal HARD FAIL")
            SAFE_FALLBACK["elapsed"] = time.time() - start_time
            SAFE_FALLBACK["reason"] = "exception"
            return SAFE_FALLBACK


    # Alias seguro
    def evaluate_signal(self, payload: dict[str, Any], **kwargs) -> dict[str, Any]:
        import time, logging

        log = getattr(self, "logger", logging.getLogger(__name__))
        start = time.time()

        # Defensive copy + type guard
        if not isinstance(payload, dict):
            log.warning(
                f"evaluate_signal received invalid payload type: {type(payload)}; forcing empty dict"
            )
            payload = {}
        else:
            payload = dict(payload)  # evita mutação externa

        try:
            result = self.evaluate_proposed_signal(payload, **kwargs)

            # Sanity check mínimo do retorno
            if not isinstance(result, dict):
                raise ValueError("evaluate_proposed_signal returned non-dict")

            # Garantir campos críticos
            result.setdefault("approved", False)
            result.setdefault("reason", "unknown")
            result.setdefault("vote", {"decision": "HOLD", "confidence": 0.5, "votes": []})
            result.setdefault("adjusted_payload", payload)
            result.setdefault("elapsed", time.time() - start)

            return result

        except Exception:
            log.exception(f"evaluate_signal HARD FAIL for payload={payload}")

            return {
                "approved": False,
                "adjusted_payload": payload,
                "reason": "error_alias",
                "vote": {"decision": "HOLD", "confidence": 0.5, "votes": []},
                "elapsed": time.time() - start
            }


    def evaluate_signal_socket(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Entrada única via SOCKET.
        Decide se há trade ou não, com fallback seguro e logging detalhado.
        NUNCA levanta exceção.

        Inclui fallback robusto de market data, clamps de pips/confiança e logging completo.
        """
        import time
        import logging

        log = getattr(self, "logger", logging.getLogger(__name__))
        start_time = time.time()

        SAFE_FALLBACK = {
            "approved": False,
            "adjusted_payload": {},
            "reason": "fallback",
            "meta": {},
            "elapsed": 0.0
        }

        try:
            # -------------------- PAYLOAD SAFE --------------------
            if not isinstance(payload, dict):
                log.warning(
                    f"evaluate_signal_socket received invalid payload type: {type(payload)}; forcing empty dict"
                )
                payload = {}
            else:
                payload = dict(payload)  # cópia defensiva

            symbol = payload.get("symbol")
            if not isinstance(symbol, str) or not symbol:
                return {
                    **SAFE_FALLBACK,
                    "reason": "missing_symbol",
                    "elapsed": time.time() - start_time
                }

            # -------------------- MARKET DATA Fallback --------------------
            market = payload.get("market_data") or payload.get("features")
            if not isinstance(market, dict):
                # tenta pegar do cache interno
                market = getattr(self, "_last_market_cache", {}).get(symbol, {"symbol": symbol})
            # ainda garante valores mínimos
            bid = market.get("bid")
            ask = market.get("ask")
            if bid is None or ask is None:
                bid, ask = 0.0, 0.0
            market_safe = {
                "symbol": symbol,
                "bid": bid,
                "ask": ask,
                "time": market.get("time", time.time()),
                **{k: v for k, v in market.items() if k not in ("symbol", "bid", "ask", "time")}
            }
            # atualiza cache leve
            self._last_market_cache = getattr(self, "_last_market_cache", {})
            self._last_market_cache[symbol] = market_safe

            # -------------------- CHAMADA CENTRAL AO MODELO --------------------
            try:
                result = self.ask_model(
                    symbol=symbol,
                    market_input=market_safe,
                    mode="auto",
                    timeout=float(getattr(self, "model_timeout", 5.0))
                ) or {}
            except Exception as e:
                log.warning(f"[SOCKET] ask_model failed for {symbol}: {e}")
                result = {}

            # -------------------- NORMALIZAÇÃO --------------------
            decision = str(result.get("decision", "HOLD")).strip().upper()
            if decision not in ("BUY", "SELL", "HOLD"):
                decision = "HOLD"

            try:
                confidence = float(result.get("confidence", 0.0))
            except Exception:
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))

            def _safe_pips(v, default=1.0):
                try:
                    v = float(v)
                except Exception:
                    v = default
                return max(1.0, min(5000.0, v))

            tp_pips = _safe_pips(result.get("tp_pips", payload.get("tp_pips", 1.0)))
            sl_pips = _safe_pips(result.get("sl_pips", payload.get("sl_pips", 1.0)))

            # -------------------- APROVAÇÃO --------------------
            min_conf = float(getattr(self, "min_confidence", 0.5))
            approved = decision in ("BUY", "SELL") and confidence >= min_conf

            reason = (
                "ai_decision"
                if approved
                else "rejected_confidence"
                if decision in ("BUY", "SELL")
                else "rejected_hold"
            )

            # -------------------- PAYLOAD AJUSTADO --------------------
            adjusted = dict(payload)
            adjusted.update({
                "symbol": symbol,
                "side": decision,
                "confidence": confidence,
                "tp_pips": tp_pips,
                "sl_pips": sl_pips,
                "ai_decision": decision,
                "ai_confidence": confidence,
                "ai_votes": result.get("votes", []),
                "market_data": market_safe
            })

            elapsed = time.time() - start_time

            # -------------------- RETORNO FINAL --------------------
            return {
                "approved": bool(approved),
                "adjusted_payload": adjusted,
                "reason": reason,
                "meta": {
                    "model_result": result,
                    "elapsed": elapsed
                },
                "elapsed": elapsed
            }

        except Exception:
            elapsed = time.time() - start_time
            log.exception("evaluate_signal_socket HARD FAIL")
            return {
                **SAFE_FALLBACK,
                "reason": "exception",
                "elapsed": elapsed,
                "meta": {"elapsed": elapsed}
            }


    def enforce_signal(
        self,
        mt5_comm: Any,
        symbol: str,
        min_confidence: Optional[float] = None,
        timeout: float = 2.0
    ) -> Dict[str, Any]:
        """
        Ultra-Hardcore signal enforcer (PRODUCTION).
        - Orquestração
        - Segurança
        - Gestão de risco
        - Execução MT5
        NUNCA levanta exceção.
        """
        import time, logging

        log = getattr(self, "logger", logging.getLogger(__name__))
        start_time = time.time()

        SAFE_FAIL = {
            "executed": False,
            "symbol": symbol,
            "vote": {},
            "reason": "fallback",
            "elapsed": 0.0,
        }

        try:
            # ==================== 1) BASIC CHECK ====================
            if not symbol or not isinstance(symbol, str) or mt5_comm is None:
                return {**SAFE_FAIL, "reason": "missing_symbol_or_mt5"}

            # ==================== 2) MARKET DATA ====================
            market_data = None
            try:
                if hasattr(mt5_comm, "get_symbol_data"):
                    market_data = mt5_comm.get_symbol_data(symbol)
            except Exception as e:
                log.debug("[enforce] get_symbol_data failed %s: %s", symbol, e)

            # Fallback mínimo seguro
            if not isinstance(market_data, dict):
                tick = None
                try:
                    tick = mt5_comm.symbol_info_tick(symbol)
                except Exception:
                    pass

                market_data = {
                    "symbol": symbol,
                    "bid": getattr(tick, "bid", None),
                    "ask": getattr(tick, "ask", None),
                    "time": time.time(),
                }

            if market_data.get("bid") is None and market_data.get("ask") is None:
                return {**SAFE_FAIL, "reason": "no_price_data"}

            # Cache leve
            self._last_market_cache = getattr(self, "_last_market_cache", {})
            self._last_market_cache[symbol] = market_data

            # ==================== 3) AI VOTE ====================
            try:
                vote = self.vote_trade(
                    market_data,
                    symbol=symbol,
                    timeout=max(0.5, float(timeout))
                ) or {}
            except Exception as e:
                log.warning("[enforce] vote_trade exception: %s", e)
                return {**SAFE_FAIL, "reason": "vote_exception"}

            if not isinstance(vote, dict):
                return {**SAFE_FAIL, "reason": "invalid_vote_type"}

            decision = str(vote.get("decision", "HOLD")).upper()
            if decision not in ("BUY", "SELL", "HOLD"):
                return {**SAFE_FAIL, "reason": "invalid_vote_decision"}

            # ==================== 3.1) CONFIDENCE NORMALIZATION ====================
            try:
                confidence = float(vote.get("confidence", 0.0))
            except Exception:
                confidence = 0.0

            confidence = max(0.0, min(1.0, confidence))

            # REGRA CRÍTICA: HOLD nunca tem confiança alta
            if decision == "HOLD":
                confidence = min(confidence, 0.15)

            # ==================== 4) PROPOSED PAYLOAD ====================
            proposed = {
                "symbol": symbol,
                "side": decision,
                "confidence": confidence,
                "tp_pips": vote.get("tp_pips"),
                "sl_pips": vote.get("sl_pips"),
            }

            # ==================== 5) AI EVALUATION LAYER ====================
            eval_res = self.evaluate_proposed_signal(
                proposed,
                min_confidence=min_confidence,
                timeout=timeout
            ) or {}

            if not eval_res.get("approved"):
                return {
                    "executed": False,
                    "symbol": symbol,
                    "vote": vote,
                    "reason": eval_res.get("reason", "not_approved"),
                    "elapsed": time.time() - start_time,
                }

            adj = eval_res.get("adjusted_payload", {})
            side = str(adj.get("side", "HOLD")).upper()

            if side not in ("BUY", "SELL"):
                return {
                    "executed": False,
                    "symbol": symbol,
                    "vote": vote,
                    "reason": "hold_after_evaluation",
                    "elapsed": time.time() - start_time,
                }

            # ==================== 6) COOLDOWN / ANTI-SPAM ====================
            now = time.time()
            self._last_trade_ts = getattr(self, "_last_trade_ts", {})
            cooldown = float(getattr(self, "trade_cooldown", 15.0))
            last_ts = float(self._last_trade_ts.get(symbol, 0.0))

            if now - last_ts < cooldown:
                return {
                    "executed": False,
                    "symbol": symbol,
                    "vote": vote,
                    "reason": "cooldown_active",
                    "elapsed": time.time() - start_time,
                }

            # ==================== 7) EXECUTION ====================
            result = mt5_comm.execute_trade(adj)
            self._last_trade_ts[symbol] = now

            return {
                "executed": bool(result),
                "symbol": symbol,
                "vote": vote,
                "result": result,
                "elapsed": time.time() - start_time,
            }

        except Exception as e:
            log.exception("[enforce] HARD FAIL %s: %s", symbol, e)
            return {
                **SAFE_FAIL,
                "reason": "hard_exception",
                "elapsed": time.time() - start_time,
            }


            # ==================== 7) NORMALIZE TP / SL ====================
            def _safe_pips(v):
                try:
                    v = float(v)
                except Exception:
                    return None
                return max(1.0, min(5000.0, v))

            tp_pips = _safe_pips(adj.get("tp_pips"))
            sl_pips = _safe_pips(adj.get("sl_pips"))

            if tp_pips is None or sl_pips is None:
                return {**SAFE_FAIL, "reason": "invalid_sl_tp"}

            # ==================== 8) RISK-AWARE VOLUME ====================
            DEFAULT_VOLUME = float(getattr(self, "default_volume", 0.01))
            volume = DEFAULT_VOLUME

            try:
                acc = mt5_comm.get_account_info() or {}
                balance = float(acc.get("balance", 0.0))
                risk_pct = float(getattr(self, "risk_per_trade", 0.005))

                symbol_info = mt5_comm.symbol_info(symbol)
                pip_value = float(getattr(symbol_info, "trade_tick_value", 1.0)) or 1.0

                raw_vol = (balance * risk_pct) / max(sl_pips * pip_value, 1e-6)

                volume = min(
                    max(DEFAULT_VOLUME, raw_vol),
                    float(getattr(self, "max_volume", 0.1))
                )
            except Exception as e:
                log.debug("[enforce] volume calc failed: %s", e)
                volume = DEFAULT_VOLUME

            # ==================== 9) FINAL EXECUTION (LOCKED) ====================
            if not hasattr(self, "_trade_lock"):
                self._trade_lock = threading.Lock()

            with self._trade_lock:
                try:
                    res = mt5_comm.place_trade(
                        symbol=symbol,
                        side=side,
                        volume=volume,
                        tp_pips=tp_pips,
                        sl_pips=sl_pips
                    ) or {}
                except Exception as e:
                    log.warning("[enforce] place_trade failed %s: %s", symbol, e)
                    return {
                        "executed": False,
                        "symbol": symbol,
                        "vote": vote,
                        "reason": "execution_failed",
                        "error": str(e),
                        "elapsed": time.time() - start_time,
                    }

            executed = bool(res.get("ok", False))
            if executed:
                self._last_trade_ts[symbol] = now

            # ==================== 10) RESULT + AUDIT ====================
            log.info(
                "[TRADE] %s %s vol=%.3f sl=%.1f tp=%.1f conf=%.2f ok=%s",
                symbol, side, volume, sl_pips, tp_pips, confidence, executed
            )

            return {
                "executed": executed,
                "symbol": symbol,
                "side": side,
                "volume": volume,
                "tp_pips": tp_pips,
                "sl_pips": sl_pips,
                "confidence": confidence,
                "vote": vote,
                "mt5_result": res,
                "elapsed": time.time() - start_time,
            }

        except Exception as e:
            log.exception("[enforce] HARD FAIL %s", symbol)
            SAFE_FAIL["reason"] = "exception"
            SAFE_FAIL["error"] = str(e)
            SAFE_FAIL["elapsed"] = time.time() - start_time
            return SAFE_FAIL


    def _call_model_safe(
        self,
        model,
        prompt: str,
        timeout: float = 10.0,
        model_id: str = None
    ) -> Tuple[str, float, float, float, str]:
        """
        Hardcore-safe model invocation.
        Returns: (decision, confidence, tp_pips, sl_pips, model_id)
        NEVER raises.
        """
        import time
        import concurrent.futures
        import logging

        log = getattr(self, "logger", logging.getLogger(__name__))

        # -------------------- resolve model_id --------------------
        if model_id is None:
            model_id = (
                getattr(model, "model_name", None)
                or getattr(model, "model_path", None)
                or getattr(model, "__class__", type(model)).__name__
            )
        model_id = str(model_id)

        # -------------------- hard fallbacks --------------------
        FALLBACK_DECISION = "HOLD"
        FALLBACK_CONF = 0.5
        FALLBACK_TP = 1.0
        FALLBACK_SL = 1.0

        # -------------------- model missing --------------------
        if model is None:
            log.warning("[AI] %s is None — fallback HOLD", model_id)
            self._update_model_stat(model_id, success=False)
            return FALLBACK_DECISION, FALLBACK_CONF, FALLBACK_TP, FALLBACK_SL, model_id

        # -------------------- trim prompt --------------------
        try:
            n_ctx = int(getattr(self, "n_ctx", 2048))
            tokens = str(prompt).split()
            if len(tokens) > n_ctx:
                prompt = " ".join(tokens[-n_ctx:])
        except Exception:
            pass

        # -------------------- isolated invoke --------------------
        def _invoke():
            try:
                if hasattr(model, "generate"):
                    return model.generate(prompt)
                elif callable(model):
                    return model(prompt)
                else:
                    raise RuntimeError("Model is not callable")
            except Exception as e:
                return {"_error": str(e)}

        start_ts = time.time()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exe:
                fut = exe.submit(_invoke)
                raw_output = fut.result(timeout=timeout)

        except concurrent.futures.TimeoutError:
            log.warning("[AI][TIMEOUT] %s exceeded %.2fs", model_id, timeout)
            self._update_model_stat(model_id, success=False)
            return FALLBACK_DECISION, FALLBACK_CONF, FALLBACK_TP, FALLBACK_SL, model_id

        except Exception as e:
            log.error("[AI][CRASH] %s: %s", model_id, e)
            self._update_model_stat(model_id, success=False)
            return FALLBACK_DECISION, FALLBACK_CONF, FALLBACK_TP, FALLBACK_SL, model_id

        latency = time.time() - start_ts

        # -------------------- normalize output --------------------
        if isinstance(raw_output, dict) and "_error" in raw_output:
            log.warning("[AI][ERROR] %s returned error: %s", model_id, raw_output["_error"])
            self._update_model_stat(model_id, success=False, latency=latency)
            return FALLBACK_DECISION, FALLBACK_CONF, FALLBACK_TP, FALLBACK_SL, model_id

        text = raw_output.get("text") if isinstance(raw_output, dict) else str(raw_output)

        if not isinstance(text, str) or not text.strip():
            log.warning("[AI] %s returned empty output", model_id)
            self._update_model_stat(model_id, success=False, latency=latency)
            return FALLBACK_DECISION, FALLBACK_CONF, FALLBACK_TP, FALLBACK_SL, model_id

        # -------------------- parse --------------------
        try:
            decision, confidence, tp_pips, sl_pips = self._parse_response_full(text)
            parsed_ok = True
        except Exception as e:
            log.debug("[AI] %s parse failed: %s", model_id, e)
            decision, confidence, tp_pips, sl_pips = (
                FALLBACK_DECISION,
                FALLBACK_CONF,
                FALLBACK_TP,
                FALLBACK_SL,
            )
            parsed_ok = False

        # -------------------- clamps --------------------
        decision = str(decision).upper()
        if decision not in ("BUY", "SELL", "HOLD"):
            decision = FALLBACK_DECISION

        try:
            confidence = float(confidence)
        except Exception:
            confidence = FALLBACK_CONF
        confidence = max(0.0, min(confidence, 1.0))

        try:
            tp_pips = max(1.0, float(tp_pips))
        except Exception:
            tp_pips = FALLBACK_TP

        try:
            sl_pips = max(1.0, float(sl_pips))
        except Exception:
            sl_pips = FALLBACK_SL

        # -------------------- stats --------------------
        self._update_model_stat(
            model_id,
            success=parsed_ok,
            latency=latency
        )

        return decision, confidence, tp_pips, sl_pips, model_id


        # -------------------- runner that calls underlying generator --------------------
        def _call_generator():
            try:
                return self._generate_from_model(model, prompt)
            except Exception as e:
                # surface exception to caller via sentinel raise
                raise

        # -------------------- run via executor (preferred) or thread fallback --------------------
        start_t = time.time()
        raw_out = None
        ok = False
        exc_info = None

        executor = getattr(self, "_executor", None)
        fut = None
        try:
            if executor is not None:
                fut = executor.submit(_call_generator)
                try:
                    raw_out = fut.result(timeout=timeout)
                    ok = True
                except FuturesTimeoutError:
                    try:
                        fut.cancel()
                    except Exception:
                        pass
                    exc_info = TimeoutError(f"timeout after {timeout}s")
                    ok = False
                    log.warning(f"{model_id} TIMEOUT after {timeout}s (executor)")
                except Exception as e:
                    exc_info = e
                    ok = False
            else:
                # fallback: thread + join
                result_container = {"ok": False, "value": None, "exc": None}

                def _thread_runner():
                    try:
                        v = _call_generator()
                        result_container["ok"] = True
                        result_container["value"] = v
                    except Exception as e:
                        result_container["exc"] = e

                th = threading.Thread(target=_thread_runner, daemon=True)
                th.start()
                th.join(timeout)
                if th.is_alive():
                    exc_info = TimeoutError(f"timeout after {timeout}s (thread)")
                    try:
                        # best-effort: can't kill thread
                        pass
                    except Exception:
                        pass
                    ok = False
                    log.warning(f"{model_id} TIMEOUT after {timeout}s (thread fallback)")
                else:
                    if result_container["ok"]:
                        raw_out = result_container["value"]
                        ok = True
                    else:
                        exc_info = result_container["exc"]
                        ok = False

        except Exception as e_outer:
            exc_info = e_outer
            ok = False

        latency = time.time() - start_t

        # -------------------- if failure mark stats and return fallback --------------------
        if not ok:
            # update stats as failure
            try:
                self._update_model_stat(model_id, success=False)
            except Exception:
                pass

            # log exception detail once
            if exc_info is not None:
                log.warning(f"{model_id} call failed: {type(exc_info).__name__}: {exc_info}")
            return "HOLD", 0.5, 1.0, 1.0, model_id

        # -------------------- normalize raw_out to text or detect tuple shaped response --------------------
        text = ""
        try:
            # If model already returned a parsed tuple/list of values (dec,conf,tp,sl[,mid])
            if isinstance(raw_out, (list, tuple)):
                # common pattern: (dec, conf, tp, sl) or (dec, conf, tp, sl, mid)
                if len(raw_out) >= 4 and all(True for _ in range(4)):  # quick length check
                    maybe_dec = raw_out[0]
                    maybe_conf = raw_out[1]
                    maybe_tp = raw_out[2]
                    maybe_sl = raw_out[3]
                    maybe_mid = raw_out[4] if len(raw_out) >= 5 else model_id
                    # try to coerce
                    dec = str(maybe_dec).upper() if maybe_dec is not None else "HOLD"
                    dec = {"LONG": "BUY", "SHORT": "SELL"}.get(dec, dec)
                    conf = _safe_float(maybe_conf, 0.5)
                    tp = _safe_float(maybe_tp, 1.0)
                    sl = _safe_float(maybe_sl, 1.0)
                    mid = str(maybe_mid or model_id)
                    dec = dec if dec in ("BUY", "SELL", "HOLD") else "HOLD"
                    if dec == "HOLD":
                        conf, tp, sl = 0.5, 1.0, 1.0
                    # push raw summary to ring and update stats as success
                    try:
                        self._raw_by_model.setdefault(mid, _Ring(RAW_RING_SIZE)).push(str(raw_out)[:4000])
                    except Exception:
                        pass
                    try:
                        self._update_model_stat(mid, success=True)
                    except Exception:
                        pass
                    log.info(f"{mid} -> {dec} conf={conf:.3f} tp={tp} sl={sl} (latency={latency:.3f}s)")
                    return dec, conf, tp, sl, mid

                # otherwise fallback to turning list into text
                text = " ".join(map(str, raw_out))

            elif isinstance(raw_out, dict):
                # prefer structured keys if present
                # try to extract fields directly
                dec = raw_out.get("decision") or raw_out.get("action") or raw_out.get("label")
                conf = raw_out.get("confidence") or raw_out.get("conf")
                tp = raw_out.get("tp") or raw_out.get("tp_pips") or raw_out.get("take_profit")
                sl = raw_out.get("sl") or raw_out.get("sl_pips") or raw_out.get("stop_loss")
                if any(x is not None for x in (dec, conf, tp, sl)):
                    dec = str(dec).upper() if dec is not None else "HOLD"
                    dec = {"LONG": "BUY", "SHORT": "SELL"}.get(dec, dec)
                    conf = _safe_float(conf, 0.5)
                    tp = _safe_float(tp, 1.0)
                    sl = _safe_float(sl, 1.0)
                    mid = raw_out.get("model") or model_id
                    mid = str(mid)
                    dec = dec if dec in ("BUY", "SELL", "HOLD") else "HOLD"
                    if dec == "HOLD":
                        conf, tp, sl = 0.5, 1.0, 1.0
                    try:
                        self._raw_by_model.setdefault(mid, _Ring(RAW_RING_SIZE)).push(json.dumps(raw_out)[:4000])
                    except Exception:
                        pass
                    try:
                        self._update_model_stat(mid, success=True)
                    except Exception:
                        pass
                    log.info(f"{mid} -> {dec} conf={conf:.3f} tp={tp} sl={sl} (latency={latency:.3f}s)")
                    return dec, conf, tp, sl, mid
                # else fallback to text form
                text = json.dumps(raw_out, ensure_ascii=False)

            elif isinstance(raw_out, (str, bytes)):
                text = raw_out.decode("utf-8", errors="replace") if isinstance(raw_out, bytes) else raw_out

            else:
                text = str(raw_out)
        except Exception as e_norm:
            # fallback
            text = str(raw_out)
            log.debug(f"{model_id} normalization warning: {e_norm}")

        text = (text or "").strip()

        # -------------------- store raw in ring (trim) --------------------
        MAX_RAW = int(os.environ.get("AI_MAX_RAW_STORE", "4000"))
        try:
            store_text = text if len(text) <= MAX_RAW else text[: int(MAX_RAW * 0.6)] + " ...[TRIMMED]... " + text[- int(MAX_RAW * 0.2):]
            self._raw_by_model.setdefault(model_id, _Ring(RAW_RING_SIZE)).push(store_text)
        except Exception:
            pass

        # -------------------- parse final decision/conf/tp/sl via parser --------------------
        try:
            dec, conf, tp, sl = self._parse_response_full(text)
        except Exception as e:
            log.warning(f"{model_id} parsing error: {e}; fallback to HOLD")
            dec, conf, tp, sl = "HOLD", 0.5, 1.0, 1.0

        # -------------------- sanitize values --------------------
        dec = dec if dec in ("BUY", "SELL", "HOLD") else "HOLD"
        conf = float(max(0.0, min(1.0, _safe_float(conf, 0.5))))
        tp = float(max(1.0, min(5000.0, _safe_float(tp, 1.0))))
        sl = float(max(1.0, min(5000.0, _safe_float(sl, 1.0))))

        if dec == "HOLD":
            conf, tp, sl = 0.5, 1.0, 1.0

        # -------------------- mark success and log --------------------
        try:
            self._update_model_stat(model_id, success=True)
        except Exception:
            pass

        log.info(f"{model_id} -> {dec} conf={conf:.3f} tp={tp} sl={sl} (latency={latency:.3f}s, raw_len={len(text)})")

        return dec, conf, tp, sl, model_id



    def _call_gpt_safe(self, model: Any, prompt: str, timeout: float, model_id: Optional[str] = None) -> Tuple[str, str, bool]:
        """
        Robust wrapper to call GPT-style models safely.

        - Accepts a single model (instance or path) OR a list/tuple of models/paths.
        - If a list is provided: each model will be attempted up to `rounds` times (default 3),
        calling each model in sequence each round (i.e. every model "entra" em cada round).
        - Returns (raw_text, model_label, ok). If multiple models used, returns first non-empty result found;
        model_label will indicate which model produced it (or aggregated label on failure).
        """
        import json
        import concurrent.futures
        import time
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        logger = getattr(self, "logger", None) or globals().get("log") or logging.getLogger("AIManager")

        # Normalize prompt
        if prompt is None:
            prompt = ""
        if not isinstance(prompt, str):
            try:
                prompt = str(prompt)
            except Exception:
                prompt = ""

        # Trim extremely large prompts (protect some CLIs / mmap)
        try:
            words = prompt.split()
            if len(words) > 16384:
                prompt = " ".join(words[-4096:])
        except Exception:
            pass

        # Configurable constants
        rounds = int(os.environ.get("AI_MODEL_ROUNDS", "3"))            # how many rounds to run for each model (default 3)
        per_model_attempts = int(os.environ.get("AI_MODEL_ATTEMPTS", "3"))  # attempts per model per round (conservative)
        model_call_timeout = float(timeout or getattr(self, "model_timeout", 30.0))
        backoff_default = float(getattr(self, "_model_backoff_seconds", 30.0))

        # Support passing a list/tuple of models
        multi_models = False
        models_list = []
        if isinstance(model, (list, tuple)):
            multi_models = True
            models_list = list(model)
        else:
            models_list = [model]

        # derive a composite model_label for backoff lookups if single
        base_label = model_id or (getattr(model, "model_name", None) or getattr(model, "name", None) or str(model))
        base_label = str(base_label) if base_label is not None else "unknown_model"

        # Ensure backoff dict
        try:
            if not hasattr(self, "_model_backoff") or self._model_backoff is None:
                self._model_backoff = {}
        except Exception:
            self._model_backoff = {}

        # helper: check per-model backoff
        def _is_on_backoff(label):
            try:
                next_ok = float(self._model_backoff.get(label, 0.0))
                return time.time() < next_ok
            except Exception:
                return False

        # helper: set backoff
        def _set_backoff(label, secs=backoff_default):
            try:
                self._model_backoff[label] = time.time() + float(secs)
            except Exception:
                pass

        # helper: extract text from many shapes
        def _extract_text(raw) -> str:
            try:
                if raw is None: return ""
                if isinstance(raw, str): return raw.strip()
                if isinstance(raw, dict):
                    for key in ("text", "content", "response", "generated_text", "result"):
                        if key in raw and raw[key]:
                            return str(raw[key]).strip()
                    if "choices" in raw and isinstance(raw["choices"], (list, tuple)) and raw["choices"]:
                        pieces = []
                        for c in raw["choices"]:
                            if isinstance(c, dict):
                                if "message" in c and isinstance(c["message"], dict) and c["message"].get("content"):
                                    pieces.append(str(c["message"]["content"]))
                                elif c.get("text"):
                                    pieces.append(str(c.get("text")))
                                elif c.get("content"):
                                    pieces.append(str(c.get("content")))
                                else:
                                    pieces.append(json.dumps(c, ensure_ascii=False))
                            else:
                                pieces.append(str(c))
                        return " ".join(pieces).strip()
                    if "data" in raw:
                        return _extract_text(raw["data"])
                    # fallback
                    return json.dumps(raw, ensure_ascii=False)
                if isinstance(raw, (list, tuple)):
                    parts = []
                    for x in raw:
                        t = _extract_text(x)
                        if t: parts.append(t)
                    return " ".join(parts).strip()
                # generator/iterable fallback
                if hasattr(raw, "__iter__") and not isinstance(raw, (str, bytes, dict)):
                    try:
                        parts = [str(chunk) for chunk in raw]
                        return " ".join(parts).strip()
                    except Exception:
                        pass
                return str(raw).strip()
            except Exception:
                try:
                    return str(raw)
                except Exception:
                    return ""

        # helper: if path -> try lazy instantiate with GPT4All (best-effort)
        def _lazy_instantiate_if_path(m):
            lazy_inst = m
            if isinstance(m, (str, os.PathLike)):
                p = os.path.abspath(str(m))
                try:
                    if os.path.isdir(p):
                        ggufs = []
                        for root, _, files in os.walk(p):
                            for f in files:
                                if f.lower().endswith(".gguf"):
                                    ggufs.append(os.path.join(root, f))
                        ggufs.sort()
                        if ggufs:
                            p = ggufs[0]
                        else:
                            return ("<NO_GGUF_IN_DIR>", None)
                except Exception as e:
                    return (f"<BAD_PATH:{e}>", None)
                if not p.lower().endswith(".gguf"):
                    return (f"<INVALID_MODEL_PATH:{p}>", None)
                # try GPT4All lazy load
                if "GPT4All" not in globals() or globals().get("GPT4All") is None:
                    return (f"<NO_GPT4ALL_AVAILABLE:{p}>", None)
                # attempt multiple inits
                init_attempts = [
                    lambda: GPT4All(model_path=p, n_threads=int(getattr(self, "n_threads", 4)), n_ctx=int(getattr(self, "n_ctx", 512))),
                    lambda: GPT4All(p),
                    lambda: GPT4All(model=p),
                    lambda: GPT4All(model_name=os.path.basename(p), model_path=os.path.dirname(p), n_threads=int(getattr(self, "n_threads", 4)), n_ctx=int(getattr(self, "n_ctx", 512))),
                ]
                inst = None
                last_e = None
                for fn in init_attempts:
                    try:
                        inst = fn()
                        if inst is not None:
                            break
                    except Exception as e:
                        last_e = e
                        time.sleep(0.05)
                if inst is None:
                    return (f"<LAZY_LOAD_FAILED:{last_e}>", None)
                # register if possible
                try:
                    mid = getattr(inst, "model_name", None) or getattr(inst, "name", None) or os.path.basename(p)
                    mid = str(mid)
                    if isinstance(getattr(self, "gpt_models", None), list):
                        already = False
                        for m2 in self.gpt_models:
                            try:
                                if (getattr(m2, "model_name", None) or getattr(m2, "name", None) or str(m2)) == mid:
                                    already = True; break
                            except Exception:
                                pass
                        if not already:
                            try: self.gpt_models.append(inst)
                            except Exception: pass
                            try: self._ensure_model_stat(mid)
                            except Exception: pass
                            try: self._raw_by_model.setdefault(mid, _Ring(getattr(self, "RAW_RING_SIZE", 6)))
                            except Exception: pass
                    lazy_inst = inst
                    return (mid, lazy_inst)
                except Exception:
                    return (None, inst)
            else:
                # not a path
                return (None, m)

        # core: attempt one model once (single-shot) and return (text, label, ok, raw_out)
        def _call_single_model_once(m, exec_timeout):
            model_label_local = getattr(m, "model_name", None) or getattr(m, "name", None) or str(m)
            model_label_local = str(model_label_local)
            if _is_on_backoff(model_label_local):
                return (f"<BACKOFF:{model_label_local}>", model_label_local, False, None)

            # if m is a path, lazy instantiate
            try:
                lazy_label, maybe_inst = _lazy_instantiate_if_path(m)
                if maybe_inst is None and isinstance(lazy_label, str) and lazy_label.startswith("<"):
                    # failed lazy instantiate early
                    return (lazy_label, model_label_local, False, None)
                if maybe_inst is not None:
                    m = maybe_inst
                    if lazy_label and not lazy_label.startswith("<"):
                        model_label_local = lazy_label
            except Exception:
                pass

            # create call candidates
            def _attempt_calls_inner(obj):
                # try proxy.create() if exists and object has no generate
                try:
                    if hasattr(obj, "create") and callable(getattr(obj, "create")) and not (hasattr(obj, "generate") and callable(getattr(obj, "generate"))):
                        try:
                            n_ctx = int(getattr(self, "n_ctx", 512))
                            n_threads = int(getattr(self, "n_threads", 2))
                            timeout_local = float(getattr(self, "model_timeout", 30.0))
                            inst = obj.create(n_ctx=n_ctx, n_threads=n_threads, timeout=timeout_local)
                            if inst is not None:
                                obj = inst
                        except Exception:
                            pass
                except Exception:
                    pass

                gens = []
                # prefer generate
                if hasattr(obj, "generate") and callable(getattr(obj, "generate")):
                    gen = getattr(obj, "generate")
                    gens += [
                        lambda g=gen: g(prompt),
                        lambda g=gen: g(prompt=prompt),
                        lambda g=gen: g(prompt=prompt, n_predict=256),
                        lambda g=gen: g(prompt=prompt, max_tokens=256),
                        lambda g=gen: g(messages=[{"role": "user", "content": prompt}]),
                    ]
                # completions/chat/complete/create/__call__
                for attr in ("completions", "chat", "complete", "completion", "create", "__call__", "generate_one"):
                    try:
                        if hasattr(obj, attr) and callable(getattr(obj, attr)):
                            fn = getattr(obj, attr)
                            gens.append(lambda g=fn: g(prompt))
                            gens.append(lambda g=fn: g(prompt=prompt))
                            gens.append(lambda g=fn: g(messages=[{"role":"user","content":prompt}]))
                    except Exception:
                        pass

                # model directly callable
                if callable(obj):
                    gens.append(lambda g=obj: g(prompt))
                    gens.append(lambda g=obj: g(prompt=prompt))

                last_e = None
                for fn in gens:
                    try:
                        out = fn()
                        if out is None:
                            last_e = RuntimeError("generator returned None")
                            continue
                        return out
                    except Exception as e:
                        last_e = e
                        time.sleep(0.02)
                        continue
                raise RuntimeError(f"No supported generation method succeeded; last_exc={last_e}")

            # run attempts in executor with timeout
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(_attempt_calls_inner, m)
                    try:
                        raw_out = fut.result(timeout=max(0.01, exec_timeout))
                    except FuturesTimeoutError as e:
                        _set_backoff(model_label_local)
                        try: self._update_model_stat(model_label_local, success=False)
                        except Exception: pass
                        return (f"<TIMEOUT:{model_label_local}>", model_label_local, False, None)
                    except Exception as e:
                        _set_backoff(model_label_local)
                        try: self._update_model_stat(model_label_local, success=False)
                        except Exception: pass
                        return (f"<CALL_FAILED:{e}>", model_label_local, False, None)
            except Exception as e:
                _set_backoff(model_label_local)
                return (f"<EXEC_ERROR:{e}>", model_label_local, False, None)

            text = _extract_text(raw_out)
            # store raw trace
            try:
                ring = getattr(self, "_raw_by_model", {}).get(model_label_local)
                if ring is None:
                    ring = _Ring(getattr(self, "RAW_RING_SIZE", 6))
                    self._raw_by_model.setdefault(model_label_local, ring)
                ring.push((text or "")[:4000])
            except Exception:
                pass

            if text:
                try: self._update_model_stat(model_label_local, success=True)
                except Exception: pass
                return (text, model_label_local, True, raw_out)
            else:
                # empty -> set backoff and mark failure
                _set_backoff(model_label_local)
                try: self._update_model_stat(model_label_local, success=False)
                except Exception: pass
                return (f"<EMPTY:{model_label_local}>", model_label_local, False, raw_out)

        # --- MAIN LOGIC FOR MULTI/SINGLE MODELS ---
        # iterate 'rounds' times; each round call each model once up to per_model_attempts tries
        composite_errors = []
        found_text = None
        found_label = None

        for r in range(rounds):
            for m in models_list:
                # run up to per_model_attempts tries for this model in this round
                for attempt in range(per_model_attempts):
                    txt, lbl, ok, raw = _call_single_model_once(m, model_call_timeout)
                    # If we get a 'backoff' special token, skip attempts for this model
                    if isinstance(txt, str) and txt.startswith("<BACKOFF:"):
                        composite_errors.append(txt)
                        break
                    if ok and txt:
                        # success — return immediately (but we tried each model each round as requested)
                        return (txt, lbl, True)
                    else:
                        # collect the textual failure for debugging and try again (if attempt left)
                        composite_errors.append(f"{txt}")
                        # small sleep to avoid tight loop
                        time.sleep(0.05)
                # after per_model_attempts for this model in this round, continue to next model
            # small gap between rounds
            time.sleep(0.05)

        # If we reach here, nothing returned successfully
        # Prefer a helpful composite message: first non-special error if any, else generic
        first_non_backoff = None
        for e in composite_errors:
            if e and not e.startswith("<BACKOFF:") and not e.startswith("<TIMEOUT:"):
                first_non_backoff = e
                break
        if first_non_backoff:
            return (first_non_backoff, ",".join([str(x) for x in models_list]), False)
        # else fallback to a generic failure
        return (f"<NO_SUCCESS:{','.join([str(x) for x in models_list])}>", ",".join([str(x) for x in models_list]), False)

    def _call_llama_safe(
        self,
        prompt: str,
        model_id: str = "llama",
        timeout: float = 60.0,
        max_attempts: int = 2
    ) -> Tuple[str, float, float, float, str]:
        """
        Hardcore-safe wrapper for LLaMA model calls.
        Returns (decision, confidence, tp, sl, model_id)
        """
        llama = getattr(self, "llama", None)
        if llama is None:
            log.warning(f"LLaMA ({model_id}) not initialized — fallback HOLD")
            return "HOLD", 0.5, 1.0, 1.0, model_id

        for attempt in range(1, max_attempts + 1):
            try:
                with self._llama_lock:
                    fut = self._executor.submit(lambda: self._generate_from_model(llama, prompt))
                    raw = fut.result(timeout=timeout)

                # normalize any type -> string
                if isinstance(raw, str):
                    text = raw
                elif isinstance(raw, dict):
                    if "choices" in raw and isinstance(raw["choices"], (list, tuple)):
                        text = " ".join(
                            str(c.get("text") or (c.get("message") or {}).get("content") or json.dumps(c))
                            if isinstance(c, dict) else str(c)
                            for c in raw["choices"]
                        )
                    else:
                        text = str(raw.get("text") or raw.get("response") or json.dumps(raw))
                elif isinstance(raw, (list, tuple)):
                    text = " ".join(str(x) for x in raw if x)
                else:
                    text = str(raw)
                text = (text or "").strip()

                if not text:
                    raise ValueError("LLaMA returned empty text")

                # push raw
                try:
                    self._raw_by_model.setdefault(model_id, _Ring(RAW_RING_SIZE)).push(text[:4000])
                except Exception:
                    pass

                # parse response
                dec, conf, tp, sl = self._parse_response_full(text)
                dec = dec if dec in ("BUY", "SELL", "HOLD") else "HOLD"
                conf = max(0.0, min(1.0, _safe_float(conf, 0.5)))
                tp = max(1.0, min(5000.0, _safe_float(tp, 1.0)))
                sl = max(1.0, min(5000.0, _safe_float(sl, 1.0)))

                if dec == "HOLD":
                    conf, tp, sl = 0.5, 1.0, 1.0

                self._update_model_stat(model_id, success=True)
                log.info(f"LLaMA {model_id} [attempt {attempt}] -> {dec} conf={conf:.3f} tp={tp} sl={sl}")
                return dec, conf, tp, sl, model_id

            except FuturesTimeoutError:
                log.warning(f"LLaMA {model_id} attempt {attempt} TIMEOUT ({timeout}s)")
                self._update_model_stat(model_id, success=False)
                time.sleep(0.05 * attempt)
            except Exception as e:
                log.warning(f"LLaMA {model_id} attempt {attempt} error: {type(e).__name__}: {e}")
                self._update_model_stat(model_id, success=False)
                time.sleep(0.05 * attempt)

        log.warning(f"LLaMA {model_id} failed after {max_attempts} attempts — fallback HOLD")
        return "HOLD", 0.5, 1.0, 1.0, model_id

    def _normalize_signal(dec, conf, tp, sl):
        dec = str(dec).upper() if dec else "HOLD"
        dec = {"LONG": "BUY", "SHORT": "SELL"}.get(dec, dec)
        if dec not in ("BUY", "SELL", "HOLD"):
            dec = "HOLD"
        conf = max(0.0, min(1.0, _safe_float(conf, 0.5)))
        tp = max(1.0, min(5000.0, _safe_float(tp, 1.0)))
        sl = max(1.0, min(5000.0, _safe_float(sl, 1.0)))
        if dec == "HOLD":
            conf, tp, sl = 0.5, 1.0, 1.0
        return dec, conf, tp, sl


    def vote_trade(self, market_df: Union[pd.DataFrame, dict, str], symbol: Optional[str] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        t0 = time.time()
        timeout_total = float(timeout or getattr(self, "max_total_timeout", 6.0))
        deadline = t0 + timeout_total
        log = getattr(self, "logger", logging.getLogger(__name__))

        # ----------------- Build prompt -----------------
        if isinstance(market_df, str):
            prompt = market_df
            features = {}
        else:
            features = self._extract_features(market_df)
            prompt = self._build_prompt(features)

        # ----------------- Caching -----------------
        if symbol:
            with self._lock:
                last = self._last_call.get(symbol)
                if last and time.time() - last < getattr(self, "min_interval", 0.0):
                    cached = self._cache.get(symbol)
                    if cached:
                        return cached

        # ----------------- Submit GPT models -----------------
        futures = []
        for i, m in enumerate(getattr(self, "gpt_models", [])):
            mid = getattr(m, "model_name", f"gpt{i}")
            futures.append((self._executor.submit(self._call_gpt_safe, m, prompt, getattr(self, "model_timeout", 6.0), mid), mid))

        # ----------------- Submit LLaMA -----------------
        llama_future = None
        if getattr(self, "llama", None):
            llama_future = self._executor.submit(self._call_llama_safe, prompt, "llama", getattr(self, "model_timeout", 6.0))

        # ----------------- Collect results -----------------
        results: List[Tuple[str, float, float, float, str]] = []

        for fut, mid in futures:
            try:
                r = fut.result(timeout=max(0.05, deadline - time.time()))
                if isinstance(r, (list, tuple)) and len(r) == 5:
                    results.append(r)
                else:
                    # fallback parse
                    try:
                        dec, conf, tp, sl = self._parse_response_full(json.dumps(r) if isinstance(r, dict) else str(r))
                    except Exception:
                        dec, conf, tp, sl = "HOLD", 0.5, 1.0, 1.0
                    results.append((dec, conf, tp, sl, mid))
            except Exception as e:
                log.debug(f"GPT model {mid} failed/timeout: {e}")

        if llama_future:
            try:
                r = llama_future.result(timeout=max(0.05, deadline - time.time()))
                if isinstance(r, (tuple, list)) and len(r) == 5:
                    results.append(r)
            except Exception as e:
                log.debug(f"LLaMA call failed: {e}")

        if not results:
            out = {"decision": "HOLD", "confidence": 0.5, "tp_pips": 1.0, "sl_pips": 1.0, "votes": [], "elapsed": time.time() - t0}
            if symbol:
                with self._lock:
                    self._cache[symbol] = out
                    self._last_call[symbol] = time.time()
            return out

        # ----------------- Voting & aggregation -----------------
        score = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        votes = []

        for dec, conf, tp, sl, mid in results:
            conf = float(conf)
            tp = float(tp)
            sl = float(sl)
            w = float(self.get_model_weight(mid)) if hasattr(self, "get_model_weight") else 1.0
            votes.append({"model": mid, "decision": dec, "confidence": conf, "tp": tp, "sl": sl})
            if dec in score:
                score[dec] += conf * w

        final_dec = max(score.items(), key=lambda kv: kv[1])[0]

        # Ponderar TP/SL apenas dos modelos que votaram para final_dec
        selected = [(conf, tp, sl, mid) for dec, conf, tp, sl, mid in results if dec == final_dec]
        if selected:
            weights = [self.get_model_weight(mid) * conf for conf, tp, sl, mid in selected]
            ws = sum(weights) or 1.0
            tp_final = sum(tp * w for (conf, tp, sl, mid), w in zip(selected, weights)) / ws
            sl_final = sum(sl * w for (conf, tp, sl, mid), w in zip(selected, weights)) / ws
        else:
            final_dec = "HOLD"
            tp_final = 1.0
            sl_final = 1.0

        total_score = sum(score.values()) + 1e-9
        conf_final = min(1.0, max(0.0, score.get(final_dec, 0.0) / total_score))

        # ----------------- Adjust with Deep-Q if available -----------------
        try:
            final_dec, conf_final, tp_final, sl_final = self.adjust_with_deep_q(final_dec, conf_final, tp_final, sl_final, features)
        except Exception:
            pass

        # 🔥 REAL FIX: Detectar quando TODOS os modelos retornam HOLD 0.0
        all_models_failed = all(
            v.get("confidence", 0.0) == 0.0 and v.get("decision") == "HOLD"
            for v in votes
        )
        
        if all_models_failed and len(votes) > 0:
            log.warning(f"🚨 TODOS os {len(votes)} modelos AI retornaram HOLD 0.0 — marcando ai_failed=True")
            ai_failed_flag = True
        else:
            ai_failed_flag = False

        out = {
            "decision": final_dec,
            "confidence": round(conf_final, 4),
            "tp_pips": round(float(tp_final), 4),
            "sl_pips": round(float(sl_final), 4),
            "votes": votes,
            "elapsed": time.time() - t0,
            "ai_failed": ai_failed_flag  # 🔥 REAL FIX: flag para trading_bot_core
        }

        if symbol:
            with self._lock:
                self._cache[symbol] = out
                self._last_call[symbol] = time.time()
                # flush stats asynchronously
                try:
                    threading.Thread(target=self._maybe_flush_stats, kwargs={"force": False}, daemon=True).start()
                except Exception:
                    pass

        return out


    def attach_mt5(self, mt5_comm: Any):
        """
        Attach an MT5Communication instance (duck-typed) to the AIManager.
        Performs minimal validation and logs warning if required methods are missing.
        """
        required_methods = ["place_trade", "get_symbol_data", "get_account_info"]
        missing = [m for m in required_methods if not hasattr(mt5_comm, m)]

        if missing:
            log.warning(f"Attaching MT5 instance is missing methods: {missing}")

        self._mt5 = mt5_comm
        log.info(f"MT5Communication attached: {mt5_comm.__class__.__name__}")


    def enforce_signal(self, mt5_comm, symbol: str, min_confidence: float = MIN_CONF_ENV) -> Dict[str, Any]:
        """Get market data from mt5_comm, ask vote_trade and force a place_trade if above threshold.
        Returns a dict with result and ai decision info.
        """
        try:
            df = mt5_comm.get_symbol_data(symbol)
            if df is None or (hasattr(df, 'empty') and getattr(df, 'empty')):
                return {"ok": False, "error": "no_data"}
            ai_res = self.vote_trade(df, symbol=symbol)
            dec = ai_res.get('decision')
            conf = float(ai_res.get('confidence', 0.0))
            tp = float(ai_res.get('tp_pips', 0.0))
            sl = float(ai_res.get('sl_pips', 0.0))
            if dec in ('BUY','SELL') and conf >= float(min_confidence) and tp > 0 and sl > 0:
                vol = getattr(mt5_comm, 'DEFAULT_VOLUME', 0.01)  # fallback direto
                res = mt5_comm.place_trade(symbol=symbol, side=dec, volume=vol, tp_pips=tp, sl_pips=sl)
                log.info(f"Enforced {dec} {symbol} vol={vol} tp={tp} sl={sl} conf={conf}")
                return {"ok": True, "trade_result": res, "ai": ai_res}
            else:
                return {"ok": False, "reason": "low_confidence_or_hold", "ai": ai_res}
        except Exception as e:
            log.error(f"enforce_signal error: {e}")
            return {"ok": False, "error": str(e)}


    def get_recent_raw(
        self,
        model_id: str,
        limit: Optional[int] = None,
        as_text: bool = True
    ) -> List[str]:
        """
        Hardcore-safe retrieval of recent raw model outputs.

        Args:
            model_id: exact model identifier
            limit: max number of items to return (None = all available)
            as_text: force string output (safe for logs/UI)

        Returns:
            List[str] of recent raw outputs (most recent last)
        """

        # -------------------- Sanity checks --------------------
        if not model_id or not isinstance(model_id, str):
            return []

        try:
            ring = self._raw_by_model.get(model_id)
            if ring is None:
                return []
        except Exception:
            return []

        # -------------------- Extract ring content safely --------------------
        try:
            data = ring.dump()
        except Exception:
            return []

        if not data:
            return []

        # -------------------- Normalize & sanitize --------------------
        out: List[str] = []
        for x in data:
            try:
                if as_text:
                    out.append(str(x))
                else:
                    out.append(x)
            except Exception:
                out.append("<unprintable>")

        # -------------------- Apply limit (keep most recent) --------------------
        try:
            if limit is not None:
                limit = int(limit)
                if limit > 0:
                    out = out[-limit:]
        except Exception:
            pass

        return out



    def close(self):
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
        for m in self.gpt_models:
            try:
                if hasattr(m, 'close'):
                    m.close()
            except Exception:
                pass
        if self.llama and hasattr(self.llama, 'close'):
            try:
                self.llama.close()
            except Exception:
                pass
        try:
            self._maybe_flush_stats(force=True)
        except Exception:
            pass
        log.info("AIManager closed")

