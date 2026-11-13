export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// FastAPI returns either {detail: "..."} or, for validation errors, {detail: [{msg, loc}, ...]}.
function messageFrom(body, fallback) {
  const detail = body?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${d.loc?.at(-1) ?? 'value'}: ${d.msg}`).join('; ');
  return fallback;
}

async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, { headers: { Accept: 'application/json' }, ...options });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(messageFrom(body, response.statusText), response.status);
  return body;
}

const query = (params) => new URLSearchParams(Object.entries(params).filter(([, v]) => v != null)).toString();

export const api = {
  run: () => request('/run'),
  scorecard: () => request('/scorecard'),
  levels: (variant) => request(`/levels?${query({ variant })}`),
  composition: (variant, date) => request(`/composition?${query({ variant, date })}`),
  rebalances: (variant) => request(`/rebalances?${query({ variant })}`),
  rebuild: (mandate) =>
    request('/rebuild', {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(mandate),
    }),
};
