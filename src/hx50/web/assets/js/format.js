const LOCALE = 'en-US';
const MINUS = '−';
const cache = new Map();

function formatter(key, options) {
  if (!cache.has(key)) cache.set(key, new Intl.NumberFormat(LOCALE, options));
  return cache.get(key);
}

const sign = (x) => (x > 0 ? '+' : x < 0 ? MINUS : '');

export const percent = (x, digits = 2) =>
  formatter(`pct${digits}`, { style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits }).format(x);

export const signedPercent = (x, digits = 2) => sign(x) + percent(Math.abs(x), digits);

export const points = (x, digits = 2) => `${sign(x)}${Math.abs(x * 100).toFixed(digits)} pts`;

export const decimal = (x, digits = 2) =>
  formatter(`dec${digits}`, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(x);

export const signedDecimal = (x, digits = 2) => sign(x) + decimal(Math.abs(x), digits);

export const integer = (x) => formatter('int', { maximumFractionDigits: 0 }).format(x);

export const signedInteger = (x) => sign(x) + integer(Math.abs(x));

// ISO dates are calendar dates, so format them in UTC to avoid shifting a day in western time zones.
const asDate = (iso) => new Date(`${iso}T00:00:00Z`);

export const shortDate = (iso) =>
  asDate(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });

export const longDate = (iso) =>
  asDate(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

export function relativeTime(isoTimestamp) {
  const seconds = (new Date(isoTimestamp).getTime() - Date.now()) / 1000;
  const units = [['day', 86400], ['hour', 3600], ['minute', 60]];
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: 'auto' });
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return 'just now';
}

export const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
