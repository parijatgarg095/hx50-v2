import { html, mount } from '../dom.js';
import { decimal, integer, percent, points, signedDecimal, signedInteger, signedPercent } from '../format.js';
import { deltaBadge } from './kpis.js';

// How each metric's difference is expressed: relative change for turnover, percentage points for returns.
const COMPARE = {
  relative: (s, r) => (r === 0 ? 0 : s / r - 1),
  difference: (s, r) => s - r,
};

function sections(mandate) {
  return [
    {
      title: 'Trading',
      rows: [
        { label: 'Rebalances', key: 'rebalances', format: integer },
        { label: 'Avg one-way turnover', key: 'avg_turnover', format: percent, better: 'lower', compare: 'relative', delta: (x) => signedPercent(x, 0) },
        { label: 'Total one-way turnover', key: 'total_turnover', format: percent, better: 'lower', compare: 'relative', delta: (x) => signedPercent(x, 0) },
        { label: 'Membership changes', key: 'membership_turnover', format: percent, better: 'lower', compare: 'relative', delta: (x) => signedPercent(x, 0), indent: true },
        { label: `Reweighting to ${percent(1 / mandate.size)}`, key: 'reweight_turnover', format: percent, better: 'lower', compare: 'relative', delta: (x) => signedPercent(x, 0), indent: true },
      ],
    },
    {
      title: 'Churn',
      rows: [
        { label: 'Names added', key: 'names_added', format: integer, better: 'lower', compare: 'difference', delta: signedInteger },
        { label: 'Names dropped', key: 'names_dropped', format: integer, better: 'lower', compare: 'difference', delta: signedInteger },
        { label: `Re-entries within ${mandate.reentry_window} rebalances`, key: 'reentries', format: integer, better: 'lower', compare: 'difference', delta: signedInteger },
      ],
    },
    {
      title: 'Return',
      rows: [
        { label: 'Cumulative return (gross)', key: 'gross_return', format: percent, better: 'higher', compare: 'difference', delta: points },
        { label: 'Est. cost drag', key: 'cost_drag', format: percent, better: 'lower', compare: 'difference', delta: points,
          hint: `2 × total one-way turnover × ${mandate.cost_bps} bps per side` },
        { label: 'Cumulative return (net)', key: 'net_return', format: percent, better: 'higher', compare: 'difference', delta: points },
        { label: 'Final level', key: 'final_level', format: decimal, better: 'higher', compare: 'difference', delta: signedDecimal },
      ],
    },
  ];
}

function row(metric, s, r) {
  const delta = metric.compare
    ? deltaBadge(COMPARE[metric.compare](s[metric.key], r[metric.key]), { better: metric.better, format: metric.delta })
    : html`<span class="subtle">—</span>`;
  return html`
    <tr title="${metric.hint ?? ''}">
      <td class="${metric.indent ? 'indent' : ''}">${metric.label}${metric.hint ? html` <span class="subtle">ⓘ</span>` : ''}</td>
      <td class="r num">${metric.format(s[metric.key])}</td>
      <td class="r num muted">${metric.format(r[metric.key])}</td>
      <td class="r">${delta}</td>
    </tr>`;
}

export function renderScorecard(table, { stabilised, raw }, mandate) {
  mount(table, html`
    <thead><tr><th>Metric</th><th class="r">Stabilised</th><th class="r">Unstabilised</th><th class="r">Δ</th></tr></thead>
    <tbody>
      ${sections(mandate).map((section) => html`
        <tr class="group"><td colspan="4">${section.title}</td></tr>
        ${section.rows.map((metric) => row(metric, stabilised, raw))}`)}
    </tbody>`);
}
