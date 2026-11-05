import os
import sys
import json
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app

app = create_app()
client = app.test_client()

# 1. Check Session State
res = client.get('/api/session-state')
assert res.status_code == 200, f'session-state failed: {res.status_code}'
print('1. Session State: OK')

# 2. Teacher Auth with PIN gv2026
res = client.post('/api/teacher/auth', json={'pin': 'gv2026'}, headers={'X-Test-Auth-Required': '1'})
assert res.status_code == 200, f'teacher auth failed: {res.status_code}, {res.data}'
assert res.get_json().get('success') is True
print('2. Teacher Auth PIN: OK')

# 3. Teacher Data
res = client.get('/api/teacher/data', headers={'X-Teacher-PIN': 'gv2026', 'X-Test-Auth-Required': '1'})
assert res.status_code == 200, f'teacher data failed: {res.status_code}'
data = res.get_json()
assert 'submissions' in data
assert 'students_roster' in data
sub_count = len(data['submissions'])
print(f'3. Teacher Data retrieved ({sub_count} submissions): OK')

# 4. Teacher DB Backup
res = client.post('/api/teacher/database/backup', headers={'X-Teacher-PIN': 'gv2026', 'X-Test-Auth-Required': '1'})
assert res.status_code == 200, f'backup failed: {res.status_code}'
assert res.get_json().get('success') is True
print(f'4. Hot WAL Backup created ({res.get_json().get("backup_file")}): OK')

# 5. Teacher Export CSV
res = client.get('/api/teacher/export-csv', headers={'X-Teacher-PIN': 'gv2026', 'X-Test-Auth-Required': '1'})
assert res.status_code == 200, f'export-csv failed: {res.status_code}'
assert res.data.startswith(b'\xef\xbb\xbf'), 'BOM UTF-8 missing'
print('5. Export CSV with UTF-8 BOM: OK')

# 6. Check Classes
res = client.get('/api/classes')
assert res.status_code == 200
class_count = len(res.get_json().get('classes', []))
print(f'6. Classes List ({class_count} classes): OK')

# 7. Check Documents
res = client.get('/api/documents')
assert res.status_code == 200
docs = res.get_json()
doc_count = len(docs)
print(f'7. Documents List ({doc_count} doc types): OK')

# 8. Check Quiz Bank
res = client.get('/api/teacher/quiz/cong_van_de_nghi', headers={'X-Teacher-PIN': 'gv2026', 'X-Test-Auth-Required': '1'})
assert res.status_code == 200
q_data = res.get_json()
assert 'questions' in q_data
q_count = len(q_data['questions'])
print(f'8. Quiz Bank ({q_count} questions): OK')

# 9. Student Verify Roster
res = client.post('/api/student/verify', json={'class_code': '24DTH01', 'mssv': '2400003155'})
assert res.status_code == 200, f'Student verify failed: {res.status_code}, {res.data}'
v_data = res.get_json()
assert v_data.get('valid') is True
print(f'9. Student Roster Verify ({v_data.get("name")}): OK')

# 10. Student Quiz Attempt Generation
res = client.post('/api/quiz/get', json={
    'class_code': '24DTH01',
    'mssv': '2400003155',
    'name': v_data.get('name'),
    'doc_type': 'cong_van_de_nghi'
}, headers={'X-Device-Id': 'diag_device_001'})
assert res.status_code == 200, f'Quiz get failed: {res.status_code}, {res.data}'
quiz_resp = res.get_json()
assert 'attempt_id' in quiz_resp
assert 'questions' in quiz_resp
assert len(quiz_resp['questions']) == 5
print(f'10. Student Quiz Attempt generated (attempt_id={quiz_resp["attempt_id"]}): OK')

print('ALL 10 END-TO-END FLOW CHECKS PASSED!')
