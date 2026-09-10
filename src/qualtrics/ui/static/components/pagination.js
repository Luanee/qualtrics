/* Shared paging keeps filtering independent of on-screen and print visibility. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else Object.assign(root.ReportComponents ||= {}, api);
})(typeof window === 'object' ? window : globalThis, function () {
  function renderPagination(document, container, {page, size, total, noun, hidden = false, onPage}) {
    if (!container) return;
    container.replaceChildren();
    container.hidden = hidden || total === 0;
    const previous = document.createElement('button'), next = document.createElement('button');
    previous.type = next.type = 'button';
    previous.textContent = 'Previous'; next.textContent = 'Next';
    previous.disabled = page === 1; next.disabled = page * size >= total;
    previous.setAttribute('aria-label', `Previous ${noun} page`);
    next.setAttribute('aria-label', `Next ${noun} page`);
    previous.onclick = () => onPage(page - 1);
    next.onclick = () => onPage(page + 1);
    const range = document.createElement('span');
    range.setAttribute('aria-live', 'polite');
    range.textContent = `${total ? (page - 1) * size + 1 : 0}–${Math.min(page * size, total)} of ${total} ${noun}`;
    container.append(previous, range, next);
  }
  function createPagerFactory(document, isPrinting = () => false) {
    // Pagination retains the full filtered collection separately from screen visibility.
    function createPager(nodes, container, size, noun) {
      let filtered = [], page = 1;
      if (container) container.classList.add('pagination');
      function render() {
        page = Math.max(1, Math.min(page, Math.ceil(filtered.length / size) || 1));
        const displayed = new Set(isPrinting() ? filtered : filtered.slice((page - 1) * size, page * size));
        nodes.forEach(node => { node.hidden = !displayed.has(node); });
        if (!container) return;
        renderPagination(document, container, {
          page, size, total: filtered.length, noun, hidden: isPrinting(),
          onPage(next) { page = next; render(); },
        });
      }
      return {
        update(items, reset = true) { filtered = items; if (reset) page = 1; render(); },
        reveal(node) { const index = filtered.indexOf(node); if (index >= 0) page = Math.floor(index / size) + 1; render(); },
        render, getFiltered: () => filtered,
      };
    }
    return createPager;
  }
  return {createPagerFactory, renderPagination};
});
