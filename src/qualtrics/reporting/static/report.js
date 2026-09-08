(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const all = selector => [...document.querySelectorAll(selector)];
  const searchTools = window.ReportSearch;
  const {normalize, terms, matches, excerpt} = searchTools;
  const text = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
  const on = (selector, event, callback) => $(selector)?.addEventListener(event, callback);
  const surveyChoices = all('.survey-choice');
  const choices = all('.question-choice');
  const cards = all('.respondent');
  const written = all('.written-answer');
  const occurrences = all('.survey-analysis.survey-occurrence');
  const viewIds = ['overview', 'question-analytics', 'written-answers', 'by-responses', 'codebook'];
  const views = viewIds.map(id => document.getElementById(id)).filter(Boolean);
  let activeView = 'overview', activeQuestion = '', printing = false, showAllFindings = false;
  const selectedSurveys = () => new Set(surveyChoices.filter(input => input.checked).map(input => input.value));
  const surveyNames = new Map(surveyChoices.map(input => [input.value, input.closest('label').textContent.trim()]));
  const eligible = node => Boolean(node && selectedSurveys().has(node.dataset.survey));
  const labelOf = node => node.dataset.label || node.dataset.question || node.querySelector('summary')?.textContent.trim() || 'Question';

  // Pagination retains the full filtered collection separately from screen visibility.
  function createPager(nodes, container, size, noun) {
    let filtered = [], page = 1;
    if (container) container.classList.add('pagination');
    function render() {
      page = Math.max(1, Math.min(page, Math.ceil(filtered.length / size) || 1));
      const displayed = new Set(printing ? filtered : filtered.slice((page - 1) * size, page * size));
      nodes.forEach(node => { node.hidden = !displayed.has(node); });
      if (!container) return;
      container.replaceChildren();
      container.hidden = printing || filtered.length === 0;
      const previous = document.createElement('button'), next = document.createElement('button');
      previous.type = next.type = 'button';
      previous.textContent = 'Previous'; next.textContent = 'Next';
      previous.disabled = page === 1; next.disabled = page * size >= filtered.length;
      previous.setAttribute('aria-label', `Previous ${noun} page`);
      next.setAttribute('aria-label', `Next ${noun} page`);
      previous.onclick = () => { page--; render(); };
      next.onclick = () => { page++; render(); };
      const range = document.createElement('span');
      range.setAttribute('aria-live', 'polite');
      range.textContent = `${filtered.length ? (page - 1) * size + 1 : 0}–${Math.min(page * size, filtered.length)} of ${filtered.length} ${noun}`;
      container.append(previous, range, next);
    }
    return {
      update(items, reset = true) { filtered = items; if (reset) page = 1; render(); },
      reveal(node) { const index = filtered.indexOf(node); if (index >= 0) page = Math.floor(index / size) + 1; render(); },
      render, getFiltered: () => filtered,
    };
  }
  window.ReportUI = {createPager, selectedSurveys, normalize, terms, matches};
  window.initializeCodebook?.();
  const responsePager = createPager(cards, $('#response-pagination'), 20, 'responses');
  const writtenPager = createPager(written, $('#written-pagination'), 20, 'written answers');
  const cardCache = new Map(cards.map(card => [card, {
    metadata: [card.querySelector('.identity')?.textContent, card.querySelector('.response-meta')?.textContent].join(' '),
    answers: [...card.querySelectorAll('.answer')].map(row => ({row, content: normalize(row.textContent)})),
  }]));
  const writtenCache = new Map(written.map(node => [node, normalize(node.textContent)]));

  function updateResponses(reset = true) {
    const selected = new Set(choices.filter(choice => choice.checked).map(choice => choice.value));
    const query = terms($('#search')?.value || '');
    const filtered = cards.filter(card => {
      const cached = cardCache.get(card);
      const shown = cached.answers.filter(answer => selected.has(answer.row.dataset.question));
      cached.answers.forEach(answer => { answer.row.hidden = !selected.has(answer.row.dataset.question); });
      const empty = card.querySelector('.no-selected');
      if (empty) empty.hidden = shown.length > 0;
      const badge = card.querySelector('.badge');
      if (badge) badge.textContent = `${shown.length} ${shown.length === 1 ? 'answer' : 'answers'}`;
      return eligible(card) && matches(normalize(cached.metadata) + ' ' + shown.map(answer => answer.content).join(' '), query);
    });
    responsePager.update(filtered, reset);
    text('#count', `${filtered.length} of ${cards.filter(eligible).length}`);
    $('#empty')?.classList.toggle('hidden', filtered.length > 0);
    if ($('#empty')) $('#empty').hidden = filtered.length > 0;
    const activeChoices = choices.filter(choice => eligible(choice.closest('label')));
    choices.forEach(choice => { choice.closest('label').hidden = !eligible(choice.closest('label')); });
    const n = activeChoices.filter(choice => choice.checked).length;
    text('#selected-count', n === activeChoices.length ? 'All' : `${n} selected`);
  }

  function updateWritten(reset = true) {
    const query = terms($('#written-search')?.value || '');
    const selector = $('#written-question');
    const surveys = selectedSurveys();
    if (selector) {
      const options = [...selector.options].filter(option => option.value);
      options.forEach(option => {
        option.hidden = option.disabled = !surveys.has(option.dataset.survey);
        option.textContent = surveys.size > 1
          ? `${option.dataset.label} · ${surveyNames.get(option.dataset.survey) || option.dataset.survey}`
          : option.dataset.label;
      });
      if (selector.value && !options.some(option => option.value === selector.value && !option.disabled)) selector.value = '';
    }
    const question = selector?.value || '';
    const filtered = written.filter(node => eligible(node) && (!question || node.dataset.questionToken === question) && matches(writtenCache.get(node), query));
    writtenPager.update(filtered, reset);
    text('#written-count', `${filtered.length} written answers`);
    if ($('#written-empty')) $('#written-empty').hidden = filtered.length > 0;
  }

  function updateQuestions() {
    const permitted = occurrences.filter(eligible);
    const query = terms($('#question-filter')?.value || '');
    const matching = permitted.filter(node => matches(normalize([labelOf(node), node.dataset.question, node.dataset.section, surveyNames.get(node.dataset.survey)].join(' ')), query));
    if (!matching.some(node => node.id === activeQuestion)) activeQuestion = matching[0]?.id || '';
    occurrences.forEach(node => {
      node.hidden = node.id !== activeQuestion || !eligible(node);
      if (!node.hidden) node.open = true;
    });
    all('#question-analytics .catalog-group').forEach(group => {
      group.hidden = ![...group.querySelectorAll('.survey-analysis.survey-occurrence')].some(node => !node.hidden);
      if (!group.hidden) group.open = true;
    });
    const navigator = $('#question-navigator');
    if (navigator) {
      navigator.replaceChildren();
      matching.forEach(node => {
        const link = document.createElement('a');
        link.href = '#' + node.id;
        link.textContent = [node.dataset.section, node.dataset.question, labelOf(node), surveyNames.get(node.dataset.survey) || node.dataset.survey].filter(Boolean).join(' · ');
        if (node.id === activeQuestion) link.setAttribute('aria-current', 'true');
        navigator.append(link);
      });
      if ($('#question-empty')) {
        $('#question-empty').hidden = navigator.childElementCount > 0;
        $('#question-empty').textContent = permitted.length ? 'No questions match this filter.' : 'No questions in the selected surveys.';
      }
    }
  }

  const findings = all('.finding');
  const findingsMore = document.createElement('button');
  findingsMore.id = 'findings-more'; findingsMore.type = 'button';
  $('.findings')?.after(findingsMore);
  function updateFindings() {
    const selected = findings.filter(eligible);
    const displayed = new Set(printing || showAllFindings ? selected : selected.slice(0, 5));
    findings.forEach(node => { node.hidden = !displayed.has(node); });
    findingsMore.hidden = printing || selected.length <= 5;
    findingsMore.textContent = showAllFindings ? 'Show fewer highlights' : `Show all ${selected.length} highlights`;
    findingsMore.setAttribute('aria-expanded', String(showAllFindings));
    if ($('#findings-empty')) $('#findings-empty').hidden = selected.length > 0;
  }
  findingsMore.addEventListener('click', () => { showAllFindings = !showAllFindings; updateFindings(); });

  function updateSurveySummary() {
    const surveys = selectedSurveys();
    const names = ['responses', 'finished', 'questions', 'answers', 'unanswered', 'unusedFields'];
    const totals = Object.fromEntries(names.map(name => [name, 0]));
    surveyChoices.filter(choice => choice.checked).forEach(choice => names.forEach(name => { totals[name] += Number(choice.dataset[name] || 0); }));
    text('#survey-selected-count', surveys.size === surveyChoices.length ? 'All' : surveys.size ? `${surveys.size} selected` : 'None');
    ['responses', 'questions', 'answers'].forEach(name => text('#stat-' + name, totals[name].toLocaleString()));
    text('#overview-finished', totals.finished.toLocaleString());
    text('#overview-completion', `${totals.responses ? Math.round(totals.finished / totals.responses * 100) : 0}%`);
    text('#overview-unanswered', totals.unanswered.toLocaleString());
    text('#overview-unused-fields', totals.unusedFields.toLocaleString());
    all('.quality').forEach(node => { node.hidden = !eligible(node); });
    updateFindings();
    let coverage = 0, analytics = 0;
    all('.catalog-group').forEach(group => {
      const rows = [...group.querySelectorAll('.survey-occurrence')];
      const selectedRows = rows.filter(eligible);
      const n = new Set(selectedRows.map(node => node.dataset.survey)).size;
      const count = group.querySelector('.occurrence-count');
      if (count) count.textContent = `${n} survey ${n === 1 ? 'occurrence' : 'occurrences'}`;
      if (group.closest('#question-coverage')) {
        rows.forEach(node => { node.hidden = !eligible(node); });
        group.hidden = !selectedRows.length;
        if (selectedRows.length) coverage++;
      }
      if (group.closest('#question-analytics') && selectedRows.length) analytics++;
    });
    text('#coverage-count', `${coverage} canonical ${coverage === 1 ? 'question' : 'questions'}`);
    text('#analytics-count', `${analytics} canonical ${analytics === 1 ? 'question' : 'questions'}`);
  }

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
    const controls = $('#search-pagination');
    controls.replaceChildren(); controls.hidden = searchMatches.length === 0;
    const previous = document.createElement('button'), next = document.createElement('button');
    previous.type = next.type = 'button'; previous.textContent = 'Previous'; next.textContent = 'Next';
    previous.setAttribute('aria-label', 'Previous results page'); next.setAttribute('aria-label', 'Next results page');
    previous.disabled = searchPage === 1; next.disabled = searchPage * 20 >= searchMatches.length;
    previous.onclick = () => { searchPage--; renderSearchPage(); };
    next.onclick = () => { searchPage++; renderSearchPage(); };
    const range = document.createElement('span'); range.setAttribute('aria-live', 'polite');
    range.textContent = `${searchMatches.length ? (searchPage - 1) * 20 + 1 : 0}–${Math.min(searchPage * 20, searchMatches.length)} of ${searchMatches.length} results`;
    controls.append(previous, range, next);
  }
  function updateSearch() {
    if (!searchList) return;
    searchQuery = terms($('#report-search')?.value || '');
    const surveys = selectedSurveys();
    searchMatches = searchQuery.length ? records.filter(item => surveys.has(item.node.closest('[data-survey]')?.dataset.survey) && matches(item.normalized, searchQuery)) : [];
    searchPage = 1;
    $('#search-results').hidden = !searchQuery.length;
    text('#search-result-count', `${searchMatches.length} ${searchMatches.length === 1 ? 'result' : 'results'}`);
    renderSearchPage();
  }

  function updateAll() {
    updateSurveySummary(); updateQuestions(); updateResponses(); updateWritten();
    window.updateCodebook?.(); updateSearch();
  }
  function showView(id) {
    activeView = viewIds.includes(id) ? id : 'overview';
    views.forEach(view => { view.hidden = view.id !== activeView; if (!view.hidden && view.tagName === 'DETAILS') view.open = true; });
    all('a[data-view]').forEach(link => {
      const current = link.getAttribute('href') === '#' + activeView;
      link.classList.toggle('is-active', current);
      if (current) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
  }
  function navigate(hash, focus = true) {
    let id; try { id = decodeURIComponent(hash.replace(/^#/, '')); } catch { id = ''; }
    const target = document.getElementById(id);
    if (!target) { showView('overview'); return; }
    const view = views.find(node => node === target || node.contains(target));
    if (!view) { showView('overview'); return; }
    const owner = target.closest('[data-survey]');
    if (owner && !eligible(owner)) {
      const choice = surveyChoices.find(input => input.value === owner.dataset.survey);
      if (choice) { choice.checked = true; updateAll(); }
    }
    const occurrence = target.closest('.survey-analysis.survey-occurrence');
    if (occurrence) { if ($('#question-filter')) $('#question-filter').value = ''; activeQuestion = occurrence.id; updateQuestions(); }
    const card = target.closest('.respondent');
    if (card) {
      if ($('#search')) $('#search').value = '';
      const answer = target.closest('.answer');
      if (answer) choices.filter(choice => choice.value === answer.dataset.question).forEach(choice => { choice.checked = true; });
      updateResponses(); responsePager.reveal(card); card.open = true;
    }
    const comment = target.closest('.written-answer');
    if (comment) {
      if ($('#written-search')) $('#written-search').value = '';
      if ($('#written-question')) $('#written-question').value = '';
      updateWritten(); writtenPager.reveal(comment);
    }
    const field = target.closest('.codebook-row');
    if (field) window.revealCodebook?.(field);
    showView(view.id);
    for (let parent = target; parent && parent !== view.parentElement; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    if (focus) {
      target.setAttribute('tabindex', '-1');
      target.focus({preventScroll: true});
      target.scrollIntoView({block: 'start'});
    }
  }
  // Native keyboard activation of a summary also dispatches click. Cancel that
  // default action for page headings only; no toggle listener/reopen loop is needed.
  document.addEventListener('click', event => {
    const summary = event.target.closest('summary');
    const details = summary?.parentElement;
    const pageHeading = details && details.id === activeView &&
      (details.id === 'question-analytics' || details.id === 'codebook');
    const questionHeading = activeView === 'question-analytics' && details &&
      !details.hidden && details.closest('#question-analytics') &&
      details.matches('.question-analysis.catalog-group, .survey-analysis.survey-occurrence');
    if ((pageHeading || questionHeading) && !event.target.closest('a, button, input, select, textarea')) {
      event.preventDefault();
      return;
    }
    const link = event.target.closest('a[href^="#"]');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (link.closest('#search-result-list')) { $('#report-search').value = ''; updateSearch(); }
    if (location.hash !== link.hash) history.pushState(null, '', link.hash);
    navigate(link.hash);
  });
  window.addEventListener('popstate', () => navigate(location.hash));
  window.addEventListener('hashchange', () => navigate(location.hash));
  on('#report-search', 'input', updateSearch);
  on('#search-clear', 'click', () => { $('#report-search').value = ''; updateSearch(); $('#report-search').focus(); });
  on('#search', 'input', () => updateResponses());
  on('#written-search', 'input', () => updateWritten());
  on('#written-question', 'change', () => updateWritten());
  on('#question-filter', 'input', updateQuestions);
  surveyChoices.forEach(choice => choice.addEventListener('change', updateAll));
  choices.forEach(choice => choice.addEventListener('change', () => updateResponses()));
  on('#survey-select-all', 'click', () => { surveyChoices.forEach(choice => { choice.checked = true; }); updateAll(); });
  on('#survey-clear', 'click', () => { surveyChoices.forEach(choice => { choice.checked = false; }); updateAll(); });
  on('#select-all', 'click', () => { choices.filter(choice => eligible(choice.closest('label'))).forEach(choice => { choice.checked = true; }); updateResponses(); });
  on('#clear-all', 'click', () => { choices.filter(choice => eligible(choice.closest('label'))).forEach(choice => { choice.checked = false; }); updateResponses(); });
  on('#expand', 'click', () => cards.filter(card => !card.hidden).forEach(card => { card.open = true; }));
  on('#collapse', 'click', () => cards.filter(card => !card.hidden).forEach(card => { card.open = false; }));
  const menus = [['#question-toggle', '#question-menu'], ['#survey-toggle', '#survey-menu']];
  function closeMenus() { menus.forEach(([toggle, menu]) => { if ($(menu)) $(menu).hidden = true; $(toggle)?.setAttribute('aria-expanded', 'false'); }); }
  menus.forEach(([toggle, menu]) => {
    on(toggle, 'click', event => { event.stopPropagation(); const opening = $(menu).hidden; closeMenus(); $(menu).hidden = !opening; $(toggle).setAttribute('aria-expanded', String(opening)); });
    on(menu, 'click', event => event.stopPropagation());
  });
  document.addEventListener('click', closeMenus);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenus(); });
  let detailsBeforePrint = [];
  window.addEventListener('beforeprint', () => {
    if (printing) return;
    printing = true;
    detailsBeforePrint = all('details').map(node => [node, node.open]);
    responsePager.render(); writtenPager.render(); window.renderCodebookPage?.(); updateFindings();
    const active = document.getElementById(activeView);
    if (active?.tagName === 'DETAILS') active.open = true;
    active?.querySelectorAll('details').forEach(node => { if (!node.hidden) node.open = true; });
  });
  window.addEventListener('afterprint', () => {
    printing = false;
    detailsBeforePrint.forEach(([node, open]) => { node.open = open; });
    responsePager.render(); writtenPager.render(); window.renderCodebookPage?.(); updateFindings();
  });
  document.documentElement.classList.add('report-ready');
  updateAll(); navigate(location.hash || '#overview', false);
})();
