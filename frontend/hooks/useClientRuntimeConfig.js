"use client";

import { useEffect, useState } from "react";
import {
  DEFAULT_CLIENT_RUNTIME_CONFIG,
  fetchClientRuntimeConfig,
} from "@/services/runtime-config.service";

export function useClientRuntimeConfig() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const data = await fetchClientRuntimeConfig();
        if (active) {
          setConfig(data);
        }
      } catch {
        if (active) {
          setConfig(DEFAULT_CLIENT_RUNTIME_CONFIG);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      active = false;
    };
  }, []);

  return {
    config,
    loading,
    clientPollingEnabled:
      loading ? null : (config?.client_polling_enabled ?? true),
  };
}
