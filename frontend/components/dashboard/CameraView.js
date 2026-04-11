"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  STREAM_HEALTH_INTERVAL,
  STREAM_HEALTH_URL,
  STREAM_RELAY_HEALTH_URL,
  STREAM_RELAY_URL,
  STREAM_URL,
  WEBRTC_SIGNAL_URL,
} from "@/lib/constants";

const RECONNECT_DELAY_MS = 1500;
const HEALTH_POLL_MS = Math.max(STREAM_HEALTH_INTERVAL || 0, 1500);

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Request failed");
  }
  return response.json();
}

function normalizeIceServers(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => {
      if (typeof item === "string") {
        return { urls: item };
      }

      if (item && typeof item === "object" && item.urls) {
        return item;
      }

      return null;
    })
    .filter(Boolean);
}

function waitForIceGatheringComplete(pc, timeoutMs = 2000) {
  if (pc.iceGatheringState === "complete") {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    let resolved = false;

    const finish = () => {
      if (resolved) return;
      resolved = true;
      pc.removeEventListener("icegatheringstatechange", handleChange);
      window.clearTimeout(timerId);
      resolve();
    };

    const handleChange = () => {
      if (pc.iceGatheringState === "complete") {
        finish();
      }
    };

    const timerId = window.setTimeout(finish, timeoutMs);
    pc.addEventListener("icegatheringstatechange", handleChange);
  });
}

/**
 * Live camera viewer.
 * Primary path: WebRTC video track from edge worker.
 * Fallback path: MJPEG edge feed / backend relay.
 */
export default function CameraView() {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [streamSrc, setStreamSrc] = useState("");
  const [streamSourceLabel, setStreamSourceLabel] = useState("");
  const [transport, setTransport] = useState("");

  const videoRef = useRef(null);
  const imgRef = useRef(null);
  const pcRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const activeRequestRef = useRef(0);
  const mountedRef = useRef(false);
  const transportRef = useRef("");
  const streamSrcRef = useRef("");
  const probingRef = useRef(false);
  const ensureStreamRef = useRef(null);

  const setTransportState = useCallback((nextTransport, nextSrc, label) => {
    transportRef.current = nextTransport;
    streamSrcRef.current = nextSrc;
    setTransport(nextTransport);
    setStreamSrc(nextSrc);
    setStreamSourceLabel(label);
  }, []);

  const cleanupPeerConnection = useCallback(() => {
    const pc = pcRef.current;
    pcRef.current = null;

    if (pc) {
      pc.ontrack = null;
      pc.onconnectionstatechange = null;
      pc.oniceconnectionstatechange = null;
      try {
        pc.close();
      } catch {
        // Ignore teardown errors.
      }
    }

    if (videoRef.current) {
      try {
        videoRef.current.pause();
      } catch {
        // Ignore pause errors.
      }
      videoRef.current.srcObject = null;
    }
  }, []);

  const switchToMjpeg = useCallback(
    (src, label, forceReload = false) => {
      const currentBaseSrc = streamSrcRef.current.split("?")[0];
      const nextBaseSrc = src.split("?")[0];
      if (!forceReload && transportRef.current === "mjpeg" && currentBaseSrc === nextBaseSrc) {
        setError("");
        setLoading(false);
        setStreamSourceLabel(label);
        return;
      }

      cleanupPeerConnection();
      setTransportState("mjpeg", src, label);
      setError("");
      setLoading(true);
    },
    [cleanupPeerConnection, setTransportState],
  );

  const scheduleReconnect = useCallback((delayMs = RECONNECT_DELAY_MS) => {
    if (!mountedRef.current || reconnectTimerRef.current) {
      return;
    }

    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = null;
      ensureStreamRef.current?.(true);
    }, delayMs);
  }, []);

  const connectWebRtc = useCallback(
    async (edgeHealth, requestId) => {
      if (
        typeof window === "undefined"
        || typeof window.RTCPeerConnection === "undefined"
      ) {
        throw new Error("WebRTC is not supported in this browser");
      }

      cleanupPeerConnection();

      const peerConnection = new window.RTCPeerConnection({
        iceServers: normalizeIceServers(edgeHealth?.webrtc_ice_servers),
      });
      pcRef.current = peerConnection;

      const fallbackStream = new MediaStream();
      peerConnection.addTransceiver("video", { direction: "recvonly" });

      peerConnection.ontrack = ({ streams, track }) => {
        if (requestId !== activeRequestRef.current || peerConnection !== pcRef.current) {
          return;
        }

        const remoteStream = streams?.[0] || fallbackStream;
        if (!streams?.[0]) {
          fallbackStream.addTrack(track);
        }

        if (videoRef.current && videoRef.current.srcObject !== remoteStream) {
          videoRef.current.srcObject = remoteStream;
        }

        videoRef.current?.play?.().catch(() => {});
        setTransportState("webrtc", "", "edge worker via WebRTC");
        setError("");
      };

      peerConnection.onconnectionstatechange = () => {
        if (peerConnection !== pcRef.current) {
          return;
        }

        const state = peerConnection.connectionState;
        if (state === "connected") {
          setTransportState("webrtc", "", "edge worker via WebRTC");
          setError("");
          setLoading(false);
          return;
        }

        if (state === "failed" || state === "disconnected") {
          scheduleReconnect();
        }
      };

      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);
      await waitForIceGatheringComplete(peerConnection);

      if (requestId !== activeRequestRef.current || peerConnection !== pcRef.current) {
        throw new Error("WebRTC request superseded");
      }

      const response = await fetch(WEBRTC_SIGNAL_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sdp: peerConnection.localDescription?.sdp,
          type: peerConnection.localDescription?.type,
        }),
      });

      if (!response.ok) {
        const detail = await response.text().catch(() => "");
        throw new Error(detail || "WebRTC signaling failed");
      }

      const answer = await response.json();
      await peerConnection.setRemoteDescription(
        new window.RTCSessionDescription(answer),
      );

      if (requestId !== activeRequestRef.current || peerConnection !== pcRef.current) {
        throw new Error("WebRTC request superseded");
      }

      setTransportState("webrtc", "", "edge worker via WebRTC");
      setError("");
      return true;
    },
    [cleanupPeerConnection, scheduleReconnect, setTransportState],
  );

  const ensureStream = useCallback(
    async (force = false) => {
      if (probingRef.current && !force) {
        return;
      }

      probingRef.current = true;
      const requestId = activeRequestRef.current + 1;
      activeRequestRef.current = requestId;

      try {
        const edge = await fetchJson(STREAM_HEALTH_URL).catch(() => null);
        const currentPeerState = pcRef.current?.connectionState;

        if (edge?.status === "ok") {
          if (!force && transportRef.current === "webrtc" && currentPeerState === "connected") {
            setLoading(false);
            setError("");
            return;
          }

          if (edge.webrtc_enabled) {
            setLoading(true);
            try {
              await connectWebRtc(edge, requestId);
              return;
            } catch (webrtcError) {
              cleanupPeerConnection();
              console.error("WebRTC connect failed, using MJPEG fallback.", webrtcError);
            }
          }

          switchToMjpeg(
            `${STREAM_URL}?t=${Date.now()}`,
            edge.webrtc_enabled ? "edge worker (MJPEG fallback)" : "edge worker",
            force,
          );
          return;
        }

        const relay = await fetchJson(STREAM_RELAY_HEALTH_URL).catch(() => null);
        if (relay?.has_frame) {
          switchToMjpeg(`${STREAM_RELAY_URL}?t=${Date.now()}`, "backend relay", force);
          return;
        }

        cleanupPeerConnection();
        setTransportState("", "", "");
        setError(
          "Camera stream not available. Pastikan edge worker aktif atau relay backend menerima frame.",
        );
        setLoading(false);
      } finally {
        probingRef.current = false;
      }
    },
    [cleanupPeerConnection, connectWebRtc, setTransportState, switchToMjpeg],
  );

  ensureStreamRef.current = ensureStream;

  useEffect(() => {
    mountedRef.current = true;
    ensureStream(true);

    const intervalId = window.setInterval(() => {
      ensureStream(false);
    }, HEALTH_POLL_MS);

    return () => {
      mountedRef.current = false;
      window.clearInterval(intervalId);
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      cleanupPeerConnection();
    };
  }, [cleanupPeerConnection, ensureStream]);

  const handleImageError = () => {
    setLoading(true);
    ensureStream(true);
  };

  const handleVideoLoaded = () => {
    setLoading(false);
    setError("");
  };

  const retryStream = () => {
    setError("");
    setLoading(true);
    ensureStream(true);
  };

  const transportBadge =
    transport === "webrtc" ? "WebRTC" : transport === "mjpeg" ? "MJPEG" : "";

  return (
    <div className="card bg-base-100 shadow-lg overflow-hidden h-full">
      <div className="p-5 pb-3">
        <h3 className="font-bold text-base-content/80 flex items-center gap-2">
          <span className="w-1 h-5 bg-warning rounded-full"></span>
          Pantauan Kamera Langsung
          {!loading && !error && (transport === "webrtc" || streamSrc) && (
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
          <p className="mt-2 text-sm text-base-content/50">
            Menghubungkan ke stream kamera...
          </p>
        </div>
      )}

      {error && (
        <div className="p-5 pt-0 space-y-3">
          <div className="bg-base-200/50 rounded-xl p-6 text-center">
            <svg
              className="w-12 h-full mx-auto text-base-content/20 mb-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.5"
                d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
            <p className="font-medium text-sm text-base-content/60">
              Tidak bisa terkoneksi ke CCTV
            </p>
            <p className="text-xs text-base-content/40 mt-1 max-w-sm mx-auto">{error}</p>
            <button onClick={retryStream} className="btn btn-primary btn-sm mt-4">
              Coba Lagi
            </button>
          </div>
        </div>
      )}

      <div className="relative flex-1 min-h-[320px]">
        <div className="h-full overflow-hidden bg-black">
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            onLoadedData={handleVideoLoaded}
            className={`w-full h-full object-contain ${
              loading || error || transport !== "webrtc" ? "hidden" : "block"
            }`}
          />
          <img
            ref={imgRef}
            src={streamSrc}
            alt="Camera Feed"
            onError={handleImageError}
            onLoad={handleVideoLoaded}
            className={`w-full h-full object-contain ${
              loading || error || transport !== "mjpeg" || !streamSrc ? "hidden" : "block"
            }`}
          />
        </div>

        {!loading && !error && (transport === "webrtc" || streamSrc) && (
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-white/80 text-xs flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-success"></span>
                Live stream dari {streamSourceLabel}
              </span>
              <span className="text-white/50 text-[10px] uppercase tracking-[0.2em]">
                {transportBadge || "LIVE"} · YOLO tracking
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
