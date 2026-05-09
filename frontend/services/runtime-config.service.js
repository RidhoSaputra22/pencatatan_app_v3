import { get, put } from "./api";

export function fetchRuntimeConfig() {
  return get("/api/admin/runtime-config");
}

export function updateRuntimeConfig(values) {
  return put("/api/admin/runtime-config", { values });
}
