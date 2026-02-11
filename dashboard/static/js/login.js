/**
 * JokaMazKiBu Trading Bot - Login (Melhorado v4.1)
 * - Timeout / AbortController
 * - Backoff / retries
 * - Lockout persistente após N falhas
 * - Toggle mostrar senha + medidor de força
 * - CSRF token automático (meta tag ou hidden input)
 * - 2FA inline support (se servidor devolver requires_2fa)
 * - Mensagens acessíveis (aria-live)
 */

document.addEventListener('DOMContentLoaded', () => {
  // ---------- Config ----------
  const CONFIG = {
    FETCH_TIMEOUT_MS: 10000,
    MAX_RETRIES: 2,
    BACKOFF_BASE_MS: 700,
    LOCKOUT_AFTER: 6,
    LOCKOUT_DURATION_MS: 2 * 60 * 1000, // 2 min
    MIN_PASSWORD_LENGTH: 6,
    MIN_USERNAME_LENGTH: 3,
    AUTH_ENDPOINT: '/login',
    AUTH_2FA_ENDPOINT: '/login/2fa',
    REDIRECT_ON_SUCCESS: '/dashboard'
  };

  // ---------- Helpers ----------
  const el = id => document.getElementById(id);
  const qs = sel => document.querySelector(sel);
  const text = (node, s) => { if (node) node.textContent = s; };
  const html = (node, s) => { if (node) node.innerHTML = s; };
  const now = () => Date.now();

  const safeText = (str) => String(str).replace(/</g,'&lt;').replace(/>/g,'&gt;');

  const getCsrfToken = () => {
    const meta = qs('meta[name="csrf-token"]');
    if (meta?.content) return meta.content;
    const hidden = qs('input[name="csrf_token"]');
    if (hidden?.value) return hidden.value;
    return null;
  };

  async function fetchWithTimeout(url, opts={}, timeout=CONFIG.FETCH_TIMEOUT_MS) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
      const res = await fetch(url, {...opts, signal: controller.signal});
      clearTimeout(id);
      return res;
    } catch (err) {
      clearTimeout(id);
      throw err;
    }
  }

  const wait = ms => new Promise(r => setTimeout(r, ms));

  const passwordStrength = (pw) => {
    if (!pw) return {score:0,label:'Vazia'};
    let score = 0;
    if (pw.length >= 8) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    const label = ['Muito fraca','Fraca','Razoável','Boa','Forte'][Math.min(score,4)];
    return { score, label };
  };

  // ---------- DOM ----------
  const loginForm = el('loginForm');
  const usernameInput = el('username');
  const passwordInput = el('password');
  const loginBtn = loginForm?.querySelector('button[type="submit"]') ?? el('loginBtn');
  const loginMessage = el('errorMessage') ?? (() => {
    const p = document.createElement('p');
    p.id = 'errorMessage';
    p.className = 'error-message';
    p.setAttribute('aria-live','polite');
    loginForm?.appendChild(p);
    return p;
  })();
  const rememberMe = el('remember');
  const pwToggleId = 'pw-toggle-btn';
  const pwStrengthId = 'pw-strength';

  if (!loginForm || !usernameInput || !passwordInput || !loginBtn) {
    console.warn('Login: elementos essenciais não encontrados. Script parado.');
    return;
  }

  // ---------- State ----------
  let submitting = false;
  let failedAttempts = Number(localStorage.getItem('joka_failed_attempts') || 0);
  let lockoutExpiry = Number(localStorage.getItem('joka_lockout_expiry') || 0);

  // ---------- UI ----------
  const setMessage = (msg, type='info', persist=false) => {
    loginMessage.className = `error-message ${type}`;
    text(loginMessage, msg);
    loginMessage.style.display = msg ? 'block' : 'none';
    if (!persist) setTimeout(() => {
      if (loginMessage && loginMessage.textContent === msg) loginMessage.style.display='none';
    }, 6000);
  };
  const clearMessage = () => setMessage('', 'info');

  const disableForm = (v=true, replaceText=null) => {
    submitting = v;
    if (loginBtn) { loginBtn.disabled = v; if (replaceText!==null) loginBtn.textContent = replaceText; }
    [usernameInput,passwordInput].forEach(i => { if(i) i.disabled = v; });
  };

  const showSpinnerOnButton = (show=true) => {
    if (!loginBtn) return;
    if (show) {
      loginBtn.dataset.orig = loginBtn.textContent;
      loginBtn.innerHTML = `<span class="btn-spinner" aria-hidden="true"></span> ${safeText(loginBtn.dataset.loading || 'Processando...')}`;
    } else {
      loginBtn.innerHTML = safeText(loginBtn.dataset.orig || 'Entrar');
    }
  };

  // ---------- Lockout ----------
  const recordFailure = () => {
    failedAttempts++;
    localStorage.setItem('joka_failed_attempts', failedAttempts);
    if (failedAttempts >= CONFIG.LOCKOUT_AFTER) {
      lockoutExpiry = now() + CONFIG.LOCKOUT_DURATION_MS;
      localStorage.setItem('joka_lockout_expiry', lockoutExpiry);
      setMessage(`Muitas tentativas inválidas. Bloqueado por ${Math.round(CONFIG.LOCKOUT_DURATION_MS/1000)}s.`, 'error', true);
      disableForm(true);
      setTimeout(() => {
        failedAttempts = 0; lockoutExpiry = 0;
        localStorage.removeItem('joka_failed_attempts');
        localStorage.removeItem('joka_lockout_expiry');
        disableForm(false); clearMessage();
      }, CONFIG.LOCKOUT_DURATION_MS);
    }
  };

  const checkLockout = () => {
    if (lockoutExpiry && now() < lockoutExpiry) {
      const remaining = Math.ceil((lockoutExpiry-now())/1000);
      setMessage(`Bloqueado. Tente novamente em ${remaining}s.`, 'error');
      disableForm(true);
      return true;
    } else if (lockoutExpiry && now() >= lockoutExpiry) {
      failedAttempts = 0; lockoutExpiry = 0;
      localStorage.removeItem('joka_failed_attempts');
      localStorage.removeItem('joka_lockout_expiry');
      disableForm(false); clearMessage();
      return false;
    }
    return false;
  };

  // ---------- Password Extras ----------
  const ensurePwExtras = () => {
    if (!passwordInput) return;
    // toggle
    if (!el(pwToggleId)) {
      const btn = document.createElement('button');
      btn.type = 'button'; btn.id = pwToggleId; btn.className='pw-toggle';
      btn.setAttribute('aria-label','Mostrar senha'); btn.textContent='Mostrar';
      passwordInput.after(btn);
      btn.addEventListener('click', ()=>{
        const isPwd = passwordInput.type==='password';
        passwordInput.type=isPwd?'text':'password';
        btn.textContent=isPwd?'Ocultar':'Mostrar';
        btn.setAttribute('aria-label', isPwd?'Ocultar senha':'Mostrar senha');
      });
    }
    // strength meter
    if (!el(pwStrengthId)) {
      const meter = document.createElement('div');
      meter.id = pwStrengthId; meter.className='pw-strength';
      passwordInput.after(meter);
    }
    passwordInput.addEventListener('input', ()=>{
      const meter = el(pwStrengthId);
      const s = passwordStrength(passwordInput.value);
      if (meter) meter.textContent = `Força: ${s.label}`;
    });
  };

  // ---------- Validation ----------
  const validateInputs = () => {
    clearMessage();
    if (checkLockout()) return false;
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    if (username.length < CONFIG.MIN_USERNAME_LENGTH) {
      setMessage(`Usuário precisa ter ao menos ${CONFIG.MIN_USERNAME_LENGTH} caracteres.`, 'error');
      usernameInput.focus(); return false;
    }
    if (!password || password.length < CONFIG.MIN_PASSWORD_LENGTH) {
      setMessage(`Senha precisa ter ao menos ${CONFIG.MIN_PASSWORD_LENGTH} caracteres.`, 'error');
      passwordInput.focus(); return false;
    }
    const strength = passwordStrength(password);
    if (strength.score < 2) { // força mínima
      setMessage('Senha muito fraca. Força mínima: Razoável', 'error');
      passwordInput.focus(); return false;
    }
    return true;
  };

  // ---------- 2FA ----------
  function prompt2FA(onSubmit){
    let container = el('twoFaContainer');
    if (!container){
      container = document.createElement('div');
      container.id='twoFaContainer'; container.className='twofa';
      loginForm.appendChild(container);
    }
    html(container, `
      <label for="twofaCode">Código 2FA</label>
      <input id="twofaCode" name="twofaCode" autocomplete="one-time-code"/>
      <div class="twofa-actions">
        <button id="twofaSubmit" class="btn">Enviar 2FA</button>
        <button id="twofaCancel" class="btn btn-ghost">Cancelar</button>
      </div>
      <p id="twofaMessage" class="error-message" style="display:none;" aria-live="polite"></p>
    `);
    const code = el('twofaCode');
    const submit = el('twofaSubmit');
    const cancel = el('twofaCancel');
    const msg = el('twofaMessage');
    const cleanup = ()=>container.remove();

    submit.addEventListener('click', async ()=>{
      const val = code.value?.trim();
      if(!val){ msg.style.display='block'; text(msg,'Informe o código 2FA'); return; }
      text(msg,'Enviando...'); msg.style.display='block';
      try { await onSubmit(val); cleanup(); }
      catch(err){ text(msg, `Erro 2FA: ${err.message||err}`); msg.style.display='block'; }
    });
    cancel.addEventListener('click', ()=>{ cleanup(); clearMessage(); });
    code.focus();
  }

  // ---------- Login / retries ----------
  const doLogin = async (payload, retriesLeft=CONFIG.MAX_RETRIES)=>{
    const csrf = getCsrfToken();
    const headers = {'Content-Type':'application/json'};
    if(csrf) headers['X-CSRF-Token'] = csrf;
    try{
      const res = await fetchWithTimeout(CONFIG.AUTH_ENDPOINT,{method:'POST',headers,body:JSON.stringify(payload)},CONFIG.FETCH_TIMEOUT_MS);
      if(!res.ok){ const txt=await res.text().catch(()=>null); throw new Error(`HTTP ${res.status} ${txt||''}`);}
      return await res.json().catch(()=>({success:false,error:'Resposta inválida do servidor'}));
    }catch(err){
      if(retriesLeft>0){
        const backoff = CONFIG.BACKOFF_BASE_MS*Math.pow(2,CONFIG.MAX_RETRIES-retriesLeft);
        console.warn(`Falha login, tentando novamente em ${backoff}ms`,err);
        await wait(backoff);
        return doLogin(payload,retriesLeft-1);
      }
      throw err;
    }
  };

  // ---------- Handle ----------
  const handleLogin = async (e)=>{
    e?.preventDefault();
    if(submitting) return;
    if(!validateInputs()) return;

    const payload={username:usernameInput.value.trim(),password:passwordInput.value};
    disableForm(true); showSpinnerOnButton(true); setMessage('Autenticando...','info');

    try{
      const response = await doLogin(payload);
      if(!response) throw new Error('Resposta vazia');
      if(response.success){
        setMessage('Login efetuado com sucesso!','success');
        localStorage.removeItem('joka_failed_attempts'); localStorage.removeItem('joka_lockout_expiry');
        if(rememberMe?.checked) localStorage.setItem('rememberedUsername',payload.username);
        else localStorage.removeItem('rememberedUsername');
        setTimeout(()=> window.location.href=response.next||CONFIG.REDIRECT_ON_SUCCESS,600);
        return;
      }
      if(response.requires_2fa){
        setMessage('Código 2FA requisitado. Insira abaixo.','info',true);
        prompt2FA(async (code)=>{
          disableForm(true,'Validando 2FA...'); showSpinnerOnButton(true);
          try{
            const body={username:payload.username,code};
            const csrf=getCsrfToken();
            const headers={'Content-Type':'application/json'};
            if(csrf) headers['X-CSRF-Token']=csrf;
            const r = await fetchWithTimeout(CONFIG.AUTH_2FA_ENDPOINT,{method:'POST',headers,body:JSON.stringify(body)},CONFIG.FETCH_TIMEOUT_MS);
            if(!r.ok){ const t=await r.text().catch(()=>null); throw new Error(`HTTP ${r.status} ${t||''}`);}
            const jr = await r.json().catch(()=>({success:false,error:'Resposta inválida'}));
            if(jr.success){ setMessage('2FA ok! Redirecionando...','success'); setTimeout(()=> window.location.href=jr.next||CONFIG.REDIRECT_ON_SUCCESS,500);}
            else throw new Error(jr.error||'Código inválido');
          }catch(err){ setMessage(`Erro 2FA: ${err.message}`,'error'); disableForm(false,'Entrar'); showSpinnerOnButton(false); throw err; }
        });
        return;
      }
      recordFailure();
      setMessage(`Erro: ${response.error||'Credenciais inválidas'}`,'error');
      disableForm(false,'Entrar'); showSpinnerOnButton(false);
    }catch(err){
      console.error('Erro no login:',err);
      recordFailure();
      setMessage(`Erro de comunicação: ${err.message||'timeout'}`,'error');
      disableForm(false,'Entrar'); showSpinnerOnButton(false);
    }
  };

  // ---------- Bindings ----------
  loginForm.addEventListener('submit',handleLogin);
  [usernameInput,passwordInput].forEach(inp=>{
    if(!inp) return;
    inp.addEventListener('keypress',(ev)=>{ if(ev.key==='Enter'){ ev.preventDefault(); handleLogin(ev); }});
  });

  // ---------- Init ----------
  const savedName = localStorage.getItem('rememberedUsername');
  if(savedName && usernameInput){ usernameInput.value=savedName; if(rememberMe) rememberMe.checked=true; }
  ensurePwExtras();
  if(!checkLockout()) setMessage('Por favor faça login','info');

  // expose debug
  window.jokaLogin={validateInputs,handleLogin,recordFailure,failedAttempts};
});
