"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  STREAM_HEALTH_INTERVAL,
  STREAM_HEALTH_URL,
  STREAM_RELAY_HEALTH_URL,
  STREAM_RELAY_URL,
  STREAM_RAW_URL,
} from "@/lib/constants";

/**
 * Default canvas size (matches typical YOLO frame: 1280×720).
 * The polygon coordinates saved are always in this "real" resolution.
 */
const NATIVE_W = 1280;
const NATIVE_H = 720;

/**
 * Interactive ROI polygon editor.
 * – Live camera MJPEG feed as background
 * – Click to add points
 * – Drag points to reposition
 * – Right‑click / double‑click a point to delete it
 * – Keyboard shortcuts (Ctrl+Z undo, Delete clear all)
 * – Coordinates stored in native resolution (1280×720)
 *
 * @param {{ points: number[][], onChange: (pts: number[][]) => void }} props
 */
export default function RoiEditor({ points = [], onChange }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const imgRef = useRef(null);

  // Local copy of points for drawing & manipulation
  const [pts, setPts] = useState(points);
  const [dragging, setDragging] = useState(-1); // index of point being dragged
  const [hovered, setHovered] = useState(-1);
  const [streamOk, setStreamOk] = useState(false);
  const [streamUrl, setStreamUrl] = useState("");
  const [scale, setScale] = useState(1);
  const [canvasW, setCanvasW] = useState(NATIVE_W);
  const [canvasH, setCanvasH] = useState(NATIVE_H);
  const [history, setHistory] = useState([]);

  // Sync from parent when "points" prop changes
  useEffect(() => {
    if (JSON.stringify(points) !== JSON.stringify(pts)) {
      setPts(points);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points]);

  // Propagate changes to parent
  const commit = useCallback(
    (newPts) => {
      setPts(newPts);
      onChange?.(newPts);
    },
    [onChange]
  );

  // Push current state into undo history before mutation
  const pushHistory = useCallback(() => {
    setHistory((h) => [...h.slice(-30), JSON.stringify(pts)]);
  }, [pts]);

  // Undo last action
  const undo = useCallback(() => {
    setHistory((h) => {
      if (h.length === 0) return h;
      const prev = h[h.length - 1];
      const restored = JSON.parse(prev);
      setPts(restored);
      onChange?.(restored);
      return h.slice(0, -1);
    });
  }, [onChange]);

  /* ───────── Stream health check ───────── */
  useEffect(() => {
    let timer;
    const check = async () => {
      try {
        const edgeResponse = await fetch(STREAM_HEALTH_URL, { cache: "no-store" }).catch(() => null);
        if (edgeResponse?.ok) {
          const edge = await edgeResponse.json();
          if (edge?.status === "ok") {
            setStreamOk(true);
            setStreamUrl(STREAM_RAW_URL);
            return;
          }
        }

        const relayResponse = await fetch(STREAM_RELAY_HEALTH_URL, { cache: "no-store" }).catch(() => null);
        if (relayResponse?.ok) {
          const relay = await relayResponse.json();
          if (relay?.has_frame) {
            setStreamOk(true);
            setStreamUrl(STREAM_RELAY_URL);
            return;
          }
        }

        setStreamOk(false);
        setStreamUrl("");
      } catch {
        setStreamOk(false);
        setStreamUrl("");
      }
    };
    check();
    timer = setInterval(check, STREAM_HEALTH_INTERVAL);
    return () => clearInterval(timer);
  }, []);

  /* ───────── MJPEG image loader ───────── */
  // Use a hidden <img> element — the browser handles MJPEG multipart
  // streams natively without needing periodic src refreshes.
  const hiddenImgRef = useRef(null);

  useEffect(() => {
    if (!streamOk || !hiddenImgRef.current) return;
    const img = hiddenImgRef.current;
    img.src = streamUrl;
    imgRef.current = img;
    return () => {
      img.src = "";
      imgRef.current = null;
    };
  }, [streamOk, streamUrl]);

  /* ───────── Resize observer → responsive canvas ───────── */
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver(() => {
      const w = container.clientWidth;
      const s = w / NATIVE_W;
      const h = Math.round(NATIVE_H * s);
      setScale(s);
      setCanvasW(w);
      setCanvasH(h);
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  /* ───────── Draw loop (requestAnimationFrame) ───────── */
  useEffect(() => {
    let raf;
    const draw = () => {
      const ctx = canvasRef.current?.getContext("2d");
      if (!ctx) {
        raf = requestAnimationFrame(draw);
        return;
      }
      const w = canvasW;
      const h = canvasH;
      ctx.clearRect(0, 0, w, h);

      // Background: live feed or dark placeholder
      if (imgRef.current && imgRef.current.naturalWidth > 0 && imgRef.current.complete) {
        try {
          ctx.drawImage(imgRef.current, 0, 0, w, h);
        } catch {
          // Image not ready yet, draw placeholder instead
          ctx.fillStyle = "#1a1a2e";
          ctx.fillRect(0, 0, w, h);
        }
      } else {
        ctx.fillStyle = "#1a1a2e";
        ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = "#aaa";
        ctx.font = "16px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(
          streamOk ? "Loading camera…" : "Camera stream offline – klik untuk menambah titik ROI",
          w / 2,
          h / 2
        );
      }

      // Semi-transparent overlay outside ROI
      if (pts.length >= 3) {
        // Draw filled polygon (semi-transparent green)
        ctx.save();
        ctx.beginPath();
        pts.forEach(([x, y], i) => {
          const sx = x * scale;
          const sy = y * scale;
          if (i === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        });
        ctx.closePath();
        ctx.fillStyle = "rgba(0, 200, 100, 0.15)";
        ctx.fill();
        ctx.restore();
      }

      // Draw polygon edges
      if (pts.length >= 2) {
        ctx.beginPath();
        ctx.strokeStyle = "#00e676";
        ctx.lineWidth = 2;
        pts.forEach(([x, y], i) => {
          const sx = x * scale;
          const sy = y * scale;
          if (i === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        });
        if (pts.length >= 3) ctx.closePath();
        ctx.stroke();

        // Draw dashed line to show direction
        ctx.setLineDash([6, 4]);
        ctx.strokeStyle = "rgba(255,255,255,0.3)";
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Draw vertices
      pts.forEach(([x, y], i) => {
        const sx = x * scale;
        const sy = y * scale;
        const isHovered = i === hovered;
        const isDragging = i === dragging;
        const radius = isDragging ? 9 : isHovered ? 8 : 6;

        // Outer ring
        ctx.beginPath();
        ctx.arc(sx, sy, radius + 2, 0, Math.PI * 2);
        ctx.fillStyle = isDragging
          ? "rgba(255, 255, 0, 0.6)"
          : isHovered
          ? "rgba(255, 100, 100, 0.6)"
          : "rgba(255, 255, 255, 0.4)";
        ctx.fill();

        // Inner circle
        ctx.beginPath();
        ctx.arc(sx, sy, radius, 0, Math.PI * 2);
        ctx.fillStyle = isDragging
          ? "#ffeb3b"
          : isHovered
          ? "#ff5252"
          : "#00e676";
        ctx.fill();

        // Point number label
        ctx.fillStyle = "#fff";
        ctx.font = "bold 11px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(i + 1), sx, sy);
      });

      // Edge midpoints (click to insert new point)
      if (pts.length >= 2) {
        for (let i = 0; i < pts.length; i++) {
          const next = (i + 1) % pts.length;
          if (next === 0 && pts.length < 3) continue;
          const mx = ((pts[i][0] + pts[next][0]) / 2) * scale;
          const my = ((pts[i][1] + pts[next][1]) / 2) * scale;
          ctx.beginPath();
          ctx.arc(mx, my, 4, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(255, 255, 255, 0.3)";
          ctx.fill();
          ctx.strokeStyle = "rgba(0, 230, 118, 0.5)";
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      // Coordinate tooltip
      if (hovered >= 0 && hovered < pts.length) {
        const [px, py] = pts[hovered];
        const sx = px * scale;
        const sy = py * scale;
        const label = `[${Math.round(px)}, ${Math.round(py)}]`;
        ctx.font = "12px monospace";
        const tw = ctx.measureText(label).width;
        const tx = sx + 14;
        const ty = sy - 14;
        ctx.fillStyle = "rgba(0,0,0,0.75)";
        ctx.fillRect(tx - 4, ty - 12, tw + 8, 18);
        ctx.fillStyle = "#fff";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(label, tx, ty);
      }

      // Instructions overlay at bottom
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(0, h - 28, w, 28);
      ctx.fillStyle = "#ddd";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(
        `Klik = tambah titik  |  Drag = geser titik  |  Klik kanan = hapus titik  |  Titik: ${pts.length}`,
        w / 2,
        h - 14
      );

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [canvasW, canvasH, pts, scale, hovered, dragging, streamOk]);

  /* ───────── Mouse helpers ───────── */
  const toNative = useCallback(
    (e) => {
      const rect = canvasRef.current.getBoundingClientRect();
      return [(e.clientX - rect.left) / scale, (e.clientY - rect.top) / scale];
    },
    [scale]
  );

  const findPoint = useCallback(
    (nx, ny, threshold = 12) => {
      const thr = threshold / scale;
      for (let i = 0; i < pts.length; i++) {
        const dx = pts[i][0] - nx;
        const dy = pts[i][1] - ny;
        if (Math.sqrt(dx * dx + dy * dy) < thr) return i;
      }
      return -1;
    },
    [pts, scale]
  );

  // Find midpoint of an edge (to insert a new point between two existing ones)
  const findMidpoint = useCallback(
    (nx, ny, threshold = 12) => {
      if (pts.length < 2) return -1;
      const thr = threshold / scale;
      for (let i = 0; i < pts.length; i++) {
        const next = (i + 1) % pts.length;
        if (next === 0 && pts.length < 3) continue;
        const mx = (pts[i][0] + pts[next][0]) / 2;
        const my = (pts[i][1] + pts[next][1]) / 2;
        const dx = mx - nx;
        const dy = my - ny;
        if (Math.sqrt(dx * dx + dy * dy) < thr) return i + 1; // insert after index i
      }
      return -1;
    },
    [pts, scale]
  );

  /* ───────── Event handlers ───────── */
  const handleMouseDown = useCallback(
    (e) => {
      e.preventDefault();
      const [nx, ny] = toNative(e);

      // Right click → delete nearest point
      if (e.button === 2) {
        const idx = findPoint(nx, ny, 16);
        if (idx >= 0) {
          pushHistory();
          const newPts = pts.filter((_, i) => i !== idx);
          commit(newPts);
        }
        return;
      }

      // Left click
      const idx = findPoint(nx, ny);
      if (idx >= 0) {
        // Start dragging existing point
        setDragging(idx);
        return;
      }

      // Check if clicking on a midpoint to insert
      const midIdx = findMidpoint(nx, ny);
      if (midIdx >= 0) {
        pushHistory();
        const newPts = [...pts];
        newPts.splice(midIdx, 0, [Math.round(nx), Math.round(ny)]);
        commit(newPts);
        setDragging(midIdx);
        return;
      }

      // Otherwise add a new point at the end
      pushHistory();
      commit([...pts, [Math.round(nx), Math.round(ny)]]);
    },
    [pts, toNative, findPoint, findMidpoint, pushHistory, commit]
  );

  const handleMouseMove = useCallback(
    (e) => {
      const [nx, ny] = toNative(e);

      if (dragging >= 0) {
        const newPts = pts.map((p, i) =>
          i === dragging ? [Math.round(nx), Math.round(ny)] : p
        );
        // Direct set without commit (commit on mouseUp for perf)
        setPts(newPts);
        return;
      }

      setHovered(findPoint(nx, ny));
    },
    [dragging, pts, toNative, findPoint]
  );

  const handleMouseUp = useCallback(() => {
    if (dragging >= 0) {
      pushHistory();
      commit(pts); // final position
      setDragging(-1);
    }
  }, [dragging, pts, pushHistory, commit]);

  const handleContextMenu = useCallback((e) => e.preventDefault(), []);

  const handleDoubleClick = useCallback(
    (e) => {
      e.preventDefault();
      const [nx, ny] = toNative(e);
      const idx = findPoint(nx, ny, 16);
      if (idx >= 0) {
        pushHistory();
        commit(pts.filter((_, i) => i !== idx));
      }
    },
    [pts, toNative, findPoint, pushHistory, commit]
  );

  /* ───────── Keyboard shortcuts ───────── */
  useEffect(() => {
    const handler = (e) => {
      // Ctrl+Z → undo
      if (e.ctrlKey && e.key === "z") {
        e.preventDefault();
        undo();
        return;
      }
      // Delete → clear all
      if (e.key === "Delete") {
        pushHistory();
        commit([]);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [undo, pushHistory, commit]);

  /* ───────── Preset buttons ───────── */
  const setFullFrame = () => {
    pushHistory();
    commit([
      [50, 50],
      [1230, 50],
      [1230, 670],
      [50, 670],
    ]);
  };
  const setGateCenter = () => {
    pushHistory();
    commit([
      [400, 150],
      [880, 150],
      [880, 600],
      [400, 600],
    ]);
  };
  const setDoorLeft = () => {
    pushHistory();
    commit([
      [50, 100],
      [500, 100],
      [500, 670],
      [50, 670],
    ]);
  };
  const clearAll = () => {
    pushHistory();
    commit([]);
  };

  return (
    <div className="space-y-3">
      {/* Hidden img for MJPEG stream — browser decodes multipart natively */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={hiddenImgRef}
        alt=""
        style={{ display: "none" }}
        crossOrigin="anonymous"
      />

      {/* Toolbar */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-sm font-semibold opacity-70 mr-1">Preset:</span>
        <button className="btn btn-xs btn-outline" onClick={setFullFrame}>
          Full Frame
        </button>
        <button className="btn btn-xs btn-outline" onClick={setGateCenter}>
          Gate Tengah
        </button>
        <button className="btn btn-xs btn-outline" onClick={setDoorLeft}>
          Pintu Kiri
        </button>
        <div className="flex-1" />
        <button
          className="btn btn-xs btn-ghost"
          onClick={undo}
          disabled={history.length === 0}
          title="Undo (Ctrl+Z)"
        >
          ↩ Undo
        </button>
        <button
          className="btn btn-xs btn-error btn-outline"
          onClick={clearAll}
          disabled={pts.length === 0}
        >
          ✕ Clear
        </button>
      </div>

      {/* Canvas container */}
      <div
        ref={containerRef}
        className="relative w-full border-2 border-base-300 rounded-sm overflow-hidden bg-base-300"
        style={{ aspectRatio: `${NATIVE_W}/${NATIVE_H}` }}
      >
        <canvas
          ref={canvasRef}
          width={canvasW}
          height={canvasH}
          className="block w-full h-full cursor-crosshair"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onContextMenu={handleContextMenu}
          onDoubleClick={handleDoubleClick}
        />

        {/* Stream status badge */}
        <div className="absolute top-2 left-2">
          <span
            className={`badge badge-sm ${
              streamOk ? "badge-success" : "badge-error"
            } gap-1`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                streamOk ? "bg-green-300 animate-pulse" : "bg-red-300"
              }`}
            />
            {streamOk ? "LIVE" : "OFFLINE"}
          </span>
        </div>

        {/* Point count badge */}
        <div className="absolute top-2 right-2">
          <span className="badge badge-sm badge-neutral">
            {pts.length} titik
          </span>
        </div>
      </div>

      {/* Point list (compact) */}
      {pts.length > 0 && (
        <div className="bg-base-200 rounded-sm p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold opacity-70">
              Koordinat Titik ROI ({NATIVE_W}×{NATIVE_H})
            </span>
            <span className="text-xs opacity-50 font-mono">
              {JSON.stringify(pts)}
            </span>
          </div>
          <div className="flex flex-wrap gap-1">
            {pts.map(([x, y], i) => (
              <span
                key={i}
                className="badge badge-sm badge-outline font-mono cursor-pointer hover:badge-error"
                title="Klik untuk hapus"
                onClick={() => {
                  pushHistory();
                  commit(pts.filter((_, j) => j !== i));
                }}
              >
                P{i + 1}: [{x},{y}]
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
