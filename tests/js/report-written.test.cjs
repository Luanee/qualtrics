const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const search = require('../../src/qualtrics/ui/static/report-search.js');

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
    setAttribute() {}, closest() { return null; }, contains() { return false; }, focus() {}, scrollIntoView() {}};
}
function fixture({paginated = false, properties = false} = {}) {
  const surveyA = node(), surveyB = node();
  surveyA.value = 'a'; surveyB.value = 'b';
  surveyA.closest = () => ({textContent: 'Survey A'});
  surveyB.closest = () => ({textContent: 'Survey B'});
  const field1 = node({fieldId: 'first'}, {'.value': [{textContent: 'Lee'}]});
  const field2 = node({fieldId: 'last'}, {'.value': [{textContent: 'Lee'}]});
  const row = node({question: 'a::q'}, {'.field-answer': [field1, field2]});
  const propertyRows = properties ? [['Region', 'North'], ['Email permission', 'False'], ['Count', '0']].map(([label, value]) => {
    const property = node({}, {'.property-label': [{textContent: label}], '.property-value': [{textContent: value}]});
    property.textContent = `${label} ${value}`;
    return property;
  }) : [];
  const propertyDetails = node(); propertyDetails.tagName = 'DETAILS'; propertyDetails.open = false;
  propertyDetails.textContent = propertyRows.map(item => item.textContent).join(' ');
  const card = node({survey: 'a'}, {'.answer': [row], '.response-property': propertyRows, '.response-properties': [propertyDetails]}); card.id = 'response-1';
  propertyDetails.parentElement = card;
  propertyRows.forEach(property => {
    property.parentElement = propertyDetails;
    property.closest = selector => ['[data-survey]', '.respondent'].includes(selector) ? card : null;
  });
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
  responseView.contains = item => cards.includes(item) || propertyRows.includes(item);
  const overview = node(); overview.id = 'overview';
  const flowView = node(); flowView.id = 'survey-flow';
  const flowCard = node({survey: 'a'}); flowCard.id = 'flow-sales';
  flowCard.closest = selector => selector === '[data-survey]' ? flowCard : null;
  flowView.contains = item => item === flowCard;
  const reportSearch = node(), responseSearch = node(), searchResults = node(), searchClear = node(), theme = node(), other = node();
  const selectors = {'.survey-choice': [surveyA, surveyB], '.respondent': cards, '.written-answer': written,
    details: cards, '#response-pagination': [responsePagination], '#written-pagination': [writtenPagination],
    '#written-question': [select], '#written-empty': [empty], '#report-search': [reportSearch], '#search': [responseSearch],
    '#search-results': [searchResults], '#search-result-list': [node()], '#search-pagination': [node()],
    '#search-clear': [searchClear], '#theme-choice': [theme], '#overview-other': [other]};
  const document = node({}, selectors);
  document.addEventListener = (event, callback) => {
    const previous = document.handlers[event];
    document.handlers[event] = previous ? value => { previous(value); callback(value); } : callback;
  };
  const content = node(); content.id = 'report-content'; content.focus = () => { content.focused = true; };
  document.getElementById = id => [content, overview, responseView, flowView, flowCard, ...cards, ...propertyRows].find(item => item.id === id) || null;
  document.createElement = () => node(); document.documentElement = node();
  const dashboardSelections = [];
  const dashboardResizes = [];
  const flowSelections = [], flowReveals = [], flowResizes = [];
  const window = {ReportSearch: search, handlers: {}, addEventListener(event, callback) { this.handlers[event] = callback; },
    ReportDashboard: {update(selected) { dashboardSelections.push([...selected]); }, resize() { dashboardResizes.push(true); }},
    ReportFlow: {update(selected) { flowSelections.push([...selected]); },
      resize() { flowResizes.push(flowView.hidden); },
      reveal(id) { flowReveals.push(id); assert.equal(flowView.hidden, false); return true; },
      records() { return [{node: flowCard, title: 'Sales route', content: 'Department is Sales', context: 'Survey A', scope: 'Flow'}]; }}};
  const location = {hash: '#by-responses'};
  const manifest = fs.readFileSync(require.resolve('../../src/qualtrics/ui/assets.py'), 'utf8')
    .split('SCRIPT_ASSETS = (')[1].split(')')[0];
  const files = [...manifest.matchAll(/"([^"]+\.js)"/g)].map(match => match[1])
    .filter(name => /^(components\/|pages\/|layouts\/|report\.js$)/.test(name));
  const context = vm.createContext({document, window, location});
  for (const name of files) vm.runInContext(fs.readFileSync(require.resolve('../../src/qualtrics/ui/static/' + name), 'utf8'), context);
  return {surveyA, surveyB, a, b, field2, link, select, optionA, optionB, empty,
    cards, written, responsePagination, writtenPagination, window, location, document,
    overview, responseView, reportSearch, searchResults, searchClear, theme, other, dashboardSelections, dashboardResizes,
    flowView, flowCard, flowSelections, flowReveals, flowResizes, content, responseSearch, propertyRows, propertyDetails};
}

test('response properties participate in local search without requiring question selection', () => {
  const f = fixture({properties: true});
  f.responseSearch.value = 'Region North'; f.responseSearch.handlers.input();
  assert.equal(f.cards[0].hidden, false);
  f.responseSearch.value = 'Email permission False'; f.responseSearch.handlers.input();
  assert.equal(f.cards[0].hidden, false);
  f.responseSearch.value = 'Count 0'; f.responseSearch.handlers.input();
  assert.equal(f.cards[0].hidden, false);
  f.responseSearch.value = 'South'; f.responseSearch.handlers.input();
  assert.equal(f.cards[0].hidden, true);
});

test('global search finds individual property labels and values and opens their disclosure', () => {
  const f = fixture({properties: true});
  f.reportSearch.value = 'Email permission false'; f.reportSearch.handlers.input();
  const results = f.document.querySelector('#search-result-list');
  assert.equal(results.children.length, 1);
  assert.equal(results.children[0].children[1].href, '#' + f.propertyRows[1].id);
  f.location.hash = '#' + f.propertyRows[1].id; f.window.handlers.hashchange();
  assert.equal(f.propertyDetails.open, true);
  assert.equal(f.cards[0].open, true);
  assert.equal(f.responseView.hidden, false);
  f.reportSearch.value = 'Region false'; f.reportSearch.handlers.input();
  assert.equal(results.children.length, 0);
});

test('skip to content focuses the main landmark without changing the current page', () => {
  const f = fixture();
  let prevented = false;
  const link = {getAttribute: () => '#report-content'};
  f.document.handlers.click({target: {closest: selector => selector === 'a[href^="#"]' ? link : null},
    preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
  assert.equal(f.content.focused, true);
  assert.equal(f.location.hash, '#by-responses');
  assert.equal(f.responseView.hidden, false);
});

test('flow participates in shared survey selection, global search and exact-link navigation', () => {
  const f = fixture();
  assert.deepEqual(f.flowSelections.at(-1), ['a', 'b']);
  f.surveyA.checked = false; f.surveyA.handlers.change();
  assert.deepEqual(f.flowSelections.at(-1), ['b']);
  f.location.hash = '#flow-sales'; f.window.handlers.hashchange();
  assert.equal(f.surveyA.checked, true);
  assert.equal(f.flowView.hidden, false);
  assert.equal(f.flowReveals.at(-1), 'flow-sales');
  assert.equal(f.flowResizes.at(-1), false);
  f.reportSearch.value = 'Sales route'; f.reportSearch.handlers.input();
  assert.equal(f.document.querySelector('#search-result-list').children.length, 1);
  f.surveyA.checked = false; f.surveyA.handlers.change();
  assert.equal(f.document.querySelector('#search-result-list').children.length, 0);
});

test('report forwards the shared survey scope to dashboard charts on initial load and changes', () => {
  const f = fixture();
  assert.deepEqual(f.dashboardSelections.at(-1), ['a', 'b']);
  f.surveyA.checked = false; f.surveyA.handlers.change();
  assert.deepEqual(f.dashboardSelections.at(-1), ['b']);
  f.surveyB.checked = false; f.surveyB.handlers.change();
  assert.deepEqual(f.dashboardSelections.at(-1), []);
});

test('returning to Summary redraws the chart after its container becomes visible', () => {
  const f = fixture();
  const previous = f.dashboardResizes.length;
  f.location.hash = '#overview'; f.window.handlers.hashchange();
  assert.ok(f.dashboardResizes.length > previous);
  f.reportSearch.value = 'no match'; f.reportSearch.handlers.input();
  const duringSearch = f.dashboardResizes.length;
  f.searchClear.handlers.click();
  assert.ok(f.dashboardResizes.length > duringSearch);
});

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

test('global search replaces the current view and clearing restores it', () => {
  const f = fixture();
  f.reportSearch.value = 'no match'; f.reportSearch.handlers.input();
  assert.equal(f.responseView.hidden, true);
  assert.equal(f.overview.hidden, true);
  assert.equal(f.searchResults.hidden, false);
  assert.equal(f.searchClear.hidden, false);
  f.searchClear.handlers.click();
  assert.equal(f.responseView.hidden, false);
  assert.equal(f.searchResults.hidden, true);
  assert.equal(f.searchClear.hidden, true);
});

test('navigation clears global search, including browser history navigation', () => {
  const f = fixture();
  f.reportSearch.value = 'no match'; f.reportSearch.handlers.input();
  f.location.hash = '#overview'; f.window.handlers.hashchange();
  assert.equal(f.reportSearch.value, '');
  assert.equal(f.searchResults.hidden, true);
  assert.equal(f.overview.hidden, false);
  assert.equal(f.responseView.hidden, true);
});

test('theme selection updates the document and summary follows selected surveys', () => {
  const f = fixture();
  f.theme.value = 'dark'; f.theme.handlers.change();
  assert.equal(f.document.documentElement.dataset.theme, 'dark');
  f.theme.value = 'system'; f.theme.handlers.change();
  assert.equal(f.document.documentElement.dataset.theme, 'system');
  f.surveyA.dataset.responses = '8'; f.surveyA.dataset.finished = '5';
  f.surveyB.dataset.responses = '3'; f.surveyB.dataset.finished = '1';
  f.surveyA.handlers.change();
  assert.equal(f.other.textContent, '5');
  f.surveyB.checked = false; f.surveyB.handlers.change();
  assert.equal(f.other.textContent, '3');
});

test('printing during search prints the active view and restores the search afterward', () => {
  const f = fixture();
  f.reportSearch.value = 'no match'; f.reportSearch.handlers.input();
  f.window.handlers.beforeprint();
  assert.equal(f.responseView.hidden, false);
  assert.equal(f.overview.hidden, true);
  f.window.handlers.afterprint();
  assert.equal(f.responseView.hidden, true);
  assert.equal(f.overview.hidden, true);
  assert.equal(f.reportSearch.value, 'no match');
  assert.equal(f.searchResults.hidden, false);
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
