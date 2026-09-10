/* Page behavior; composed by report.js with shared UI dependencies. */
(function (root) {
  'use strict';
  root.ReportPages ||= {};
  root.ReportPages.search = function ({document, searchTools, selectedSurveys, surveyNames, questions, responses, writtenPage, onVisibilityChange}) {
    const {$, all, text, on} = root.ReportComponents.dom(document);
    const {normalize, terms, matches, excerpt} = searchTools;
    const {occurrences, labelOf} = questions;
    const {cards, cache: cardCache} = responses;
    const written = writtenPage.items;
  // Each answer field is indexed independently; unrelated answer text cannot satisfy a query.
  const records = [];
  function record(scope, node, title, content, context = '') {
    records.push({scope, node, title, content, context, normalized: normalize(`${title} ${context} ${content}`)});
  }
  occurrences.forEach(node => record('Question', node, labelOf(node), [node.dataset.section, node.dataset.question].filter(Boolean).join(' · '), surveyNames.get(node.dataset.survey) || ''));
  written.forEach(node => record('Written answer', node, node.querySelector('.written-question')?.textContent || 'Written answer', node.querySelector('.written-value')?.textContent || node.textContent, [surveyNames.get(node.dataset.survey), node.querySelector('small')?.textContent].filter(Boolean).join(' · ')));
  cards.forEach((card, cardIndex) => {
    if (!card.id) card.id = `response-${cardIndex + 1}`;
    const identity = card.querySelector('.identity')?.textContent || 'Response';
    const context = `${identity} · ${surveyNames.get(card.dataset.survey) || card.dataset.survey}`;
    record('Response metadata', card, identity, card.querySelector('.response-meta')?.textContent || '', surveyNames.get(card.dataset.survey) || '');
    cardCache.get(card).answers.forEach(({row}, rowIndex) => {
      row.id ||= `${card.id}-answer-${rowIndex + 1}`;
      [...row.querySelectorAll('.field-answer')].forEach((field, fieldIndex) => {
        field.id ||= `${row.id}-field-${fieldIndex + 1}`;
        record('Response answer', field, row.querySelector('.question')?.textContent || row.dataset.question, field.textContent, context);
      });
    });
  });
  written.forEach(node => {
    const card = document.getElementById(node.dataset.responseTarget);
    if (!card || card.dataset.survey !== node.dataset.survey) return;
    const answer = cardCache.get(card)?.answers.find(item => item.row.dataset.question === node.dataset.questionToken)?.row;
    if (!answer) return;
    const field = [...answer.querySelectorAll('.field-answer')].find(item => item.dataset.fieldId === node.dataset.fieldId);
    const destination = field || answer;
    node.querySelectorAll('a').forEach(link => {
      if (link.getAttribute('href') === '#' + card.id) link.href = '#' + destination.id;
    });
  });
  all('.codebook-row').forEach((node, index) => {
    node.id ||= `codebook-field-${index + 1}`;
    record('Codebook', node, node.querySelector('strong')?.textContent || 'Exported field', [...node.cells].map(cell => cell.textContent).join(' · '));
  });
  window.ReportFlow?.records().forEach(item => record('Flow', item.node, item.title, item.content, item.context));
  const searchList = $('#search-result-list');
  let searchMatches = [], searchPage = 1, searchQuery = [];
  function appendExcerpt(node, value, query) {
    excerpt(value, query).forEach(part => {
      const span = document.createElement(part.match ? 'mark' : 'span');
      span.textContent = part.text;
      node.append(span);
    });
  }
  function renderSearchPage() {
    if (!searchList) return;
    const query = searchQuery;
    searchPage = Math.max(1, Math.min(searchPage, Math.ceil(searchMatches.length / 20) || 1));
    searchList.replaceChildren();
    searchMatches.slice((searchPage - 1) * 20, searchPage * 20).forEach(item => {
      const entry = document.createElement('article'); entry.className = 'search-result';
      const scope = document.createElement('span'); scope.className = 'search-result-scope'; scope.textContent = item.scope;
      const link = document.createElement('a'); link.href = '#' + item.node.id;
      appendExcerpt(link, item.title, query);
      const context = document.createElement('p'); context.className = 'search-result-context';
      appendExcerpt(context, item.context, query);
      const snippet = document.createElement('p'); snippet.className = 'search-result-snippet';
      appendExcerpt(snippet, item.content, query);
      entry.append(scope, link, context, snippet); searchList.append(entry);
    });
    root.ReportComponents.renderPagination(document, $('#search-pagination'), {
      page: searchPage, size: 20, total: searchMatches.length, noun: 'results',
      onPage(page) { searchPage = page; renderSearchPage(); },
    });
  }
  function updateSearch() {
    if (!searchList) return;
    searchQuery = terms($('#report-search')?.value || '');
    const surveys = selectedSurveys();
    searchMatches = searchQuery.length ? records.filter(item => surveys.has(item.node.closest('[data-survey]')?.dataset.survey) && matches(item.normalized, searchQuery)) : [];
    searchPage = 1;
    $('#search-results').hidden = !searchQuery.length;
    if ($('#search-clear')) $('#search-clear').hidden = !searchQuery.length;
    onVisibilityChange();
    text('#search-result-count', `${searchMatches.length} ${searchMatches.length === 1 ? 'result' : 'results'}`);
    renderSearchPage();
  }

    function clear() { if ($('#report-search')) $('#report-search').value = ''; updateSearch(); }

    return {update: updateSearch, clear, hasQuery: () => searchQuery.length > 0};
  };
})(window);
