import { html, mount } from '../dom.js';
import { decimal, integer, longDate, percent, points, signedPercent } from '../format.js';

// Tone answers "is this good for the client?": lower turnover is better, higher return is better.
export function deltaBadge(difference, { better, format }) {
  const improved = better === 'higher' ? difference > 0 : difference < 0;
  const tone = Math.abs(difference) < 1e-12 ? 'is-neutral' : improved ? 'is-better' : 'is-worse';
  return html`<span class="delta ${tone}">${format(difference)}</span>`;
}

const tile = ({ label, value, foot }) => html`
  <article class="card kpi">
    <span class="kpi-label">${label}</span>
    <span class="kpi-value num">${value}</span>
    <span class="kpi-foot">${foot}</span>
  </article>`;

export function renderKpisLoading(element) {
  mount(element, Array.from({ length: 4 }, () => html`
    <article class="card kpi">
      <span class="skeleton" style="height: 14px; width: 45%"></span>
      <span class="skeleton" style="height: 28px; width: 60%"></span>
      <span class="skeleton" style="height: 14px; width: 80%"></span>
    </article>`));
}

export function renderKpis(element, { stabilised: s, raw: r }, run) {
  mount(element, [
    tile({
      label: 'Index level · stabilised',
      value: decimal(s.final_level),
      foot: html`${deltaBadge(s.gross_return, { better: 'higher', format: signedPercent })} since ${longDate(run.first_date)}`,
    }),
    tile({
      label: 'Net return after est. costs',
      value: signedPercent(s.net_return),
      foot: html`${deltaBadge(s.net_return - r.net_return, { better: 'higher', format: points })} vs unstabilised`,
    }),
    tile({
      label: 'Avg one-way turnover per rebalance',
      value: percent(s.avg_turnover),
      foot: html`${deltaBadge(s.avg_turnover / r.avg_turnover - 1, { better: 'lower', format: (x) => signedPercent(x, 0) })}
        vs ${percent(r.avg_turnover)} unstabilised`,
    }),
    tile({
      label: 'Names added',
      value: integer(s.names_added),
      foot: html`${deltaBadge(s.names_added - r.names_added, { better: 'lower', format: (x) => `${x > 0 ? '+' : '−'}${integer(Math.abs(x))}` })}
        vs ${integer(r.names_added)} · ${integer(s.reentries)} re-entries vs ${integer(r.reentries)}`,
    }),
  ]);
}
