/* Page behavior; composed by report.js with shared UI dependencies. */
(function (root) {
  'use strict';
  root.ReportPages ||= {};
  root.ReportPages.written = function ({document, searchTools, createPager, selectedSurveys, surveyNames}) {
    const {$, all, text, on} = root.ReportComponents.dom(document);
    const {normalize, terms, matches} = searchTools;
    const written = all('.written-answer');
    const translations = JSON.parse($('#written-translation-data')?.textContent || '{}');
    const originals = new Map(written.map(node => [node, node.querySelector('.written-value')?.textContent || '']));
    const eligible = node => Boolean(node && selectedSurveys().has(node.dataset.survey)
      && ((root.ReportUI?.respondentLanguage?.() || 'all') === 'all'
        || node.dataset.userLanguage === root.ReportUI.respondentLanguage()));
    const writtenPager = createPager(written, $('#written-pagination'), 20, 'written answers');
  const writtenCache = new Map(written.map(node => [node, normalize(node.textContent)]));
  function refreshCache() { written.forEach(node => writtenCache.set(node, normalize(node.textContent))); }

  function setLanguage(target) {
    written.forEach(node => {
      const value = node.querySelector('.written-value');
      const cue = node.querySelector('.translation-cue');
      const original = node.querySelector('.written-original');
      if (!value || !cue || !original) return;
      const source = node.dataset.userLanguage;
      const requested = Boolean(target && target !== source);
      const prepared = translations[node.dataset.answerId]?.[target];
      const current = requested && prepared?.current && typeof prepared.text === 'string';
      value.textContent = current ? prepared.text : originals.get(node);
      value.lang = current ? target : source === '__missing__' ? '' : source || '';
      original.hidden = !current;
      if (!current) original.open = false;
      cue.hidden = !requested || current;
      cue.textContent = prepared && !prepared.current
        ? 'Translation out of date · showing original'
        : 'Translation unavailable · showing original';
      node.dataset.translationStatus = current ? 'translated' : requested ? prepared ? 'stale' : 'missing' : 'original';
    });
    refreshCache();
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


    return {update: updateWritten, pager: writtenPager, items: written, refreshCache, setLanguage};
  };
})(window);
