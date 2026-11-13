import { html, mount } from '../dom.js';
import { longDate, percent } from '../format.js';

const chips = (tickers, kind) =>
  tickers.length
    ? html`<div class="chips">${tickers.map((t) => html`<span class="chip is-${kind}">${t}</span>`)}</div>`
    : html`<span class="subtle">—</span>`;

function turnoverCell(r, scale) {
  const width = (x) => `${(x / scale) * 100}%`;
  return html`
    <div class="turnover-cell">
      <span class="num"><strong>${percent(r.turnover)}</strong></span>
      <span class="turnover-bar" aria-hidden="true">
        <span class="membership" style="width: ${width(r.membership_turnover)}"></span>
        <span class="reweight" style="width: ${width(r.reweight_turnover)}"></span>
      </span>
      <span class="subtle num" style="font-size: 11.5px">${percent(r.membership_turnover)} · ${percent(r.reweight_turnover)}</span>
    </div>`;
}

export function createRebalancesView({ table, onSelectDate }) {
  table.addEventListener('click', (event) => {
    const row = event.target.closest('tr[data-date]');
    if (row) onSelectDate(row.dataset.date);
  });

  function render(rebalances) {
    const periodic = rebalances.filter((r) => !r.initial);
    const scale = Math.max(...periodic.map((r) => r.turnover), 1e-9);
    const newestFirst = [...rebalances].reverse();

    mount(table, html`
      <thead><tr><th>Date</th><th class="r">One-way turnover</th><th>Added</th><th>Dropped</th></tr></thead>
      <tbody>${newestFirst.map((r) => html`
        <tr class="is-link" data-date="${r.date}" title="Show holdings after this rebalance">
          <td class="num" style="white-space: nowrap">${longDate(r.date)}</td>
          ${r.initial
            ? html`<td class="r"><span class="badge is-accent">Initial construction</span></td>
                   <td colspan="2" class="muted">${r.added.length} names bought at equal weight</td>`
            : html`<td class="r">${turnoverCell(r, scale)}</td><td>${chips(r.added, 'added')}</td><td>${chips(r.dropped, 'dropped')}</td>`}
        </tr>`)}
      </tbody>`);
  }

  return { render };
}
