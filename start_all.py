import subprocess
import os
import time

BOT_BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# Backend do dashboard
backend_cmd = f'python "{os.path.join(BOT_BASE_PATH, "backend", "dashboard_server.py")}"'
backend_proc = subprocess.Popen(backend_cmd, shell=True)
print("✅ Backend do dashboard iniciado")

# Aguardar backend subir
time.sleep(3)

# Frontend
frontend_cmd = 'npm run dev'
frontend_proc = subprocess.Popen(frontend_cmd, shell=True, cwd=BOT_BASE_PATH)
print("✅ Frontend iniciado")

# Bot principal
bot_cmd = f'python "{os.path.join(BOT_BASE_PATH, "trading_bot_core.py")}"'
bot_proc = subprocess.Popen(bot_cmd, shell=True)
print("✅ Bot principal iniciado")

# Mantém o script ativo
try:
    backend_proc.wait()
    frontend_proc.wait()
    bot_proc.wait()
except KeyboardInterrupt:
    print("🛑 Parando tudo...")
    backend_proc.terminate()
    frontend_proc.terminate()
    bot_proc.terminate()
