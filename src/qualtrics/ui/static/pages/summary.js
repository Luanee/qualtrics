/* Page behavior; composed by report.js with shared UI dependencies. */
(function (root) {
  'use strict';
  root.ReportPages ||= {};
  root.ReportPages.summary = function ({document, selectedSurveys, isPrinting}) {
    const {$, all, text, on} = root.ReportComponents.dom(document);
    let showAllFindings = false;
    const surveyChoices = all('.survey-choice');
    const eligible = node => Boolean(node && selectedSurveys().has(node.dataset.survey));
  const findings = all('.finding');
  const findingsMore = document.createElement('button');
  findingsMore.id = 'findings-more'; findingsMore.type = 'button';
  $('.findings')?.after(findingsMore);
  function updateFindings() {
    const selected = findings.filter(eligible);
    const displayed = new Set(isPrinting() || showAllFindings ? selected : selected.slice(0, 5));
    findings.forEach(node => { node.hidden = !displayed.has(node); });
    findingsMore.hidden = isPrinting() || selected.length <= 5;
    findingsMore.textContent = showAllFindings ? 'Show fewer highlights' : `Show all ${selected.length} highlights`;
    findingsMore.setAttribute('aria-expanded', String(showAllFindings));
    if ($('#findings-empty')) $('#findings-empty').hidden = selected.length > 0;
  }
  findingsMore.addEventListener('click', () => { showAllFindings = !showAllFindings; updateFindings(); });

  function updateSurveySummary() {
    const surveys = selectedSurveys();
    window.ReportDashboard?.update(surveys);
    window.ReportFlow?.update(surveys);
    const names = ['responses', 'finished', 'questions', 'answers', 'unanswered', 'unusedFields'];
    const totals = Object.fromEntries(names.map(name => [name, 0]));
    surveyChoices.filter(choice => choice.checked).forEach(choice => names.forEach(name => { totals[name] += Number(choice.dataset[name] || 0); }));
    text('#survey-selected-count', surveys.size === surveyChoices.length ? 'All' : surveys.size ? `${surveys.size} selected` : 'None');
    ['responses', 'questions', 'answers'].forEach(name => text('#stat-' + name, totals[name].toLocaleString()));
    text('#overview-finished', totals.finished.toLocaleString());
    text('#overview-other', (totals.responses - totals.finished).toLocaleString());
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


    return {update: updateSurveySummary, updateFindings};
  };
})(window);
