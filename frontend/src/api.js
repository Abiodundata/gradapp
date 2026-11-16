export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const KEYS = { access: "gradapp_access", refresh: "gradapp_refresh", user: "gradapp_user" };

// localStorage can throw (private mode, blocked storage), so every access is guarded.
const storage = {
  get(key) {
    try { return localStorage.getItem(key); } catch { return null; }
  },
  set(key, value) {
    try { localStorage.setItem(key, value); } catch { /* storage unavailable */ }
  },
  remove(key) {
    try { localStorage.removeItem(key); } catch { /* storage unavailable */ }
  },
};

export class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

let sessionExpiredHandler = () => {};
export function onSessionExpired(handler) {
  sessionExpiredHandler = handler;
}

/** Turn the backend's {error: {message, details}} shape into one readable sentence. */
export function errorMessage(data, status) {
  if (data?.error?.message) return data.error.message;
  if (typeof data?.detail === "string") return data.detail;
  if (status >= 500) return "The server had a problem. Please try again in a moment.";
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  return "Something went wrong. Please try again.";
}

let refreshInFlight = null;

/** Exchange the refresh token for a new access token. Concurrent callers share one request. */
async function refreshAccessToken() {
  const refresh = storage.get(KEYS.refresh);
  if (!refresh) return false;
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_URL}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    })
      .then(async (response) => {
        if (!response.ok) return false;
        const data = await response.json();
        storage.set(KEYS.access, data.access);
        if (data.refresh) storage.set(KEYS.refresh, data.refresh);
        return true;
      })
      .catch(() => false)
      .finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

/**
 * Call the GradApp API.
 * - `body` is an object and is sent as JSON.
 * - On 401 the access token is refreshed once and the request retried;
 *   if that fails the session is cleared and the app returns to sign-in.
 */
export async function api(path, { body, method = "GET", headers = {}, retry = true, ...rest } = {}) {
  const requestHeaders = { ...headers };
  if (body !== undefined) requestHeaders["Content-Type"] = "application/json";
  const token = storage.get(KEYS.access);
  if (token) requestHeaders.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers: requestHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...rest,
    });
  } catch {
    throw new ApiError("Cannot reach the GradApp server. Check that it is running and try again.", 0);
  }

  if (response.status === 401 && retry && token) {
    if (await refreshAccessToken()) {
      return api(path, { body, method, headers, retry: false, ...rest });
    }
    clearSession();
    sessionExpiredHandler();
    throw new ApiError("Your session has expired. Please sign in again.", 401);
  }

  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(errorMessage(data, response.status), response.status, data?.error?.details);
  }
  return data;
}

/** Build a query string from an object, skipping empty values. */
export function query(params) {
  const entries = Object.entries(params).filter(([, value]) => value !== "" && value !== null && value !== undefined && value !== false);
  const search = new URLSearchParams(entries.map(([key, value]) => [key, String(value)]));
  const text = search.toString();
  return text ? `?${text}` : "";
}

export function saveSession(data) {
  storage.set(KEYS.access, data.access);
  storage.set(KEYS.refresh, data.refresh);
  saveUser(data.user);
}

export function saveUser(user) {
  storage.set(KEYS.user, JSON.stringify(user));
}

export function getRefreshToken() {
  return storage.get(KEYS.refresh);
}

export function clearSession() {
  storage.remove(KEYS.access);
  storage.remove(KEYS.refresh);
  storage.remove(KEYS.user);
  storage.remove("gradapp_compare"); // per-user selection must not leak to the next account
}

export function getSavedUser() {
  try {
    return storage.get(KEYS.access) ? JSON.parse(storage.get(KEYS.user)) : null;
  } catch {
    return null;
  }
}
