import { byId, html, mount } from '../dom.js';

const LIFETIME_MS = 4500;

export function toast(message, { tone = 'info' } = {}) {
  const element = document.createElement('div');
  element.className = `toast${tone === 'error' ? ' is-error' : ''}`;
  element.setAttribute('role', tone === 'error' ? 'alert' : 'status');
  mount(element, html`<span>${message}</span>`);
  byId('toasts').append(element);
  setTimeout(() => element.remove(), LIFETIME_MS);
}
