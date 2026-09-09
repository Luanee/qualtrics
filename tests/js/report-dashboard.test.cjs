const test = require('node:test');
const assert = require('node:assert/strict');
const {aggregateTimeline, createDashboard} = require('../../src/qualtrics/reporting/static/dashboard.js');

test('weekly timeline uses Monday boundaries, fills gaps and counts undated records', () => {
  const result = aggregateTimeline([
    {dates: [['2025-01-05', 2], ['2025-01-06', 3], ['2025-01-20', 1]], undated: 2},
    {dates: [['2025-01-06', 4]], undated: 1},
  ], 'week');
  assert.deepEqual(result.points.map(p => [p.date, p.count]), [
    ['2024-12-30', 2], ['2025-01-06', 7], ['2025-01-13', 0], ['2025-01-20', 1],
  ]);
  assert.equal(result.undated, 3);
});

test('monthly timeline preserves calendar months across years and leap days', () => {
  const result = aggregateTimeline([{dates: [['2023-12-31', 1], ['2024-02-29', 2]], undated: 0}], 'month');
  assert.deepEqual(result.points.map(p => [p.date, p.count]), [
    ['2023-12-01', 1], ['2024-01-01', 0], ['2024-02-01', 2],
  ]);
  assert.deepEqual(aggregateTimeline([], 'week').points, []);
});

test('very long timelines bound chart size without losing dated response counts', () => {
  const result = aggregateTimeline([{dates: [['1900-01-01', 3], ['2100-01-01', 7]], undated: 0}], 'week');
  assert.ok(result.points.length <= 260);
  assert.equal(result.points.reduce((sum, p) => sum + p.count, 0), 10);
  assert.ok(result.step > 1);
});

function element(tag = 'div') {
  return {tagName: tag.toUpperCase(), children: [], attributes: {}, style: {}, handlers: {}, value: '', hidden: false,
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; this.ownText = ''; },
    set textContent(value) { this.ownText = String(value); this.children = []; },
    get textContent() { return (this.ownText || '') + this.children.map(c => c.textContent).join(''); },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    addEventListener(name, callback) { this.handlers[name] = callback; },
  };
}
function fixture() {
  const nodes = Object.fromEntries(['period','timeline','timeline-table','date-note','surveys','coverage',
    'question-1','question-2','spotlight-1','spotlight-2'].map(id => ['dashboard-' + id, element()]));
  nodes['dashboard-period'].value = 'week';
  const document = {getElementById: id => nodes[id] || null, createElement: element, createElementNS: (_, tag) => element(tag)};
  const spotlight = (id, survey, kind, target) => ({id, survey, kind, target, label:'Score <script>', field:'',
    denominator:2, bins:[{label:'Yes <script>',count:2}], note:'Two recorded values.', metric:null});
  const payload = {
    surveys: [{id:'a',label:'Survey A',responses:3,finished:2,dates:[['2025-01-01',3]],undated:0},
      {id:'b',label:'Survey B',responses:2,finished:0,dates:[['2025-02-01',1]],undated:1}],
    spotlights:[spotlight('one','a','nps','question-detail-1'), spotlight('two','a','categorical','question-detail-2'),
      spotlight('three','b','numeric','question-detail-3')],
    coverage:[{survey:'a',label:'High',answered:3,total:3,target:'question-detail-1'},
      {survey:'a',label:'Low',answered:0,total:3,target:'question-detail-2'},
      {survey:'b',label:'Other',answered:1,total:2,target:'question-detail-3'}],
  };
  const controller = createDashboard(document, payload);
  return {nodes, payload, controller};
}
function descendants(node) { return [node, ...node.children.flatMap(descendants)]; }

test('survey selection updates every chart and clears unavailable question choices', () => {
  const {nodes, controller} = fixture();
  controller.update(new Set(['a', 'b']));
  assert.match(nodes['dashboard-surveys'].textContent, /Survey A/);
  assert.match(nodes['dashboard-surveys'].textContent, /Survey B/);
  nodes['dashboard-question-1'].value = 'one'; nodes['dashboard-question-1'].handlers.change();
  controller.update(new Set(['b']));
  assert.doesNotMatch(nodes['dashboard-surveys'].textContent, /Survey A/);
  assert.equal(nodes['dashboard-question-1'].value, 'three');
  assert.ok(descendants(nodes['dashboard-spotlight-1']).some(n => n.href === '#question-detail-3'));
  assert.match(nodes['dashboard-date-note'].textContent, /1.*missing or invalid/);
  const datedRows = nodes['dashboard-timeline-table'].children[1].children;
  assert.equal(datedRows.length, 1);
  assert.equal(datedRows[0].children[0].textContent, '2025-01-27');
  assert.equal(datedRows[0].children[1].textContent, '1');
  assert.doesNotMatch(nodes['dashboard-coverage'].textContent, /High|Low/);
});

test('spotlight controls render the selected question and keep user labels as text', () => {
  const {nodes, controller} = fixture();
  controller.update(new Set(['a', 'b']));
  nodes['dashboard-question-2'].value = 'three'; nodes['dashboard-question-2'].handlers.change();
  const content = descendants(nodes['dashboard-spotlight-2']);
  assert.ok(content.some(n => n.href === '#question-detail-3'));
  assert.match(nodes['dashboard-spotlight-2'].textContent, /Yes <script>/);
  assert.equal(content.some(n => n.tagName === 'SCRIPT'), false);
});

test('empty survey selection removes previous charts and avoids invalid percentages', () => {
  const {nodes, controller} = fixture();
  controller.update(new Set(['a'])); controller.update(new Set());
  for (const id of ['surveys', 'spotlight-1', 'coverage', 'timeline']) {
    assert.match(nodes['dashboard-' + id].textContent, /No /);
    assert.doesNotMatch(nodes['dashboard-' + id].textContent, /NaN|Infinity|Survey A/);
  }
  assert.equal(nodes['dashboard-question-1'].disabled, true);
});

test('coverage ranks question occurrences by answered share and preserves drill-down targets', () => {
  const {nodes, controller} = fixture();
  controller.update(new Set(['a', 'b']));
  const links = descendants(nodes['dashboard-coverage']).filter(n => n.tagName === 'A' && n.href.startsWith('#question-detail-'));
  assert.deepEqual(links.map(n => n.href), ['#question-detail-2', '#question-detail-3', '#question-detail-1']);
});

test('period changes redraw the actual timeline table with monthly bins', () => {
  const {nodes, controller} = fixture();
  controller.update(new Set(['a', 'b']));
  nodes['dashboard-period'].value = 'month'; nodes['dashboard-period'].handlers.change();
  assert.match(nodes['dashboard-timeline-table'].textContent, /2025-01-01/);
  assert.match(nodes['dashboard-timeline-table'].textContent, /2025-02-01/);
  assert.equal(nodes['dashboard-timeline-table'].children[1].children.length, 2);
});
