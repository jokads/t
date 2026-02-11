//+------------------------------------------------------------------+
//| JokaBot MT5 - AI Trading Bot (HTTP / WebRequest)                 |
//+------------------------------------------------------------------+
#property strict
#property description "JokaBot MT5 - comunica via HTTP (WebRequest) com servidor local - substitui ficheiros por socket/http"

#include <Trade\Trade.mqh>
CTrade trade;

//================ INPUTS =================
input string    IN_SERVER_BASE_URL     = "http://127.0.0.1:9090"; // adicionar em Options -> Expert Advisors -> Allow WebRequest
input string    IN_REQUEST_ENDPOINT    = "/request";
input string    IN_RESULT_ENDPOINT     = "/result/"; // será concatenado com request_id
input int       IN_MAX_OPEN_TRADES     = 10;
input int       IN_TRADE_COOLDOWN      = 8;      // segundos
input int       IN_RESPONSE_TIMEOUT    = 6000;   // ms total (para polling)
input int       IN_RESPONSE_RETRIES    = 20;     // número de tentativas de polling
input int       IN_POLL_INTERVAL_MS    = 800;    // poll entre tentativas (ms)
input double    IN_RISK_PCT_PER_TRADE  = 0.5;
input bool      IN_DEBUG_LOG           = true;
input double    IN_MAX_VOLUME          = 5.0;    // volume máximo permitido (ex.: 5 lots)
input int       IN_HTTP_TIMEOUT_MS     = 10000;  // timeout para WebRequest (ms)

//================ GLOBALS =================
struct LastTrade { string symbol; datetime time; };
LastTrade last_trades[];

struct IndicatorDef { string name; int handle; };
IndicatorDef indicators[]; // lista simples de indicadores dinamicamente criada

enum EAState { STATE_IDLE, STATE_WAITING_AI };
EAState ea_state = STATE_IDLE;
string pending_request_id = "";
datetime ai_request_time = 0;

//================ LOG HELPERS =================
void LogInfo(const string s)  { if(IN_DEBUG_LOG) Print(TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS) + " | INFO  | " + s); }
void LogWarn(const string s)  { Print(TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS) + " | WARN  | " + s); }
void LogError(const string s) { Print(TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS) + " | ERROR | " + s); }

//================ STRING HELPERS (safe) =================
// Trim (left+right)
string TrimStringSafe(const string s)
{
   int L = StringLen(s);
   if(L == 0) return "";
   int start = 0;
   int end = L - 1;
   while(start <= end && StringGetCharacter(s, start) <= 32) start++;
   while(end >= start && StringGetCharacter(s, end) <= 32) end--;
   if(end < start) return "";
   return StringSubstr(s, start, end - start + 1);
}

// Uppercase safe (avoid passing constants by ref)
string UpperCopy(const string s)
{
   string tmp = s;
   // StringToUpper modifies in-place, so operate on tmp
   StringToUpper(tmp);
   return tmp;
}

//================ UTIL HELPERS =================
int DigitsSymbolSafe(const string symbol)
{
   int d = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   if(d <= 0) d = 5;
   return d;
}

double JsonGetNumber(const string txt, const string key, double default_val=0.0)
{
   int p = StringFind(txt, "\"" + key + "\"");
   if(p == -1) p = StringFind(txt, key);
   if(p == -1) return default_val;
   int colon = StringFind(txt, ":", p);
   if(colon == -1) return default_val;
   int i = colon + 1;
   while(i < StringLen(txt) && (StringGetCharacter(txt,i) <= 32)) i++;
   int j = i;
   while(j < StringLen(txt))
   {
      int ch = StringGetCharacter(txt, j);
      if(ch==',' || ch=='}' || ch==10 || ch==13) break;
      j++;
   }
   string tok = TrimStringSafe(StringSubstr(txt, i, j-i));
   if(StringLen(tok) == 0) return default_val;
   if(StringGetCharacter(tok,0) == '"' && StringLen(tok) >= 2) tok = StringSubstr(tok, 1, StringLen(tok)-2);
   return StringToDouble(tok);
}

string JsonGetString(const string txt, const string key, const string default_val = "")
{
   int p = StringFind(txt, "\"" + key + "\"");
   if(p == -1) p = StringFind(txt, key);
   if(p == -1) return default_val;
   int colon = StringFind(txt, ":", p);
   if(colon == -1) return default_val;
   int i = colon + 1;
   while(i < StringLen(txt) && (StringGetCharacter(txt,i) <= 32)) i++;
   if(i < StringLen(txt) && StringGetCharacter(txt,i) == '"')
   {
      i++;
      int j = i;
      while(j < StringLen(txt) && StringGetCharacter(txt,j) != '"') j++;
      return StringSubstr(txt, i, j-i);
   }
   int j = i;
   while(j < StringLen(txt))
   {
      int ch = StringGetCharacter(txt, j);
      if(ch==',' || ch=='}' || ch==10 || ch==13) break;
      j++;
   }
   return TrimStringSafe(StringSubstr(txt, i, j-i));
}

//================ INDICATOR MANAGEMENT =================
bool AddIndicator(const string name, const int handle)
{
   int n = ArraySize(indicators);
   ArrayResize(indicators, n+1);
   indicators[n].name = name;
   indicators[n].handle = handle;
   return true;
}

int FindIndicatorHandle(const string name)
{
   for(int i=0;i<ArraySize(indicators);i++)
      if(indicators[i].name == name) return indicators[i].handle;
   return INVALID_HANDLE;
}

void ReleaseAllIndicators()
{
   for(int i=0;i<ArraySize(indicators);i++)
   {
      if(indicators[i].handle != INVALID_HANDLE)
         IndicatorRelease(indicators[i].handle);
   }
   ArrayResize(indicators,0);
}

bool CreateDefaultIndicators(const string symbol)
{
   ReleaseAllIndicators();
   int h;

   h = iMA(symbol, PERIOD_M1, 9, 0, MODE_EMA, PRICE_CLOSE);
   AddIndicator("EMA9", h);

   h = iMA(symbol, PERIOD_M1, 21, 0, MODE_EMA, PRICE_CLOSE);
   AddIndicator("EMA21", h);

   h = iRSI(symbol, PERIOD_M1, 14, PRICE_CLOSE);
   AddIndicator("RSI14", h);

   h = iATR(symbol, PERIOD_M1, 14);
   AddIndicator("ATR14", h);

   return true;
}

bool FetchIndicatorValue(const string name, double &val)
{
   int handle = FindIndicatorHandle(name);
   if(handle == INVALID_HANDLE) return false;
   double arr[];
   ArraySetAsSeries(arr,true);
   if(CopyBuffer(handle,0,0,1,arr) <= 0) return false;
   val = arr[0];
   return true;
}

//================ POSITIONS SUMMARY =================
string BuildPositionsSummary()
{
   string result = "[";
   int total = PositionsTotal();
   for(int idx=0; idx<total; idx++)
   {
      ulong ticket = PositionGetTicket(idx);
      if(!PositionSelectByTicket(ticket)) continue;

      string pos_symbol = PositionGetString(POSITION_SYMBOL);
      double pos_volume = PositionGetDouble(POSITION_VOLUME);
      double pos_price  = PositionGetDouble(POSITION_PRICE_OPEN);
      double pos_sl     = PositionGetDouble(POSITION_SL);
      double pos_tp     = PositionGetDouble(POSITION_TP);
      double pos_profit = PositionGetDouble(POSITION_PROFIT);
      long pos_type     = (long)PositionGetInteger(POSITION_TYPE);
      string pos_side = (pos_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";

      if(StringLen(result) > 1) result += ",";
      result += "{";
      result += "\"ticket\":" + IntegerToString((int)ticket) + ",";
      result += "\"symbol\":\"" + pos_symbol + "\",";
      result += "\"side\":\"" + pos_side + "\",";
      result += "\"volume\":" + DoubleToString(pos_volume,2) + ",";
      result += "\"price\":" + DoubleToString(pos_price, DigitsSymbolSafe(pos_symbol)) + ",";
      result += "\"sl\":" + DoubleToString(pos_sl, DigitsSymbolSafe(pos_symbol)) + ",";
      result += "\"tp\":" + DoubleToString(pos_tp, DigitsSymbolSafe(pos_symbol)) + ",";
      result += "\"profit\":" + DoubleToString(pos_profit,2);
      result += "}";
   }
   result += "]";
   return result;
}

//================ HTTP helpers (WebRequest) =================
// Builds a uchar[] payload from a string (no trailing zero)
void StringToUcharArrayNoTerm(const string s, uchar &out[])
{
   int L = StringLen(s);
   ArrayResize(out, L);
   for(int i=0;i<L;i++) out[i] = (uchar)StringGetCharacter(s, i);
}

// Safe POST JSON
bool HttpPostJson(const string url, const string payload, string &out_body, int &out_status)
{
    uchar post[];
    StringToUcharArrayNoTerm(payload, post);
    int post_len = ArraySize(post);

    uchar result[];
    ArrayResize(result,0);
    string result_headers = "";

    int timeout = MathMax(1000, IN_HTTP_TIMEOUT_MS);

    int res = WebRequest("POST", url, "", "Content-Type: application/json\r\n", timeout, post, post_len, result, result_headers);

    if(res == -1)
    {
        int err = GetLastError();
        LogError("WebRequest POST denied/failed for URL: " + url + " | GetLastError=" + IntegerToString(err));
        out_status = -1;
        out_body = "";
        return false;
    }

    out_status = res;

    if(ArraySize(result) > 0)
        out_body = CharArrayToString(result, 0, ArraySize(result));
    else
        out_body = "";

    out_body = TrimStringSafe(out_body);

    // Log only small body preview to avoid huge logs
    string preview = (StringLen(out_body) > 300) ? StringSubstr(out_body,0,300) + "..." : out_body;
    LogInfo("POST concluído | Status=" + IntegerToString(out_status) + " | BodyPreview=" + preview);

    return true;
}

// Safe GET JSON
bool HttpGetJson(const string url, string &out_body, int &out_status)
{
    uchar empty_post[];
    ArrayResize(empty_post,0);
    uchar result[];
    ArrayResize(result,0);
    string result_headers = "";

    int timeout = MathMax(1000, IN_HTTP_TIMEOUT_MS);

    int res = WebRequest("GET", url, "", "", timeout, empty_post, 0, result, result_headers);

    if(res == -1)
    {
        int err = GetLastError();
        LogError("WebRequest GET denied/failed for URL: " + url + " | GetLastError=" + IntegerToString(err));
        out_status = -1;
        out_body = "";
        return false;
    }

    out_status = res;

    if(ArraySize(result) > 0)
        out_body = CharArrayToString(result, 0, ArraySize(result));
    else
        out_body = "";

    out_body = TrimStringSafe(out_body);

    string preview = (StringLen(out_body) > 300) ? StringSubstr(out_body,0,300) + "..." : out_body;
    LogInfo("GET concluído | Status=" + IntegerToString(out_status) + " | BodyPreview=" + preview);

    return true;
}

//================ RISK / STOPS / VOLUME HELPERS =================
double ConvertDistanceToPrice(string symbol, double distance, bool is_pips_guess = true)
{
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double pip_factor = (digits == 5 || digits == 3) ? 10.0 : 1.0;
   if(is_pips_guess && MathAbs(distance) < 10000.0) // wide guard
      return distance * pip_factor * point;
   return distance;
}

bool EnsureStops(string symbol, double &sl_price, double &tp_price, double entry_price, int order_type)
{
   int min_points = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(min_points < 0) min_points = 0;
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double min_distance = (double)min_points * point;

   double sl_dist = 0.0, tp_dist = 0.0;
   if(sl_price != 0.0) sl_dist = (order_type == ORDER_TYPE_BUY) ? (entry_price - sl_price) : (sl_price - entry_price);
   if(tp_price != 0.0) tp_dist = (order_type == ORDER_TYPE_BUY) ? (tp_price - entry_price) : (entry_price - tp_price);

   if(sl_price != 0.0 && sl_dist < min_distance)
   {
      if(order_type == ORDER_TYPE_BUY) sl_price = entry_price - min_distance; else sl_price = entry_price + min_distance;
   }
   if(tp_price != 0.0 && tp_dist < min_distance)
   {
      if(order_type == ORDER_TYPE_BUY) tp_price = entry_price + min_distance; else tp_price = entry_price - min_distance;
   }
   return true;
}

double NormalizeVolume(string symbol, double vol)
{
    // Obter informações do símbolo
    double min_vol  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
    double step     = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
    double max_vol  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);

    // Proteção básica
    if(min_vol <= 0) min_vol = 0.01;
    if(step <= 0) step = 0.01;
    if(max_vol <= 0) max_vol = 1000; // fallback arbitrário

    // Ajustar volume inicial
    if(vol <= 0) vol = min_vol;

    // Limitar volume entre min e max
    vol = MathMax(min_vol, MathMin(vol, max_vol));

    // Ajustar para o step correto
    double steps_d = MathFloor(vol / step + 1e-9);
    long steps = (long)steps_d;
    vol = steps * step;

    // Garantir que não fique abaixo do mínimo
    if(vol < min_vol) vol = min_vol;

    // Limitar ao máximo global definido no EA (se houver)
    vol = MathMin(vol, IN_MAX_VOLUME);

    return vol;
}

//================ COOLDOWN =================
int FindLastTrade(string symbol)
{
   for(int i=0;i<ArraySize(last_trades);i++)
      if(last_trades[i].symbol == symbol) return i;
   return -1;
}

bool CooldownOK(string symbol)
{
    for(int i=0;i<ArraySize(last_trades);i++)
    {
        if(last_trades[i].symbol == symbol)
        {
            int elapsed = (int)(TimeCurrent() - last_trades[i].time);
            return elapsed >= IN_TRADE_COOLDOWN;
        }
    }
    return true;
}

//================ SEND MARKET DATA (via HTTP POST) =================
bool SendMarketDataHTTP(string symbol, string &request_id_or_body, bool &immediate_response)
{
   double ema9=0, ema21=0, rsi=0, atr=0;
   FetchIndicatorValue("EMA9", ema9);
   FetchIndicatorValue("EMA21", ema21);
   FetchIndicatorValue("RSI14", rsi);
   FetchIndicatorValue("ATR14", atr);

   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double spread = ask - bid;
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   long leverage = (long)AccountInfoInteger(ACCOUNT_LEVERAGE);
   string pos_json = BuildPositionsSummary();

   double suggested_volume = 0.0;
   double risk_amount = balance * (IN_RISK_PCT_PER_TRADE / 100.0);
   if(atr > 0.0)
   {
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double atr_pips = atr / point;
      if(atr_pips > 0)
      {
         double pip_value_est = 1.0;
         double raw_vol = 0.0;
         raw_vol = risk_amount / (atr_pips * pip_value_est);
         suggested_volume = NormalizeVolume(symbol, raw_vol);
      }
   }
   if(suggested_volume <= 0) suggested_volume = NormalizeVolume(symbol, 0.01);

   string req_id = IntegerToString((int)TimeLocal()) + "_" + IntegerToString(MathRand());

   string payload = "{";
   payload += "\"request_id\":\"" + req_id + "\",";
   payload += "\"ts\":" + IntegerToString((int)TimeLocal()) + ",";
   payload += "\"symbol\":\"" + symbol + "\",";
   payload += "\"bid\":" + DoubleToString(bid, DigitsSymbolSafe(symbol)) + ",";
   payload += "\"ask\":" + DoubleToString(ask, DigitsSymbolSafe(symbol)) + ",";
   payload += "\"spread\":" + DoubleToString(spread, DigitsSymbolSafe(symbol)) + ",";
   payload += "\"ema9\":" + DoubleToString(ema9,5) + ",";
   payload += "\"ema21\":" + DoubleToString(ema21,5) + ",";
   payload += "\"rsi\":" + DoubleToString(rsi,2) + ",";
   payload += "\"atr\":" + DoubleToString(atr,5) + ",";
   payload += "\"balance\":" + DoubleToString(balance,2) + ",";
   payload += "\"equity\":" + DoubleToString(equity,2) + ",";
   payload += "\"free_margin\":" + DoubleToString(free_margin,2) + ",";
   payload += "\"leverage\":" + IntegerToString((int)leverage) + ",";
   payload += "\"open_positions\":" + pos_json + ",";
   payload += "\"suggested_volume\":" + DoubleToString(suggested_volume,2);
   payload += "}";

   string url = IN_SERVER_BASE_URL;
   // Ensure proper concatenation
   if(StringLen(IN_REQUEST_ENDPOINT) > 0)
   {
      if(StringSubstr(url, StringLen(url)-1,1) == "/")
         url = StringSubstr(url,0,StringLen(url)-1);
      url += IN_REQUEST_ENDPOINT;
   }

   string http_body;
   int http_status;
   if(!HttpPostJson(url, payload, http_body, http_status))
   {
      LogError("POST failed to " + url + " status=" + IntegerToString(http_status));
      // If POST failed (e.g. WebRequest not allowed), detect common error and stop
      if(http_status == -1) LogError("Verifica: URL adicionada em Options->Expert Advisors->Allow WebRequest?");
      return false;
   }

   // If server returned immediate decision JSON
   string decision = JsonGetString(http_body, "decision", "");
   if(StringLen(decision) > 0)
   {
      request_id_or_body = http_body;
      immediate_response = true;
      return true;
   }

   // otherwise accept request_id returned (async)
   string rid = JsonGetString(http_body, "request_id", "");
   if(StringLen(rid) > 0)
   {
      request_id_or_body = rid;
      immediate_response = false;
      return true;
   }

   // last resort: return our generated req_id
   request_id_or_body = req_id;
   immediate_response = false;
   return true;
}

//================ Poll result =================
// Poll result from server
bool PollResult(const string request_id, string &out_response)
{
    string base = IN_SERVER_BASE_URL;
    if(StringLen(base) > 0 && StringSubstr(base, StringLen(base)-1, 1) == "/")
        base = StringSubstr(base, 0, StringLen(base)-1);

    string url = base + IN_RESULT_ENDPOINT + request_id;

    int attempts = 0;
    int max_attempts = MathMax(1, IN_RESPONSE_RETRIES);
    int wait_ms = MathMax(60, IN_POLL_INTERVAL_MS);

    while(attempts < max_attempts)
    {
        string http_body = ""; 
        int http_status = 0;

        if(HttpGetJson(url, http_body, http_status))
        {
            string decision = JsonGetString(http_body, "decision", "");
            if(StringLen(decision) > 0)
            {
                out_response = http_body;
                return true;
            }
        }

        Sleep(wait_ms);
        attempts++;
    }

    // Nenhuma resposta válida recebida
    out_response = "";
    return false;
}

// Parse response JSON into action/volume/sl/tp (supports sl_pips/tp_pips)
bool ParseSignalFromJson(const string txt, string &action, double &volume, double &sl_price, double &tp_price)
{
    action = UpperCopy(JsonGetString(txt, "decision", ""));
    volume = 0.0;
    sl_price = 0.0;
    tp_price = 0.0;

    // Se decisão não foi explícita, tenta achar keywords
    if(StringLen(action) == 0)
    {
        string up = UpperCopy(txt);
        if(StringFind(up, "HOLD") >= 0) { action = "HOLD"; volume = 0; return true; }
        if(StringFind(up, "BUY") >= 0) action = "BUY";
        else if(StringFind(up, "SELL") >= 0) action = "SELL";
        else return false; // inválido
    }

    // Volume mínimo 0.01
    volume = MathMax(0.01, JsonGetNumber(txt, "volume", 0.01));

    // SL/TP podem vir em pips ou preço direto
    double sl_pips = JsonGetNumber(txt, "sl_pips", 0.0);
    double tp_pips = JsonGetNumber(txt, "tp_pips", 0.0);
    double sl_val  = JsonGetNumber(txt, "sl", 0.0);
    double tp_val  = JsonGetNumber(txt, "tp", 0.0);

    // Preço de entrada
    double entry = (action == "BUY") ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);

    // Calcula SL/TP baseado em pips ou preço
    sl_price = (sl_pips > 0.0) ? ((action=="BUY") ? entry - ConvertDistanceToPrice(_Symbol, sl_pips, true)
                                                 : entry + ConvertDistanceToPrice(_Symbol, sl_pips, true))
                               : sl_val;

    tp_price = (tp_pips > 0.0) ? ((action=="BUY") ? entry + ConvertDistanceToPrice(_Symbol, tp_pips, true)
                                                 : entry - ConvertDistanceToPrice(_Symbol, tp_pips, true))
                               : tp_val;

    // Garante stops mínimos exigidos pelo broker
    int order_type = (action == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
    EnsureStops(_Symbol, sl_price, tp_price, entry, order_type);

    // Segurança extra: SL/TP não podem ser negativos ou iguais a zero se trade real
    if(action != "HOLD")
    {
        if(sl_price <= 0.0) sl_price = 0.0; // fallback, sem SL
        if(tp_price <= 0.0) tp_price = 0.0; // fallback, sem TP
    }

    return true;
}


bool ExecuteOrderFromSignal(const string action, double volume, double sl_price, double tp_price)
{
    string symbol = _Symbol;

    // Normaliza e valida volume
    volume = NormalizeVolume(symbol, volume);
    if(volume <= 0)
    {
        LogWarn("Volume inválido após normalização: " + DoubleToString(volume,2));
        return false;
    }

    // Limita ao volume máximo definido no EA
    if(volume > IN_MAX_VOLUME)
    {
        LogWarn("Volume excede IN_MAX_VOLUME: " + DoubleToString(volume,2) + " | Limitando...");
        volume = IN_MAX_VOLUME;
    }

    // Verifica free margin
    double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
    if(free_margin <= 0)
    {
        LogWarn("Free margin insuficiente para abrir trade");
        return false;
    }

    // Executa ordem de mercado
    bool ok = false;
    if(action == "BUY") ok = trade.Buy(volume, symbol, 0, sl_price, tp_price);
    else if(action == "SELL") ok = trade.Sell(volume, symbol, 0, sl_price, tp_price);
    else
    {
        LogWarn("Ação desconhecida recebida: " + action);
        return false;
    }

    if(ok)
    {
        // Atualiza histórico de trades
        int idx = FindLastTrade(symbol);
        if(idx == -1)
        {
            ArrayResize(last_trades, ArraySize(last_trades) + 1);
            idx = ArraySize(last_trades) - 1;
        }
        last_trades[idx].symbol = symbol;
        last_trades[idx].time   = TimeCurrent();

        LogInfo("Trade executado | " + action + " | Vol=" + DoubleToString(volume,2) +
                " | SL=" + DoubleToString(sl_price,DigitsSymbolSafe(symbol)) +
                " | TP=" + DoubleToString(tp_price,DigitsSymbolSafe(symbol)));
        return true;
    }
    else
    {
        LogError("Falha ao executar trade | Retcode=" + IntegerToString(trade.ResultRetcode()) +
                 " | Desc=" + trade.ResultRetcodeDescription());
        return false;
    }
}

//================ MAIN HANDLERS =================
int OnInit()
{
    MathSrand((int)TimeLocal());
    ArrayResize(last_trades,0);
    CreateDefaultIndicators(_Symbol);
    EventSetTimer(1); // 1 segundo
    LogInfo("JokaBot inicializado - comunicação HTTP para " + IN_SERVER_BASE_URL);
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   ReleaseAllIndicators();
   LogInfo("JokaBot finalizado");
}

void OnTimer()
{
    if(ea_state != STATE_WAITING_AI) return;

    // Timeout
    if((TimeCurrent() - ai_request_time) * 1000 > IN_RESPONSE_TIMEOUT)
    {
        LogWarn("Timeout IA — cancelando pedido " + pending_request_id);
        ea_state = STATE_IDLE; pending_request_id = "";
        return;
    }

    string response;
    if(!PollResult(pending_request_id, response)) return;

    string action; double vol=0, sl=0, tp=0;
    if(!ParseSignalFromJson(response, action, vol, sl, tp))
    {
        LogWarn("Resposta IA inválida: " + response);
        ea_state = STATE_IDLE; pending_request_id = "";
        return;
    }

    ea_state = STATE_IDLE; pending_request_id = "";
    if(action != "HOLD") ExecuteOrderFromSignal(action, vol, sl, tp);
    else LogInfo("IA decidiu HOLD");
}

void OnTick()
{
    // ===============================
    // 1️⃣ Executar apenas em NOVO CANDLE (M1)
    // ===============================
    static datetime last_bar = 0;
    datetime current_bar = iTime(_Symbol, PERIOD_M1, 0);
    if(current_bar == last_bar) return;
    last_bar = current_bar;

    // ===============================
    // 2️⃣ Se estiver aguardando IA, NÃO faz nada
    // ===============================
    if(ea_state == STATE_WAITING_AI)
        return;

    // ===============================
    // 3️⃣ Verificações básicas do terminal
    // ===============================
    if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
    {
        LogWarn("AutoTrading desativado no terminal");
        return;
    }

    string symbol = _Symbol;

    // ===============================
    // 4️⃣ Cooldown por símbolo
    // ===============================
    if(!CooldownOK(symbol))
        return;

    // ===============================
    // 5️⃣ Limite de trades POR SÍMBOLO (corrigido)
    // ===============================
    int open_count = 0;
    for(int i = 0; i < PositionsTotal(); i++)
    {
        if(PositionGetTicket(i))
        {
            if(PositionGetString(POSITION_SYMBOL) == symbol)
                open_count++;
        }
    }

    if(open_count >= IN_MAX_OPEN_TRADES)
    {
        LogInfo("Limite de trades atingido para " + symbol);
        return;
    }

    // ===============================
    // 6️⃣ Enviar dados ao backend IA
    // ===============================
    string returned;
    bool immediate = false;

    if(!SendMarketDataHTTP(symbol, returned, immediate))
    {
        LogWarn("Falha ao enviar market data HTTP");
        return;
    }

    // ===============================
    // 7️⃣ Resposta imediata
    // ===============================
    if(immediate)
    {
        string action;
        double vol = 0, sl = 0, tp = 0;

        if(ParseSignalFromJson(returned, action, vol, sl, tp))
        {
            if(action == "HOLD")
            {
                LogInfo("IA retornou HOLD (imediato)");
                return;
            }

            // Segurança extra
            if(sl <= 0 || tp <= 0)
            {
                LogWarn("SL/TP inválidos na resposta imediata — trade abortado");
                return;
            }

            ExecuteOrderFromSignal(action, vol, sl, tp);
        }
        else
        {
            LogWarn("Resposta imediata inválida: " + returned);
        }
    }
    // ===============================
    // 8️⃣ Resposta assíncrona
    // ===============================
    else
    {
        pending_request_id = returned;
        ai_request_time = TimeCurrent();
        ea_state = STATE_WAITING_AI;

        LogInfo(
            "Market data enviado (async) | request_id=" + pending_request_id +
            " | aguardando resposta da IA..."
        );
    }
}

//+------------------------------------------------------------------+
