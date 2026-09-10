/* Page behavior; composed by report.js with shared UI dependencies. */
(function (root) {
  'use strict';
  root.ReportPages ||= {};
  root.ReportPages.questions = function ({document, searchTools, selectedSurveys, surveyNames}) {
    const {$, all, text, on} = root.ReportComponents.dom(document);
    const {normalize, terms, matches} = searchTools;
    let activeQuestion = '';
    const occurrences = all('.survey-analysis.survey-occurrence');
    const eligible = node => Boolean(node && selectedSurveys().has(node.dataset.survey));
  const labelOf = node => node.dataset.label || node.dataset.question || node.querySelector('summary')?.textContent.trim() || 'Question';

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

    function reveal(node) { if ($('#question-filter')) $('#question-filter').value = ''; activeQuestion = node.id; updateQuestions(); }

    return {update: updateQuestions, reveal, occurrences, labelOf};
  };
})(window);
