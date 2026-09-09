/* Small aggregate datasets drive the dashboard; response cards are never scanned. */
(function (root) {
  'use strict';
  const DAY = 86400000;
  const format = value => Number(value).toLocaleString();
  const dateLabel = (index, period) => period === 'month'
    ? `${String(Math.floor(index / 12)).padStart(4, '0')}-${String(index % 12 + 1).padStart(2, '0')}-01`
    : new Date((index * 7 - 3) * DAY).toISOString().slice(0, 10);

  function aggregateTimeline(surveys, period) {
    const counts = new Map();
    let undated = 0;
    for (const survey of surveys) {
      undated += survey.undated;
      for (const [date, count] of survey.dates) {
        const index = period === 'month'
          ? Number(date.slice(0, 4)) * 12 + Number(date.slice(5, 7)) - 1
          : Math.floor((Date.parse(date + 'T00:00:00Z') / DAY + 3) / 7);
        counts.set(index, (counts.get(index) || 0) + count);
      }
    }
    if (!counts.size) return {points: [], undated, step: 1};
    const indexes = [...counts.keys()], first = Math.min(...indexes), last = Math.max(...indexes);
    // Keep long exports bounded while preserving counts and zero-response gaps.
    const step = Math.max(1, Math.ceil((last - first + 1) / 260));
    const points = Array.from({length: Math.ceil((last - first + 1) / step)}, (_, offset) => {
      const start = first + offset * step, end = Math.min(last, start + step - 1);
      return {date: dateLabel(start, period), end: dateLabel(end, period), count: 0};
    });
    counts.forEach((count, index) => { points[Math.floor((index - first) / step)].count += count; });
    return {points, undated, step};
  }

  function createDashboard(document, payload) {
    const $ = id => document.getElementById('dashboard-' + id);
    const surveyNames = new Map(payload.surveys.map(s => [s.id, s.label]));
    let selected = new Set(), available = [];
    const node = (tag, className = '', content) => {
      const element = document.createElement(tag);
      if (className) element.className = className;
      if (content !== undefined) element.textContent = content;
      return element;
    };
    const empty = (target, message) => target.replaceChildren(node('p', 'dashboard-chart-empty', message));
    const link = (label, target) => { const element = node('a', '', label); element.href = '#' + target; return element; };
    const percent = (n, total) => total ? Math.round(n / total * 100) : 0;
    const svgNode = (tag, attributes = {}, content) => {
      const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
      Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
      if (content !== undefined) element.textContent = content;
      return element;
    };

    function renderTimeline() {
      const period = $('period').value || 'week';
      const series = aggregateTimeline(payload.surveys.filter(s => selected.has(s.id)), period);
      const {points, undated, step} = series;
      const total = points.reduce((sum, p) => sum + p.count, 0);
      $('date-note').textContent = `${format(total)} dated responses · ${format(undated)} with missing or invalid recorded dates excluded. Dates follow the export's calendar dates.`
        + (step > 1 ? ` Each point groups up to ${step} ${period}s.` : '');
      const table = $('timeline-table'); table.replaceChildren();
      const head = node('thead'), heading = node('tr'), body = node('tbody');
      for (const label of [period === 'month' ? 'Month starting' : 'Week starting Monday', 'Responses']) {
        const th = node('th', '', label); th.setAttribute('scope', 'col'); heading.append(th);
      }
      head.append(heading); table.append(head, body);
      for (const p of points) {
        const row = node('tr');
        row.append(node('td', '', p.date + (step > 1 ? ' – ' + p.end : '')), node('td', '', format(p.count)));
        body.append(row);
      }
      if (!points.length) { empty($('timeline'), 'No dated responses in the selected surveys.'); return; }
      const width = Math.max(320, Math.min(700, $('timeline').clientWidth || 700));
      const left = 46, right = width - 14, top = 16, bottom = 184;
      const max = Math.max(4, Math.ceil(Math.max(...points.map(p => p.count)) / 4) * 4);
      const x = i => points.length === 1 ? (left + right) / 2 : left + i / (points.length - 1) * (right - left);
      const y = count => bottom - count / max * (bottom - top);
      const svg = svgNode('svg', {viewBox: `0 0 ${width} 220`, role: 'img', 'aria-label': `${format(total)} recorded responses by ${period}. Exact counts are in the table below.`});
      for (let tick = 0; tick <= 4; tick++) {
        const value = max * tick / 4;
        svg.append(svgNode('line', {x1: left, x2: right, y1: y(value), y2: y(value), class: 'dashboard-gridline'}));
        svg.append(svgNode('text', {x: left - 8, y: y(value) + 4, 'text-anchor': 'end', class: 'dashboard-axis-label'}, format(value)));
      }
      const coordinates = points.map((p, i) => `${x(i)},${y(p.count)}`).join(' L');
      svg.append(svgNode('path', {d: `M${x(0)},${bottom} L${coordinates} L${x(points.length - 1)},${bottom} Z`, class: 'dashboard-area'}));
      svg.append(svgNode('path', {d: 'M' + coordinates, class: 'dashboard-line'}));
      points.forEach((p, i) => {
        if (!p.count) return;
        const dot = svgNode('circle', {cx: x(i), cy: y(p.count), r: points.length > 60 ? 2 : 3, class: 'dashboard-dot'});
        dot.append(svgNode('title', {}, `${p.date}${step > 1 ? ' – ' + p.end : ''}: ${format(p.count)} responses`));
        svg.append(dot);
      });
      const tickCount = width < 450 ? 3 : 5;
      const ticks = new Set(Array.from({length: tickCount}, (_, i) => Math.round(i * (points.length - 1) / (tickCount - 1))));
      for (const i of ticks) {
        const label = period === 'month' ? points[i].date.slice(0, 7) : points[i].date;
        svg.append(svgNode('text', {x: x(i), y: 210, 'text-anchor': i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle', class: 'dashboard-axis-label'}, label));
      }
      $('timeline').replaceChildren(svg);
    }

    function renderSurveys() {
      const target = $('surveys'); target.replaceChildren();
      const surveys = payload.surveys.filter(s => selected.has(s.id)).sort((a, b) => b.responses - a.responses);
      if (!surveys.length) { empty(target, 'No surveys selected.'); return; }
      const maximum = Math.max(1, ...surveys.map(s => s.responses));
      for (const survey of surveys) {
        const row = node('div', 'dashboard-bar-row');
        const track = node('div', 'dashboard-bar-track'); track.setAttribute('aria-hidden', 'true');
        const finished = node('span', 'dashboard-bar-finished'), other = node('span', 'dashboard-bar-other');
        finished.style.width = `${survey.finished / maximum * 100}%`;
        other.style.width = `${(survey.responses - survey.finished) / maximum * 100}%`;
        track.append(finished, other);
        row.append(node('strong', '', survey.label), track,
          node('span', 'dashboard-bar-value', `${format(survey.responses)} · ${percent(survey.finished, survey.responses)}% finished`));
        row.append(node('small', 'meta', `${format(survey.finished)} finished · ${format(survey.responses - survey.finished)} not marked finished`));
        target.append(row);
      }
    }

    function renderSpotlight(index) {
      const select = $('question-' + index), target = $('spotlight-' + index);
      const item = available.find(s => s.id === select.value);
      if (!item) { empty(target, available.length ? 'No question selected.' : 'No numeric or choice answers in the selected surveys.'); return; }
      target.replaceChildren();
      const title = node('h4'); title.append(link(item.label, item.target));
      target.append(title, node('p', 'meta', [surveyNames.get(item.survey), item.field, item.kind === 'nps' ? 'NPS score distribution' : item.kind === 'numeric' ? 'Numeric distribution' : 'Answer choices'].filter(Boolean).join(' · ')));
      if (item.metric) {
        const metric = node('p', 'dashboard-metric');
        metric.append(node('strong', '', item.metric.value), node('span', '', item.metric.label)); target.append(metric);
      }
      const bins = item.bins.length > 12 ? [...item.bins].sort((a, b) => b.count - a.count).slice(0, 12) : item.bins;
      for (const bin of bins) {
        const row = node('div', 'distribution-row');
        const label = node('span', '', bin.label); label.setAttribute('title', bin.label);
        const bar = node('div', 'distribution-bar'); bar.setAttribute('aria-hidden', 'true');
        const fill = node('i'); fill.style.width = `${Math.min(100, item.denominator ? bin.count / item.denominator * 100 : 0)}%`; bar.append(fill);
        row.append(label, bar, node('b', '', format(bin.count)), node('small', '', `${percent(bin.count, item.denominator)}%`));
        target.append(row);
      }
      target.append(node('p', 'dashboard-chart-note meta', item.note));
      if (item.bins.length > bins.length) target.append(node('p', 'meta', `Showing the 12 most selected of ${item.bins.length} options. All options are in question details.`));
      target.append(link('Open question details', item.target));
    }

    function updateSpotlights() {
      available = payload.spotlights.filter(s => selected.has(s.survey));
      let previous = null;
      for (const index of [1, 2]) {
        const select = $('question-' + index), current = select.value;
        let choice = available.find(s => s.id === current);
        if (!choice) choice = index === 1 ? available[0]
          : available.find(s => s.id !== previous?.id && s.kind !== previous?.kind)
            || available.find(s => s.target !== previous?.target) || available.find(s => s.id !== previous?.id);
        select.replaceChildren();
        const placeholder = node('option', '', 'Choose a question'); placeholder.value = ''; select.append(placeholder);
        for (const item of available) {
          const option = node('option', '', [surveyNames.get(item.survey), item.label, item.field].filter(Boolean).join(' · '));
          option.value = item.id; select.append(option);
        }
        select.value = choice?.id || ''; select.disabled = !available.length;
        previous = choice; renderSpotlight(index);
      }
    }

    function renderCoverage() {
      const rows = payload.coverage.filter(q => selected.has(q.survey) && q.total > 0)
        .sort((a, b) => a.answered / a.total - b.answered / b.total);
      const target = $('coverage'); target.replaceChildren();
      if (!rows.length) { empty(target, 'No recorded responses for question coverage.'); return; }
      for (const item of rows.slice(0, 8)) {
        const row = node('div', 'dashboard-bar-row');
        const label = link(item.label, item.target);
        const track = node('div', 'dashboard-bar-track'); track.setAttribute('aria-hidden', 'true');
        const fill = node('span', 'dashboard-bar-finished'); fill.style.width = `${item.answered / item.total * 100}%`; track.append(fill);
        row.append(label, track, node('span', 'dashboard-bar-value', `${format(item.answered)} / ${format(item.total)} · ${percent(item.answered, item.total)}%`),
          node('small', 'meta', surveyNames.get(item.survey)));
        target.append(row);
      }
      const note = node('p', 'dashboard-chart-note meta', `Showing ${Math.min(8, rows.length)} of ${format(rows.length)} questions, ordered by recorded answer share. `);
      note.append(link('See all question coverage', 'question-coverage')); target.append(note);
    }

    $('period').addEventListener('change', renderTimeline);
    for (const index of [1, 2]) $('question-' + index).addEventListener('change', () => renderSpotlight(index));
    return {
      update(surveyIds) { selected = new Set(surveyIds); renderTimeline(); renderSurveys(); updateSpotlights(); renderCoverage(); },
      resize: renderTimeline,
    };
  }

  const api = {aggregateTimeline, createDashboard};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else {
    const data = root.document.getElementById('dashboard-data');
    if (data) {
      root.ReportDashboard = createDashboard(root.document, JSON.parse(data.textContent));
      root.addEventListener('resize', () => root.ReportDashboard.resize());
    }
  }
})(typeof window === 'undefined' ? globalThis : window);
