"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { fetchSummary, fetchDaily } from "@/services/stats.service";
import { todayISO } from "@/lib/utils";
import { POLL_INTERVAL } from "@/lib/constants";

/**
 * Hook that polls stats every POLL_INTERVAL ms and exposes
 * summary + daily data, plus manual reload and date range filter.
 */
export function useStats() {
  const [summary, setSummary] = useState(null);
  const [daily, setDaily] = useState([]);
  const [error, setError] = useState("");
  const today = useMemo(() => todayISO(), []);
  
  // Date filter state
  const [filterFrom, setFilterFrom] = useState(today);
  const [filterTo, setFilterTo] = useState(today);
  const [filterMode, setFilterMode] = useState("today"); // "today" | "range"

  const load = useCallback(async () => {
    setError("");
    try {
      if (filterMode === "range" && filterFrom && filterTo) {
        // Range mode: fetch daily stats for the range
        const dailyData = await fetchDaily(null, filterFrom, filterTo);
        setDaily(dailyData);
        // Calculate summary from daily data
        setSummary({
          date: filterFrom,
          total_events: dailyData.reduce((s, r) => s + r.total_events, 0),
          unique_visitors: dailyData.reduce((s, r) => s + r.unique_visitors, 0),
          total_in: dailyData.reduce((s, r) => s + r.total_in, 0),
          total_out: dailyData.reduce((s, r) => s + r.total_out, 0),
        });
      } else {
        // Today mode
        const [summaryData, dailyData] = await Promise.all([
          fetchSummary(today).catch(() => null),
          fetchDaily(today),
        ]);
        if (summaryData) setSummary(summaryData);
        setDaily(dailyData);
      }
    } catch (e) {
      setError(e.message || "Failed to load stats");
    }
  }, [today, filterMode, filterFrom, filterTo]);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_INTERVAL);
    return () => clearInterval(t);
  }, [load]);

  const totalEvents = summary?.total_events || daily.reduce((s, r) => s + r.total_events, 0);
  const uniqueVisitors = summary?.unique_visitors || daily.reduce((s, r) => s + r.unique_visitors, 0);
  const totalIn = summary?.total_in || daily.reduce((s, r) => s + r.total_in, 0);
  const totalOut = summary?.total_out || daily.reduce((s, r) => s + r.total_out, 0);

  const day = filterMode === "range" ? `${filterFrom} s/d ${filterTo}` : today;

  return {
    day,
    today,
    summary,
    daily,
    totalEvents,
    uniqueVisitors,
    totalIn,
    totalOut,
    error,
    reload: load,
    // Filter controls
    filterMode,
    setFilterMode,
    filterFrom,
    setFilterFrom,
    filterTo,
    setFilterTo,
  };
}
