import os
for root, dirs, files in os.walk('.'):
    for fn in files:
        if fn.endswith(('.py', '.html', '.js')):
            fp = os.path.join(root, fn)
            with open(fp, encoding='utf-8', errors='ignore') as f:
                c = f.read()
                if "5a/5b" in c:
                    print(f"Found in {fp}")
