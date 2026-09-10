const test = require('node:test');
const assert = require('node:assert/strict');
const {aggregateTimeline, createDashboard} = require('../../src/qualtrics/ui/static/dashboard.js');

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

test('yearly timeline uses calendar years, fills missing years and carries the running total', () => {
  const result = aggregateTimeline([
    {dates: [['2022-12-31', 2], ['2023-01-01', 3], ['2025-02-28', 4]], undated: 2},
    {dates: [['2023-12-31', 1]], undated: 1},
  ], 'year');
  assert.deepEqual(result.points.map(p => [p.date, p.end, p.count, p.cumulative]), [
    ['2022-01-01', '2022-01-01', 2, 2], ['2023-01-01', '2023-01-01', 4, 6],
    ['2024-01-01', '2024-01-01', 0, 6], ['2025-01-01', '2025-01-01', 4, 10],
  ]);
  assert.equal(result.undated, 3);
});

test('weekly and monthly running totals carry across year boundaries and empty periods', () => {
  const surveys = [{dates: [['2023-12-31', 2], ['2024-02-01', 3]], undated: 1}];
  for (const period of ['week', 'month']) {
    const {points} = aggregateTimeline(surveys, period);
    assert.equal(points[0].cumulative, 2);
    assert.equal(points.at(-1).cumulative, 5);
    assert.ok(points.slice(1, -1).every(p => p.count === 0 && p.cumulative === 2));
  }
});

test('very long timelines bound chart size without losing dated response counts', () => {
  for (const period of ['week', 'month', 'year']) {
    const result = aggregateTimeline([{dates: [['1000-01-01', 3], ['2100-01-01', 7]], undated: 0}], period);
    assert.ok(result.points.length <= 260);
    assert.equal(result.points.reduce((sum, p) => sum + p.count, 0), 10);
    assert.equal(result.points.at(-1).cumulative, 10);
    assert.ok(result.step > 1);
  }
});

function element(tag = 'div') {
  return {tagName: tag.toUpperCase(), children: [], attributes: {}, style: {}, handlers: {}, value: '', checked: false, hidden: false,
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; this.ownText = ''; },
    set textContent(value) { this.ownText = String(value); this.children = []; },
    get textContent() { return (this.ownText || '') + this.children.map(c => c.textContent).join(''); },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    addEventListener(name, callback) { this.handlers[name] = callback; },
  };
}
function fixture() {
  const nodes = Object.fromEntries(['period','cumulative','timeline','timeline-table','date-note','surveys','coverage',
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

test('year grouping displays years in the table and chart instead of January dates', () => {
  const {nodes, payload, controller} = fixture();
  payload.surveys[0].dates = [['2023-12-31', 2], ['2025-01-01', 1]];
  controller.update(new Set(['a']));
  nodes['dashboard-period'].value = 'year'; nodes['dashboard-period'].handlers.change();
  const table = nodes['dashboard-timeline-table'];
  assert.deepEqual(table.children[0].children[0].children.map(n => n.textContent), ['Year', 'Responses']);
  assert.deepEqual(table.children[1].children.map(row => row.children.map(n => n.textContent)), [
    ['2023', '2'], ['2024', '0'], ['2025', '1'],
  ]);
  const chart = descendants(nodes['dashboard-timeline']);
  assert.ok(chart.some(n => n.tagName === 'TEXT' && n.textContent === '2024'));
  assert.match(chart.find(n => n.tagName === 'SVG').attributes['aria-label'], /by year/);
  assert.doesNotMatch(nodes['dashboard-timeline'].textContent, /202\d-01-01/);
});

test('cumulative mode plots running totals, retains period counts and reverses when unchecked', () => {
  const {nodes, controller} = fixture();
  nodes['dashboard-period'].value = 'month';
  controller.update(new Set(['a', 'b']));
  const plot = () => descendants(nodes['dashboard-timeline']);
  const dots = () => plot().filter(n => n.tagName === 'CIRCLE');
  assert.ok(Number(dots()[1].attributes.cy) > Number(dots()[0].attributes.cy));
  nodes['dashboard-cumulative'].checked = true; nodes['dashboard-cumulative'].handlers.change();
  const table = nodes['dashboard-timeline-table'];
  assert.deepEqual(table.children[0].children[0].children.map(n => n.textContent), ['Month starting', 'Responses', 'Cumulative responses']);
  assert.deepEqual(table.children[1].children.map(row => row.children.map(n => n.textContent)), [
    ['2025-01-01', '3', '3'], ['2025-02-01', '1', '4'],
  ]);
  assert.ok(Number(dots()[1].attributes.cy) < Number(dots()[0].attributes.cy));
  assert.match(dots()[1].textContent, /1 responses.*4 cumulative responses/);
  assert.match(plot().find(n => n.tagName === 'SVG').attributes['aria-label'], /cumulative/i);
  assert.match(nodes['dashboard-date-note'].textContent, /running total/i);
  assert.match(nodes['dashboard-date-note'].textContent, /1 with missing or invalid recorded dates excluded/);
  nodes['dashboard-cumulative'].checked = false; nodes['dashboard-cumulative'].handlers.change();
  assert.equal(table.children[0].children[0].children.length, 2);
  assert.ok(Number(dots()[1].attributes.cy) > Number(dots()[0].attributes.cy));
  assert.doesNotMatch(plot().find(n => n.tagName === 'SVG').attributes['aria-label'], /cumulative/i);
});

test('cumulative totals recompute for selected surveys and persist through regrouping and resize', () => {
  const {nodes, payload, controller} = fixture();
  payload.surveys[0].dates = [['2023-12-31', 2], ['2025-01-01', 1]];
  nodes['dashboard-cumulative'].checked = true;
  nodes['dashboard-period'].value = 'year';
  controller.update(new Set(['a', 'b']));
  const rows = () => nodes['dashboard-timeline-table'].children[1].children;
  assert.deepEqual(rows().map(row => row.children.map(n => n.textContent)), [
    ['2023', '2', '2'], ['2024', '0', '2'], ['2025', '2', '4'],
  ]);
  const circles = descendants(nodes['dashboard-timeline']).filter(n => n.tagName === 'CIRCLE');
  assert.equal(circles.length, 3);
  assert.equal(circles[0].attributes.cy, circles[1].attributes.cy);
  controller.update(new Set(['b']));
  assert.deepEqual(rows()[0].children.map(n => n.textContent), ['2025', '1', '1']);
  nodes['dashboard-period'].value = 'month'; nodes['dashboard-period'].handlers.change();
  controller.resize();
  assert.equal(nodes['dashboard-cumulative'].checked, true);
  assert.deepEqual(rows()[0].children.map(n => n.textContent), ['2025-02-01', '1', '1']);
  controller.update(new Set());
  assert.equal(rows().length, 0);
  assert.match(nodes['dashboard-timeline'].textContent, /No dated responses/);
  assert.match(nodes['dashboard-date-note'].textContent, /0 dated responses/);
});
