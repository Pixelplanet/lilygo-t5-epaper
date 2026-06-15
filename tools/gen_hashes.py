import json, hashlib, os

src = 'src'
fh = {}
for root, dirs, files in os.walk(src):
    dirs[:] = [d for d in dirs if '__pycache__' not in d]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            rel = os.path.relpath(path, src).replace('\\', '/')
            with open(path, 'rb') as fh2:
                data = fh2.read()
            # Normalize CRLF -> LF so the hash matches what GitHub serves
            # (raw.githubusercontent.com always returns LF line endings).
            data = data.replace(b'\r\n', b'\n')
            fh[rel] = hashlib.sha256(data).hexdigest()

with open('update.json') as fh2:
    u = json.load(fh2)
u['files'] = fh
u['description'] = 'Regenerated hashes to match current source'
with open('update.json', 'w') as fh2:
    json.dump(u, fh2, indent=2)

print('update.json v{}: {} files'.format(u['version'], len(fh)))
