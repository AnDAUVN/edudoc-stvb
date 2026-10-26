import urllib.request
import json

def get(url):
    req = urllib.request.Request('http://127.0.0.1:5000' + url)
    with urllib.request.urlopen(req) as resp:
        return resp.getcode(), resp.read()

def post(url, data):
    req = urllib.request.Request('http://127.0.0.1:5000' + url, 
                                 data=json.dumps(data).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        return resp.getcode(), resp.read()

# 1. Index
code, html = get('/')
print('GET /:', code, '| Guide modal:', b'modal-decree30-guide' in html, '| Stepper:', b'step-nav-1' in html)

# 2. Documents
code, data = get('/api/documents')
docs = json.loads(data.decode('utf-8'))
print('GET /api/documents:', code, '| Count:', len(docs))

# 3. Classes
code, data = get('/api/classes')
cls_data = json.loads(data.decode('utf-8'))
print('GET /api/classes:', code, '| Classes:', cls_data['classes'])

# 4. Teacher Data
code, data = get('/api/teacher/data')
t_data = json.loads(data.decode('utf-8'))
print('GET /api/teacher/data:', code, '| Submissions:', len(t_data['submissions']), '| Frauds:', len(t_data['fraud_logs']))

# 5. Export CSV
code, csv_bytes = get('/api/teacher/export-csv')
print('GET /api/teacher/export-csv:', code, '| Length:', len(csv_bytes), '| Has UTF-8 BOM:', csv_bytes.startswith(b'\xef\xbb\xbf'))

# 6. Quiz Get
code, q_data = post('/api/quiz/get', {'doc_type': 'cong_van_de_nghi'})
quiz = json.loads(q_data.decode('utf-8'))
print('POST /api/quiz/get (cong_van):', code, '| Total questions:', quiz['total'])

# 7. Generate Template
code, tmpl_resp = post('/api/template/generate', {
    'class_code': 'KN01',
    'sbd': '99',
    'mssv': '2200009999',
    'name': 'Trần Thị Cẩm Tú',
    'doc_type': 'cong_van_de_nghi'
})
gen_info = json.loads(tmpl_resp.decode('utf-8'))
print('POST /api/template/generate:', code, '| Filename:', gen_info['filename'])

print('🎉 TẤT CẢ ENDPOINT API ĐANG CHẠY HOÀN HẢO!')
