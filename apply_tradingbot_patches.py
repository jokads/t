#!/usr/bin/env python3
# apply_tradingbot_patches.py
# Usage: run this from your repo root where trading_bot_core.py is located:
#   python apply_tradingbot_patches.py
#
# What it does (best-effort):
# - Inserts default attributes `self.force_send` and `self.min_confidence` into TradingBot.__init__
# - Replaces fragile AIManager log line that accessed ai.mode directly with a safe getattr version
# - Makes a backup of trading_bot_core.py as trading_bot_core.py.bak before modifying
#
# This script is conservative but make sure to review the patched file afterwards.
import re, sys, os, shutil
from pathlib import Path

TARGET = Path("trading_bot_core.py")
BACKUP = TARGET.with_suffix(".py.bak")

if not TARGET.exists():
    print("Error: trading_bot_core.py not found in current directory:", Path.cwd())
    sys.exit(1)

# backup
shutil.copy2(TARGET, BACKUP)
print(f"Backup saved to {BACKUP}")

text = TARGET.read_text(encoding="utf-8")

# 1) ensure 'import os' exists near top
if "import os" not in text.splitlines()[0:40]:
    # insert after initial shebang or first module docstring
    insert_at = 0
    lines = text.splitlines()
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    # put import os at insert_at
    lines.insert(insert_at, "import os")
    text = "\n".join(lines)
    print("Inserted 'import os' near top of file.")

# 2) Find TradingBot.__init__ and inject defaults
# We'll find 'class TradingBot' then the following 'def __init__' occurrence.
cls_idx = text.find("class TradingBot")
if cls_idx == -1:
    print("Warning: 'class TradingBot' not found. Skipping __init__ patch.")
else:
    # search for def __init__ after cls_idx
    init_idx = text.find("def __init__", cls_idx)
    if init_idx == -1:
        print("Warning: 'def __init__' not found after TradingBot. Skipping __init__ patch.")
    else:
        # find the end of the signature line (the line that ends with ':')
        sig_end = text.find(":\n", init_idx)
        if sig_end == -1:
            print("Could not find end of __init__ signature. Skipping.")
        else:
            # determine indentation of the next line (body)
            body_start = sig_end + 2
            # find start of next non-empty line to detect indentation
            m = re.search(r"\n([ \t]+)\S", text[sig_end: sig_end+200], re.M)
            indent = " " * 8
            if m:
                indent = m.group(1)
            # build injection text
            inject = f"\n{indent}# --- AUTO-INJECTED DEFAULTS to avoid AttributeError ---\n"
            inject += f"{indent}self.force_send = getattr(self, 'force_send', False)\n"
            inject += f"{indent}self.min_confidence = getattr(self, 'min_confidence', float(os.getenv('MIN_CONFIDENCE', '0.55')))\n"
            inject += f"{indent}# ----------------------------------------------------\n"
            # insert after the signature line but before existing body
            new_text = text[:body_start] + inject + text[body_start:]
            text = new_text
            print("Injected force_send and min_confidence defaults into TradingBot.__init__.")

# 3) Replace fragile AIManager log line to use getattr
# Pattern: f"AIManager initialized | mode={ai.mode} | timeout={ai.max_total_timeout}s"
# We'll replace occurrences that contain 'AIManager initialized' and 'ai.mode' with a safe version.
pattern = re.compile(r'AIManager initialized\s*\|.*?ai\.mode.*', re.DOTALL)
if pattern.search(text):
    # safer replacement - uses getattr on ai
    replacement = "AIManager initialized | mode={mode} | timeout={timeout}s"
    # perform specific f-string replacement occurrences
    text = re.sub(r'\{ai\.mode\}', "{getattr(ai,'mode','unknown')}", text)
    text = re.sub(r'\{ai\.max_total_timeout\}', "{getattr(ai,'max_total_timeout', getattr(ai,'model_timeout','unknown'))}", text)
    print("Replaced direct ai.mode access with safe getattr pattern where matched.")
else:
    # Also attempt to replace common variant
    text = text.replace("AIManager initialized | mode={ai.mode} | timeout={ai.max_total_timeout}s",
                        "AIManager initialized | mode={getattr(ai,'mode','unknown')} | timeout={getattr(ai,'max_total_timeout', getattr(ai,'model_timeout','unknown'))}s")
    print("Attempted simple replacement of ai.mode access (if present).")

# 4) Save file
TARGET.write_text(text, encoding="utf-8")
print("Patched trading_bot_core.py written. Please review the file and then run your bot.")
print("If anything goes wrong, restore the backup:", BACKUP)
