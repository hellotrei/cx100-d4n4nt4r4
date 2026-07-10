import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time, json, imaplib, email as email_module, re, os, subprocess
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))

# Config
with open('config.json') as f:
    CONFIG = json.load(f)
with open('accounts.json') as f:
    ACCOUNTS = json.load(f)

IMAP_USER = CONFIG['imap']['user']
IMAP_PASS = CONFIG['imap']['password']
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
    """Render template with data, screenshot it"""
    now = datetime.now(WIB)
    short_ts = now.strftime('%a %-d %b %-H:%M').replace('  ', ' ')
    full_ts = now.strftime('%Y-%m-%d %H:%M:%S') + ' WIB'
    
    with open(TEMPLATE) as f:
        html = f.read()
    
    html = html.replace('{{EMAIL}}', email_addr.lower())
    html = html.replace('{{COMPANY}}', 'Galeri 24 Pegadaian')
    html = html.replace('{{SHORT_TIMESTAMP}}', short_ts)
    html = html.replace('{{FULL_TIMESTAMP}}', full_ts)
    html = html.replace("url('src/SS.png')", f"url('file://{SS_PNG}')")
    
    # Write temp HTML, screenshot, delete
    tmp = '/tmp/evidence_tmp.html'
    with open(tmp, 'w') as f:
        f.write(html)
    
    # Use Chrome to screenshot
    tmp_driver = uc.Chrome(headless=True, use_subprocess=True)
    tmp_driver.get(f'file://{tmp}')
    time.sleep(2)
    
    filename = f'{email_addr.split("@")[0].lower()}_{now.strftime("%H%M%S")}.png'
    filepath = os.path.join(evidence_dir, filename)
    tmp_driver.save_screenshot(filepath)
    tmp_driver.quit()
    
    log(f'  Screenshot: {filepath}')
    os.remove(tmp)
    return filepath

def process_account(acc):
    email_addr = acc['email']
    password = acc['password']
    log(f'[{email_addr}]')
    
    subprocess.run(['pkill', '-f', 'undetected_chromedriver'], capture_output=True)
    time.sleep(1)
    
    driver = uc.Chrome(headless=False, use_subprocess=True)
    try:
        # 1. Login Google
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
        
        # 2. Navigate to voting
        driver.get(f'{CONFIG["voting"]["baseUrl"]}{CONFIG["voting"]["pollPath"]}?ref={CONFIG["vote"]["ref"]}&state=landing')
        time.sleep(3)
        
        # 3. Fill email
        email_input = driver.find_element(By.CSS_SELECTOR, 'input[type="email"]')
        email_input.clear()
        email_input.send_keys(email_addr)
        driver.execute_script('document.querySelector("input[type=checkbox]").click()')
        time.sleep(1)
        
        # 4. Wait Turnstile
        for i in range(15):
            time.sleep(2)
            r = driver.execute_script('return document.querySelector("[name=cf-turnstile-response]")?.value || "empty"')
            if r != 'empty':
                log(f'  Turnstile OK')
                break
        
        # 5. Submit
        driver.execute_script('var b=document.querySelector("button"); if(b){b.disabled=false;b.click()}')
        time.sleep(5)
        
        # 6. OTP
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
            
            # Find and type OTP
            for attempt in range(5):
                otp_input = None
                for inp in driver.find_elements(By.CSS_SELECTOR, 'input'):
                    if inp.is_displayed():
                        otp_input = inp
                        break
                if otp_input:
                    break
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
            # Click submit
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
        
        # 7. Check page
        text = driver.find_element(By.TAG_NAME, 'body').text
        
        if 'Polling Sector' in text or 'Sektor' in text:
            log(f'  Selecting sector...')
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
            log(f'  Selecting subsector...')
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
        
        # 8. Select factors
        text = driver.find_element(By.TAG_NAME, 'body').text
        if 'faktor' in text.lower() or 'unggul' in text.lower():
            log(f'  Selecting factors...')
            for factor in CONFIG['vote']['selectedFactors']:
                driver.execute_script('''
                    var items = document.querySelectorAll('button, label, div[role="button"], [class*="chip"], [class*="Chip"]');
                    var search = arguments[0].toLowerCase();
                    for (var i = 0; i < items.length; i++) {
                        if ((items[i].textContent || '').trim().toLowerCase().includes(search.substring(0, 15))) {
                            items[i].click(); return true;
                        }
                    }
                    var labels = document.querySelectorAll('label');
                    for (var i = 0; i < labels.length; i++) {
                        if ((labels[i].textContent || '').toLowerCase().includes(search.substring(0, 15))) {
                            labels[i].click(); return true;
                        }
                    }
                    return false;
                ''', factor)
                time.sleep(1)
            
            # Click vote button
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
            time.sleep(5)
        
        # 9. Screenshot evidence
        evidence_dir = make_evidence_dir()
        screenshot_evidence(driver, email_addr, evidence_dir)
        log(f'  ✅ Done')
        return True
        
    except Exception as e:
        log(f'  ❌ {str(e)[:100]}')
        return False
    finally:
        try: driver.quit()
        except: pass

# Main
log(f'=== CX100 Test ({len(ACCOUNTS)} accounts) ===')
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
