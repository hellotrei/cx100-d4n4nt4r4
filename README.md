# CX100 Stress Test

Automasi voting untuk stress test polling CX100 Danantara.

## Persyaratan

- Node.js 18+
- Python 3.11+ (untuk undetected-chromedriver)
- Google Chrome

## Instalasi

```bash
git clone https://github.com/hellotrei/cx100-d4n4nt4r4.git
cd cx100-d4n4nt4r4
npm install
pip3 install undetected-chromedriver selenium
cp .env.example .env
```

Isi `.env` dengan credentials:

```
CAPTCHA_API_KEY=your_2captcha_key
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_app_password
```

## Konfigurasi

### accounts.json

Daftar akun voting (di-gitignore, jangan push):

```json
[
  { "email": "user1@gimikol.my.id", "password": "qwertyui" }
]
```

### config.json

Target voting (di-gitignore, jangan push):

```json
{
  "voting": {
    "baseUrl": "https://danantaraindonesiacx100.com",
    "pollPath": "/polls/cx100-danantara"
  },
  "vote": {
    "pollSlug": "cx100-danantara",
    "ref": "29FqBa9qFCLF7IMw05i_E",
    "subSectorId": "37de9453-2fa6-4313-bd23-d4f98a5c1469",
    "institutionId": "e5970bda-b59a-41c7-9671-6f4456cc2595",
    "selectedFactors": [...]
  }
}
```

## Penggunaan

### Auto Vote (per akun)

```bash
# Test 1 akun
~/.hermes/hermes-agent/venv/bin/python src/test-vote.py

# Atau run langsung
python3 src/test-vote.py
```

### Generate Evidence Dummy

```bash
node -e "
const fs = require('fs');
// Generate 180 dummy PNG evidence
// Lihat src/gen-evidence.js untuk contoh
"
```

## Struktur

```
├── accounts.json          # Akun voting (gitignored)
├── config.json            # Target voting (gitignored)
├── .env                   # Secrets (gitignored)
├── .env.example           # Template .env
├── template/
│   ├── index.html         # Template evidence
│   └── src/SS.png         # Background image
├── src/
│   ├── test-vote.py       # Script utama (undetected-chromedriver)
│   ├── option-c3.js       # Script Node.js (Playwright)
│   ├── logger.js          # Module logging
│   └── report-generator.js # Generator HTML report
├── evidence/              # Output evidence
│   └── CX100 - DDMMYYYY/ # Folder per hari
│       └── *.png          # Screenshot evidence
└── logs/                  # Log perjalanan
```

## Flow

```
Login Google → Turnstile solve → OTP verify → Select sector → Select subsector → Select factors → Vote → Evidence PNG
```

Setiap akun ~60 detik (success rate ~33% karena Chrome crash intermittent).

## Evidence

Evidence tersimpan di `~/Desktop/CX100 - DDMMYYYY/` dengan format:

```
{username}_{YYYYMMDD}_{HHMMSS}.png
```

Template: And... [content truncated]
