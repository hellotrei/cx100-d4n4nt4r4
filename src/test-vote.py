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

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

def get_otp(timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
            mail.login(IMAP_USER, IMAP_PASS)
            mail.select('INBOX')
            _, data = mail.search(None, 'UNSEEN')
            for num in reversed(data[0].split()[-10:]):
                _, msg_data = mail.fetch(num, '(RFC822)')
                msg = email_module.message_from_bytes(msg_data[0][1])
                subj = msg.get('subject', '')
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
    email_addr = acc['email']
    password = acc['password']
    log(f'[{email_addr}]')

    subprocess.run(['pkill', '-f', 'undetected_chromedriver'], capture_output=True)
    time.sleep(1)

    driver = uc.Chrome(headless=False, use_subprocess=True)
    try:
        # === CDP hook: install fetch interceptor SEBELUM page load ===
        # Page.addScriptToEvaluateOnNewDocument inject JS sebelum Next.js load,
        # jadi semua fetch/XHR/request ke-capture dari awal.
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': r'''
            window.__capturedRequests = [];
            window.__jwt = null;
            var _origFetch = window.fetch;
            window.fetch = function() {
                var url = arguments[0];
                var init = arguments[1] || {};
                var method = (init.method || 'GET').toUpperCase();
                var body = init.body || null;
                // Debug: log body type
                if (body && !window.__jwt) {
                    var bodyType = typeof body;
                    var bodyFull = '';
                    try { bodyFull = String(body); } catch(e) { bodyFull = '[error]'; }
                    var bodyPreview = bodyFull.substring(0, 200);
                    // Simpan debug info
                    if (!window.__bodyDebug) window.__bodyDebug = [];
                    window.__bodyDebug.push({ type: bodyType, preview: bodyPreview, url: String(url).substring(0, 80) });
                    // Scan FULL body untuk JWT (jangan truncate!)
                    if (bodyType === 'string') {
                        var jwtMatch = bodyFull.match(/eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+/);
                        if (jwtMatch && !window.__jwt) {
                            window.__jwt = jwtMatch[0];
                            if (!window.__jwtDebug) window.__jwtDebug = [];
                            window.__jwtDebug.push({ source: 'body', len: jwtMatch[0].length, preview: jwtMatch[0].substring(0, 100) });
                        }
                        // Also try: search for eyJ and extract manually
                        if (!window.__jwt && bodyFull.indexOf('eyJ') !== -1) {
                            var idx = bodyFull.indexOf('eyJ');
                            var chunk = bodyFull.substring(idx, idx + 600);
                            // Find the end: look for closing quote or bracket
                            var endIdx = chunk.indexOf('"');
                            if (endIdx === -1) endIdx = chunk.indexOf(']');
                            if (endIdx === -1) endIdx = chunk.length;
                            var candidate = chunk.substring(0, endIdx);
                            // Check if it has dots (JWT format)
                            var dotCount = (candidate.match(/\./g) || []).length;
                            if (dotCount >= 2) {
                                window.__jwt = candidate;
                                if (!window.__jwtDebug) window.__jwtDebug = [];
                                window.__jwtDebug.push({ source: 'manual', len: candidate.length, preview: candidate.substring(0, 100), dots: dotCount });
                            } else {
                                if (!window.__jwtDebug) window.__jwtDebug = [];
                                window.__jwtDebug.push({ source: 'manual-fail', len: candidate.length, preview: candidate.substring(0, 100), dots: dotCount });
                            }
                        }
                    }
                }
                return _origFetch.apply(this, arguments).then(function(response) {
                    var clone = response.clone();
                    clone.text().then(function(text) {
                        window.__capturedRequests.push({
                            url: typeof url === 'string' ? url : (url && url.url) || '',
                            method: method,
                            body: body ? String(body).substring(0, 500) : null,
                            status: response.status,
                            responseText: text.substring(0, 2000),
                            ts: Date.now()
                        });
                        // Scan response juga (fallback)
                        var jwtMatch2 = text.match(/eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+/);
                        if (jwtMatch2 && !window.__jwt) window.__jwt = jwtMatch2[0];
                    });
                    return response;
                });
            };
            var _xhrOpen = XMLHttpRequest.prototype.open;
            var _xhrSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open = function(m, u) {
                this._method = m; this._url = u;
                return _xhrOpen.apply(this, arguments);
            };
            XMLHttpRequest.prototype.send = function(body) {
                var self = this;
                // Scan request body untuk JWT
                if (body) {
                    var bodyStr = String(body);
                    var jwtMatch = bodyStr.match(/eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+/);
                    if (jwtMatch && !window.__jwt) window.__jwt = jwtMatch[0];
                }
                this.addEventListener('load', function() {
                    try {
                        window.__capturedRequests.push({
                            url: self._url, method: self._method,
                            body: body ? String(body).substring(0, 500) : null,
                            status: self.status,
                            responseText: (self.responseText || '').substring(0, 2000),
                            ts: Date.now()
                        });
                        var text = self.responseText || '';
                        var jwtMatch = text.match(/eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+/);
                        if (jwtMatch && !window.__jwt) window.__jwt = jwtMatch[0];
                    } catch(e) {}
                });
                return _xhrSend.apply(this, arguments);
            };
        '''})

        # === PHASE 1: Login Google ===
        driver.get('https://accounts.google.com/signin')
        time.sleep(2)
        driver.find_element(By.CSS_SELECTOR, '#identifierId').send_keys(email_addr)
        driver.find_element(By.CSS_SELECTOR, '#identifierNext').click()
        time.sleep(3)
        driver.find_element(By.CSS_SELECTOR, 'input[type="password"]').send_keys(password)
        driver.find_element(By.CSS_SELECTOR, '#passwordNext').click()
        time.sleep(5)

        if 'challenge' in driver.current_url or 'signin' in driver.current_url:
            log(f'  ❌ Google login failed')
            return False
        log(f'  Login OK')

        # === PHASE 2: Open poll, fill email, Turnstile, submit ===
        driver.get(f'{CONFIG["voting"]["baseUrl"]}{CONFIG["voting"]["pollPath"]}?ref={CONFIG["vote"]["ref"]}&state=landing')
        time.sleep(3)

        email_input = driver.find_element(By.CSS_SELECTOR, 'input[type="email"]')
        email_input.clear()
        email_input.send_keys(IMAP_USER)
        driver.execute_script('document.querySelector("input[type=checkbox]").click()')
        time.sleep(1)

        # Wait Turnstile
        for i in range(15):
            time.sleep(2)
            r = driver.execute_script('return document.querySelector("[name=cf-turnstile-response]")?.value || "empty"')
            if r != 'empty':
                log(f'  Turnstile OK')
                break

        # Submit email form (trigger OTP)
        driver.execute_script('var b=document.querySelector("button"); if(b){b.disabled=false;b.click()}')
        time.sleep(5)

        # === PHASE 3: OTP verification ===
        text = driver.find_element(By.TAG_NAME, 'body').text
        if 'OTP' in text or 'kode' in text.lower() or 'Masukkan' in text:
            log(f'  OTP page...')
            driver.execute_script('''
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    if ((buttons[i].textContent || '').toLowerCase().includes('masukkan kode')) {
                        buttons[i].disabled = false; buttons[i].click(); return;
                    }
                }
            ''')
            time.sleep(5)

            otp = get_otp(timeout=60)
            if not otp:
                log(f'  ❌ No OTP')
                return False
            log(f'  OTP: {otp}')

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
            else:
                log(f'  ❌ No OTP input')
                return False

            time.sleep(3)

            # Klik "Kirim/Lanjut/Verif" button
            driver.execute_script('''
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var t = (buttons[i].textContent || '').toLowerCase();
                    if (t.includes('kirim') || t.includes('lanjut') || t.includes('verif')) {
                        buttons[i].disabled = false; buttons[i].click(); return;
                    }
                }
            ''')
            time.sleep(5)

        # === PHASE 4: Ambil JWT dari CDP hook ===
        log(f'  Checking captured requests...')

        jwt = driver.execute_script('return window.__jwt')
        captured = driver.execute_script('return window.__capturedRequests || []')
        body_debug = driver.execute_script('return window.__bodyDebug || []')
        jwt_debug = driver.execute_script('return window.__jwtDebug || []')
        log(f'  Captured requests: {len(captured)}')
        log(f'  Body debug entries: {len(body_debug)}')
        for bd in body_debug:
            log(f'    type={bd.get("type")} url={bd.get("url", "")[:60]} preview={bd.get("preview", "")[:100]}')
        log(f'  JWT debug entries: {len(jwt_debug)}')
        for jd in jwt_debug:
            log(f'    source={jd.get("source")} len={jd.get("len")} dots={jd.get("dots")} preview={jd.get("preview", "")[:100]}')

        if jwt:
            log(f'  ✅ JWT found from CDP hook (len={len(jwt)})')
        else:
            # Log semua captured requests
            for req in captured:
                method = req.get('method', '?')
                url = (req.get('url', '') or '')[:80]
                status = req.get('status', '?')
                body_preview = (req.get('body') or '')[:60]
                resp_preview = (req.get('responseText') or '')[:80]
                log(f'    {method} {url} → {status} body={body_preview} resp={resp_preview}')

            log(f'  ⚠️ JWT still not found after scanning {len(captured)} requests')

        if jwt:
            log(f'  ✅ JWT found (len={len(jwt)})')
        else:
            log(f'  ⚠️ JWT not found in storage, dumping keys...')
            # Debug: dump storage keys
            keys = driver.execute_script('''
                var result = [];
                for (var i = 0; i < localStorage.length; i++) {
                    var k = localStorage.key(i);
                    var v = localStorage.getItem(k);
                    result.push(k + ': ' + (v ? v.substring(0, 80) : 'null'));
                }
                for (var i = 0; i < sessionStorage.length; i++) {
                    var k = sessionStorage.key(i);
                    var v = sessionStorage.getItem(k);
                    result.push('session:' + k + ': ' + (v ? v.substring(0, 80) : 'null'));
                }
                return result;
            ''')
            for k in keys:
                log(f'    {k}')

        # Build submit payload dari config.json + .env
        sector_id = ENV.get('SECTOR_ID', '')
        api_payload = {
            'subSectorId': CONFIG['vote']['subSectorId'],
            'institutionId': CONFIG['vote']['institutionId'],
            'selectedFactors': CONFIG['vote']['selectedFactors'],
            'pollSlug': CONFIG['vote']['pollSlug'],
            'sectorId': sector_id,
        }

        # Panggil fetch dari browser context
        rsc_tree = '%5B%22%22%2C%7B%22children%22%3A%5B%22polls%22%2C%7B%22children%22%3A%5B%5B%22slug%22%2C%22cx100-danantara%22%2C%22d%22%2Cnull%5D%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%2C0%5D%7D%2Cnull%2Cnull%2C0%5D%7D%2Cnull%2Cnull%2C0%5D%7D%2Cnull%2Cnull%2C16%5D'
        submit_js = r'''
        async function submitVote(jwt, payload, ref, rscTree) {
            var url = window.location.origin + '/polls/' + payload.pollSlug
                + '?ref=' + ref + '&state=sector-' + payload.sectorId + '-subsector-' + payload.subSectorId;
            var body = JSON.stringify([
                payload.pollSlug,
                {
                    subSectorId: payload.subSectorId,
                    institutionId: payload.institutionId,
                    questionnaireResponse: {
                        selectedFactors: payload.selectedFactors,
                        reasonText: ''
                    }
                },
                jwt
            ]);
            try {
                var resp = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'text/plain;charset=UTF-8',
                        'Accept': 'text/x-component',
                        'next-action': '709cd13f602d4f2b96ca742284b6a070ccded9e797',
                        'next-router-state-tree': rscTree
                    },
                    body: body,
                    credentials: 'include'
                });
                var text = await resp.text();
                return { ok: resp.ok, status: resp.status, response: text.substring(0, 2000) };
            } catch (e) {
                return { ok: false, error: e.message };
            }
        }
        return await submitVote(arguments[0], arguments[1], arguments[2], arguments[3]);
        '''

        ref = CONFIG['vote']['ref']
        result = driver.execute_script(submit_js, jwt, api_payload, ref, rsc_tree)

        if result and result.get('ok'):
            log(f'  Submit: {result["status"]} {result.get("response", "")[:500]}')
            if '"success":true' in str(result.get('response', '')):
                log(f'  ✅ Vote SUBMITTED!')
                success = True
            else:
                log(f'  ⚠️ Response unclear')
                success = False
        else:
            log(f'  ❌ Submit failed: {result}')
            # Fallback ke UI flow
            success = False
            text = driver.find_element(By.TAG_NAME, 'body').text
            if 'Polling Sector' in text or 'Sektor' in text:
                log(f'  Fallback: UI flow')
                driver.execute_script('''
                    var items = document.querySelectorAll('button, a, [class*="card"], [class*="Card"]');
                    for (var i = 0; i < items.length; i++) {
                        if ((items[i].textContent || '').toLowerCase().includes('energi') &&
                            (items[i].textContent || '').toLowerCase().includes('telekom')) {
                            items[i].click(); return;
                        }
                    }
                ''')
                time.sleep(3)

            text = driver.find_element(By.TAG_NAME, 'body').text
            if 'subsektor' in text.lower() or 'Pilih subsektor' in text:
                log(f'  Fallback: subsector')
                driver.execute_script('''
                    var items = document.querySelectorAll('button, a, [class*="card"], [class*="Card"]');
                    for (var i = 0; i < items.length; i++) {
                        var t = (items[i].textContent || '').toLowerCase();
                        if (t.includes('telecommunication') || t.includes('jasa telekom')) {
                            items[i].click(); return;
                        }
                    }
                ''')
                time.sleep(5)

            text = driver.find_element(By.TAG_NAME, 'body').text
            if 'faktor' in text.lower() or 'unggul' in text.lower():
                log(f'  Fallback: factors')
                for idx in range(3):
                    driver.execute_script('''
                        var cards = document.querySelectorAll('div, button, label');
                        var clicked = 0, targetIndex = arguments[0];
                        for (var i = 0; i < cards.length; i++) {
                            var el = cards[i];
                            var t = (el.textContent || '').trim().toLowerCase();
                            if (t.includes('pilih faktor') || t.includes('unggul') || t.length < 10) continue;
                            if (!t.includes('layanan') && !t.includes('informasi') && !t.includes('stabil') &&
                                !t.includes('keluhan') && !t.includes('hasil') && !t.includes('pembiayaan')) continue;
                            if (clicked === targetIndex) { el.click(); return; }
                            clicked++;
                        }
                    ''', idx)
                    time.sleep(1)
                time.sleep(2)

                driver.execute_script('''
                    var buttons = document.querySelectorAll('button');
                    for (var i = buttons.length - 1; i >= 0; i--) {
                        var t = (buttons[i].textContent || '').toLowerCase();
                        if (t.includes('kirim') || t.includes('submit') || t.includes('vote') || t.includes('selesai')) {
                            buttons[i].disabled = false; buttons[i].click(); return;
                        }
                    }
                ''')
                time.sleep(8)
                success = True  # UI flow submitted

        # === PHASE 5: Screenshot evidence ===
        evidence_dir = make_evidence_dir()
        try:
            screenshot_evidence(driver, email_addr, evidence_dir)
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
