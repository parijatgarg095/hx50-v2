import { html, mount } from '../dom.js';
import { integer, percent, plural, shortDate, signedPercent } from '../format.js';

const COLUMNS = [
  { key: 'position', label: '#', align: '' },
  { key: 'ticker', label: 'Ticker', align: '', sortable: true },
  { key: 'weight', label: 'Weight', align: 'r', sortable: true },
  { key: 'drift', label: 'vs equal', align: 'r', sortable: true },
  { key: 'market_cap_rank', label: 'Mkt-cap rank', align: 'r', sortable: true },
];

const compare = {
  ticker: (a, b) => a.ticker.localeCompare(b.ticker),
  weight: (a, b) => a.weight - b.weight,
  drift: (a, b) => a.drift - b.drift,
  market_cap_rank: (a, b) => (a.market_cap_rank ?? Infinity) - (b.market_cap_rank ?? Infinity),
};

// Below 0.005% drift is rounding noise on a rebalance day, not a real move.
const driftTone = (drift) => (drift > 5e-5 ? 'is-up' : drift < -5e-5 ? 'is-down' : '');

const heldViaBuffer = (rank, mandate) => rank != null && (rank > mandate.last_rank || rank < mandate.first_rank);

// A rank outside the entry band means the name is held only because the retention buffer kept it.
function rankBadge(rank, mandate) {
  if (rank == null) return html`<span class="badge is-neutral" title="No price on this date">no price</span>`;
  if (rank > mandate.last_rank) return html`<span class="badge is-caution" title="Held via retention buffer">buffer</span>`;
  if (rank < mandate.first_rank) return html`<span class="badge is-caution" title="Held via top-edge buffer">top edge</span>`;
  return '';
}

function statusLine(composition, calendar, visible, buffered) {
  const parts = [];
  if (composition.requested !== composition.as_of) {
    parts.push(html`<span class="badge is-neutral">${shortDate(composition.requested)} is not a trading day</span>`);
  }
  if (composition.rebalance_day) {
    parts.push(html`<span class="badge is-accent">Rebalance day</span>
      <span>weights reset to ${percent(1 / composition.count)} each</span>`);
  } else {
    const sessions = calendar.indexOf(composition.as_of) - calendar.indexOf(composition.last_rebalance);
    parts.push(html`<span>Drifted ${plural(sessions, 'session')} since the ${shortDate(composition.last_rebalance)} rebalance</span>`);
  }
  parts.push(html`<span class="subtle">·</span><span class="num">${composition.count} names · Σ ${percent(composition.weight_sum)}</span>`);
  if (buffered) parts.push(html`<span class="subtle">·</span><span>${plural(buffered, 'name')} held via buffer</span>`);
  if (visible !== composition.count) parts.push(html`<span class="subtle">·</span><span>${visible} shown</span>`);
  return parts;
}

export function createHoldingsView({ table, status, onSort }) {
  table.addEventListener('click', (event) => {
    const header = event.target.closest('th[data-sort]');
    if (header) onSort(header.dataset.sort);
  });

  function render({ composition, mandate, calendar, filter, sort }) {
    const equal = 1 / composition.count;
    const enriched = composition.holdings.map((h) => ({ ...h, drift: h.weight / equal - 1 }));
    const needle = filter.trim().toUpperCase();
    const direction = sort.direction === 'asc' ? 1 : -1;
    const rows = enriched
      .filter((h) => !needle || h.ticker.includes(needle))
      .sort((a, b) => direction * compare[sort.key](a, b) || a.ticker.localeCompare(b.ticker));
    const maxDrift = Math.max(...enriched.map((h) => Math.abs(h.drift)), 1e-9);
    const buffered = enriched.filter((h) => heldViaBuffer(h.market_cap_rank, mandate)).length;

    mount(status, statusLine(composition, calendar, rows.length, buffered));
    mount(table, html`
      <thead><tr>${COLUMNS.map((c) => html`
        <th class="${c.align} ${c.sortable ? 'sortable' : ''}" ${c.sortable ? html`data-sort="${c.key}"` : ''}
            aria-sort="${sort.key === c.key ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}">${c.label}</th>`)}
      </tr></thead>
      <tbody>${rows.length ? rows.map((h, i) => html`
        <tr>
          <td class="subtle num">${i + 1}</td>
          <td class="ticker">${h.ticker}</td>
          <td class="r num">${percent(h.weight)}</td>
          <td class="r"><div class="drift-cell">
            <span class="drift-bar" aria-hidden="true">
              <span class="${h.drift >= 0 ? 'is-up' : 'is-down'}" style="width: ${(Math.abs(h.drift) / maxDrift) * 50}%"></span>
            </span>
            <span class="num drift drift-value ${driftTone(h.drift)}">${signedPercent(h.drift, 1)}</span></div></td>
          <td class="r num">${rankBadge(h.market_cap_rank, mandate)} ${h.market_cap_rank == null ? '—' : integer(h.market_cap_rank)}</td>
        </tr>`) : html`<tr><td colspan="5" class="empty">No tickers match “${filter}”</td></tr>`}
      </tbody>`);
  }

  return { render };
}
