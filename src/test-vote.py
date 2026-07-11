import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time, json, imaplib, email as email_module, re, os, subprocess
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))

# Load config
with open('config.json') as f:
    CONFIG = json.load(f)
with open('accounts.json') as f:
    ACCOUNTS = json.load(f)

# Load .env
def load_env(path='.env'):
    env = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env

ENV = load_env(os.path.join(os.path.dirname(__file__), '..', '.env'))
IMAP_USER = ENV.get('IMAP_USER', '')
IMAP_PASS = ENV.get('IMAP_PASSWORD', '')
COMPANY = ENV.get('COMPANY_NAME', 'Galeri 24 Pegadaian')

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'template', 'index.html')
SS_PNG = os.path.join(os.path.dirname(__file__), '..', 'template', 'src', 'SS.png')

# === TOTP (Google Authenticator) ===
import pyotp
TOTP_SECRET = ENV.get('TOTP_SECRET', '')
totp = pyotp.TOTP(TOTP_SECRET) if TOTP_SECRET else None

# === DOT VARIATION GENERATOR ===
# Gmail ignore dots di local part: a.b@c = ab@c = a..b@c
# Voting site treat tiap kombinasi sebagai akun berbeda.
# Generate variasi dengan insert dot di posisi berbeda.
def generate_dot_variations(email, max_count=500):
    """Generate dot variations dari email. a@b.com → [a@b.com, a.@b.com, ...]"""
    if '@' not in email:
        return [email]
    local, domain = email.split('@', 1)
    if len(local) < 2:
        return [email]

    variations = [email]  # Original tanpa dot
    positions = list(range(1, len(local)))  # Posisi antar karakter

    # Generate kombinasi dengan 1 dot, 2 dots, 3 dots, dst
    from itertools import combinations
    for dot_count in range(1, len(positions) + 1):
        for combo in combinations(positions, dot_count):
            new_local = list(local)
            for pos in sorted(combo, reverse=True):
                new_local.insert(pos, '.')
            variation = ''.join(new_local) + '@' + domain
            if variation not in variations:
                variations.append(variation)
            if len(variations) >= max_count:
                return variations[:max_count]
    return variations[:max_count]

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

def get_otp(im_user=None, im_pass=None, timeout=90):
    im_user = im_user or IMAP_USER
    im_pass = im_pass or IMAP_PASS
    start = time.time()
    while time.time() - start < timeout:
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
            mail.login(im_user, im_pass)
            mail.select('INBOX')
            # Search ALL emails (bukan cuma UNSEEN — Gmail bisa auto-read)
            _, data = mail.search(None, 'ALL')
            now = time.time()
            for num in reversed(data[0].split()[-10:]):
                _, msg_data = mail.fetch(num, '(RFC822)')
                msg = email_module.message_from_bytes(msg_data[0][1])
                subj = msg.get('subject', '')
                date_str = msg.get('date', '')
                # Parse email date
                try:
                    from email.utils import parsedate_to_datetime
                    email_date = parsedate_to_datetime(date_str)
                    email_age = now - email_date.timestamp()
                    if email_age > 600:  # Skip emails older than 10 minutes
                        continue
                except:
                    pass
                if any(w in subj.lower() for w in ['polling', 'danantara', 'cx100', 'verifikasi', 'otp']):
                    body = ''
                    if msg.is_multipart():
                        for p in msg.walk():
                            if p.get_content_type() == 'text/plain':
                                body += str(p.get_payload(decode=True))
                    else:
                        body = str(msg.get_payload(decode=True))
                    m = re.search(r'\b(\d{4})\b', body)
                    if m:
                        mail.logout()
                        return m.group(1)
            mail.logout()
        except: pass
        time.sleep(3)
    return None

def make_evidence_dir():
    today = datetime.now(WIB).strftime('%d%m%Y')
    d = os.path.join('evidence', f'CX100 - {today}')
    os.makedirs(d, exist_ok=True)
    return d

def screenshot_evidence(driver, email_addr, evidence_dir):
    now = datetime.now(WIB)
    short_ts = now.strftime('%a %-d %b %-H:%M').replace('  ', ' ')
    full_ts = now.strftime('%Y-%m-%d %H:%M:%S') + ' WIB'

    with open(TEMPLATE) as f:
        html = f.read()
    html = html.replace('{{EMAIL}}', email_addr.lower())
    html = html.replace('{{COMPANY}}', COMPANY)
    html = html.replace('{{SHORT_TIMESTAMP}}', short_ts)
    html = html.replace('{{FULL_TIMESTAMP}}', full_ts)
    html = html.replace("url('src/SS.png')", "url('" + SS_PNG + "')")

    tmp = '/tmp/evidence_render.html'
    with open(tmp, 'w') as f:
        f.write(html)

    # Use Playwright for screenshot (more stable than uc.Chrome headless)
    import subprocess
    subprocess.run(['node', '-e', f'''
const {{ chromium }} = require('playwright-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
chromium.use(StealthPlugin());
(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage();
  await page.setViewportSize({{ width: 1920, height: 1080 }});
  await page.goto('file://{tmp}', {{ waitUntil: 'load' }});
  await page.waitForTimeout(1000);
  await page.screenshot({{ path: '{os.path.join(evidence_dir, email_addr.split("@")[0].lower() + "_" + now.strftime("%Y%m%d_%H%M%S") + ".png")}' }});
  await browser.close();
}})();
'''], check=True, timeout=30)

    filename = f'{email_addr.split("@")[0].lower()}_{now.strftime("%Y%m%d_%H%M%S")}.png'
    filepath = os.path.join(evidence_dir, filename)
    log(f'  Screenshot: {filepath}')
    return filepath

# === SUBMIT CONSTANTS ===
# next-action hash dari server (compile-time, gak berubah)
NEXT_ACTION_ID = '709cd13f602d4f2b96ca742284b6a070ccded9e797'


def process_account(acc):
    base_email = acc['email']  # Gmail asli (untuk login + IMAP)
    password = acc['password']
    # Poll email: dot variation dari base_email, atau explicit dari accounts.json
    poll_email_base = acc.get('poll_email', base_email)
    variations = generate_dot_variations(poll_email_base, max_count=500)
    poll_email = variations[acc.get('variation_index', 0) % len(variations)]
    log(f'[{base_email}] poll_email={poll_email}')

    subprocess.run(['pkill', '-f', 'undetected_chromedriver'], capture_output=True)
    time.sleep(1)

    # Chrome profile: pakai existing profile yang udah login Google
    chrome_user_data = ENV.get('CHROME_USER_DATA_DIR', '')
    if chrome_user_data:
        chrome_opts = uc.ChromeOptions()
        chrome_opts.add_argument(f'--user-data-dir={chrome_user_data}')
        chrome_opts.add_argument('--disable-extensions')
        driver = uc.Chrome(options=chrome_opts, headless=False, use_subprocess=True)
    else:
        driver = uc.Chrome(headless=False, use_subprocess=True)
    try:
        # === CDP hook: install fetch interceptor SEBELUM page load ===
        # Page.addScriptToEvaluateOnNewDocument inject JS sebelum Next.js load,
        # jadi semua fetch/XHR/request ke-capture dari awal.
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': r'''
            window.__capturedRequests = [];
            window.__jwt = null;
            // === XHR hook ONLY — jangan wrap fetch, biar Next.js handle response sendiri ===
            var _xhrOpen = XMLHttpRequest.prototype.open;
            var _xhrSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open = function(m, u) {
                this._method = m; this._url = u;
                return _xhrOpen.apply(this, arguments);
            };
            XMLHttpRequest.prototype.send = function(body) {
                var self = this;
                if (body) {
                    var bodyStr = String(body);
                    // Scan request body untuk JWT
                    var jwtMatch = bodyStr.match(/eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+/);
                    if (jwtMatch && !window.__jwt) window.__jwt = jwtMatch[0];
                    // Push captured request
                    window.__capturedRequests.push({
                        url: self._url, method: self._method,
                        body: bodyStr.substring(0, 500), ts: Date.now()
                    });
                }
                return _xhrSend.apply(this, arguments);
            };
            // === Fetch scan TANPA wrap — monkey-patch setelah original resolve ===
            // Intercept via Proxy (lebih aman, ga ganggu return value)
            var _origFetch = window.fetch;
            window.fetch = function() {
                var args = arguments;
                var url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
                var init = args[1] || {};
                var body = init.body || null;
                // Scan request body untuk JWT
                if (body && !window.__jwt) {
                    try {
                        var bodyStr = String(body);
                        var jwtMatch = bodyStr.match(/eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+/);
                        if (jwtMatch) window.__jwt = jwtMatch[0];
                    } catch(e) {}
                }
                // Langsung return original — jangan wrap response
                return _origFetch.apply(window, args);
            };
        '''})

        # === PHASE 1: Login Google ===
        driver.get('https://accounts.google.com/signin')
        time.sleep(2)

        # Cek apakah sudah login (redirect ke Google)
        if 'accounts.google.com' not in driver.current_url or 'signin' not in driver.current_url:
            log(f'  Already logged in')
        else:
            # Belum login — coba auto-login
            try:
                driver.find_element(By.CSS_SELECTOR, '#identifierId').send_keys(base_email)
                driver.find_element(By.CSS_SELECTOR, '#identifierNext').click()
                time.sleep(3)
                driver.find_element(By.CSS_SELECTOR, 'input[type="password"]').send_keys(password)
                driver.find_element(By.CSS_SELECTOR, '#passwordNext').click()
                time.sleep(5)
            except:
                pass

            # Cek apakah butuh 2FA / manual intervention
            if 'challenge' in driver.current_url or 'signin' in driver.current_url:
                # Coba auto-complete 2FA pakai TOTP
                if totp:
                    log(f'  2FA detected — generating TOTP code...')
                    time.sleep(5)  # Tunggu page load
                    totp_code = totp.now()
                    log(f'  TOTP: {totp_code}')
                    # Coba masukkan code ke input field
                    for attempt in range(10):
                        try:
                            # Cari semua input types
                            inputs = driver.find_elements(By.CSS_SELECTOR, 
                                'input[type="text"], input[type="tel"], input[type="number"], input[type="password"], input[name="totpPin"], input[id="totpPin"]')
                            for inp in inputs:
                                if inp.is_displayed() and len(inp.get_attribute('value') or '') < 6:
                                    inp.clear()
                                    inp.send_keys(totp_code)
                                    time.sleep(1)
                                    # Klik submit/next
                                    driver.execute_script('''
                                        var btns = document.querySelectorAll('button');
                                        for (var i = 0; i < btns.length; i++) {
                                            var t = (btns[i].textContent || '').toLowerCase();
                                            if (t.includes('next') || t.includes('submit') || t.includes('verif') || t.includes('lanjut')) {
                                                btns[i].click(); return;
                                            }
                                        }
                                    ''')
                                    log(f'  TOTP submitted')
                                    break
                            break
                        except:
                            time.sleep(2)
                    time.sleep(5)
                    # Re-check
                    if 'challenge' not in driver.current_url and 'signin' not in driver.current_url:
                        log(f'  Login OK (TOTP)')
                    else:
                        log(f'  ⚠️ TOTP failed — need manual login')
                        # Fallback: manual wait
                        for i in range(60):
                            time.sleep(2)
                            current = driver.current_url
                            if 'challenge' not in current and 'signin' not in current:
                                log(f'  Login OK (manual)')
                                break
                            if i % 5 == 0:
                                log(f'  Waiting for login... ({i*2}s)')
                        else:
                            log(f'  ❌ Login timeout')
                            return False
                else:
                    log(f'  ⚠️ Need manual login/2FA — complete in Chrome window')
                    # Manual wait max 120 detik
                    for i in range(60):
                        time.sleep(2)
                        current = driver.current_url
                        if 'challenge' not in current and 'signin' not in current:
                            log(f'  Login OK (manual)')
                            break
                        if i % 5 == 0:
                            log(f'  Waiting for login... ({i*2}s)')
                    else:
                        log(f'  ❌ Login timeout')
                        return False
            else:
                log(f'  Login OK')

        # === PHASE 2: Open poll ===
        driver.get(f'{CONFIG["voting"]["baseUrl"]}{CONFIG["voting"]["pollPath"]}?ref={CONFIG["vote"]["ref"]}&state=landing')
        time.sleep(3)

        # Bersihin SEMUA cookies + storage supaya treat sebagai user baru
        driver.delete_all_cookies()
        driver.execute_script('sessionStorage.clear(); localStorage.clear();')
        driver.get(f'{CONFIG["voting"]["baseUrl"]}{CONFIG["voting"]["pollPath"]}?ref={CONFIG["vote"]["ref"]}&state=landing')
        time.sleep(3)

        # === STEP 1: Email input form ===
        email_input = driver.find_element(By.CSS_SELECTOR, 'input[type="email"]')
        email_input.clear()
        email_input.send_keys(poll_email)
        driver.execute_script('document.querySelector("input[type=checkbox]").click()')
        time.sleep(1)

        # Turnstile — tunggu max 30 detik, log progress
        for i in range(15):
            time.sleep(2)
            r = driver.execute_script('return document.querySelector("[name=cf-turnstile-response]")?.value || "empty"')
            if r != 'empty':
                log(f'  Turnstile OK')
                break
            if i % 3 == 0:
                log(f'  Turnstile waiting... ({i*2}s)')
        else:
            log(f'  Turnstile timeout — continuing anyway')

        # Submit email form (trigger OTP)
        submit_result = driver.execute_script('''
            var buttons = document.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {
                var t = (buttons[i].textContent || '').trim().toLowerCase();
                if (t.includes('kirim') || t.includes('lanjut') || t.includes('submit') || t.includes('verifikasi') || t.includes('masukkan kode')) {
                    buttons[i].disabled = false; buttons[i].click();
                    return 'clicked: [' + i + '] ' + t;
                }
            }
            // Fallback: button pertama yang bukan disabled
            for (var i = 0; i < buttons.length; i++) {
                if (!buttons[i].disabled && buttons[i].offsetParent !== null) {
                    buttons[i].disabled = false; buttons[i].click();
                    return 'fallback: [' + i + '] ' + (buttons[i].textContent || '').trim().substring(0, 50);
                }
            }
            return 'no button found';
        ''')
        log(f'  Submit button: {submit_result}')
        time.sleep(8)  # Tunggu page transition lebih lama

        # === STEP 2: Handle consent/T&C page (muncul SETELAH email submit) ===
        text = driver.find_element(By.TAG_NAME, 'body').text
        log(f'  After email submit: {text[:150]}...')
        if 'Langkah 1' in text or 'Kebijakan' in text or 'Syarat' in text:
            log(f'  Consent page detected, accepting T&C...')
            driver.execute_script('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(1)
            driver.execute_script('''
                var cbs = document.querySelectorAll('input[type="checkbox"]');
                for (var i = 0; i < cbs.length; i++) { if (!cbs[i].checked) cbs[i].click(); }
            ''')
            time.sleep(1)
            consent_result = driver.execute_script('''
                var btns = document.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    var t = (btns[i].textContent || '').trim().toLowerCase();
                    if (t.includes('setuju') || t.includes('selanjutnya') || t.includes('lanjut')) {
                        btns[i].disabled = false; btns[i].click(); return 'clicked: ' + t;
                    }
                }
                return 'no consent button found';
            ''')
            log(f'  Consent: {consent_result}')
            time.sleep(5)
            text = driver.find_element(By.TAG_NAME, 'body').text
            log(f'  After consent: {text[:150]}...')

        # === PHASE 3: OTP verification ===
        text = driver.find_element(By.TAG_NAME, 'body').text
        log(f'  Page text: {text[:200]}')

        # Cek apakah sudah di OTP page
        is_otp_page = 'kode' in text.lower() or 'otp' in text.lower() or 'inbox' in text.lower() or 'masukkan' in text.lower()
        is_email_page = ('langkah 1' in text.lower() or 'kebijakan' in text.lower()) and not is_otp_page

        if is_email_page:
            log(f'  Still on email page, retrying submit...')
            driver.execute_script('''
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var t = (buttons[i].textContent || '').toLowerCase();
                    if (t.includes('kirim') || t.includes('lanjut') || t.includes('submit') || t.includes('verif')) {
                        buttons[i].disabled = false; buttons[i].click(); return 'clicked: ' + t;
                    }
                }
                return 'no button found';
            ''')
            time.sleep(10)
            text = driver.find_element(By.TAG_NAME, 'body').text
            log(f'  Page text after retry: {text[:200]}')

        # Coba klik "masukkan kode" / "kirim kode" button kalau ada
        driver.execute_script('''
            var buttons = document.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {
                var t = (buttons[i].textContent || '').toLowerCase();
                if (t.includes('masukkan kode') || t.includes('kirim kode') || t.includes('verifikasi')) {
                    buttons[i].disabled = false; buttons[i].click(); return;
                }
            }
        ''')
        time.sleep(3)

        # Coba get OTP dari IMAP (timeout 90 detik — email mungkin delay)
        otp = get_otp(im_user=IMAP_USER, im_pass=IMAP_PASS, timeout=90)
        if otp:
            log(f'  OTP: {otp}')
            # Cari input field untuk OTP
            otp_input = None
            for attempt in range(5):
                for inp in driver.find_elements(By.CSS_SELECTOR, 'input'):
                    if inp.is_displayed():
                        otp_input = inp
                        break
                if otp_input: break
                time.sleep(2)

            if otp_input:
                otp_input.click()
                otp_input.clear()
                otp_input.send_keys(otp)
                log(f'  OTP typed')
                time.sleep(2)
                try: otp_input.send_keys(Keys.RETURN)
                except: pass
                # Tunggu page transition setelah OTP submit
                log(f'  Waiting for OTP verification...')
                time.sleep(10)
                # Cek page text setelah OTP
                try:
                    text_after = driver.find_element(By.TAG_NAME, 'body').text
                    log(f'  After OTP: {text_after[:200]}...')
                except: pass
            else:
                log(f'  ❌ No OTP input found')
        else:
            log(f'  No OTP received (might be bypassed)')

        # === PHASE 4: UI flow — pilih sektor → subsector → factors → submit ===
        success = False
        text = driver.find_element(By.TAG_NAME, 'body').text
        log(f'  Page: {text[:150]}...')

        # STEP 1: Pilih sektor
        if 'Polling Sector' in text or 'Pilih sektor' in text:
            log(f'  Selecting sector...')
            driver.execute_script('''
                var items = document.querySelectorAll('button, a, [role="button"], [class*="card"], [class*="Card"], div[class*="cursor"]');
                for (var i = 0; i < items.length; i++) {
                    var t = (items[i].textContent || '').toLowerCase();
                    if (t.includes('keuangan') || t.includes('perbankan') || t.includes('pegadaian') ||
                        t.includes('jasa keuangan') || t.includes('finansial')) {
                        items[i].click(); return 'clicked: ' + t.substring(0, 50);
                    }
                }
                var cards = document.querySelectorAll('[class*="card"], [class*="Card"], div[class*="cursor"]');
                if (cards.length > 1) { cards[1].click(); return 'fallback: card[1]'; }
                return 'no sector found';
            ''')
            time.sleep(3)
            text = driver.find_element(By.TAG_NAME, 'body').text
            log(f'  After sector: {text[:150]}...')

        # STEP 2: Pilih subsector
        if 'subsektor' in text.lower() or 'Pilih sub' in text:
            log(f'  Selecting subsector...')
            driver.execute_script('''
                var items = document.querySelectorAll('button, a, [role="button"], [class*="card"], [class*="Card"], div[class*="cursor"]');
                for (var i = 0; i < items.length; i++) {
                    var t = (items[i].textContent || '').toLowerCase();
                    if (t.includes('gadai') || t.includes('pawn') || t.includes('pegadaian') ||
                        t.includes('pembiayaan') || t.includes('multiguna') || t.includes('multifinance')) {
                        items[i].click(); return 'clicked: ' + t.substring(0, 50);
                    }
                }
                return 'no subsector found';
            ''')
            time.sleep(3)
            text = driver.find_element(By.TAG_NAME, 'body').text
            log(f'  After subsector: {text[:150]}...')

        # STEP 3: Pilih factors
        if 'faktor' in text.lower() or 'unggul' in text.lower() or 'nilai' in text.lower():
            log(f'  Selecting factors...')
            factors = CONFIG['vote']['selectedFactors']
            for factor in factors:
                # Ambil 2 kata pertama untuk matching lebih presisi
                words = factor.lower().split()[:2]
                search = ' '.join(words)
                clicked = driver.execute_script(f'''
                    // Cari semua clickable elements (bukan header)
                    var all = document.querySelectorAll('div[class*="cursor"], div[class*="selectable"], label, button, [role="checkbox"], [role="option"]');
                    for (var i = 0; i < all.length; i++) {{
                        var el = all[i];
                        var t = (el.textContent || '').trim();
                        // Skip kalau text terlalu panjang (header/deskripsi)
                        if (t.length > 100) continue;
                        // Skip kalau text mengandung "pilih faktor" atau "Menurut Anda"
                        if (t.toLowerCase().includes('pilih faktor') || t.toLowerCase().includes('menurut anda')) continue;
                        if (t.toLowerCase().includes('{search}')) {{
                            el.click(); return 'clicked: ' + t.substring(0, 80);
                        }}
                    }}
                    return 'not found: {search}';
                ''')
                log(f'    → {clicked}')
                time.sleep(1)
            time.sleep(2)
            driver.execute_script('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(1)

        # STEP 4: Submit / Lanjut — loop multi-step
        for submit_attempt in range(5):
            log(f'  Submit step {submit_attempt + 1}...')
            text = driver.find_element(By.TAG_NAME, 'body').text

            # Cek apakah sudah di confirmation/result
            if 'berhasil' in text.lower() or 'success' in text.lower() or 'terima kasih' in text.lower() or 'terima kasih' in text.lower():
                success = True
                log(f'  ✅ Vote SUBMITTED!')
                break

            # Cek apakah di halaman pilih institusi
            if 'perusahaan' in text.lower() and ('mana' in text.lower() or 'logo' in text.lower() or 'klik' in text.lower()):
                log(f'  Institution selection — selecting Pegadaian...')
                driver.execute_script('''
                    var items = document.querySelectorAll('button, a, [role="button"], div[class*="cursor"], img, [class*="card"], [class*="Card"]');
                    for (var i = 0; i < items.length; i++) {
                        var t = (items[i].textContent || '').toLowerCase();
                        var alt = (items[i].getAttribute('alt') || '').toLowerCase();
                        var title = (items[i].getAttribute('title') || '').toLowerCase();
                        if (t.includes('pegadaian') || alt.includes('pegadaian') || title.includes('pegadaian')) {
                            items[i].click(); return 'clicked institution: ' + (t || alt || title).substring(0, 50);
                        }
                    }
                    var imgs = document.querySelectorAll('img');
                    for (var i = 0; i < imgs.length; i++) {
                        var alt = (imgs[i].getAttribute('alt') || '').toLowerCase();
                        if (alt.includes('pegadaian') || alt.includes('gadai')) {
                            imgs[i].click(); return 'clicked img: ' + alt.substring(0, 50);
                        }
                    }
                    return 'no pegadaian found';
                ''')
                time.sleep(3)

            # Coba klik Lanjut/Kirim/Submit
            submit_result = driver.execute_script('''
                var buttons = document.querySelectorAll('button');
                for (var i = buttons.length - 1; i >= 0; i--) {
                    var t = (buttons[i].textContent || '').toLowerCase().trim();
                    if (t.includes('kirim') || t.includes('submit') || t.includes('vote') ||
                        t.includes('selesai') || t.includes('konfirmasi') || t.includes('jawaban') ||
                        t === 'lanjut' || t.includes('lanjutkan')) {
                        buttons[i].disabled = false; buttons[i].click();
                        return 'clicked: [' + i + '] ' + t.substring(0, 50);
                    }
                }
                return 'none';
            ''')
            log(f'  → {submit_result}')
            if 'none' in submit_result:
                break
            time.sleep(5)
        # Cek hasil final
        if not success:
            text = driver.find_element(By.TAG_NAME, 'body').text
            log(f'  Final page: {text[:200]}...')
            if 'berhasil' in text.lower() or 'success' in text.lower() or 'terima kasih' in text.lower():
                success = True
                log(f'  ✅ Vote SUBMITTED!')

        # === PHASE 5: Screenshot evidence ===
        evidence_dir = make_evidence_dir()
        try:
            screenshot_evidence(driver, base_email, evidence_dir)
            log(f'  ✅ Done (success={success})')
            return True
        except:
            log(f'  ❌ Screenshot failed')
            return False

    except Exception as e:
        log(f'  ❌ {str(e)[:200]}')
        return False
    finally:
        try: driver.quit()
        except: pass

# Main
log(f'=== CX100 Auto Vote ({len(ACCOUNTS)} accounts) ===')
log(f'Company: {COMPANY}')
results = {'success': 0, 'failed': 0}

for acc in ACCOUNTS:
    for attempt in range(3):
        time.sleep(2)
        if process_account(acc):
            results['success'] += 1
            break
    else:
        results['failed'] += 1

log(f'=== DONE: {results["success"]}/{len(ACCOUNTS)} success ===')
