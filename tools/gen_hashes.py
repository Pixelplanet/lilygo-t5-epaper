import json, hashlib, os, subprocess

src = 'src'
# Only hash files that git tracks — untracked files (secrets.py, ui.json, etc.)
# don't exist on GitHub and would cause 404 / hash mismatch during OTA.
tracked = set()
try:
    out = subprocess.check_output(
        ['git', 'ls-files', '--', 'src/'], text=True)
    for line in out.strip().split('\n'):
        # git ls-files returns paths relative to repo root, strip "src/"
        if line.startswith('src/'):
            tracked.add(line[4:].replace('\\', '/'))
except Exception:
    pass  # fall back to walking all files if git not available

fh = {}
for root, dirs, files in os.walk(src):
    dirs[:] = [d for d in dirs if '__pycache__' not in d]
    for f in files:
        if not f.endswith('.py'):
            continue
        rel = os.path.relpath(os.path.join(root, f), src).replace('\\', '/')
        # Skip files not tracked by git (e.g. secrets.py, user files).
        if tracked and rel not in tracked:
            continue
        path = os.path.join(root, f)
        with open(path, 'rb') as fh2:
            data = fh2.read()
        # Normalize CRLF -> LF so the hash matches what GitHub serves
        # (raw.githubusercontent.com always returns LF line endings).
        data = data.replace(b'\r\n', b'\n')
        fh[rel] = hashlib.sha256(data).hexdigest()

with open('update.json') as fh2:
    u = json.load(fh2)
u['files'] = fh
# Store the current commit hash so the updater can fetch from the exact
# commit, bypassing GitHub's CDN cache on the /master/ branch URL.
try:
    commit = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip()
    u['commit'] = commit
except Exception:
    pass
u['description'] = 'Regenerated hashes to match current source'
with open('update.json', 'w') as fh2:
    json.dump(u, fh2, indent=2)

# Auto-update PINNED_COMMIT in updater.py to the current HEAD so
# OTA fetches always use the same commit as the recorded hashes.
if commit:
    updater_path = os.path.join(src, 'lib', 'updater.py')
    if os.path.exists(updater_path):
        with open(updater_path, 'r') as fh2:
            content = fh2.read()
        import re
        content = re.sub(
            r'PINNED_COMMIT = "[0-9a-f]+"',
            'PINNED_COMMIT = "' + commit + '"',
            content)
        with open(updater_path, 'w') as fh2:
            fh2.write(content)

c = u.get('commit', '?')
print('update.json v{}: {} files, commit={}'.format(u['version'], len(fh), c))
