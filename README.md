# CX100 Stress Test

Automasi voting untuk stress test polling CX100 Danantara.

## Persyaratan

- Node.js 18+
- Chromium (otomatis ter-install via Playwright)

## Instalasi

```bash
git clone https://github.com/hellotrei/cx100-d4n4nt4r4.git
cd cx100-d4n4nt4r4
npm install
npx playwright install chromium
```

## Konfigurasi

### accounts.json

Isi dengan daftar email dan password:

```json
[
  { "email": "user1@gimikol.my.id", "password": "password123", "imapPassword": "password123" },
  { "email": "user2@gimikol.my.id", "password": "password123", "imapPassword": "password123" }
]
```

### config.json

Atur target voting dan faktor yang dipilih:

```json
{
  "vote": {
    "pollSlug": "cx100-danantara",
    "ref": "29FqBa9qFCLF7IMw05i_E",
    "subSectorId": "43988074-7483-4508-bdd0-9beaeacf1fb7",
    "institutionId": "e5970bda-b59a-41c7-9671-6f4456cc2595",
    "selectedFactors": [
      "Mudah menemukan informasi produk dan layanan",
      "Hasil pembiayaan sesuai dengan yang diharapkan",
      "Keluhan ditangani dengan cepat dan tuntas"
    ],
    "reasonText": ""
  }
}
```

## Penggunaan

```bash
npm start
```

Script akan:
1. Login ke Google untuk setiap akun
2. Navigasi ke halaman voting
3. Submit vote otomatis
4. Log hasil ke `logs/`

## Output

Log tersimpan di folder `logs/` dengan format:
- `run-<timestamp>.json` — hasil terstruktur
- `run-<timestamp>.log` — log human-readable

## Struktur

```
├── accounts.json        # Daftar akun email:password
├── config.json          # Target voting dan faktor
├── src/
│   ├── option-c3.js     # Script utama
│   └── logger.js        # Module logging
└── logs/                # Output log perjalanan
```

## Flow

```
Login Google → Navigate voting page → Submit vote → Log result
```

Setiap akun diproses secara serial (~47 detik/akun).
