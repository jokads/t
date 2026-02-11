#!/usr/bin/env python3
"""
JOKA Trading Bot - Startup Script
Inicia automaticamente o trading_bot_core.py e dashboard_server.py
"""

import os
import sys
import time
import subprocess
import signal
import psutil
from pathlib import Path

# Cores para output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def is_process_running(process_name):
    """Verifica se um processo está em execução"""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if process_name in cmdline:
                return True, proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False, None

def kill_process(pid):
    """Termina um processo pelo PID"""
    try:
        process = psutil.Process(pid)
        process.terminate()
        process.wait(timeout=5)
        return True
    except Exception as e:
        print_error(f"Erro ao terminar processo {pid}: {e}")
        return False

def start_dashboard():
    """Inicia o dashboard_server.py"""
    print_info("A verificar dashboard_server.py...")
    
    running, pid = is_process_running('dashboard_server.py')
    if running:
        print_warning(f"Dashboard já está em execução (PID: {pid})")
        return pid
    
    print_info("A iniciar dashboard_server.py...")
    try:
        process = subprocess.Popen(
            [sys.executable, 'dashboard_server.py'],
            cwd='backend',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(2)
        
        if process.poll() is None:
            print_success(f"Dashboard iniciado com sucesso (PID: {process.pid})")
            print_info("Dashboard disponível em: http://localhost:5000")
            return process.pid
        else:
            print_error("Falha ao iniciar dashboard")
            return None
    except Exception as e:
        print_error(f"Erro ao iniciar dashboard: {e}")
        return None

def start_trading_bot():
    """Inicia o trading_bot_core.py"""
    print_info("A verificar trading_bot_core.py...")
    
    running, pid = is_process_running('trading_bot_core.py')
    if running:
        print_warning(f"Trading bot já está em execução (PID: {pid})")
        return pid
    
    print_info("A iniciar trading_bot_core.py...")
    try:
        # Nota: Ajuste o caminho conforme a estrutura do seu projeto bot-mt5
        process = subprocess.Popen(
            [sys.executable, 'trading_bot_core.py'],
            cwd='.',  # Assumindo que está na raiz do bot-mt5
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(2)
        
        if process.poll() is None:
            print_success(f"Trading bot iniciado com sucesso (PID: {process.pid})")
            return process.pid
        else:
            print_error("Falha ao iniciar trading bot")
            return None
    except Exception as e:
        print_error(f"Erro ao iniciar trading bot: {e}")
        return None

def open_browser():
    """Abre o dashboard no navegador"""
    import webbrowser
    print_info("A abrir dashboard no navegador...")
    time.sleep(1)
    webbrowser.open('http://localhost:5000')

def main():
    print_header("JOKA TRADING BOT - STARTUP")
    
    # Verificar se estamos no diretório correto
    if not os.path.exists('backend'):
        print_error("Diretório 'backend' não encontrado!")
        print_info("Execute este script a partir da raiz do projeto bot-mt5")
        sys.exit(1)
    
    # Iniciar dashboard
    dashboard_pid = start_dashboard()
    if not dashboard_pid:
        print_error("Não foi possível iniciar o dashboard. Abortando...")
        sys.exit(1)
    
    # Aguardar dashboard estar pronto
    time.sleep(3)
    
    # Iniciar trading bot
    bot_pid = start_trading_bot()
    if not bot_pid:
        print_warning("Trading bot não foi iniciado, mas dashboard está ativo")
    
    # Abrir navegador
    open_browser()
    
    print_header("SISTEMA INICIADO COM SUCESSO")
    print_success(f"Dashboard PID: {dashboard_pid}")
    if bot_pid:
        print_success(f"Trading Bot PID: {bot_pid}")
    print_info("\nPressione Ctrl+C para parar todos os processos\n")
    
    # Manter script ativo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print_header("A ENCERRAR SISTEMA")
        
        if dashboard_pid:
            print_info(f"A terminar dashboard (PID: {dashboard_pid})...")
            kill_process(dashboard_pid)
        
        if bot_pid:
            print_info(f"A terminar trading bot (PID: {bot_pid})...")
            kill_process(bot_pid)
        
        print_success("Sistema encerrado com sucesso!")
        sys.exit(0)

if __name__ == '__main__':
    main()
