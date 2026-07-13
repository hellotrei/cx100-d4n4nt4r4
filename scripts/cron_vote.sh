#!/bin/bash
# CX100 Auto Vote - Pegadaian 250 votes
# Dijalankan via crontab: 0 0 * * *

export PATH="/Users/trei/.local/bin:$PATH"
PROJ="/Users/trei/Desktop/cx100-stress-test"
LOG="/tmp/cx100_pegadaian_$(date +%Y%m%d).log"

cd "$PROJ" || exit 1

# Pastikan config Pegadaian
cp presets/pegadaian.json config.json

# Reset variation_index ke 1
python3 -c "
import json
with open('accounts.json') as f: acc = json.load(f)
acc[0]['variation_index'] = 1
with open('accounts.json','w') as f: json.dump(acc, f, indent=2)
print('variation_index reset to 1')
"

# Jalankan 250 votes, delay 15 detik
python3 src/batch_runner.py 250 15 2>&1 | tee "$LOG"

echo "[$(date)] CX100 Pegadaian batch selesai" >> "$LOG"
