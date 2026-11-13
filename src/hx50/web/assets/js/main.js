// Controller: owns UI state, fetches through the API client and hands plain data to the views.
// Views never fetch and never hold state, so each one can be read in isolation.
import { api } from './api.js';
import { byId, html, mount, setPressed } from './dom.js';
import { longDate, relativeTime } from './format.js';
import { createLevelChart } from './views/chart.js';
import { createHoldingsView } from './views/holdings.js';
import { renderKpis, renderKpisLoading } from './views/kpis.js';
import { createMandateDialog } from './views/mandate.js';
import { createRebalancesView } from './views/rebalances.js';
import { renderScorecard } from './views/scorecard.js';
import { toast } from './views/toast.js';

const state = {
  variant: 'stabilised',
  tab: 'holdings',
  range: 'all',
  asOf: null,
  filter: '',
  sort: { key: 'weight', direction: 'desc' },
  run: null,
  levels: null,
  calendar: [],
  composition: null,
};

const chart = createLevelChart(byId('level-chart'));
const holdings = createHoldingsView({ table: byId('holdings'), status: byId('holdings-status'), onSort: changeSort });
const rebalances = createRebalancesView({ table: byId('rebalances'), onSelectDate: showHoldingsOn });
const mandateDialog = createMandateDialog({ onSubmit: rebuild });

const byVariant = (rows) => Object.fromEntries(rows.map((row) => [row.variant, row]));

// The latest drifted (non-rebalance) session shows live weights rather than a freshly reset 1/N.
const defaultAsOf = (levels) => (levels.findLast((p) => !p.rebalanced) ?? levels.at(-1)).date;

async function loadEverything() {
  setBusy(true);
  renderKpisLoading(byId('kpis'));
  try {
    const [run, scorecard, stabilised, raw] = await Promise.all([
      api.run(), api.scorecard(), api.levels('stabilised'), api.levels('raw'),
    ]);
    state.run = run;
    state.levels = { stabilised, raw };
    state.calendar = stabilised.map((p) => p.date);
    if (!state.calendar.includes(state.asOf)) state.asOf = defaultAsOf(stabilised);

    renderRunInfo(run);
    renderKpis(byId('kpis'), byVariant(scorecard), run);
    renderScorecard(byId('scorecard'), byVariant(scorecard), run.mandate);
    chart.render(stabilised, raw, state.range);
    await Promise.all([loadComposition(), loadRebalances()]);
    mount(byId('banner'), '');
    byId('banner').hidden = true;
  } catch (error) {
    showFatal(error);
  } finally {
    setBusy(false);
  }
}

async function loadComposition() {
  const input = byId('as-of');
  input.min = state.calendar[0];
  input.max = state.calendar.at(-1);
  input.value = state.asOf;
  state.composition = await api.composition(state.variant, state.asOf);
  renderHoldings();
  updateStepper();
}

async function loadRebalances() {
  const rows = await api.rebalances(state.variant);
  byId('rebalance-count').textContent = rows.filter((r) => !r.initial).length;
  rebalances.render(rows);
}

function renderHoldings() {
  holdings.render({
    composition: state.composition,
    mandate: state.run.mandate,
    calendar: state.calendar,
    filter: state.filter,
    sort: state.sort,
  });
}

function renderRunInfo(run) {
  const m = run.mandate;
  byId('mandate-summary').textContent =
    `US large caps · ranks ${m.first_rank}–${m.last_rank} · equal weight · weekly rebalance · buffer ${m.buffer}`;
  byId('run-chip-text').textContent =
    `Run ${run.run_id.slice(0, 7)} · ${longDate(run.first_date)} – ${longDate(run.last_date)} · ${run.trading_days} sessions`;
  byId('run-chip').title = `Built ${run.built_at}\nData ${run.data_sha256}\nCode ${run.code_sha256}`;
  byId('base-level').textContent = m.base_level.toLocaleString('en-US');
  mount(byId('footnote'), html`
    Run <span class="mono">${run.run_id}</span> · data <span class="mono">${run.data_sha256.slice(0, 8)}</span>
    · code <span class="mono">${run.code_sha256.slice(0, 8)}</span> · built ${relativeTime(run.built_at)}
    · ${run.universe_size} names in universe · <a href="/docs">API reference</a>`);
}

function updateStepper() {
  const position = state.calendar.indexOf(state.composition.as_of);
  byId('prev-day').disabled = position <= 0;
  byId('next-day').disabled = position >= state.calendar.length - 1;
}

function setBusy(busy) {
  byId('run-chip').classList.toggle('is-busy', busy);
  byId('open-mandate').disabled = busy;
}

function showFatal(error) {
  const banner = byId('banner');
  banner.hidden = false;
  const hint = error.status === 503 ? html` Run <span class="mono">hx50 build</span> and reload.` : '';
  mount(banner, html`<div class="banner" role="alert"><strong>Could not load the index.</strong><span>${error.message}.${hint}</span></div>`);
}

async function guarded(action) {
  try {
    await action();
  } catch (error) {
    toast(error.message, { tone: 'error' });
  }
}

async function rebuild(mandate) {
  setBusy(true);
  try {
    const result = await api.rebuild(mandate);
    toast(`Rebuilt · run ${result.run.run_id.slice(0, 7)} · ranks ${result.run.mandate.first_rank}–${result.run.mandate.last_rank}`);
  } finally {
    setBusy(false);
  }
  await loadEverything();
}

function changeSort(key) {
  const sameKey = state.sort.key === key;
  const defaultDirection = key === 'ticker' || key === 'market_cap_rank' ? 'asc' : 'desc';
  state.sort = { key, direction: sameKey ? (state.sort.direction === 'asc' ? 'desc' : 'asc') : defaultDirection };
  renderHoldings();
}

// "#view=" rather than "#<tab>" so the hash never matches an element id and scrolls the page.
const TABS = ['holdings', 'rebalances'];
const tabFromHash = () => TABS.find((tab) => location.hash === `#view=${tab}`) ?? 'holdings';

function selectTab(tab) {
  state.tab = tab;
  history.replaceState(null, '', `#view=${tab}`);
  for (const button of document.querySelectorAll('[role="tab"]')) {
    button.setAttribute('aria-selected', String(button.dataset.tab === tab));
  }
  byId('panel-holdings').hidden = tab !== 'holdings';
  byId('panel-rebalances').hidden = tab !== 'rebalances';
  for (const element of document.querySelectorAll('.toolbar [data-for]')) {
    element.hidden = element.dataset.for !== tab;
  }
}

function showHoldingsOn(date) {
  state.asOf = date;
  selectTab('holdings');
  guarded(loadComposition);
}

function stepDay(offset) {
  const position = state.calendar.indexOf(state.composition.as_of) + offset;
  if (position < 0 || position >= state.calendar.length) return;
  state.asOf = state.calendar[position];
  guarded(loadComposition);
}

function bindControls() {
  byId('range-picker').addEventListener('click', (event) => {
    const range = event.target.closest('[data-range]')?.dataset.range;
    if (!range || !state.levels) return;
    state.range = range;
    setPressed(byId('range-picker'), 'data-range', range);
    chart.render(state.levels.stabilised, state.levels.raw, range);
  });

  byId('variant-picker').addEventListener('click', (event) => {
    const variant = event.target.closest('[data-variant]')?.dataset.variant;
    if (!variant || variant === state.variant) return;
    state.variant = variant;
    setPressed(byId('variant-picker'), 'data-variant', variant);
    guarded(() => Promise.all([loadComposition(), loadRebalances()]));
  });

  for (const tab of document.querySelectorAll('[role="tab"]')) {
    tab.addEventListener('click', () => selectTab(tab.dataset.tab));
  }

  byId('as-of').addEventListener('change', (event) => {
    if (!event.target.value) return;
    state.asOf = event.target.value;
    guarded(loadComposition);
  });
  byId('prev-day').addEventListener('click', () => stepDay(-1));
  byId('next-day').addEventListener('click', () => stepDay(1));

  byId('ticker-filter').addEventListener('input', (event) => {
    state.filter = event.target.value;
    if (state.composition) renderHoldings();
  });

  byId('open-mandate').addEventListener('click', () => {
    if (state.run) mandateDialog.open(state.run.mandate, state.run.universe_size);
  });
}

bindControls();
selectTab(tabFromHash());
loadEverything();
