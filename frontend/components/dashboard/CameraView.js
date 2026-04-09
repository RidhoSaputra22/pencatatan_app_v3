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
    <div className="card bg-base-100 shadow-lg overflow-hidden h-full">
      <div className="p-5 pb-3">
        <h3 className="font-bold text-base-content/80 flex items-center gap-2">
          <span className="w-1 h-5 bg-warning rounded-full"></span>
          Pantauan Kamera Langsung
          {!loading && !error && streamSrc && (
            <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-success/10 text-success rounded-full font-bold ml-auto">
              <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse"></span>
              LIVE
            </span>
          )}
        </h3>
      </div>

      {loading && !error && (
        <div className="bg-base-200/50 p-10 text-center">
          <span className="loading loading-dots loading-md text-primary" />
          <p className="mt-2 text-sm text-base-content/50">Menghubungkan ke kamera...</p>
        </div>
      )}

      {error && (
        <div className="p-5 pt-0 space-y-3">
          <div className="bg-base-200/50 rounded-xl p-6 text-center">
            <svg className="w-12 h-full mx-auto text-base-content/20 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <p className="font-medium text-sm text-base-content/60">Tidak bisa terkoneksi ke CCTV</p>
            <p className="text-xs text-base-content/40 mt-1 max-w-sm mx-auto">{error}</p>
            <button
              onClick={retryStream}
              className="btn btn-primary btn-sm mt-4"
            >
              Coba Lagi
            </button>
          </div>
        </div>
      )}

      <div className="relative">
        <div className="h-full overflow-hidden bg-black">
          <img
            ref={imgRef}
            src={streamSrc}
            alt="Camera Feed"
            onError={handleImageError}
            onLoad={handleImageLoad}
            className={`w-full h-full object-contain ${loading || error || !streamSrc ? "hidden" : "block"}`}
          />
        </div>
        {!loading && !error && streamSrc && (
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-3">
            <div className="flex items-center justify-between">
              <span className="text-white/80 text-xs flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-success"></span>
                Live stream dari {streamSourceLabel}
              </span>
              <span className="text-white/50 text-[10px]">YOLO v5 tracking</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
