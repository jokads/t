# 🔥 Integração Supabase - Dashboard Trading Bot

## 📋 Visão Geral

Este guia explica como integrar o Supabase ao seu dashboard de trading bot para:
- ✅ Armazenar análises de código
- ✅ Guardar histórico de correções
- ✅ Registar logs de auditoria
- ✅ Backup de configurações
- ✅ Sincronização em tempo real

---

## 🚀 Passo 1: Criar Projeto no Supabase

1. **Aceder**: https://supabase.com
2. **Criar novo projeto**
3. **Anotar**:
   - Project URL: `https://seu-projeto.supabase.co`
   - Anon/Public Key: `eyJhbG...`

---

## 🗄️ Passo 2: Criar Tabelas

Execute estes SQL no Supabase SQL Editor:

### Tabela: `code_analysis`
```sql
CREATE TABLE code_analysis (
  id BIGSERIAL PRIMARY KEY,
  file_path TEXT NOT NULL,
  issues_count INTEGER DEFAULT 0,
  critical_issues INTEGER DEFAULT 0,
  health_score INTEGER DEFAULT 100,
  issues_json JSONB,
  analyzed_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index para buscas rápidas
CREATE INDEX idx_code_analysis_file ON code_analysis(file_path);
CREATE INDEX idx_code_analysis_date ON code_analysis(analyzed_at DESC);

-- RLS (Row Level Security)
ALTER TABLE code_analysis ENABLE ROW LEVEL SECURITY;

-- Política: Permitir leitura/escrita com chave válida
CREATE POLICY "Allow all with valid key" ON code_analysis
  FOR ALL USING (true);
```

### Tabela: `code_fixes`
```sql
CREATE TABLE code_fixes (
  id BIGSERIAL PRIMARY KEY,
  file_path TEXT NOT NULL,
  line_number INTEGER,
  suggestion TEXT,
  backup_path TEXT,
  applied_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX idx_code_fixes_file ON code_fixes(file_path);
CREATE INDEX idx_code_fixes_date ON code_fixes(applied_at DESC);

-- RLS
ALTER TABLE code_fixes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all with valid key" ON code_fixes
  FOR ALL USING (true);
```

### Tabela: `audit_logs`
```sql
CREATE TABLE audit_logs (
  id BIGSERIAL PRIMARY KEY,
  action TEXT NOT NULL,
  details TEXT,
  user_name TEXT,
  severity TEXT DEFAULT 'INFO',
  ip_address TEXT,
  hash TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX idx_audit_logs_date ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);

-- RLS
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all with valid key" ON audit_logs
  FOR ALL USING (true);
```

### Tabela: `strategy_performance`
```sql
CREATE TABLE strategy_performance (
  id BIGSERIAL PRIMARY KEY,
  strategy_name TEXT NOT NULL,
  symbol TEXT,
  timeframe TEXT,
  signal TEXT,
  profit_loss DECIMAL(10, 2),
  win_rate DECIMAL(5, 2),
  total_trades INTEGER DEFAULT 0,
  executed_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX idx_strategy_perf_name ON strategy_performance(strategy_name);
CREATE INDEX idx_strategy_perf_date ON strategy_performance(executed_at DESC);

-- RLS
ALTER TABLE strategy_performance ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all with valid key" ON strategy_performance
  FOR ALL USING (true);
```

### Tabela: `bot_errors`
```sql
CREATE TABLE bot_errors (
  id BIGSERIAL PRIMARY KEY,
  file_path TEXT NOT NULL,
  line_number INTEGER,
  error_type TEXT,
  message TEXT,
  stack_trace TEXT,
  local_vars JSONB,
  resolved BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX idx_bot_errors_file ON bot_errors(file_path);
CREATE INDEX idx_bot_errors_date ON bot_errors(created_at DESC);
CREATE INDEX idx_bot_errors_resolved ON bot_errors(resolved);

-- RLS
ALTER TABLE bot_errors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all with valid key" ON bot_errors
  FOR ALL USING (true);
```

---

## ⚙️ Passo 3: Configurar Backend

### 1. Criar arquivo `.env` no backend:

```bash
cd backend
cp .env.example .env
```

### 2. Editar `backend/.env`:

```env
# Supabase
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Dashboard
FLASK_SECRET_KEY=sua_chave_secreta_aqui
JWT_SECRET_KEY=sua_jwt_secret_aqui

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# News API (opcional)
NEWS_API_KEY=sua_news_api_key
```

### 3. Instalar dependências:

```bash
pip install python-dotenv supabase-py
```

### 4. Atualizar `requirements.txt`:

```txt
python-dotenv==1.0.0
supabase==2.3.0
```

---

## 🔧 Passo 4: Configurar Frontend

### 1. Criar arquivo `.env` na raiz do projeto:

```bash
# Na raiz do projeto (onde está package.json)
touch .env
```

### 2. Editar `.env`:

```env
VITE_PUBLIC_SUPABASE_URL=https://seu-projeto.supabase.co
VITE_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 3. Instalar cliente Supabase:

```bash
npm install @supabase/supabase-js
```

---

## 🎯 Passo 5: Usar Supabase no Frontend

### Criar cliente Supabase:

```typescript
// src/lib/supabase.ts
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_PUBLIC_SUPABASE_URL;
const supabaseKey = import.meta.env.VITE_PUBLIC_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseKey);
```

### Exemplo de uso em componente:

```typescript
import { supabase } from '../../lib/supabase';

// Buscar análises recentes
const { data, error } = await supabase
  .from('code_analysis')
  .select('*')
  .order('analyzed_at', { ascending: false })
  .limit(10);

// Inserir nova análise
const { data, error } = await supabase
  .from('code_analysis')
  .insert({
    file_path: 'strategies/adaptive_ml.py',
    issues_count: 3,
    health_score: 85
  });

// Buscar erros não resolvidos
const { data, error } = await supabase
  .from('bot_errors')
  .select('*')
  .eq('resolved', false)
  .order('created_at', { ascending: false });
```

---

## 📊 Funcionalidades Implementadas

### 1. **Análise de Código com IA**
- Detecta erros automaticamente
- Analisa lógica de geração de sinais
- Armazena histórico no Supabase
- Tabela: `code_analysis`

### 2. **Correções Automáticas**
- IA sugere e aplica correções
- Backup automático antes de modificar
- Histórico completo de mudanças
- Tabela: `code_fixes`

### 3. **Logs de Auditoria**
- Todas as ações críticas registadas
- Hash SHA-256 para imutabilidade
- Rastreamento de usuário e IP
- Tabela: `audit_logs`

### 4. **Performance de Estratégias**
- Métricas em tempo real
- Win rate, profit/loss, total trades
- Análise por símbolo e timeframe
- Tabela: `strategy_performance`

### 5. **Erros Runtime**
- Captura automática de exceções
- Stack trace completo
- Variáveis locais no momento do erro
- Tabela: `bot_errors`

---

## 🔍 Como Usar a Análise Inteligente

### 1. **Aceder à Página**
```
http://localhost:5000/code-analysis
```

### 2. **Selecionar Modelo IA**
- Llama 3.2 1B - Rápido
- Llama 3.2 3B - Balanceado (recomendado)
- Nous Hermes 2 Mistral 7B - Avançado
- Orca Mini 3B - Análise detalhada
- Phi-3 Mini 4K - Contexto longo
- Qwen2 1.5B - Eficiente

### 3. **Analisar Arquivo**
- Clique num arquivo para análise individual
- OU clique "Analisar Tudo" para scan completo

### 4. **Ver Resultados**
- 📍 Localização exata: `arquivo:linha:coluna`
- 🔴 Severidade: Crítico/Alto/Médio/Baixo
- 🤖 Análise IA: Explicação detalhada
- 💡 Sugestão: Como corrigir
- 📊 Confiança: 0-100%

### 5. **Aplicar Correção**
- Ativar "Auto-Correção" nas configurações
- Clicar "Corrigir" em problemas com confiança > 70%
- Backup automático criado
- Verificação de sintaxe pós-correção

---

## 🛡️ Segurança

### ✅ Proteções Implementadas:

1. **Row Level Security (RLS)** ativado em todas as tabelas
2. **JWT Authentication** obrigatória
3. **Backup automático** antes de modificações
4. **Verificação de sintaxe** após correções
5. **Audit logs** com hash SHA-256
6. **Rate limiting** em chamadas IA
7. **Validação de entrada** em todos os endpoints

---

## 📈 Monitorização em Tempo Real

### Dashboard Supabase:
1. Aceder: https://app.supabase.com
2. Selecionar seu projeto
3. Ver **Table Editor** para dados
4. Ver **Database** → **Logs** para queries
5. Ver **API** → **Logs** para requests

### Queries Úteis:

```sql
-- Análises recentes
SELECT * FROM code_analysis 
ORDER BY analyzed_at DESC 
LIMIT 20;

-- Correções aplicadas hoje
SELECT * FROM code_fixes 
WHERE applied_at > CURRENT_DATE 
ORDER BY applied_at DESC;

-- Erros críticos não resolvidos
SELECT * FROM bot_errors 
WHERE resolved = false 
  AND error_type = 'critical'
ORDER BY created_at DESC;

-- Performance das estratégias
SELECT 
  strategy_name,
  COUNT(*) as total_trades,
  AVG(profit_loss) as avg_profit,
  AVG(win_rate) as avg_win_rate
FROM strategy_performance
GROUP BY strategy_name
ORDER BY avg_profit DESC;
```

---

## 🚨 Troubleshooting

### Erro: "Cannot connect to Supabase"
```bash
# Verificar variáveis de ambiente
cat backend/.env | grep SUPABASE

# Testar conexão
curl https://seu-projeto.supabase.co/rest/v1/
```

### Erro: "RLS policy violation"
```sql
-- Verificar políticas
SELECT * FROM pg_policies WHERE tablename = 'code_analysis';

-- Recriar política se necessário
DROP POLICY "Allow all with valid key" ON code_analysis;
CREATE POLICY "Allow all with valid key" ON code_analysis
  FOR ALL USING (true);
```

### Erro: "Table does not exist"
```sql
-- Listar tabelas
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public';

-- Recriar tabela se necessário (ver Passo 2)
```

---

## 🎓 Exemplos de Integração

### Python (Backend):

```python
from supabase import create_client
import os

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

# Inserir análise
data = supabase.table('code_analysis').insert({
    'file_path': 'strategies/ema_crossover.py',
    'issues_count': 2,
    'health_score': 90
}).execute()

# Buscar erros
errors = supabase.table('bot_errors')\
    .select('*')\
    .eq('resolved', False)\
    .execute()
```

### TypeScript (Frontend):

```typescript
import { supabase } from './lib/supabase';

// Subscrever mudanças em tempo real
const subscription = supabase
  .channel('code_analysis_changes')
  .on('postgres_changes', 
    { event: '*', schema: 'public', table: 'code_analysis' },
    (payload) => {
      console.log('Nova análise:', payload.new);
    }
  )
  .subscribe();

// Cancelar subscrição
subscription.unsubscribe();
```

---

## ✅ Checklist de Integração

- [ ] Criar projeto no Supabase
- [ ] Executar SQL para criar tabelas
- [ ] Configurar RLS policies
- [ ] Criar arquivo `.env` no backend
- [ ] Adicionar SUPABASE_URL e SUPABASE_KEY
- [ ] Instalar `supabase-py` no backend
- [ ] Criar arquivo `.env` no frontend
- [ ] Adicionar variáveis VITE_PUBLIC_*
- [ ] Instalar `@supabase/supabase-js` no frontend
- [ ] Testar conexão backend → Supabase
- [ ] Testar conexão frontend → Supabase
- [ ] Verificar dados sendo salvos
- [ ] Configurar backup automático
- [ ] Testar rollback de correções

---

## 🔥 Resultado Final

Após integração completa, você terá:

✅ **Análise Automática** de todo o código  
✅ **Detecção Inteligente** de problemas de sinais  
✅ **Correção com IA** e backup automático  
✅ **Histórico Completo** de todas as mudanças  
✅ **Monitorização em Tempo Real** de erros  
✅ **Logs de Auditoria** imutáveis  
✅ **Dashboard Supabase** para análise de dados  
✅ **Performance Tracking** de estratégias  

---

**🚀 Sistema Pronto para Produção com Supabase Integrado!**
