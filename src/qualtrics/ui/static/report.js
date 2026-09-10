/* Compose shared components, independent pages and the report layout. */
(() => {
  'use strict';
  const {$, all, text, on} = window.ReportComponents.dom(document);
  const searchTools = window.ReportSearch;
  const {normalize, terms, matches} = searchTools;
  const surveyChoices = all('.survey-choice');
  const selectedSurveys = () => new Set(surveyChoices.filter(input => input.checked).map(input => input.value));
  const surveyNames = new Map(surveyChoices.map(input => [input.value, input.closest('label').textContent.trim()]));
  const eligible = node => Boolean(node && selectedSurveys().has(node.dataset.survey));
  let printing = false, navigation;
  const createPager = window.ReportComponents.createPagerFactory(document, () => printing);
  window.ReportUI = {createPager, selectedSurveys, normalize, terms, matches};
  window.initializeCodebook?.();
  const responses = window.ReportPages.responses({document, searchTools, createPager, selectedSurveys});
  const writtenPage = window.ReportPages.written({document, searchTools, createPager, selectedSurveys, surveyNames});
  const questions = window.ReportPages.questions({document, searchTools, selectedSurveys, surveyNames});
  const summary = window.ReportPages.summary({document, selectedSurveys, isPrinting: () => printing});
  const search = window.ReportPages.search({document, searchTools, selectedSurveys, surveyNames, questions, responses, writtenPage,
    onVisibilityChange: () => navigation?.updateVisibility()});
  function updateAll() {
    summary.update(); questions.update(); responses.update(); writtenPage.update();
    window.updateCodebook?.(); search.update();
  }
  navigation = window.ReportNavigation({document, selectedSurveys, updateAll, questions, responses, writtenPage, search, isPrinting: () => printing});
  const {cards, choices} = responses;
  on('#report-search', 'input', search.update);
  on('#search-clear', 'click', () => { $('#report-search').value = ''; search.update(); $('#report-search').focus(); });
  on('#theme-choice', 'change', () => { document.documentElement.dataset.theme = $('#theme-choice').value; });
  on('#search', 'input', () => responses.update());
  on('#written-search', 'input', () => writtenPage.update());
  on('#written-question', 'change', () => writtenPage.update());
  on('#question-filter', 'input', questions.update);
  surveyChoices.forEach(choice => choice.addEventListener('change', updateAll));
  choices.forEach(choice => choice.addEventListener('change', () => responses.update()));
  on('#survey-select-all', 'click', () => { surveyChoices.forEach(choice => { choice.checked = true; }); updateAll(); });
  on('#survey-clear', 'click', () => { surveyChoices.forEach(choice => { choice.checked = false; }); updateAll(); });
  on('#select-all', 'click', () => { choices.filter(choice => eligible(choice.closest('label'))).forEach(choice => { choice.checked = true; }); responses.update(); });
  on('#clear-all', 'click', () => { choices.filter(choice => eligible(choice.closest('label'))).forEach(choice => { choice.checked = false; }); responses.update(); });
  on('#expand', 'click', () => cards.filter(card => !card.hidden).forEach(card => { card.open = true; }));
  on('#collapse', 'click', () => cards.filter(card => !card.hidden).forEach(card => { card.open = false; }));
  window.ReportComponents.initializeMenus(document);
  let detailsBeforePrint = [];
  window.addEventListener('beforeprint', () => {
    if (printing) return;
    printing = true;
    detailsBeforePrint = all('details').map(node => [node, node.open]);
    navigation.updateVisibility();
    responses.pager.render(); writtenPage.pager.render(); window.renderCodebookPage?.(); summary.updateFindings();
    const active = document.getElementById(navigation.activeView());
    if (active?.tagName === 'DETAILS') active.open = true;
    active?.querySelectorAll('details').forEach(node => { if (!node.hidden) node.open = true; });
  });
  window.addEventListener('afterprint', () => {
    printing = false;
    navigation.updateVisibility();
    detailsBeforePrint.forEach(([node, open]) => { node.open = open; });
    responses.pager.render(); writtenPage.pager.render(); window.renderCodebookPage?.(); summary.updateFindings();
  });
  document.documentElement.classList.add('report-ready');
  updateAll(); navigation.navigate(location.hash || '#overview', false);
})();
