import { byId, html, mount } from '../dom.js';

const FIELDS = ['size', 'exclude_top', 'buffer', 'top_buffer'];

function readForm(form) {
  const data = new FormData(form);
  return Object.fromEntries(FIELDS.map((name) => [name, Number(data.get(name))]));
}

// Mirrors the server rules so obvious mistakes are caught before a multi-second rebuild.
function validate(m, universeSize) {
  if (FIELDS.some((f) => !Number.isInteger(m[f]) || m[f] < 0)) return 'All values must be whole numbers ≥ 0.';
  if (m.size < 1) return 'Hold at least one constituent.';
  if (m.top_buffer > m.exclude_top) return 'Top-edge buffer cannot exceed the excluded count.';
  if (m.size + m.exclude_top > universeSize) return `Constituents + excluded exceeds the ${universeSize}-name universe.`;
  return null;
}

function renderPreview(element, m) {
  const first = m.exclude_top + 1;
  const last = m.exclude_top + m.size;
  const floor = last + m.buffer;
  const scale = Math.max(100, Math.ceil((floor * 1.15) / 10) * 10);
  const pos = (rank) => `${((rank - 1) / scale) * 100}%`;
  const span = (from, to) => `${((to - from + 1) / scale) * 100}%`;
  mount(element, html`
    <span>Holds ranks <strong>${first}–${last}</strong> at <strong>${(100 / m.size).toFixed(2)}%</strong> each.
      ${m.buffer ? html`Incumbents stay until they fall below rank <strong>${floor}</strong>.` : 'No retention buffer: strict ranks every week.'}
      ${m.top_buffer ? html` Incumbents may rise to rank <strong>${m.exclude_top - m.top_buffer + 1}</strong>.` : ''}</span>
    <div class="rank-track" aria-hidden="true">
      ${m.top_buffer ? html`<span class="band" style="left: ${pos(first - m.top_buffer)}; width: ${span(first - m.top_buffer, first - 1)}"></span>` : ''}
      <span class="held" style="left: ${pos(first)}; width: ${span(first, last)}"></span>
      ${m.buffer ? html`<span class="band" style="left: ${pos(last + 1)}; width: ${span(last + 1, floor)}"></span>` : ''}
    </div>
    <span class="subtle num" style="display: flex; justify-content: space-between"><span>rank 1</span><span>${scale}</span></span>`);
}

export function createMandateDialog({ onSubmit }) {
  const dialog = byId('mandate-dialog');
  const form = byId('mandate-form');
  const error = byId('mandate-error');
  const submit = byId('mandate-submit');
  const preview = byId('mandate-preview');
  let universeSize = Infinity;

  const showError = (message) => {
    error.textContent = message ?? '';
    error.hidden = !message;
  };

  const setBusy = (busy) => {
    submit.disabled = busy;
    mount(submit, busy ? html`<span class="spinner"></span> Rebuilding…` : 'Rebuild index');
  };

  form.addEventListener('input', () => {
    const values = readForm(form);
    const problem = validate(values, universeSize);
    showError(problem);
    if (!problem) renderPreview(preview, values);
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const values = readForm(form);
    const problem = validate(values, universeSize);
    if (problem) return showError(problem);
    setBusy(true);
    try {
      await onSubmit(values);
      dialog.close();
    } catch (failure) {
      showError(failure.message);
    } finally {
      setBusy(false);
    }
  });

  byId('mandate-cancel').addEventListener('click', () => dialog.close());

  function open(mandate, universe) {
    universeSize = universe;
    for (const name of FIELDS) form.elements[name].value = mandate[name];
    showError(null);
    renderPreview(preview, mandate);
    dialog.showModal();
    form.elements.size.focus();
  }

  return { open };
}
