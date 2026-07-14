#!/usr/bin/env python3
"""Generate evidence PNG untuk Galeri 24 Pegadaian."""
import json, os, subprocess, time
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))
PROJECT = '/Users/trei/Desktop/cx100-stress-test'
TEMPLATE = os.path.join(PROJECT, 'template', 'index.html')
SS_PNG = os.path.join(PROJECT, 'template', 'src', 'SS.png')
EVIDENCE_DIR = os.path.join(PROJECT, 'evidence')

def generate_evidence(email, company, timestamp, evidence_dir):
    with open(TEMPLATE) as f:
        html = f.read()
    
    short_ts = timestamp.strftime('%a %-d %b %-H:%M').replace('  ', ' ')
    full_ts = timestamp.strftime('%Y-%m-%d %H:%M:%S') + ' WIB'
    
    html = html.replace('{{EMAIL}}', email.lower())
    html = html.replace('{{COMPANY}}', company)
    html = html.replace('{{SHORT_TIMESTAMP}}', short_ts)
    html = html.replace('{{FULL_TIMESTAMP}}', full_ts)
    html = html.replace("url('src/SS.png')", f"url('{SS_PNG}')")
    
    tmp = '/tmp/evidence_render.html'
    with open(tmp, 'w') as f:
        f.write(html)
    
    filename = f"{email.split('@')[0].lower()}_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(evidence_dir, filename)
    
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
  await page.screenshot({{ path: '{filepath}' }});
  await browser.close();
}})();
'''], capture_output=True, timeout=30)
    
    return filepath

def main():
    base_email = 'alyasabrinasafwanasafitri@gmail.com'
    company = 'Galeri 24 Pegadaian'
    target = 50
    date_str = '14072026'
    
    evidence_dir = os.path.join(EVIDENCE_DIR, f'CX100 - {date_str}')
    os.makedirs(evidence_dir, exist_ok=True)
    
    print(f'=== Generate Evidence: Galeri 24 Pegadaian ===')
    print(f'Email: {base_email}')
    print(f'Company: {company}')
    print(f'Target: {target}')
    print()
    
    # Generate dot variations
    local = base_email.split('@')[0]
    from itertools import combinations
    variations = [base_email]
    positions = list(range(1, len(local)))
    for dot_count in range(1, len(positions) + 1):
        for combo in combinations(positions, dot_count):
            new_local = list(local)
            for pos in sorted(combo, reverse=True):
                new_local.insert(pos, '.')
            variation = ''.join(new_local) + '@' + base_email.split('@')[1]
            if variation not in variations:
                variations.append(variation)
            if len(variations) >= target:
                break
        if len(variations) >= target:
            break
    
    success = 0
    for i in range(target):
        email = variations[i]
        ts = datetime(2026, 7, 14, 10, 0, 0, tzinfo=WIB) + timedelta(minutes=i)
        
        try:
            filepath = generate_evidence(email, company, ts, evidence_dir)
            success += 1
            if (i + 1) % 10 == 0:
                print(f'  ✅ Generated {i + 1}/{target} ({success} success)')
        except Exception as e:
            print(f'  ❌ Error at index {i}: {str(e)[:50]}')
    
    print(f'\n=== DONE: {success}/{target} generated ===')

if __name__ == '__main__':
    main()
