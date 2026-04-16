"use client";

import { useState } from "react";
import { API_BASE } from "@/lib/constants";
import { formatNumber, getToken } from "@/lib/utils";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatPrintDateTime() {
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "full",
    timeStyle: "medium",
  }).format(new Date());
}

function cleanupPrintFrame(frame) {
  if (frame?.parentNode) {
    frame.parentNode.removeChild(frame);
  }
}

/**
 * Export & print section with actual download and print functionality.
 */
export default function ExportSection({
  filterFrom,
  filterTo,
  day,
  totalEvents = 0,
  uniqueVisitors = 0,
  totalIn = 0,
  totalOut = 0,
  insights = {},
}) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  const fromDay = filterFrom || day;
  const toDay = filterTo || day;

  /**
   * Download CSV file from backend.
   */
  async function handleDownloadCSV() {
    setDownloading(true);
    setError("");
    try {
      const token = getToken();
      const res = await fetch(
        `${API_BASE}/api/reports/csv?from_day=${fromDay}&to_day=${toDay}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) {
        throw new Error("Gagal download CSV");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `laporan_pengunjung_${fromDay}_${toDay}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message || "Gagal download");
    } finally {
      setDownloading(false);
    }
  }

  /**
   * Print the current dashboard stats.
   */
  function handlePrint() {
    setError("");
    const statsTable = document.querySelector("table");
    const printedAt = formatPrintDateTime();
    const summaryCards = [
      {
        label: "Total Aktivitas",
        value: formatNumber(totalEvents),
        tone: "#2563eb",
      },
      {
        label: "Pengunjung Unik",
        value: formatNumber(uniqueVisitors),
        tone: "#0891b2",
      },
      {
        label: "Total Masuk",
        value: formatNumber(totalIn),
        tone: "#16a34a",
      },
      {
        label: "Total Keluar",
        value: formatNumber(totalOut),
        tone: "#dc2626",
      },
    ];

    const insightItems = [
      {
        label: "Jam Tersibuk",
        value: insights?.peakHour || "-",
      },
      {
        label: "Kondisi Hari Ini",
        value:
          insights?.busyLabel && insights?.busyPercent !== null && insights?.busyPercent !== undefined
            ? `${insights.busyLabel} (${insights.busyPercent > 0 ? "+" : ""}${insights.busyPercent}%)`
            : "-",
      },
      {
        label: "Rasio Masuk/Keluar",
        value: insights?.ratio || "-",
      },
    ].filter((item) => item.value && item.value !== "-");

    const printMarkup = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8" />
        <title>Laporan Pengunjung Perpustakaan</title>
        <style>
          @page {
            size: A4 portrait;
            margin: 14mm;
          }

          * {
            box-sizing: border-box;
          }

          body {
            margin: 0;
            font-family: Arial, sans-serif;
            color: #1f2937;
            background: #ffffff;
            font-size: 12px;
            line-height: 1.45;
          }

          .report {
            width: 100%;
          }

          .header {
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 14px;
            margin-bottom: 18px;
          }

          h1 {
            font-size: 22px;
            margin: 0 0 6px;
            color: #111827;
          }

          h2 {
            font-size: 13px;
            color: #4b5563;
            margin: 0;
            font-weight: 600;
          }

          .info {
            margin-top: 8px;
            font-size: 11px;
            color: #6b7280;
          }

          .summary-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin: 18px 0;
          }

          .summary-card {
            border: 1px solid #e5e7eb;
            border-left: 4px solid var(--tone, #2563eb);
            border-radius: 10px;
            padding: 12px 14px;
            background: #f9fafb;
            page-break-inside: avoid;
          }

          .summary-label {
            display: block;
            font-size: 11px;
            color: #6b7280;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-weight: 700;
          }

          .summary-value {
            font-size: 24px;
            line-height: 1.1;
            font-weight: 700;
            color: var(--tone, #111827);
          }

          .section-title {
            font-size: 14px;
            font-weight: 700;
            color: #111827;
            margin: 22px 0 10px;
          }

          .insights {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 8px;
          }

          .insight-card {
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 10px 12px;
            background: #ffffff;
          }

          .insight-label {
            display: block;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #9ca3af;
            margin-bottom: 4px;
            font-weight: 700;
          }

          .insight-value {
            font-size: 13px;
            font-weight: 700;
            color: #1f2937;
          }

          .table-wrap {
            margin-top: 12px;
          }

          table {
            width: 100%;
            border-collapse: collapse;
            table-layout: auto;
          }

          thead {
            display: table-header-group;
          }

          th,
          td {
            border: 1px solid #d1d5db;
            padding: 8px 10px;
            text-align: left;
            vertical-align: top;
            font-size: 11px;
          }

          th {
            background: #f3f4f6;
            color: #111827;
            font-weight: 700;
          }

          tbody tr:nth-child(even) {
            background: #f9fafb;
          }

          tbody tr {
            page-break-inside: avoid;
          }

          .empty-state {
            border: 1px dashed #d1d5db;
            border-radius: 10px;
            padding: 18px;
            color: #6b7280;
            text-align: center;
            background: #f9fafb;
          }

          .footer {
            margin-top: 24px;
            padding-top: 12px;
            border-top: 1px solid #e5e7eb;
            font-size: 10px;
            color: #6b7280;
          }

          @media print {
            body {
              -webkit-print-color-adjust: exact;
              print-color-adjust: exact;
            }
          }
        </style>
      </head>
      <body>
        <main class="report">
          <header class="header">
            <h1>Laporan Monitoring Pengunjung Perpustakaan</h1>
            <h2>Periode: ${escapeHtml(fromDay)} s/d ${escapeHtml(toDay)}</h2>
            <div class="info">Dicetak pada: ${escapeHtml(printedAt)}</div>
          </header>

          <section>
            <div class="summary-grid">
              ${summaryCards
                .map(
                  (item) => `
                    <article class="summary-card" style="--tone:${item.tone}">
                      <span class="summary-label">${escapeHtml(item.label)}</span>
                      <div class="summary-value">${escapeHtml(item.value)}</div>
                    </article>
                  `,
                )
                .join("")}
            </div>
          </section>

          ${
            insightItems.length > 0
              ? `
                <section>
                  <div class="section-title">Ringkasan Aktivitas</div>
                  <div class="insights">
                    ${insightItems
                      .map(
                        (item) => `
                          <article class="insight-card">
                            <span class="insight-label">${escapeHtml(item.label)}</span>
                            <div class="insight-value">${escapeHtml(item.value)}</div>
                          </article>
                        `,
                      )
                      .join("")}
                  </div>
                </section>
              `
              : ""
          }

          <section>
            <div class="section-title">Statistik Per Kamera</div>
            ${
              statsTable
                ? `<div class="table-wrap">${statsTable.outerHTML}</div>`
                : `<div class="empty-state">Tidak ada data tabel untuk dicetak.</div>`
            }
          </section>

          <div class="footer">
            Dokumen ini dicetak dari Sistem Monitoring Pengunjung Perpustakaan.
          </div>
        </main>
      </body>
      </html>
    `;

    const existingFrame = document.getElementById("dashboard-print-frame");
    if (existingFrame) {
      cleanupPrintFrame(existingFrame);
    }

    const printFrame = document.createElement("iframe");
    printFrame.id = "dashboard-print-frame";
    printFrame.title = "Cetak laporan";
    printFrame.setAttribute("aria-hidden", "true");
    printFrame.style.position = "fixed";
    printFrame.style.right = "0";
    printFrame.style.bottom = "0";
    printFrame.style.width = "0";
    printFrame.style.height = "0";
    printFrame.style.border = "0";
    printFrame.style.opacity = "0";
    printFrame.srcdoc = printMarkup;

    printFrame.onload = () => {
      const frameWindow = printFrame.contentWindow;
      if (!frameWindow) {
        setError("Gagal menyiapkan dokumen untuk dicetak.");
        cleanupPrintFrame(printFrame);
        return;
      }

      const handleAfterPrint = () => {
        cleanupPrintFrame(printFrame);
      };

      frameWindow.onafterprint = handleAfterPrint;

      window.setTimeout(() => {
        try {
          frameWindow.focus();
          frameWindow.print();
        } catch {
          setError("Gagal membuka dialog cetak. Coba ulangi sekali lagi.");
          cleanupPrintFrame(printFrame);
        }
      }, 250);
    };

    document.body.appendChild(printFrame);
  }

  return (
    <div className="card bg-gradient-to-r from-base-100 to-primary/5 shadow-lg p-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h3 className="font-bold text-base-content/80 flex items-center gap-2 mb-1">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Export & Cetak Laporan
          </h3>
          <p className="text-xs text-base-content/40">
            Periode: <strong className="text-base-content/60">{fromDay}</strong> s/d <strong className="text-base-content/60">{toDay}</strong>
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" loading={downloading} onClick={handleDownloadCSV}>
            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
            Download CSV
          </Button>
          <Button variant="primary" onClick={handlePrint}>
            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" /></svg>
            Cetak Laporan
          </Button>
        </div>
      </div>

      {error && <div className="mt-3"><Alert variant="error">{error}</Alert></div>}
    </div>
  );
}
