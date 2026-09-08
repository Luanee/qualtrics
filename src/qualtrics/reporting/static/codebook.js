(() => {
  const search = document.querySelector('#codebook-search');
  if (!search) return;
  const rows = [...document.querySelectorAll('.codebook-row')];
  const download = document.querySelector('#codebook-download');
  window.updateCodebook = () => {
    const surveys = new Set([...document.querySelectorAll('.survey-choice:checked')].map(input => input.value));
    const term = search.value.trim().toLowerCase();
    rows.forEach(row => {
      row.hidden = !surveys.has(row.dataset.survey) || !row.dataset.search.includes(term);
    });
    const visible = rows.filter(row => !row.hidden).length;
    document.querySelector('#codebook-count').textContent = `${visible} of ${rows.length} fields`;
    document.querySelector('#codebook-empty').hidden = visible > 0;
    download.disabled = visible === 0;
  };
  search.addEventListener('input', window.updateCodebook);
  document.querySelector("a[href='#codebook']").addEventListener('click', () => {
    document.querySelector('#codebook').open = true;
  });
  download.addEventListener('click', () => {
    const lines = [download.dataset.header, ...rows.filter(row => !row.hidden).map(row => row.dataset.csv)];
    const blob = new Blob(['\ufeff' + lines.join('\r\n') + '\r\n'], {type: 'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'codebook.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  window.updateCodebook();
})();
