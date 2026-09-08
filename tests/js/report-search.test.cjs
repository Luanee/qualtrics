const test = require('node:test');
const assert = require('node:assert/strict');
const search = require('../../src/qualtrics/reporting/static/report-search.js');
test('normalizes case, German sharp s and accents', () => {
  assert.equal(search.normalize('Straße CAFÉ'), 'strasse cafe');
  assert.equal(search.normalize('STRASSE Cafe\u0301'), 'strasse cafe');
});
test('requires every term, allowing terms across record fields', () => {
  assert.equal(search.matches(search.normalize('Travel survey — Café Straße'), search.terms('STRASSE travel')), true);
  assert.equal(search.matches(search.normalize('Travel survey — Café Straße'), search.terms('travel missing')), false);
});
test('excerpts retain literal markup as plain strings and exact original Unicode', () => {
  const parts = search.excerpt('<img onerror="x"> Straße & café', search.terms('STRASSE café'));
  assert.equal(parts.map(p => p.text).join(''), '<img onerror="x"> Straße & café');
  assert.deepEqual(parts.filter(p => p.match).map(p => p.text), ['Straße', 'café']);
});
test('long excerpts find later matches and absent queries never highlight', () => {
  const text = 'start '.repeat(80) + 'needle tail';
  assert.ok(search.excerpt(text, ['needle']).some(p => p.match && p.text === 'needle'));
  assert.ok(search.excerpt('unmatched content', ['absent']).every(p => !p.match));
});
test('decomposed accent is included in highlighted range', () => {
  assert.equal(search.excerpt('Cafe\u0301', ['cafe']).filter(p => p.match).map(p => p.text).join(''), 'Cafe\u0301');
});
