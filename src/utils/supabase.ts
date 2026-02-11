/**
 * Cliente Supabase configurado para o Trading Bot
 * Gerencia conexão com base de dados em tempo real
 */

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_PUBLIC_SUPABASE_ANON_KEY || '';

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('⚠️ Supabase credentials não configuradas no .env');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
  db: {
    schema: 'public',
  },
  global: {
    headers: {
      'x-application': 'joka-trading-bot',
    },
  },
});

// ==================== TYPES ====================
export interface User {
  id: number;
  username: string;
  password_hash: string;
  role: 'admin' | 'trader' | 'viewer';
  email?: string;
  created_at: string;
  updated_at: string;
  last_login?: string;
  is_active: boolean;
}

export interface AuditLog {
  id: number;
  user_id?: number;
  action: string;
  details?: Record<string, any>;
  ip_address?: string;
  user_agent?: string;
  timestamp: string;
}

export interface MT5Account {
  id: number;
  user_id: number;
  account_number: string;
  account_name?: string;
  broker?: string;
  server?: string;
  balance?: number;
  equity?: number;
  margin?: number;
  free_margin?: number;
  margin_level?: number;
  profit?: number;
  currency: string;
  leverage?: number;
  is_active: boolean;
  last_sync: string;
  created_at: string;
  updated_at: string;
}

export interface Trade {
  id: number;
  user_id: number;
  mt5_account_id?: number;
  ticket?: string;
  symbol: string;
  side: 'BUY' | 'SELL' | 'LONG' | 'SHORT';
  volume: number;
  open_price?: number;
  close_price?: number;
  tp_pips?: number;
  sl_pips?: number;
  tp_price?: number;
  sl_price?: number;
  profit?: number;
  commission?: number;
  swap?: number;
  confidence?: number;
  strategy_name?: string;
  signal_source?: string;
  status: 'pending' | 'open' | 'closed' | 'cancelled' | 'rejected';
  error_message?: string;
  opened_at: string;
  closed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface Signal {
  id: number;
  user_id: number;
  symbol: string;
  decision: 'BUY' | 'SELL' | 'HOLD' | 'LONG' | 'SHORT';
  confidence?: number;
  tp_pips?: number;
  sl_pips?: number;
  strategy_name?: string;
  signal_source?: string;
  raw_data?: Record<string, any>;
  processed: boolean;
  executed: boolean;
  trade_id?: number;
  created_at: string;
  processed_at?: string;
  executed_at?: string;
}

export interface Strategy {
  id: number;
  user_id: number;
  name: string;
  description?: string;
  strategy_type?: string;
  config?: Record<string, any>;
  is_active: boolean;
  performance_stats?: Record<string, any>;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_profit: number;
  win_rate?: number;
  created_at: string;
  updated_at: string;
  last_signal_at?: string;
}

export interface SystemConfig {
  id: number;
  user_id: number;
  key: string;
  value?: Record<string, any>;
  description?: string;
  created_at: string;
  updated_at: string;
}

// ==================== AUTH HELPERS ====================
export async function signInWithPassword(username: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email: `${username}@trading.local`,
    password,
  });
  return { data, error };
}

export async function signOut() {
  const { error } = await supabase.auth.signOut();
  return { error };
}

export async function getCurrentUser() {
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}

// ==================== DATABASE HELPERS ====================

// --- USERS ---
export async function getUsers() {
  const { data, error } = await supabase
    .from('users')
    .select('*')
    .order('created_at', { ascending: false });
  return { data, error };
}

export async function getUserById(id: number) {
  const { data, error } = await supabase
    .from('users')
    .select('*')
    .eq('id', id)
    .single();
  return { data, error };
}

export async function updateUser(id: number, updates: Partial<User>) {
  const { data, error } = await supabase
    .from('users')
    .update(updates)
    .eq('id', id)
    .select()
    .single();
  return { data, error };
}

// --- AUDIT LOGS ---
export async function createAuditLog(log: Omit<AuditLog, 'id' | 'timestamp'>) {
  const { data, error } = await supabase
    .from('audit_logs')
    .insert(log)
    .select()
    .single();
  return { data, error };
}

export async function getAuditLogs(limit = 100) {
  const { data, error } = await supabase
    .from('audit_logs')
    .select('*')
    .order('timestamp', { ascending: false })
    .limit(limit);
  return { data, error };
}

// --- MT5 ACCOUNTS ---
export async function getMT5Accounts() {
  const { data, error } = await supabase
    .from('mt5_accounts')
    .select('*')
    .order('created_at', { ascending: false });
  return { data, error };
}

export async function getMT5AccountById(id: number) {
  const { data, error } = await supabase
    .from('mt5_accounts')
    .select('*')
    .eq('id', id)
    .single();
  return { data, error };
}

export async function updateMT5Account(id: number, updates: Partial<MT5Account>) {
  const { data, error } = await supabase
    .from('mt5_accounts')
    .update({ ...updates, last_sync: new Date().toISOString() })
    .eq('id', id)
    .select()
    .single();
  return { data, error };
}

export async function createMT5Account(account: Omit<MT5Account, 'id' | 'created_at' | 'updated_at' | 'last_sync'>) {
  const { data, error } = await supabase
    .from('mt5_accounts')
    .insert(account)
    .select()
    .single();
  return { data, error };
}

// --- TRADES ---
export async function getTrades(filters?: { symbol?: string; status?: string; limit?: number }) {
  let query = supabase
    .from('trades')
    .select('*')
    .order('opened_at', { ascending: false });

  if (filters?.symbol) {
    query = query.eq('symbol', filters.symbol);
  }
  if (filters?.status) {
    query = query.eq('status', filters.status);
  }
  if (filters?.limit) {
    query = query.limit(filters.limit);
  }

  const { data, error } = await query;
  return { data, error };
}

export async function getTradeById(id: number) {
  const { data, error } = await supabase
    .from('trades')
    .select('*')
    .eq('id', id)
    .single();
  return { data, error };
}

export async function createTrade(trade: Omit<Trade, 'id' | 'created_at' | 'updated_at'>) {
  const { data, error } = await supabase
    .from('trades')
    .insert(trade)
    .select()
    .single();
  return { data, error };
}

export async function updateTrade(id: number, updates: Partial<Trade>) {
  const { data, error } = await supabase
    .from('trades')
    .update(updates)
    .eq('id', id)
    .select()
    .single();
  return { data, error };
}

// --- SIGNALS ---
export async function getSignals(filters?: { processed?: boolean; executed?: boolean; limit?: number }) {
  let query = supabase
    .from('signals')
    .select('*')
    .order('created_at', { ascending: false });

  if (filters?.processed !== undefined) {
    query = query.eq('processed', filters.processed);
  }
  if (filters?.executed !== undefined) {
    query = query.eq('executed', filters.executed);
  }
  if (filters?.limit) {
    query = query.limit(filters.limit);
  }

  const { data, error } = await query;
  return { data, error };
}

export async function createSignal(signal: Omit<Signal, 'id' | 'created_at' | 'processed_at' | 'executed_at'>) {
  const { data, error } = await supabase
    .from('signals')
    .insert(signal)
    .select()
    .single();
  return { data, error };
}

export async function updateSignal(id: number, updates: Partial<Signal>) {
  const { data, error } = await supabase
    .from('signals')
    .update(updates)
    .eq('id', id)
    .select()
    .single();
  return { data, error };
}

// --- STRATEGIES ---
export async function getStrategies(activeOnly = false) {
  let query = supabase
    .from('strategies')
    .select('*')
    .order('created_at', { ascending: false });

  if (activeOnly) {
    query = query.eq('is_active', true);
  }

  const { data, error } = await query;
  return { data, error };
}

export async function getStrategyById(id: number) {
  const { data, error } = await supabase
    .from('strategies')
    .select('*')
    .eq('id', id)
    .single();
  return { data, error };
}

export async function createStrategy(strategy: Omit<Strategy, 'id' | 'created_at' | 'updated_at' | 'total_trades' | 'winning_trades' | 'losing_trades' | 'total_profit'>) {
  const { data, error } = await supabase
    .from('strategies')
    .insert(strategy)
    .select()
    .single();
  return { data, error };
}

export async function updateStrategy(id: number, updates: Partial<Strategy>) {
  const { data, error } = await supabase
    .from('strategies')
    .update(updates)
    .eq('id', id)
    .select()
    .single();
  return { data, error };
}

// --- SYSTEM CONFIG ---
export async function getSystemConfig(key?: string) {
  let query = supabase
    .from('system_config')
    .select('*');

  if (key) {
    query = query.eq('key', key);
    const { data, error } = await query.single();
    return { data, error };
  }

  const { data, error } = await query;
  return { data, error };
}

export async function setSystemConfig(key: string, value: any, description?: string) {
  const userId = (await getCurrentUser())?.id;
  
  const { data, error } = await supabase
    .from('system_config')
    .upsert({
      user_id: userId,
      key,
      value,
      description,
      updated_at: new Date().toISOString(),
    })
    .select()
    .single();
  
  return { data, error };
}

// ==================== REAL-TIME SUBSCRIPTIONS ====================
export function subscribeToTrades(callback: (trade: Trade) => void) {
  return supabase
    .channel('trades-channel')
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'trades' },
      (payload) => callback(payload.new as Trade)
    )
    .subscribe();
}

export function subscribeToSignals(callback: (signal: Signal) => void) {
  return supabase
    .channel('signals-channel')
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'signals' },
      (payload) => callback(payload.new as Signal)
    )
    .subscribe();
}

export function subscribeToMT5Accounts(callback: (account: MT5Account) => void) {
  return supabase
    .channel('mt5-accounts-channel')
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'mt5_accounts' },
      (payload) => callback(payload.new as MT5Account)
    )
    .subscribe();
}

// ==================== STATISTICS ====================
export async function getTradeStatistics() {
  const { data: trades, error } = await getTrades({ status: 'closed' });
  
  if (error || !trades) return null;

  const totalTrades = trades.length;
  const winningTrades = trades.filter((t) => (t.profit || 0) > 0).length;
  const losingTrades = trades.filter((t) => (t.profit || 0) <= 0).length;
  const totalProfit = trades.reduce((sum, t) => sum + (t.profit || 0), 0);
  const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;

  return {
    totalTrades,
    winningTrades,
    losingTrades,
    totalProfit,
    winRate,
  };
}

export async function getStrategyPerformance() {
  const { data: strategies, error } = await getStrategies();
  
  if (error || !strategies) return [];

  return strategies.map((s) => ({
    name: s.name,
    totalTrades: s.total_trades,
    winRate: s.win_rate || 0,
    totalProfit: s.total_profit,
    isActive: s.is_active,
  }));
}

export default supabase;
