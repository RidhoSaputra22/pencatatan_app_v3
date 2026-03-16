import { API_BASE } from "@/lib/constants";
import { getToken } from "@/lib/utils";

/**
 * Thin wrapper around fetch that auto-attaches the JWT token and
 * handles JSON parsing + error normalisation.
 */
async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errData.detail || `Request failed (${res.status})`);
  }

  // Some endpoints may return 204 No Content
  if (res.status === 204) return null;
  return res.json();
}

export function get(path) {
  return request(path, { method: "GET" });
}

export function post(path, body) {
  return request(path, { method: "POST", body });
}

export function put(path, body) {
  return request(path, { method: "PUT", body });
}

export function del(path) {
  return request(path, { method: "DELETE" });
}
