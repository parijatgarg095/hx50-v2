import { byId, html, mount } from '../dom.js';
import { decimal, longDate, shortDate, signedDecimal, signedPercent } from '../format.js';

const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// Canvas colour parsing does not understand color-mix(), so tokens (hex) are converted to rgba here.
function rgba(hex, alpha) {
  const value = parseInt(hex.replace('#', ''), 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
}

function areaFill(color) {
  return ({ chart }) => {
    const { ctx, chartArea } = chart;
    if (!chartArea) return 'transparent';
    const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    gradient.addColorStop(0, rgba(color, 0.16));
    gradient.addColorStop(1, rgba(color, 0));
    return gradient;
  };
}

function renderLegend(stabilised, raw) {
  const last = (series) => series.at(-1);
  mount(byId('chart-legend'), html`
    <span class="legend-item"><span class="swatch" style="border-color: var(--series-stabilised)"></span>
      Stabilised <strong class="num">${decimal(last(stabilised).level)}</strong>
      <span class="num">${signedPercent(last(stabilised).cumulative_return)}</span></span>
    <span class="legend-item"><span class="swatch is-dashed" style="border-color: var(--series-raw)"></span>
      Unstabilised <strong class="num">${decimal(last(raw).level)}</strong>
      <span class="num">${signedPercent(last(raw).cumulative_return)}</span></span>`);
}

export function createLevelChart(canvas) {
  let chart = null;
  let latest = null;

  function render(stabilised, raw, range) {
    latest = { stabilised, raw, range };
    const window = (series) => (range === 'all' ? series : series.slice(-Number(range)));
    const [a, b] = [window(stabilised), window(raw)];
    const colors = { a: token('--series-stabilised'), b: token('--series-raw'), grid: token('--border'), text: token('--text-subtle') };

    renderLegend(stabilised, raw);
    chart?.destroy();
    chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: a.map((p) => p.date),
        datasets: [
          { label: 'Stabilised', data: a.map((p) => p.level), borderColor: colors.a, backgroundColor: areaFill(colors.a),
            fill: true, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.15 },
          { label: 'Unstabilised', data: b.map((p) => p.level), borderColor: colors.b, borderDash: [5, 4],
            borderWidth: 1.6, pointRadius: 0, pointHoverRadius: 4, tension: 0.15 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 250 },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            padding: 10, boxPadding: 4, usePointStyle: true,
            callbacks: {
              title: ([item]) => longDate(item.label),
              label: (item) => ` ${item.dataset.label}  ${decimal(item.parsed.y)}`,
              footer: ([item]) => {
                const i = item.dataIndex;
                const spread = `Spread ${signedDecimal(a[i].level - b[i].level)}`;
                return a[i].rebalanced ? [spread, 'Rebalance day'] : spread;
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false }, border: { color: colors.grid },
               ticks: { color: colors.text, maxTicksLimit: 8, maxRotation: 0, callback(v) { return shortDate(this.getLabelForValue(v)); } } },
          y: { grid: { color: colors.grid }, border: { display: false },
               ticks: { color: colors.text, callback: (v) => decimal(v, 0) } },
        },
      },
    });
  }

  // Colours come from CSS tokens, so a theme switch must redraw the canvas.
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (latest) render(latest.stabilised, latest.raw, latest.range);
  });

  return { render };
}
