#!/usr/bin/env python3
"""CX100 Batch Vote Runner — auto-increment variation_index per vote."""
import json, time, subprocess, sys, os

ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'accounts.json')
VOTE_SCRIPT = os.path.join(os.path.dirname(__file__), 'test-vote.py')
PYTHON = sys.executable

def load_accounts():
    with open(ACCOUNTS_FILE) as f:
        return json.load(f)

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(accounts, f, indent=2)

def run_vote():
    """Run test-vote.py sekali, return True jika success."""
    result = subprocess.run(
        [PYTHON, VOTE_SCRIPT],
        capture_output=True, text=True, timeout=300
    )
    output = result.stdout + result.stderr
    # Cari baris DONE
    for line in output.split('\n'):
        if 'DONE:' in line:
            print(f'  {line.strip()}')
            return 'success' in line.lower() and '1/1' in line
    return False

def main():
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    delay = int(sys.argv[2]) if len(sys.argv) > 2 else 10  # detik antar vote

    accounts = load_accounts()
    if not accounts:
        print('No accounts in accounts.json')
        return

    acc = accounts[0]  # pakai akun pertama
    start_index = acc.get('variation_index', 0)

    print(f'=== CX100 Batch Vote ===')
    print(f'Account: {acc["email"]}')
    print(f'Poll email base: {acc.get("poll_email", acc["email"])}')
    print(f'Starting variation_index: {start_index}')
    print(f'Batch size: {batch_size}')
    print(f'Delay: {delay}s between votes')
    print()

    success = 0
    failed = 0

    for i in range(batch_size):
        acc['variation_index'] = start_index + i
        save_accounts(accounts)

        print(f'[{i+1}/{batch_size}] variation_index={acc["variation_index"]}')
        try:
            ok = run_vote()
            if ok:
                success += 1
                print(f'  ✅ SUCCESS ({success}/{i+1})')
            else:
                failed += 1
                print(f'  ❌ FAILED ({failed}/{i+1})')
        except subprocess.TimeoutExpired:
            failed += 1
            print(f'  ⏰ TIMEOUT ({failed}/{i+1})')
        except Exception as e:
            failed += 1
            print(f'  ❌ ERROR: {str(e)[:80]} ({failed}/{i+1})')

        # Cleanup Chrome
        subprocess.run(['pkill', '-9', '-f', 'chrome'], capture_output=True)
        subprocess.run(['pkill', '-9', '-f', 'chromedriver'], capture_output=True)

        if i < batch_size - 1:
            print(f'  Waiting {delay}s...')
            time.sleep(delay)

    print(f'\n=== BATCH DONE: {success}/{batch_size} success, {failed} failed ===')

if __name__ == '__main__':
    main()
