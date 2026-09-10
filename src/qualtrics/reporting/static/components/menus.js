/* Disclosure menus shared by survey and question filters. */
(function (root) {
  root.ReportComponents.initializeMenus = document => {
    const {$, all, text, on} = root.ReportComponents.dom(document);
  const menus = [['#question-toggle', '#question-menu'], ['#survey-toggle', '#survey-menu']];
  function closeMenus() { menus.forEach(([toggle, menu]) => { if ($(menu)) $(menu).hidden = true; $(toggle)?.setAttribute('aria-expanded', 'false'); }); }
  menus.forEach(([toggle, menu]) => {
    on(toggle, 'click', event => { event.stopPropagation(); const opening = $(menu).hidden; closeMenus(); $(menu).hidden = !opening; $(toggle).setAttribute('aria-expanded', String(opening)); });
    on(menu, 'click', event => event.stopPropagation());
  });
  document.addEventListener('click', closeMenus);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenus(); });
  };
})(window);
