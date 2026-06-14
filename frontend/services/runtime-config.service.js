import { get, put } from "./api";

export const DEFAULT_CLIENT_RUNTIME_CONFIG = {
  config_mtime: null,
  values: {
    CLIENT_POLLING_ENABLED: "true",
  },
  client_polling_enabled: true,
};

let clientRuntimeConfigCache = null;
let clientRuntimeConfigPromise = null;

function isTruthy(value) {
  return ["1", "true", "yes", "on"].includes(String(value).toLowerCase());
}

function normalizeClientRuntimeConfig(payload = {}) {
  const rawPollingValue =
    payload?.values?.CLIENT_POLLING_ENABLED ??
    payload?.CLIENT_POLLING_ENABLED ??
    payload?.client_polling_enabled;
  const clientPollingEnabled =
    rawPollingValue === undefined
      ? DEFAULT_CLIENT_RUNTIME_CONFIG.client_polling_enabled
      : isTruthy(rawPollingValue);

  return {
    config_mtime: payload?.config_mtime ?? null,
    values: {
      CLIENT_POLLING_ENABLED: clientPollingEnabled ? "true" : "false",
    },
    client_polling_enabled: clientPollingEnabled,
  };
}

export function fetchRuntimeConfig() {
  return get("/api/admin/runtime-config");
}

export function resetClientRuntimeConfigCache(payload = null) {
  clientRuntimeConfigPromise = null;
  clientRuntimeConfigCache = payload
    ? normalizeClientRuntimeConfig(payload)
    : null;
}

export async function fetchClientRuntimeConfig({ force = false } = {}) {
  if (!force && clientRuntimeConfigCache) {
    return clientRuntimeConfigCache;
  }

  if (!force && clientRuntimeConfigPromise) {
    return clientRuntimeConfigPromise;
  }

  clientRuntimeConfigPromise = get(
    `/api/runtime-config/client?_=${Date.now()}`,
  )
    .then((payload) => {
      const normalized = normalizeClientRuntimeConfig(payload);
      clientRuntimeConfigCache = normalized;
      return normalized;
    })
    .finally(() => {
      clientRuntimeConfigPromise = null;
    });

  return clientRuntimeConfigPromise;
}

export async function updateRuntimeConfig(values) {
  const result = await put("/api/admin/runtime-config", { values });
  resetClientRuntimeConfigCache(result);
  return result;
}
