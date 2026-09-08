(() => {
  'use strict';
  // The report owns shared survey state and pagination; initialize after its helpers exist.
  window.initializeCodebook = () => {
    const search = document.querySelector('#codebook-search');
    if (!search || !window.ReportUI || window.updateCodebook) return;
    const {createPager, selectedSurveys, normalize, terms, matches} = window.ReportUI;
    const rows = [...document.querySelectorAll('.codebook-row')];
    const cache = new Map(rows.map((row, index) => {
      row.id ||= `codebook-field-${index + 1}`;
      return [row, normalize([...row.cells].map(cell => cell.textContent).join(' '))];
    }));
    const download = document.querySelector('#codebook-download');
    const container = document.createElement('div');
    container.id = 'codebook-pagination';
    document.querySelector('.codebook-scroll').after(container);
    const pager = createPager(rows, container, 25, 'fields');
    window.updateCodebook = () => {
      const surveys = selectedSurveys(), query = terms(search.value);
      const filtered = rows.filter(row => surveys.has(row.dataset.survey) && matches(cache.get(row), query));
      pager.update(filtered);
      document.querySelector('#codebook-count').textContent = `${filtered.length} of ${rows.filter(row => surveys.has(row.dataset.survey)).length} fields`;
      document.querySelector('#codebook-empty').hidden = filtered.length > 0;
      download.disabled = filtered.length === 0;
    };
    window.revealCodebook = row => {
      search.value = '';
      window.updateCodebook();
      pager.reveal(row);
    };
    window.renderCodebookPage = pager.render;
    search.addEventListener('input', window.updateCodebook);
    download.addEventListener('click', () => {
      const lines = [download.dataset.header, ...pager.getFiltered().map(row => row.dataset.csv)];
      const blob = new Blob(['\ufeff' + lines.join('\r\n') + '\r\n'], {type: 'text/csv;charset=utf-8'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = 'codebook.csv';
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    window.updateCodebook();
  };
})();
