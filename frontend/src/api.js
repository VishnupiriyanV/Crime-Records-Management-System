export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// every call goes to /api; the header is what the server checks on writes
export async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'crms' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.detail || 'Something went wrong.', res.status);
  return data;
}

export function withQuery(path, params) {
  const clean = Object.entries(params).filter(([, v]) => v !== '' && v != null);
  return clean.length ? `${path}?${new URLSearchParams(clean)}` : path;
}
