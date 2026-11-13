// Tiny escaping template layer: every interpolated value is HTML-escaped unless wrapped in raw().
const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

class SafeHtml {
  constructor(value) { this.value = value; }
  toString() { return this.value; }
}

export const raw = (value) => new SafeHtml(String(value));

const escape = (value) => String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);

function render(value) {
  if (value instanceof SafeHtml) return value.value;
  if (Array.isArray(value)) return value.map(render).join('');
  if (value === null || value === undefined || value === false) return '';
  return escape(value);
}

export function html(strings, ...values) {
  return raw(strings.reduce((out, chunk, i) => out + chunk + (i < values.length ? render(values[i]) : ''), ''));
}

export const mount = (element, content) => { element.innerHTML = render(content); };

export const byId = (id) => document.getElementById(id);

export function setPressed(group, attribute, value) {
  for (const button of group.querySelectorAll(`[${attribute}]`)) {
    button.setAttribute('aria-pressed', String(button.getAttribute(attribute) === value));
  }
}
