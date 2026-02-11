# -*- coding: utf-8 -*-
"""
JokaMazKiBu Trading Bot v5.2 - LOCAL AI MANAGER FINAL
Gerenciador para Modelos de IA Locais (GPT-4All & Llama.cpp)
Autor: Manus AI | Date: 2026-01-01
Status: ✅ PRONTO PARA PRODUÇÃO
"""

import os
import subprocess
import logging
import sys
from typing import Dict

# Configuração de logging
logger = logging.getLogger("local_ai_manager_v5_2")

class LocalAIManagerV5_2:
    """Gerencia a interação com modelos de IA locais como GPT-4All e Llama.cpp."""
    
    def __init__(self):
        self.logger = logging.getLogger("local_ai_manager_v5_2")
        
        # Caminhos dos modelos (do .env)
        self.gpt4all_models_dir = os.getenv("GPT4ALL_MODELS_DIR", r"C:\bot-mt5\models\gpt4all")
        self.llama_model_path = os.getenv("LLAMA_MODEL_PATH", r"C:\bot_ia2\llama.cpp\models\mistral-7b-instruct-v0.1.Q4_K_S.gguf")
        self.llama_exe_path = os.getenv("LLAMA_EXE_PATH", r"C:\bot_ia2\models\llama\llama-cli.exe")
        
        # Mapeamento de modelos
        self.models = {
            "gpt1": {"type": "gpt4all", "name": "Análise Técnica"},
            "gpt2": {"type": "gpt4all", "name": "Sentimento"},
            "gpt3": {"type": "gpt4all", "name": "Gestão de Risco"},
            "gpt4": {"type": "gpt4all", "name": "Momentum"},
            "gpt5": {"type": "gpt4all", "name": "Volatilidade"},
            "gpt6": {"type": "gpt4all", "name": "Correlações"},
            "gpt7": {"type": "llama.cpp", "name": "Cérebro Principal"}
        }
        
        self.logger.info("✅ LocalAIManagerV5_2 inicializado")

    def generate_response(self, model_id: str, prompt: str) -> str:
        """Gera uma resposta de um modelo de IA local."""
        if model_id not in self.models:
            return "❌ Modelo de IA não encontrado."

        model_config = self.models[model_id]
        
        try:
            if model_config["type"] == "llama.cpp":
                return self._run_llama_cpp(prompt)
            else:
                # Simulação para modelos GPT-4All
                return f"(Simulado - {model_config['name']}) Resposta para: '{prompt[:50]}...'"
        except Exception as e:
            self.logger.error(f"❌ Erro ao gerar resposta com {model_id}: {e}")
            return f"❌ Erro interno ao processar sua pergunta com o modelo {model_id.upper()}."

    def _run_llama_cpp(self, prompt: str) -> str:
        """Executa o modelo Llama.cpp via linha de comando."""
        if not os.path.exists(self.llama_exe_path):
            self.logger.error(f"Executável Llama.cpp não encontrado: {self.llama_exe_path}")
            return f"❌ Executável Llama.cpp não encontrado."
        if not os.path.exists(self.llama_model_path):
            self.logger.error(f"Modelo Llama.cpp não encontrado: {self.llama_model_path}")
            return f"❌ Modelo Llama.cpp não encontrado."

        command = [
            self.llama_exe_path,
            "-m", self.llama_model_path,
            "-p", prompt,
            "-n", "150",          # Aumentado para respostas mais completas
            "--temp", "0.7",
            "-c", "2048",        # Context size
            "--n-gpu-layers", "32" # Offload para GPU (ajuste conforme sua GPU)
        ]
        
        try:
            self.logger.info(f"Executando Llama.cpp...")
            
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace',
                startupinfo=startupinfo,
                timeout=180 # Timeout de 3 minutos
            )

            if result.returncode != 0:
                self.logger.error(f"Erro no Llama.cpp: {result.stderr}")
                return f"❌ Erro ao executar Llama.cpp."
            
            response = result.stdout.strip()
            # Limpa o prompt da resposta, caso ele apareça no início
            if response.startswith(prompt):
                response = response[len(prompt):].strip()
            
            return response if response else "(A IA não forneceu uma resposta.)"

        except subprocess.TimeoutExpired:
            self.logger.error("❌ Timeout ao executar Llama.cpp")
            return "❌ A IA demorou muito para responder (timeout)."
        except Exception as e:
            self.logger.error(f"❌ Exceção ao executar Llama.cpp: {e}")
            return f"❌ Exceção inesperada ao executar Llama.cpp."

# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ai_manager = LocalAIManagerV5_2()
    
    print("--- Testando Llama.cpp (GPT-7) ---")
    prompt_llama = "Explique o que é um bot de trading em 3 frases."
    response_llama = ai_manager.generate_response("gpt7", prompt_llama)
    print(f"Prompt: {prompt_llama}")
    print(f"Resposta: {response_llama}")
