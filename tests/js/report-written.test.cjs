const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const search = require('../../src/qualtrics/reporting/static/report-search.js');

// Minimal DOM surface; execute the entire production controller, including its
// registered change handlers, without copying its filtering/linking logic.
function node(dataset = {}, selectors = {}) {
  return {dataset, textContent: '', value: '', hidden: false, checked: true,
    classList: {add() {}, toggle() {}}, handlers: {}, children: [],
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    querySelectorAll(selector) { return selectors[selector] || []; },
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; },
    addEventListener(event, callback) { this.handlers[event] = callback; },
    setAttribute() {}, closest() { return null; }};
}
function fixture({paginated = false} = {}) {
  const surveyA = node(), surveyB = node();
  surveyA.value = 'a'; surveyB.value = 'b';
  surveyA.closest = () => ({textContent: 'Survey A'});
  surveyB.closest = () => ({textContent: 'Survey B'});
  const field1 = node({fieldId: 'first'}, {'.value': [{textContent: 'Lee'}]});
  const field2 = node({fieldId: 'last'}, {'.value': [{textContent: 'Lee'}]});
  const row = node({question: 'a::q'}, {'.field-answer': [field1, field2]});
  const card = node({survey: 'a'}, {'.answer': [row]}); card.id = 'response-1';
  const link = {href: '#response-1', getAttribute() { return this.href; }};
  const a = node({survey: 'a', questionToken: 'a::q', fieldId: 'last', responseTarget: card.id},
    {'.written-value': [{textContent: 'Lee'}], a: [link]});
  const b = node({survey: 'b', questionToken: 'b::q', fieldId: 'last'});
  const optionA = node({survey: 'a', label: 'Name'}); optionA.value = 'a::q'; optionA.textContent = 'Name';
  const optionB = node({survey: 'b', label: 'Name'}); optionB.value = 'b::q'; optionB.textContent = 'Name';
  const select = node(); select.options = [node(), optionA, optionB];
  const empty = node();
  const cards = [card], written = [a, b];
  const responsePagination = node(), writtenPagination = node();
  if (paginated) {
    cards.push(...Array.from({length: 24}, () => node({survey: 'a'})), node({survey: 'b'}));
    written.push(...Array.from({length: 24}, () => node({survey: 'a', questionToken: 'a::q'})));
  }
  cards.forEach((item, index) => { item.tagName = 'DETAILS'; item.open = index % 2 === 0; });
  const responseView = node({}, {details: cards}); responseView.id = 'by-responses';
  const selectors = {'.survey-choice': [surveyA, surveyB], '.respondent': cards, '.written-answer': written,
    details: cards, '#response-pagination': [responsePagination], '#written-pagination': [writtenPagination],
    '#written-question': [select], '#written-empty': [empty]};
  const document = node({}, selectors);
  document.getElementById = id => id === responseView.id ? responseView : cards.find(item => item.id === id) || null;
  document.createElement = () => node(); document.documentElement = node();
  const window = {ReportSearch: search, handlers: {}, addEventListener(event, callback) { this.handlers[event] = callback; }};
  vm.runInNewContext(fs.readFileSync(require.resolve('../../src/qualtrics/reporting/static/report.js'), 'utf8'),
    {document, window, location: {hash: '#by-responses'}});
  return {surveyA, surveyB, a, b, field2, link, select, optionA, optionB, empty,
    cards, written, responsePagination, writtenPagination, window};
}

test('equal written values link to their own field within the response question', () => {
  const {link, field2} = fixture();
  assert.equal(link.href, '#' + field2.id);
});
test('survey changes discard unavailable question selection and restore eligible answers', () => {
  const f = fixture();
  f.select.value = 'a::q'; f.select.handlers.change();
  assert.equal(f.b.hidden, true);
  f.surveyA.checked = false; f.surveyA.handlers.change();
  assert.equal(f.select.value, '');
  assert.equal(f.a.hidden, true); assert.equal(f.b.hidden, false);
  assert.equal(f.empty.hidden, true);
  assert.equal(f.optionA.hidden, true); assert.equal(f.optionA.disabled, true);
  assert.equal(f.optionB.hidden, false); assert.equal(f.optionB.disabled, false);
  f.surveyA.checked = true; f.surveyA.handlers.change();
  assert.equal(f.optionA.hidden, false); assert.equal(f.optionA.disabled, false);
});
test('question labels identify surveys in multi-survey selection', () => {
  const f = fixture();
  assert.equal(f.optionA.textContent, 'Name · Survey A');
  assert.equal(f.optionB.textContent, 'Name · Survey B');
  f.surveyA.checked = false; f.surveyA.handlers.change();
  assert.equal(f.optionB.textContent, 'Name');
});


test('print shows all filtered pages and restores page and detail state afterward', () => {
  const f = fixture({paginated: true});
  f.surveyB.checked = false; f.surveyB.handlers.change();
  // Move both pagers to page two through their real generated Next buttons.
  f.responsePagination.children[2].onclick();
  f.writtenPagination.children[2].onclick();
  const cardVisibility = f.cards.map(item => item.hidden);
  const writtenVisibility = f.written.map(item => item.hidden);
  const detailState = f.cards.map(item => item.open);
  assert.equal(f.cards.filter(item => !item.hidden).length, 5);
  assert.equal(f.written.filter(item => !item.hidden).length, 5);
  f.window.handlers.beforeprint();
  assert.equal(f.responsePagination.hidden, true);
  assert.equal(f.writtenPagination.hidden, true);
  for (const item of [...f.cards, ...f.written]) {
    assert.equal(item.hidden, item.dataset.survey !== 'a');
  }
  assert.ok(f.cards.filter(item => !item.hidden).every(item => item.open));
  // Repeated beforeprint must not overwrite the original state snapshot.
  f.window.handlers.beforeprint();
  f.window.handlers.afterprint();
  assert.deepEqual(f.cards.map(item => item.hidden), cardVisibility);
  assert.deepEqual(f.written.map(item => item.hidden), writtenVisibility);
  assert.deepEqual(f.cards.map(item => item.open), detailState);
  assert.equal(f.responsePagination.hidden, false);
  assert.equal(f.writtenPagination.hidden, false);
  assert.equal(f.responsePagination.children[1].textContent, '21–25 of 25 responses');
  assert.equal(f.writtenPagination.children[1].textContent, '21–25 of 25 written answers');
});
