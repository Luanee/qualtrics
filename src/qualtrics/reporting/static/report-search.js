/* Pure search helpers shared by the offline report and its Node tests. */
(function (root) {
  'use strict';
  const normalize = value => String(value ?? '').normalize('NFKD')
    .replace(/\p{M}/gu, '').toLowerCase().replace(/ß/g, 'ss').replace(/ς/g, 'σ');
  const terms = value => [...new Set(normalize(value).trim().split(/\s+/u).filter(Boolean))];
  const matches = (normalized, query) => query.every(term => normalized.includes(term));

  // Keep a mapping back to original UTF-16 positions: folds may change length.
  function excerpt(value, query, limit = 200) {
    const original = String(value ?? '');
    let folded = '', offset = 0;
    const starts = [], ends = [];
    for (const character of original) {
      const part = normalize(character);
      for (let i = 0; i < part.length; i++) {
        starts.push(offset);
        ends.push(offset + character.length);
      }
      if (!part && ends.length) ends[ends.length - 1] = offset + character.length;
      folded += part;
      offset += character.length;
    }
    const ranges = [];
    for (const term of query) {
      if (!term) continue;
      let index = folded.indexOf(term);
      while (index !== -1) {
        ranges.push([starts[index], ends[index + term.length - 1]]);
        index = folded.indexOf(term, index + term.length);
      }
    }
    ranges.sort((a, b) => a[0] - b[0]);
    const beginning = Math.max(0, (ranges[0]?.[0] || 0) - 65);
    const ending = Math.min(original.length, beginning + limit);
    const merged = [];
    for (const [start, end] of ranges) {
      if (start >= ending || end <= beginning) continue;
      const prior = merged[merged.length - 1];
      if (prior && start <= prior[1]) prior[1] = Math.max(prior[1], Math.min(end, ending));
      else merged.push([Math.max(start, beginning), Math.min(end, ending)]);
    }
    const result = [];
    let cursor = beginning;
    if (beginning) result.push({text: '…', match: false});
    for (const [start, end] of merged) {
      if (start > cursor) result.push({text: original.slice(cursor, start), match: false});
      result.push({text: original.slice(start, end), match: true});
      cursor = end;
    }
    if (cursor < ending) result.push({text: original.slice(cursor, ending), match: false});
    if (ending < original.length) result.push({text: '…', match: false});
    return result;
  }
  const api = {normalize, terms, matches, excerpt};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ReportSearch = api;
})(typeof window === 'undefined' ? globalThis : window);
