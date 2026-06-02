"""
Test server blueprint — hub SSO di laboratorio + template Flask
================================================================

In locale: stub portale (`/stub-portal`) che emette JWT verso il client (es. UseIt SvelteKit).
In rete: sostituito da un hub SSO reale; il client imposta PORTAL_URL su quell’host.

Resta anche un template/blueprint per team che integrano SSO in applicazioni Flask.

Funzionalità implementate:
  - Landing page pubblica
  - Autenticazione SSO (portale checkin)
  - Due pagine ad accesso riservato (Dashboard, Reports)
  - Pagina Settings
  - Logout con ritorno al portale
  - Whitelist account autorizzati
  - Rate limiting: sessioni max per utente e globali
"""

import os
import sys
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt
from flask import Flask, abort, render_template, request, session, redirect, url_for, jsonify
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

# --- Import SSO Middleware ---
sys.path.insert(0, os.path.dirname(__file__))
try:
    from shared_modules.sso_middleware import SSOMiddleware, WhitelistManager, RateLimiter, render_sso_error
except ImportError:
    from sso_middleware import SSOMiddleware, WhitelistManager, RateLimiter, render_sso_error


# ============================================================
# CONFIGURAZIONE APP
# ============================================================

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

app.secret_key = os.getenv('SERVER_SECRET_KEY', 'dev-secret-change-in-production')
app.permanent_session_lifetime = timedelta(hours=8)

# Modalità SSO
SSO_MODE = os.getenv('SSO_MODE', 'production').lower()
DEV_USER_EMAIL = os.getenv('DEV_USER_EMAIL', 'demo@example.com')

SSO_CONFIG = {
    'jwt_secret': os.getenv('JWT_SECRET'),
    'jwt_algorithm': 'HS256',
    'jwt_issuer': 'sso-portal',
    'jwt_audience': os.getenv('APP_AUDIENCE', 'blueprint-app'),
    'session_timeout': 28800,
    'portal_url': os.getenv('PORTAL_URL', 'http://localhost:5000')
}

if SSO_MODE == 'production' and not SSO_CONFIG['jwt_secret']:
    raise ValueError("JWT_SECRET non configurato! Aggiungilo al file .env")

if SSO_MODE == 'production':
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )

# ============================================================
# WHITELIST & RATE LIMITER
# ============================================================

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

PREFS_DIR = os.path.join(DATA_DIR, 'prefs')
os.makedirs(PREFS_DIR, exist_ok=True)

PREFS_DEFAULTS = {
    'theme': 'light',
    'notifications': 'on'
}

whitelist_manager = WhitelistManager(
    whitelist_path=os.path.join(DATA_DIR, 'whitelist.json')
)

rate_limiter = RateLimiter(
    max_sessions_per_user=int(os.getenv('MAX_SESSIONS_PER_USER', 3)),
    max_sessions_global=int(os.getenv('MAX_SESSIONS_GLOBAL', 100)),
    session_ttl_seconds=28800  # 8 ore, allineato con session lifetime
)

# ============================================================
# SSO MIDDLEWARE
# ============================================================

sso_middleware = SSOMiddleware(
    **SSO_CONFIG,
    whitelist_manager=whitelist_manager,
    rate_limiter=rate_limiter
)


# ============================================================
# UTILITY
# ============================================================

def get_username(email: str) -> str:
    return email.split('@')[0]


# ============================================================
# USER PREFERENCES — persistenza su file JSON per utente
# ============================================================

def _prefs_path(email: str) -> str:
    """Restituisce il path del file JSON delle preferenze per un utente.
    Il nome file è sanitizzato: solo caratteri alfanumerici, . e @.
    """
    safe = ''.join(c for c in email.lower() if c.isalnum() or c in ('.', '@', '_', '-'))
    return os.path.join(PREFS_DIR, f'{safe}.json')


def load_user_prefs(email: str) -> dict:
    """
    Carica le preferenze utente dal file JSON.
    Se il file non esiste o è corrotto, ritorna i default.
    Usa merge con i default per garantire che nuove chiavi siano sempre presenti.
    """
    path = _prefs_path(email)
    if os.path.exists(path):
        try:
            import json
            with open(path, 'r') as f:
                saved = json.load(f)
            return {**PREFS_DEFAULTS, **saved}   # merge: saved sovrascrive i default
        except Exception as e:
            app.logger.warning(f"Errore lettura prefs per {email}: {e}")
    return dict(PREFS_DEFAULTS)


def save_user_prefs(email: str, prefs: dict):
    """Salva le preferenze utente su file JSON."""
    import json
    path = _prefs_path(email)
    try:
        with open(path, 'w') as f:
            json.dump(prefs, f, indent=2)
        app.logger.debug(f"Preferenze salvate per {email}")
    except Exception as e:
        app.logger.error(f"Errore salvataggio prefs per {email}: {e}")


# ============================================================
# ROUTE SSO
# ============================================================

@app.route('/sso/login')
def sso_login():
    """
    Endpoint SSO. Il portale checkin chiama questa URL passando il JWT.
    Questo è l'unico punto di ingresso autenticato nell'applicazione.
    """
    token = request.args.get('token')

    # --- Modalità DEV: simula il login senza portale reale ---
    if SSO_MODE == 'dev' and not token:
        dev_email = request.args.get('email') or DEV_USER_EMAIL
        app.logger.info(f"DEV MODE: login simulato per {dev_email}")
        user_data = {
            'email': dev_email,
            'name': get_username(dev_email).replace('.', ' ').title(),
            'googleId': 'dev-user-id',
            'picture': ''
        }
        return _complete_login(user_data)

    if not token:
        return render_sso_error(
            "Token SSO mancante. Accedi tramite il portale.",
            SSO_CONFIG['portal_url']
        )

    try:
        user_data = sso_middleware.validate_jwt(token)
        return _complete_login(user_data)
    except Exception as e:
        app.logger.error(f"Errore validazione SSO: {e}")
        return render_sso_error(
            f"Token SSO non valido o scaduto. Effettua nuovamente il login.",
            SSO_CONFIG['portal_url']
        )


def _complete_login(user_data: dict):
    """
    Logica comune post-validazione JWT:
    1. Verifica whitelist
    2. Verifica rate limit
    3. Crea sessione e redirect alla dashboard
    """
    email = user_data.get('email', '')

    # 1. Controllo whitelist
    if not whitelist_manager.is_authorized(email):
        app.logger.warning(f"Accesso negato da whitelist: {email}")
        return render_sso_error(
            f"Il tuo account ({email}) non è autorizzato ad accedere a questa applicazione. "
            "Contatta l'amministratore se ritieni sia un errore.",
            SSO_CONFIG['portal_url'],
            status_code=403,
            title="Account Non Autorizzato",
            icon="🚫"
        )

    # 2. Controllo rate limit - registra la nuova sessione
    session_id = secrets.token_hex(32)
    allowed, reason = rate_limiter.register_session(session_id, email)
    if not allowed:
        app.logger.warning(f"Rate limit raggiunto per: {email}")
        return render_sso_error(
            reason,
            SSO_CONFIG['portal_url'],
            status_code=429,
            title="Troppe Sessioni Attive",
            icon="⏱️"
        )

    # 3. Crea sessione Flask
    sso_middleware.create_session(user_data, session, session_id=session_id)

    # 4. Carica preferenze persistenti dal file e le mette in sessione
    session['preferences'] = load_user_prefs(email)

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    """Logout: rimuove la sessione (anche dal rate limiter) e torna al portale."""
    sid = session.get('session_id')
    if sid:
        rate_limiter.remove_session(sid)
    session.clear()
    return redirect(SSO_CONFIG['portal_url'])


# ============================================================
# STUB PORTALE SSO (solo test locale — NON in produzione reale)
# ============================================================
#
# Il template blueprint è un *client* SSO: in production la login page è
# PORTAL_URL (portale checkin esterno). Se non hai quel portale in ascolto,
# localhost:5000 sembra "morto". Con STUB_PORTAL_ENABLED=true questa app
# emula il portale: emette un JWT e reindirizza al client (es. UseIt SvelteKit).


def _stub_portal_enabled() -> bool:
    return os.getenv('STUB_PORTAL_ENABLED', '').lower() in ('1', 'true', 'yes')


def _issue_stub_portal_jwt(email: str) -> str:
    secret = SSO_CONFIG.get('jwt_secret')
    if not secret:
        raise RuntimeError('JWT_SECRET richiesto per emettere token stub')
    now = datetime.now(timezone.utc)
    payload = {
        'sub': email,
        'email': email,
        'name': get_username(email).replace('.', ' ').title(),
        'googleId': 'stub-portal-user',
        'picture': '',
        'iss': SSO_CONFIG.get('jwt_issuer') or 'sso-portal',
        'aud': SSO_CONFIG['jwt_audience'],
        'iat': now,
        'exp': now + timedelta(minutes=30),
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    return token.decode('utf-8') if isinstance(token, bytes) else str(token)


@app.route('/stub-portal')
def stub_portal():
    """
    Stand-in del portale SSO per test in laboratorio.

    Richiede STUB_PORTAL_ENABLED=true e JWT_SECRET (stesso valore sul client UseIt).
    GET senza go=1: pagina login hub. GET con go=1: emette JWT e reindirizza al client con ?token=...
    """
    if not _stub_portal_enabled():
        abort(404)

    if request.args.get('go') != '1':
        return render_template(
            'stub_portal_login.html',
            default_email=request.args.get('email') or DEV_USER_EMAIL,
        )

    email = request.args.get('email') or DEV_USER_EMAIL
    callback = os.getenv(
        'STUB_CLIENT_CALLBACK',
        'http://localhost:5173/sso/login',
    ).strip()

    try:
        token = _issue_stub_portal_jwt(email)
    except Exception as exc:
        app.logger.error('stub-portal: impossibile emettere JWT: %s', exc)
        abort(503)

    sep = '&' if ('?' in callback) else '?'
    target = f'{callback}{sep}token={quote(token, safe="")}'
    return redirect(target)


# ============================================================
# ROUTE PUBBLICHE
# ============================================================

@app.route('/')
def index():
    """
    Landing page pubblica — accessibile senza autenticazione.
    Se l'utente è già autenticato, mostra un link diretto alla dashboard.
    """
    logged_in = 'user' in session
    user = session.get('user') if logged_in else None
    return render_template('index.html',
                           logged_in=logged_in,
                           user=user,
                           portal_url=SSO_CONFIG['portal_url'],
                           sso_mode=SSO_MODE,
                           dev_user_email=DEV_USER_EMAIL)


# ============================================================
# ROUTE PROTETTE
# ============================================================

@app.route('/dashboard')
@sso_middleware.sso_login_required
def dashboard():
    """Pagina principale per l'utente autenticato."""
    user = session['user']
    stats = rate_limiter.get_stats()
    prefs = session.get('preferences') or load_user_prefs(session['user']['email'])
    return render_template('dashboard.html',
                           user=user,
                           portal_url=SSO_CONFIG['portal_url'],
                           stats=stats,
                           prefs=prefs)


@app.route('/reports')
@sso_middleware.sso_login_required
def reports():
    """Pagina di esempio ad accesso riservato — Reports."""
    user = session['user']
    prefs = session.get('preferences') or load_user_prefs(user['email'])
    # Dati fittizi per il template
    sample_reports = [
        {"id": 1, "name": "Report Q1 2025", "date": "2025-03-31", "status": "Completato"},
        {"id": 2, "name": "Report Q2 2025", "date": "2025-06-30", "status": "Completato"},
        {"id": 3, "name": "Report Q3 2025", "date": "2025-09-30", "status": "In corso"},
        {"id": 4, "name": "Report Q4 2025", "date": "2025-12-31", "status": "Pianificato"},
    ]
    return render_template('reports.html',
                           user=user,
                           portal_url=SSO_CONFIG['portal_url'],
                           reports=sample_reports,
                           prefs=prefs)


@app.route('/settings', methods=['GET', 'POST'])
@sso_middleware.sso_login_required
def settings():
    """Pagina impostazioni utente."""
    user = session['user']

    if request.method == 'POST':
        prefs = {
            'theme': request.form.get('theme', 'light'),
            'notifications': request.form.get('notifications', 'off')
        }
        # Salva su file JSON (persistente tra sessioni e riavvii)
        save_user_prefs(user['email'], prefs)
        # Aggiorna anche la sessione corrente
        session['preferences'] = prefs
        return redirect(url_for('settings', saved='1'))

    prefs = session.get('preferences', load_user_prefs(user['email']))
    return render_template('settings.html',
                           user=user,
                           portal_url=SSO_CONFIG['portal_url'],
                           prefs=prefs,
                           saved=request.args.get('saved'))


# ============================================================
# ROUTE DI UTILITÀ
# ============================================================

@app.route('/api/session-stats')
@sso_middleware.sso_login_required
def session_stats():
    """API endpoint per statistiche sessioni (utile per debug/admin)."""
    return jsonify(rate_limiter.get_stats())


@app.route('/favicon.ico')
def favicon():
    return '', 204


# ============================================================
# DEV ROUTE (solo in modalità dev)
# ============================================================

@app.route('/dev/auto-login')
def dev_auto_login():
    if SSO_MODE != 'dev':
        return 'Non disponibile in production', 403
    return redirect(url_for('sso_login'))


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return render_sso_error("Pagina non trovata.", SSO_CONFIG['portal_url'], 404,
                            title="Pagina Non Trovata", icon="🔍")


@app.errorhandler(403)
def forbidden(e):
    return render_sso_error("Accesso negato.", SSO_CONFIG['portal_url'], 403,
                            title="Accesso Negato", icon="🚫")


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    app.logger.info("Test server blueprint avviato")
    app.logger.info(f"Modalità SSO: {SSO_MODE.upper()}")
    app.logger.info(f"Portale SSO: {SSO_CONFIG['portal_url']}")
    app.logger.info(f"Audience JWT: {SSO_CONFIG['jwt_audience']}")
    app.logger.info(f"Rate limit: max {rate_limiter.max_sessions_per_user} sessioni/utente, "
                    f"max {rate_limiter.max_sessions_global} globali")
    if _stub_portal_enabled():
        app.logger.warning(
            "STUB_PORTAL_ENABLED: stub portale attivo su /stub-portal (solo test locale)"
        )

    app.run(
        debug=os.getenv('DEBUG', 'False').lower() == 'true',
        host='127.0.0.1',
        port=int(os.getenv('PORT', 3020))
    )
