/* Shared, document-scoped DOM helpers. */
(function (root) {
  'use strict';
  root.ReportComponents ||= {};
  root.ReportComponents.dom = document => {
    const $ = selector => document.querySelector(selector);
    const all = selector => [...document.querySelectorAll(selector)];
    const text = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
    const on = (selector, event, callback) => $(selector)?.addEventListener(event, callback);
    return {$, all, text, on};
  };
})(window);
