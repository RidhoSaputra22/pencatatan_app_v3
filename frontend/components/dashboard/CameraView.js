"use client";

import { useState, useRef, useEffect } from "react";
import { STREAM_URL, STREAM_HEALTH_INTERVAL } from "@/lib/constants";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";
import Section from "@/components/ui/Section";

/**
 * Live camera MJPEG stream viewer with health-check.
 */
export default function CameraView() {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const imgRef = useRef(null);

  const healthUrl = STREAM_URL.replace(/\/video_feed$/, "/health");

  useEffect(() => {
    const checkStream = async () => {
      try {
        const response = await fetch(healthUrl);
        if (response.ok) {
          const data = await response.json();
          if (data.status === "ok") {
            setLoading(false);
            setError("");
          } else {
            throw new Error("Edge worker belum menerima frame dari kamera.");
          }
        } else {
          throw new Error("Stream server not responding");
        }
      } catch {
        setError(
          "Camera stream not available. Pastikan edge worker sudah berjalan.",
        );
        setLoading(false);
      }
    };

    checkStream();
    const interval = setInterval(checkStream, STREAM_HEALTH_INTERVAL);
    return () => clearInterval(interval);
  }, [healthUrl]);

  const handleImageError = () => {
    setError(
      "Failed to load camera stream. Kamera mungkin busy atau disconnected.",
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
    if (imgRef.current) {
      imgRef.current.src = STREAM_URL + "?t=" + Date.now();
    }
  };

  return (
    <Section title="Live Camera Preview">
      {loading && !error && (
        <div className="bg-base-200 rounded-sm p-10 text-center my-3">
          <span className="loading loading-dots loading-md" />
          <p className="mt-2">Loading camera stream...</p>
          <p className="text-xs opacity-60">Connecting to edge server...</p>
        </div>
      )}

      {error && (
        <div className="space-y-3">
          <Alert variant="secondary">
            <div className="">
              <div>
                <p className="font-medium ">Tidak bisa terkoneksi ke CCTV</p>
                <p className="text-xs ">{error}</p>
              </div>
            </div>
          </Alert>
          <Button variant="primary" size="sm" onClick={retryStream}>
            Retry Stream
          </Button>
        </div>
      )}

      <img
        ref={imgRef}
        src={STREAM_URL}
        alt="Camera Feed"
        onError={handleImageError}
        onLoad={handleImageLoad}
        className={`w-full  rounded-sm bg-black ${loading || error ? "hidden" : "block"}`}
      />

      {!loading && !error && (
        <p className="text-xs opacity-60 mt-2">
          Live stream dari edge server (YOLO + tracking).
        </p>
      )}
    </Section>
  );
}
