// Pure JavaScript rendering tests with a minimal DOM stub; not a browser E2E test.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../templates/teacher.html'), 'utf8');
for (const file of ['teacher.html', 'index.html']) {
  const source = fs.readFileSync(path.join(__dirname, '../templates', file), 'utf8');
  for (const match of source.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
    if (match[1].trim()) new vm.Script(match[1], {filename:file});
  }
}
const elements = new Map();
const context = vm.createContext({document: {getElementById(id) {
  if (!elements.has(id)) elements.set(id, {value: '', innerHTML: ''});
  return elements.get(id);
}}});
function load(name) {
  const start = html.indexOf(`    function ${name}(`);
  assert.ok(start >= 0, `function ${name} exists`);
  const tail = html.slice(start + 1);
  const end = tail.search(/\n    (?:async )?function |\n  <\/script>/);
  vm.runInContext(html.slice(start, start + 1 + end), context);
}
load('escapeHtml');
if (html.includes('    function jsArg(')) load('jsArg');
load('renderSubmissionsTable');
const get = id => context.document.getElementById(id);
get('sel-filter-class').value = 'ALL';
const payload = `O'Neil'); globalThis.pwned=true; // <img src=x onerror=alert(1)>`;
context.rows = [{name: payload, mssv:'S01', class_code:'AUDIT', doc_type:'cv',
  filename:'file.docx', score:5, status:'Đạt chuẩn 50% Nghị định 30'}];
vm.runInContext('renderSubmissionsTable(rows)', context);
const rendered = get('tbl-submissions-body').innerHTML;
assert.ok(!rendered.includes('<img'), 'student name must remain text');
assert.ok(rendered.includes('50%'), 'show the stored result');
assert.ok(!rendered.includes('100% NĐ 30'), 'do not label a partial result as 100%');
const handler = rendered.match(/onclick="(grantReattempt\([^"]*)"/)[1]
  .replace(/&quot;/g,'"').replace(/&#039;/g,"'").replace(/&lt;/g,'<')
  .replace(/&gt;/g,'>').replace(/&amp;/g,'&');
context.grantReattempt = (...args) => {context.received = args;};
vm.runInContext(handler, context);
assert.equal(context.received[3], payload, 'apostrophes must survive as data');
assert.equal(context.pwned, undefined, 'student data cannot execute JavaScript');
load('renderRosterTable');
get('sel-roster-class').value = 'AUDIT';
context.roster = {AUDIT: [{name:payload, mssv:'S01'}]};
vm.runInContext('renderRosterTable(roster)', context);
assert.ok(!get('tbl-roster-body').innerHTML.includes('<img'));
load('renderClassDropdowns');
context.classNames = [payload];
vm.runInContext('renderClassDropdowns(classNames, {})', context);
assert.ok(!get('sel-filter-class').innerHTML.includes('<img'));
load('renderTeacherSelector');
load('renderTeachersTable');
context.allTeachersList = [{id:'teacher1', name:payload, title:payload, phone:payload}];
context.currentActiveTeacherId = 'teacher1';
vm.runInContext('renderTeacherSelector(); renderTeachersTable()', context);
assert.ok(!get('sel-active-teacher').innerHTML.includes('<img'));
assert.ok(!get('tbl-teachers-list-body').innerHTML.includes('<img'));
load('renderTeacherQuizList');
context.questions = [{id:1,question:payload, options:[payload],correct:0,explanation:payload}];
vm.runInContext('renderTeacherQuizList(questions)', context);
assert.ok(!get('teacher-quiz-list').innerHTML.includes('<img'));
console.log('PASS: both scripts parse; submission/roster/class/teacher/quiz escaping; safe action arguments; actual result display');
