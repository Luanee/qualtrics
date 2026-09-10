/* Report view routing and accessible deep links. */
(function (root) {
  'use strict';
  root.ReportNavigation = function ({document, selectedSurveys, updateAll, questions, responses, writtenPage, search, isPrinting}) {
    const {$, all, text, on} = root.ReportComponents.dom(document);
    const viewIds = ['overview', 'survey-flow', 'question-analytics', 'written-answers', 'by-responses', 'codebook'];
    const views = viewIds.map(id => document.getElementById(id)).filter(Boolean);
    const surveyChoices = all('.survey-choice'), choices = responses.choices;
    const eligible = node => Boolean(node && selectedSurveys().has(node.dataset.survey));
    let activeView = 'overview';
  function showView(id) {
    activeView = viewIds.includes(id) ? id : 'overview';
    updateViewVisibility();
    all('a[data-view]').forEach(link => {
      const current = link.getAttribute('href') === '#' + activeView;
      link.classList.toggle('is-active', current);
      if (current) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
  }
  function updateViewVisibility() {
    views.forEach(view => {
      view.hidden = (!isPrinting() && search.hasQuery()) || view.id !== activeView;
      if (!view.hidden && view.tagName === 'DETAILS') view.open = true;
    });
    if (activeView === 'survey-flow' && (isPrinting() || !search.hasQuery())) window.ReportFlow?.resize?.();
    if (activeView === 'overview' && (isPrinting() || !search.hasQuery())) window.ReportDashboard?.resize();
  }
  function navigate(hash, focus = true) {
    if ($('#report-search')?.value) search.clear();
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
    if (occurrence) questions.reveal(occurrence);
    const card = target.closest('.respondent');
    if (card) {
      if ($('#search')) $('#search').value = '';
      const answer = target.closest('.answer');
      if (answer) choices.filter(choice => choice.value === answer.dataset.question).forEach(choice => { choice.checked = true; });
      responses.update(); responses.pager.reveal(card); card.open = true;
    }
    const comment = target.closest('.written-answer');
    if (comment) {
      if ($('#written-search')) $('#written-search').value = '';
      if ($('#written-question')) $('#written-question').value = '';
      writtenPage.update(); writtenPage.pager.reveal(comment);
    }
    const field = target.closest('.codebook-row');
    if (field) window.revealCodebook?.(field);
    showView(view.id);
    const flowHandled = view.id === 'survey-flow' && window.ReportFlow?.reveal(target.id);
    for (let parent = target; parent && parent !== view.parentElement; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    if (focus && !flowHandled) {
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
    if (link.getAttribute('href') === '#report-content') {
      event.preventDefault();
      const content = document.getElementById('report-content');
      content?.focus({preventScroll: true});
      content?.scrollIntoView({block: 'start'});
      return;
    }
    event.preventDefault();
    if (location.hash !== link.hash) history.pushState(null, '', link.hash);
    navigate(link.hash);
  });
  window.addEventListener('popstate', () => navigate(location.hash));
  window.addEventListener('hashchange', () => navigate(location.hash));
    return {navigate, updateVisibility: updateViewVisibility, activeView: () => activeView};
  };
})(window);
