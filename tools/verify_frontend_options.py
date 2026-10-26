# -*- coding: utf-8 -*-
import requests
import re

r = requests.get('http://127.0.0.1:5000/')
for sid in ['sel-doc-type', 'teacher-sel-doc', 'teacher-quiz-sel-doc']:
    pattern = rf'<select[^>]*id="{sid}"[^>]*>(.*?)</select>'
    m = re.search(pattern, r.text, re.DOTALL)
    print(f'=== {sid} ===')
    if m:
        for opt in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', m.group(1)):
            print(f'  {opt[0]}: {opt[1].strip()}')
    else:
        print('  NOT FOUND')
