"use client";

import { useEffect, useRef, useState } from "react";
import {
  STREAM_HEALTH_INTERVAL,
  STREAM_HEALTH_URL,
  STREAM_RELAY_HEALTH_URL,
  STREAM_RELAY_URL,
  STREAM_URL,
} from "@/lib/constants";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";
import Section from "@/components/ui/Section";

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Request failed");
  }
  return response.json();
}

/**
 * Live camera MJPEG stream viewer with health-check.
 */
export default function CameraView() {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [streamSrc, setStreamSrc] = useState("");
  const [streamSourceLabel, setStreamSourceLabel] = useState("");
  const imgRef = useRef(null);

  useEffect(() => {
    let active = true;

    const checkStream = async () => {
      try {
        const edge = await fetchJson(STREAM_HEALTH_URL).catch(() => null);
        if (edge?.status === "ok") {
          if (!active) return;
          setStreamSrc(STREAM_URL);
          setStreamSourceLabel("edge worker");
          setLoading(false);
          setError("");
          return;
        }

        const relay = await fetchJson(STREAM_RELAY_HEALTH_URL).catch(() => null);
        if (relay?.has_frame) {
          if (!active) return;
          setStreamSrc(STREAM_RELAY_URL);
          setStreamSourceLabel("backend relay");
          setLoading(false);
          setError("");
          return;
        }

        if (active) {
          setStreamSrc("");
          setStreamSourceLabel("");
          setError(
            "Camera stream not available. Pastikan edge worker atau relay backend menerima frame.",
          );
          setLoading(false);
        }
      } catch {
        if (active) {
          setStreamSrc("");
          setStreamSourceLabel("");
          setError(
            "Camera stream not available. Pastikan edge worker atau relay backend menerima frame.",
          );
          setLoading(false);
        }
      }
    };

    checkStream();
    const interval = setInterval(checkStream, STREAM_HEALTH_INTERVAL);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const handleImageError = async () => {
    try {
      const relay = await fetchJson(STREAM_RELAY_HEALTH_URL);
      if (relay?.has_frame) {
        setStreamSrc(`${STREAM_RELAY_URL}?t=${Date.now()}`);
        setStreamSourceLabel("backend relay");
        setError("");
        setLoading(false);
        return;
      }
    } catch {
      // Fall through to error state below.
    }

    setError(
      "Failed to load camera stream. Kamera mungkin busy, edge worker belum siap, atau stream relay belum tersedia.",
    );
    setLoading(false);
  };

  const handleImageLoad = () => {
    setLoading(false);
    setError("");
  };

  const retryStream = () => {
    setError("");
    setLoading(true);
    if (imgRef.current && streamSrc) {
      imgRef.current.src = `${streamSrc.split("?")[0]}?t=${Date.now()}`;
    }
  };

  return (
    <Section title="Live Camera Preview">
      {loading && !error && (
        <div className="bg-base-200 rounded-sm p-6 text-center">
          <span className="loading loading-dots loading-sm" />
          <p className="mt-1 text-sm">Menghubungkan ke kamera...</p>
        </div>
      )}

      {error && (
        <div className="space-y-2">
          <Alert variant="secondary">
            <div>
              <p className="font-medium text-sm">Tidak bisa terkoneksi ke CCTV</p>
              <p className="text-xs">{error}</p>
            </div>
          </Alert>
          <Button variant="primary" size="xs" onClick={retryStream}>
            Retry Stream
          </Button>
        </div>
      )}

      <div className="max-h-[300px] overflow-hidden bg-black rounded-sm">
        <img
          ref={imgRef}
          src={streamSrc}
          alt="Camera Feed"
          onError={handleImageError}
          onLoad={handleImageLoad}
          className={`w-full h-full object-contain ${loading || error || !streamSrc ? "hidden" : "block"}`}
        />
      </div>

      {!loading && !error && (
        <p className="text-xs opacity-50 mt-1">Live stream dari {streamSourceLabel}.</p>
      )}
    </Section>
  );
}
