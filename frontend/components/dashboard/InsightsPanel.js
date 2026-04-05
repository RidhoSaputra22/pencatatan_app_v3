"use client";

export default function InsightsPanel({ insights = {} }) {
  const { busyLabel, busyPercent, peakHour, ratio } = insights;
  const hasData = busyLabel || peakHour || ratio;

  if (!hasData) return null;

  return (
    <div className="flex flex-wrap gap-3">
      {/* Busy/Quiet indicator */}
      {busyLabel && busyPercent !== null && (
        <div
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium ${
            busyLabel === "ramai"
              ? "bg-success/10 text-success"
              : "bg-error/10 text-error"
          }`}
        >
          {busyLabel === "ramai" ? (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
            </svg>
          )}
          Hari ini lebih {busyLabel} {Math.abs(busyPercent)}% dari kemarin
        </div>
      )}

      {/* Peak hour */}
      {peakHour && (
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-warning/10 text-warning">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Jam terpadat: {peakHour}
        </div>
      )}

      {/* In/Out ratio */}
      {ratio && (
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-info/10 text-info">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
          </svg>
          Rasio masuk : keluar = {ratio} : 1
        </div>
      )}
    </div>
  );
}
