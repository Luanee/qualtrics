/* Page behavior; composed by report.js with shared UI dependencies. */
(function (root) {
  'use strict';
  root.ReportPages ||= {};
  root.ReportPages.written = function ({document, searchTools, createPager, selectedSurveys, surveyNames}) {
    const {$, all, text, on} = root.ReportComponents.dom(document);
    const {normalize, terms, matches} = searchTools;
    const written = all('.written-answer');
    const eligible = node => Boolean(node && selectedSurveys().has(node.dataset.survey));
    const writtenPager = createPager(written, $('#written-pagination'), 20, 'written answers');
  const writtenCache = new Map(written.map(node => [node, normalize(node.textContent)]));

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


    return {update: updateWritten, pager: writtenPager, items: written};
  };
})(window);
