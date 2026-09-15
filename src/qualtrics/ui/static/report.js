/* Compose shared components, independent pages and the report layout. */
(() => {
  'use strict';
  const {$, all, text, on} = window.ReportComponents.dom(document);
  const searchTools = window.ReportSearch;
  const {normalize, terms, matches} = searchTools;
  const surveyChoices = all('.survey-choice');
  const languageData = JSON.parse($('#report-language-data')?.textContent || '{}');
  const respondentLanguage = () => $('#respondent-language')?.value || 'all';
  const displayLanguage = () => $('#display-language')?.value || '';
  const selectedSurveys = () => new Set(surveyChoices.filter(input => input.checked).map(input => input.value));
  const surveyNames = new Map(surveyChoices.map(input => [input.value, input.closest('label').textContent.trim()]));
  const eligible = node => Boolean(node && selectedSurveys().has(node.dataset.survey));
  let printing = false, navigation;
  const createPager = window.ReportComponents.createPagerFactory(document, () => printing);
  window.ReportUI = {createPager, selectedSurveys, respondentLanguage, displayLanguage, normalize, terms, matches};
  window.initializeCodebook?.();
  const responses = window.ReportPages.responses({document, searchTools, createPager, selectedSurveys});
  const writtenPage = window.ReportPages.written({document, searchTools, createPager, selectedSurveys, surveyNames});
  const questions = window.ReportPages.questions({document, searchTools, selectedSurveys, surveyNames});
  const summary = window.ReportPages.summary({document, selectedSurveys, isPrinting: () => printing});
  const search = window.ReportPages.search({document, searchTools, selectedSurveys, surveyNames, questions, responses, writtenPage,
    onVisibilityChange: () => navigation?.updateVisibility()});
  function applySnapshot() {
    const snapshot = languageData.snapshots?.[respondentLanguage()] || languageData.snapshots?.all;
    if (!snapshot) return;
    surveyChoices.forEach(choice => {
      const counts = snapshot.surveys?.[choice.value] || {};
      for (const name of ['responses', 'finished', 'questions', 'answers', 'unanswered', 'unusedFields']) {
        choice.dataset[name] = String(counts[name] || 0);
      }
    });
    window.ReportDashboard?.setData?.(snapshot.dashboard);
    all('.survey-analysis.survey-occurrence').forEach(node => {
      const metric = snapshot.questions?.[node.id];
      if (!metric) return;
      node.querySelector('.respondent-summary b').textContent = Number(metric.respondents).toLocaleString();
      node.querySelector('.coverage-summary b').textContent = `${metric.coverage}%`;
      const valueSummary = node.querySelector('.value-summary');
      valueSummary.querySelector('b').textContent = Number(metric.value_count).toLocaleString();
      valueSummary.lastChild.textContent = ` ${metric.value_label}`;
      node.querySelector('.analysis-body').innerHTML = metric.body;
    });
    all('.coverage-survey-row').forEach(row => {
      const metric = snapshot.questions?.[row.dataset.target];
      if (!metric) return;
      row.querySelector('.coverage-count').textContent = Number(metric.respondents).toLocaleString();
      row.querySelector('.coverage-rate').textContent = `${metric.coverage}%`;
      row.querySelector('.meter i').style.width = `${metric.coverage}%`;
    });
    const findings = $('.findings');
    if (findings) findings.innerHTML = snapshot.findings.join('');
    all('.quality').forEach(node => {
      const markup = (snapshot.quality?.[displayLanguage()] || snapshot.quality?.[''])?.[node.dataset.survey];
      if (!markup) return;
      const template = document.createElement('template');
      template.innerHTML = markup;
      const replacement = template.content.firstElementChild;
      if (replacement) { replacement.open = node.open; node.replaceWith(replacement); }
    });
  }
  function applyLabels() {
    const labels = languageData.labels?.[displayLanguage()];
    if (!labels) return;
    all('.question-label[data-question-id], .question[data-question-id], .written-question[data-question-id], .finding a[data-question-id]')
      .forEach(node => { node.textContent = labels.questions[node.dataset.questionId] || node.textContent; });
    all('.survey-analysis[data-question-id]').forEach(node => {
      node.dataset.label = labels.questions[node.dataset.questionId] || node.dataset.label;
    });
    all('.field-answer[data-field-id]').forEach(node => {
      const label = node.querySelector('.field');
      if (label && labels.fields[node.dataset.fieldId]) label.textContent = labels.fields[node.dataset.fieldId];
      const value = node.querySelector('.value');
      if (value && node.dataset.optionId) {
        const raw = node.dataset.rawValue || '';
        value.textContent = labels.options[node.dataset.optionId] || raw;
        const original = node.querySelector('.answer-original');
        if (original) original.hidden = value.textContent === raw;
      }
    });
    all('.written-answer[data-field-id]').forEach(node => {
      const field = node.querySelector('.written-field');
      if (field && labels.fields[node.dataset.fieldId]) field.textContent = labels.fields[node.dataset.fieldId];
    });
    all('#written-question option[data-question-id]').forEach(node => {
      node.dataset.label = labels.questions[node.dataset.questionId] || node.dataset.label;
    });
    all('.option-row[data-option-id]').forEach(node => {
      const label = node.querySelector('.option-label');
      if (label && labels.options[node.dataset.optionId]) {
        label.textContent = labels.options[node.dataset.optionId]; label.title = label.textContent;
      }
    });
    all('.field-analysis[data-field-id], .matrix-summary tr[data-field-id]').forEach(node => {
      const heading = node.querySelector('h4, th[scope="row"]');
      if (heading && labels.fields[node.dataset.fieldId]) heading.textContent = labels.fields[node.dataset.fieldId];
    });
    all('.matrix-summary th[data-option-id]').forEach(node => {
      const label = node.querySelector('span');
      if (label && labels.options[node.dataset.optionId]) label.textContent = labels.options[node.dataset.optionId];
    });
    const flowLabels = languageData.flow_labels?.[displayLanguage()] || {};
    all('.flow-question-label[data-question-external-id]').forEach(node => {
      const survey = node.closest('.flow-survey')?.dataset.survey;
      const translated = flowLabels[survey]?.[node.dataset.questionExternalId]?.text;
      if (translated) (node.querySelector('a') || node).textContent = translated;
    });
    window.ReportFlow?.setLanguage?.(flowLabels);
    responses.refreshCache(); writtenPage.refreshCache();
    window.ReportDashboard?.setLabels?.(labels);
  }
  function updateAll() {
    applySnapshot(); applyLabels();
    writtenPage.setLanguage(displayLanguage());
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
  on('#respondent-language', 'change', updateAll);
  on('#display-language', 'change', updateAll);
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
