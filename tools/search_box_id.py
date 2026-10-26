import os
for root, dirs, files in os.walk('.'):
    for fn in files:
        if fn.endswith(('.py', '.html', '.js')):
            fp = os.path.join(root, fn)
            with open(fp, encoding='utf-8', errors='ignore') as f:
                c = f.read()
                if "box_id" in c:
                    for line in c.splitlines():
                        if "box_id" in line and ("5" in line or "==" in line):
                            print(f"{fp}: {line.strip()[:80]}")
