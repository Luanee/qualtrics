const test = require('node:test');
const assert = require('node:assert/strict');
const {createPagerFactory} = require('../../src/qualtrics/reporting/static/components/pagination.js');

function element() {
  return {hidden: false, children: [], classList: {add() {}},
    setAttribute(name, value) { this[name] = value; },
    replaceChildren() { this.children = []; }, append(...items) { this.children.push(...items); }};
}

test('shared paging reveals a distant item and resets when the filter changes', () => {
  const items = Array.from({length: 43}, element), controls = element();
  const pager = createPagerFactory({createElement: element}, () => false)(items, controls, 20, 'responses');
  pager.update(items);
  assert.equal(items.filter(item => !item.hidden).length, 20);
  pager.reveal(items[42]);
  assert.equal(items[42].hidden, false);
  assert.equal(controls.children[1].textContent, '41–43 of 43 responses');
  pager.update(items.slice(5, 9));
  assert.deepEqual(items.filter(item => !item.hidden), items.slice(5, 9));
  assert.equal(controls.children[1].textContent, '1–4 of 4 responses');
});

test('printing includes all filtered items and restores the current screen page', () => {
  let printing = false;
  const items = Array.from({length: 48}, element), controls = element();
  const pager = createPagerFactory({createElement: element}, () => printing)(items, controls, 20, 'answers');
  pager.update(items.slice(0, 45)); pager.reveal(items[40]);
  printing = true; pager.render();
  assert.equal(items.filter(item => !item.hidden).length, 45);
  assert.equal(controls.hidden, true);
  printing = false; pager.render();
  assert.equal(items.filter(item => !item.hidden).length, 5);
  assert.equal(items[40].hidden, false);
});
