"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchCamera, fetchAreas } from "@/services/camera.service";

/**
 * Hook that loads camera + counting areas for a given camera id.
 */
export function useCamera(cameraId = 1) {
  const [camera, setCamera] = useState(null);
  const [areas, setAreas] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [camData, areasData] = await Promise.all([
        fetchCamera(cameraId),
        fetchAreas(cameraId).catch(() => []),
      ]);
      setCamera(camData);
      setAreas(areasData);
    } catch (e) {
      setError(e.message || "Failed to load camera config");
    }
  }, [cameraId]);

  useEffect(() => {
    load();
  }, [load]);

  return { camera, areas, error, reload: load };
}
