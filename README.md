# CX100 Auto Vote

Automasi voting untuk stress test polling CX100 Danantara. Menggunakan `undetected_chromedriver` (Selenium) untuk bypass bot detection, IMAP untuk auto-OTP, dan TOTP untuk Google 2FA.

## Spesifikasi Minimum

| Komponen | Minimum | Recommended |
|----------|---------|-------------|
| OS | macOS / Linux / Windows | macOS (tested) |
| RAM | 4 GB | 8 GB+ |
| CPU | 2 core | 4 core+ |
| Storage | 500 MB | 1 GB+ |
| Chrome | v120+ | Latest stable |
| Python | 3.11+ | 3.12+ |
| Node.js | 18+ | 20+ (untuk evidence template) |

**Catatan:**
- macOS Apple Silicon (M1/M2/M3) ✅ supported
- Chrome harus ditutup sebelum run (script pakai user profile asli)
- IMAP ke Gmail butuh **App Password** (bukan password biasa)

## Instalasi

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/hellotrei/cx100-d4n4nt4r4.git
cd cx100-d4n4nt4r4

# Python dependencies
pip3 install undetected-chromedriver selenium pyotp

# Node.js dependencies (untuk screenshot evidence)
npm install
```

### 2. Setup Google Account

Script butuh 1 akun Gmail dengan:
- **2FA aktif** (Google Authenticator)
- **App Password** untuk IMAP access

#### Buat App Password:
1. Buka https://myaccount.google.com/apppasswords
2. Login ke akun Gmail yang akan dipakai
3. Generate App Password baru (nama: "cx100")
4. Copy password 16 karakter (format: `xxxx xxxx xxxx xxxx`)

#### Simpan TOTP Secret:
1. Saat setup 2FA Google, pastikan simpan **secret key** (bukan QR code)
2. Secret biasanya 32 karakter (base32): `JBSWY3DPEHPK3PXP`
3. Simpan di `.env` sebagai `TOTP_SECRET`

### 3. Setup .env

```bash
cp .env.example .env
```

Isi `.env`:

```env
# === IMAP (untuk auto-OTP) ===
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=xxxx xxxx xxxx xxxx    # App Password, bukan password biasa
IMAP_HOST=74.125.24.108              # Gmail IMAP IP (bypass Avast proxy)
IMAP_PORT=993
IMAP_SERVERNAME=imap.gmail.com       # SNI hostname

# === Google 2FA ===
TOTP_SECRET=JBSWY3DPEHPK3PXP        # Secret key dari Google Authenticator

# === Company (legacy, sekarang pakai config.json) ===
COMPANY_NAME=Pegadaian
```

**⚠️ Penting:**
- `IMAP_PASSWORD` = **App Password**, bukan password Gmail
- `IMAP_HOST` = IP langsung `74.125.24.108` (bukan hostname) — bypass proxy/antivirus
- `IMAP_SERVERNAME` = `imap.gmail.com` untuk SNI handshake

### 4. Setup accounts.json

```json
[
  {
    "email": "aishahumairanaurashasmira@gmail.com",
    "poll_email": "aishahumairanaurashasmira@googlemail.com",
    "password": "Qwertyui00",
    "variation_index": 1
  }
]
```

| Field | Keterangan |
|-------|------------|
| `email` | Email login Google (asli, tanpa dot) |
| `poll_email` | Email yang dikirim ke polling site (bisa pakai `@googlemail.com`) |
| `password` | Password Google |
| `variation_index` | Index dot variation email (auto-increment) |

**Dot Variation:**
Gmail mengabaikan dot (`.`) di local part. `a.b@c.com` = `ab@c.com` = `a..b@c.com`. Voting site treat setiap variasi sebagai akun berbeda. Script auto-generate dot variations berdasarkan `variation_index`.

### 5. Setup config.json

Copy preset target:

```bash
# Pegadaian (Sektor Keuangan, Subsector Multifinance)
cp presets/pegadaian.json config.json

# Atau Galeri 24 Pegadaian (Sektor Ritel, Subsector Retail)
cp presets/galeri24.json config.json
```

Struktur `config.json`:

```json
{
  "voting": {
    "baseUrl": "https://danantaraindonesiacx100.com",
    "pollPath": "/polls/cx100-danantara"
  },
  "vote": {
    "pollSlug": "cx100-danantara",
    "ref": "29FqBa9qFCLF7IMw05i_E",
    "sectorId": "...",
    "subSectorId": "...",
    "institutionId": "...",
    "selectedFactors": ["Faktor 1", "Faktor 2", "Faktor 3"],
    "sectorKeywords": ["keuangan", "perbankan"],
    "subsectorKeywords": ["multifinance"],
    "institutionName": "Pegadaian",
    "companyName": "Pegadaian"
  }
}
```

| Field | Keterangan |
|-------|------------|
| `sectorId` | UUID sector dari situs polling |
| `subSectorId` | UUID subsector |
| `institutionId` | UUID institusi/perusahaan |
| `selectedFactors` | Array faktor yang dipilih (maks 3) |
| `sectorKeywords` | Keywords untuk auto-click sector card |
| `subsectorKeywords` | Keywords untuk auto-click subsector card |
| `institutionName` | Nama institusi untuk auto-click |
| `companyName` | Nama perusahaan untuk evidence screenshot |

## Penggunaan

### Quick Start (1 Vote Test)

```bash
# 1. Tutup Chrome dulu!
# 2. Pastikan config.json sudah benar
# 3. Jalankan:
python3 src/test-vote.py
```

### Batch Vote

```bash
# Jalankan N vote dengan delay antar vote
python3 src/batch_runner.py [jumlah] [delay_detik]

# Contoh: 100 vote, delay 10 detik
python3 src/batch_runner.py 100 10

# Contoh: 250 vote, delay 15 detik (lebih aman)
python3 src/batch_runner.py 250 15
```

### Background Run

```bash
# Jalankan di background, auto-notif selesai
python3 src/batch_runner.py 100 10 2>&1 | tee /tmp/cx100_batch.log &

# Atau pakai nohup
nohup python3 src/batch_runner.py 100 10 > /tmp/cx100_batch.log 2>&1 &
```

### Switch Target

```bash
# Pindah ke Galeri 24 Pegadaian
cp presets/galeri24.json config.json

# Pindah ke Pegadaian
cp presets/pegadaian.json config.json

# Reset variation_index ke 1
# Edit accounts.json: "variation_index": 1
```

## Flow Voting

```
Login Google (profile + auto-2FA)
    ↓
Buka Polling Site
    ↓
Solve Turnstile CAPTCHA
    ↓
Input Email (dot variation)
    ↓
Submit → Consent/T&C Page
    ↓
OTP Verification (auto via IMAP)
    ↓
Pilih Sector → Subsector → Factors
    ↓
Pilih Institusi → Submit
    ↓
Screenshot Evidence (PNG)
```

**Waktu per vote:** ~60-90 detik
**Success rate:** 85-100% (tergantung rate limiting)

## Troubleshooting

| Error | Penyebab | Fix |
|-------|----------|-----|
| Google login failed | Profile expired/2FA | Re-login manual di Chrome |
| Turnstile timeout | Extension blocking | Pastikan `--disable-extensions` |
| OTP not found | App Password salah | Generate App Password baru |
| "Langkah 1 dari 2" | Consent page | Script handle otomatis |
| Factors not selected | Click header bukan card | Update `sectorKeywords` |
| Email already voted | Same dot variation | Auto-increment `variation_index` |
| Rate limiting | Terlalu cepat | Naikkan delay ke 15-20 detik |

## Struktur Project

```
cx100-stress-test/
├── src/
│   ├── test-vote.py          # Script utama (undetected-chromedriver)
│   └── batch_runner.py       # Batch runner (auto-increment variation_index)
├── presets/
│   ├── pegadaian.json        # Config Pegadaian
│   └── galeri24.json         # Config Galeri 24 Pegadaian
├── template/
│   ├── index.html            # Template evidence HTML
│   └── src/SS.png            # Background image
├── evidence/                 # Output screenshots
│   └── CX100 - DDMMYYYY/    # Folder per hari
├── accounts.json             # Akun voting (gitignored)
├── config.json               # Target voting (gitignored)
├── .env                      # Secrets (gitignored)
├── .env.example              # Template .env
└── README.md
```

## Evidence

Evidence tersimpan di `evidence/CX100 - DDMMYYYY/` dengan format:

```
{dot_variation_email}_{YYYYMMDD}_{HHMMSS}.png
```

Contoh: `a.ishahumairanaurashasmira_20260711_230446.png`

## Performance Stats

| Metric | Value |
|--------|-------|
| Success rate | 85-100% |
| Waktu per vote | ~60-90 detik |
| Batch 100 votes | ~1.5-2 jam |
| Batch 250 votes | ~4-6 jam |
| Variation capacity | 500+ email per akun |

## Dependencies

```
Python:
- undetected-chromedriver
- selenium
- pyotp

Node.js:
- playwright (untuk screenshot evidence)
```

## License

Private — untuk stress testing internal.
