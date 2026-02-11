import logging
import os
from logging.handlers import RotatingFileHandler

# --------------------------
# Configurações principais
# --------------------------
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 5 * 1024 * 1024))  # 5MB
BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))

# --------------------------
# Logger principal
# --------------------------
logger = logging.getLogger("BotLogger")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logger.propagate = False  # Evita logs duplicados

# --------------------------
# Formatter padrão
# --------------------------
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

# --------------------------
# Handler arquivo com rotação
# --------------------------
file_handler = RotatingFileHandler(
    filename=os.path.join(LOG_DIR, "bot.log"),
    maxBytes=MAX_BYTES,
    backupCount=BACKUP_COUNT,
    encoding="utf-8"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# --------------------------
# Handler console colorido
# --------------------------
try:
    from colorama import init, Fore, Style
    init(autoreset=True)

    class ColorFormatter(logging.Formatter):
        LEVEL_COLORS = {
            logging.DEBUG: Fore.CYAN,
            logging.INFO: Fore.GREEN,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Fore.MAGENTA
        }

        def format(self, record):
            color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
            record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
            return super().format(record)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    logger.addHandler(console_handler)
except ImportError:
    # Fallback sem cores
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# --------------------------
# Funções utilitárias
# --------------------------
def log_debug(message):
    logger.debug(message)

def log_info(message):
    logger.info(message)

def log_warning(message):
    logger.warning(message)

def log_error(message, exc_info=False):
    logger.error(message, exc_info=exc_info)

def log_critical(message, exc_info=True):
    logger.critical(message, exc_info=exc_info)
