/* Page behavior; composed by report.js with shared UI dependencies. */
(function (root) {
  'use strict';
  root.ReportPages ||= {};
  root.ReportPages.responses = function ({document, searchTools, createPager, selectedSurveys}) {
    const {$, all, text, on} = root.ReportComponents.dom(document);
    const {normalize, terms, matches} = searchTools;
    const cards = all('.respondent'), choices = all('.question-choice');
    const eligible = node => Boolean(node && selectedSurveys().has(node.dataset.survey));
    const responsePager = createPager(cards, $('#response-pagination'), 20, 'responses');
  const cardCache = new Map(cards.map(card => [card, {
    metadata: [card.querySelector('.identity')?.textContent, card.querySelector('.response-meta')?.textContent,
      card.querySelector('.response-properties')?.textContent].join(' '),
    answers: [...card.querySelectorAll('.answer')].map(row => ({row, content: normalize(row.textContent)})),
  }]));
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


    return {update: updateResponses, pager: responsePager, cards, choices, cache: cardCache};
  };
})(window);
