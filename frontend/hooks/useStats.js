"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { fetchSummary, fetchDaily, fetchStatsPerSecond } from "@/services/stats.service";
import { todayISO, yesterdayISO, formatDate } from "@/lib/utils";
import { POLL_INTERVAL } from "@/lib/constants";

/**
 * Compute date range for filter presets.
 */
function getPresetRange(mode, today) {
  const t = new Date(today + "T00:00:00");
  switch (mode) {
    case "yesterday": {
      const y = new Date(t);
      y.setDate(y.getDate() - 1);
      const d = formatDate(y);
      return [d, d];
    }
    case "7days": {
      const from = new Date(t);
      from.setDate(from.getDate() - 6);
      return [formatDate(from), today];
    }
    case "30days": {
      const from = new Date(t);
      from.setDate(from.getDate() - 29);
      return [formatDate(from), today];
    }
    case "month": {
      const from = new Date(t.getFullYear(), t.getMonth(), 1);
      return [formatDate(from), today];
    }
    default:
      return [today, today];
  }
}

/**
 * Aggregate per-second data into hourly buckets.
 */
function aggregateHourly(perSecondData) {
  const buckets = {};
  for (let h = 0; h < 24; h++) {
    const label = String(h).padStart(2, "0") + ":00";
    buckets[label] = 0;
  }
  for (const r of perSecondData) {
    const hour = r.second.slice(11, 13) + ":00";
    if (buckets[hour] !== undefined) {
      buckets[hour] += r.count;
    }
  }
  const labels = Object.keys(buckets);
  const data = Object.values(buckets);
  return { labels, data };
}

/**
 * Compute insight data from stats.
 */
function computeInsights(totalEvents, yesterdayEvents, hourlyData, totalIn, totalOut) {
  // Busier / quieter
  let busyLabel = null;
  let busyPercent = null;
  if (yesterdayEvents > 0) {
    const diff = ((totalEvents - yesterdayEvents) / yesterdayEvents) * 100;
    busyPercent = Math.round(diff);
    busyLabel = diff >= 0 ? "ramai" : "sepi";
  }

  // Peak hour
  let peakHour = null;
  if (hourlyData && hourlyData.labels.length > 0) {
    let maxVal = 0;
    let maxIdx = 0;
    hourlyData.data.forEach((v, i) => {
      if (v > maxVal) { maxVal = v; maxIdx = i; }
    });
    if (maxVal > 0) {
      peakHour = hourlyData.labels[maxIdx];
    }
  }

  // In/Out ratio
  let ratio = null;
  if (totalOut > 0) {
    ratio = (totalIn / totalOut).toFixed(1);
  } else if (totalIn > 0) {
    ratio = totalIn.toString();
  }

  return { busyLabel, busyPercent, peakHour, ratio };
}

/**
 * Hook that polls stats every POLL_INTERVAL ms and exposes
 * summary + daily data with yesterday comparison, hourly aggregation,
 * insights, and date filter presets.
 */
export function useStats() {
  const [summary, setSummary] = useState(null);
  const [yesterdaySummary, setYesterdaySummary] = useState(null);
  const [daily, setDaily] = useState([]);
  const [perSecond, setPerSecond] = useState([]);
  const [error, setError] = useState("");
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const today = useMemo(() => todayISO(), []);
  const yesterday = useMemo(() => yesterdayISO(), []);

  // Date filter state
  const [filterFrom, setFilterFrom] = useState(today);
  const [filterTo, setFilterTo] = useState(today);
  const [filterMode, setFilterMode] = useState("today");
  // "today" | "yesterday" | "7days" | "30days" | "month" | "range"

  // When filterMode changes (non-range), auto-compute from/to
  const handleSetFilterMode = useCallback((mode) => {
    setFilterMode(mode);
    if (mode === "today") {
      setFilterFrom(today);
      setFilterTo(today);
    } else if (mode !== "range") {
      const [from, to] = getPresetRange(mode, today);
      setFilterFrom(from);
      setFilterTo(to);
    }
  }, [today]);

  const load = useCallback(async () => {
    setError("");
    try {
      const isSingleDay = filterMode === "today" || filterMode === "yesterday";

      if (isSingleDay) {
        const targetDay = filterMode === "today" ? today : filterFrom;
        const [summaryData, dailyData, yesterdayData] = await Promise.all([
          fetchSummary(targetDay).catch(() => null),
          fetchDaily(targetDay),
          fetchSummary(yesterday).catch(() => null),
        ]);
        if (summaryData) setSummary(summaryData);
        setDaily(dailyData);
        setYesterdaySummary(yesterdayData);

        // Fetch per-second data for hourly aggregation (only for today)
        if (filterMode === "today") {
          try {
            const ps = await fetchStatsPerSecond(today);
            setPerSecond(ps || []);
          } catch {
            setPerSecond([]);
          }
        } else {
          setPerSecond([]);
        }
      } else {
        // Range modes (7days, 30days, month, range)
        const [dailyData, yesterdayData] = await Promise.all([
          fetchDaily(null, filterFrom, filterTo),
          fetchSummary(yesterday).catch(() => null),
        ]);
        setDaily(dailyData);
        setYesterdaySummary(yesterdayData);
        setSummary({
          date: filterFrom,
          total_events: dailyData.reduce((s, r) => s + r.total_events, 0),
          unique_visitors: dailyData.reduce((s, r) => s + r.unique_visitors, 0),
          total_in: dailyData.reduce((s, r) => s + r.total_in, 0),
          total_out: dailyData.reduce((s, r) => s + r.total_out, 0),
        });
        setPerSecond([]);
      }

      setLastUpdatedAt(new Date());
    } catch (e) {
      setError(e.message || "Failed to load stats");
    }
  }, [today, yesterday, filterMode, filterFrom, filterTo]);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_INTERVAL);
    return () => clearInterval(t);
  }, [load]);

  const totalEvents = summary?.total_events || daily.reduce((s, r) => s + r.total_events, 0);
  const uniqueVisitors = summary?.unique_visitors || daily.reduce((s, r) => s + r.unique_visitors, 0);
  const totalIn = summary?.total_in || daily.reduce((s, r) => s + r.total_in, 0);
  const totalOut = summary?.total_out || daily.reduce((s, r) => s + r.total_out, 0);

  // Yesterday values for comparison
  const yTotalEvents = yesterdaySummary?.total_events || 0;
  const yUniqueVisitors = yesterdaySummary?.unique_visitors || 0;
  const yTotalIn = yesterdaySummary?.total_in || 0;
  const yTotalOut = yesterdaySummary?.total_out || 0;

  // Compute change percentages
  const calcChange = (current, prev) => {
    if (!prev || prev === 0) return null;
    return Math.round(((current - prev) / prev) * 100);
  };
  const changePercents = {
    totalEvents: calcChange(totalEvents, yTotalEvents),
    uniqueVisitors: calcChange(uniqueVisitors, yUniqueVisitors),
    totalIn: calcChange(totalIn, yTotalIn),
    totalOut: calcChange(totalOut, yTotalOut),
  };

  // Hourly aggregation from per-second data
  const hourlyData = useMemo(() => aggregateHourly(perSecond), [perSecond]);

  // Insights
  const insights = useMemo(
    () => computeInsights(totalEvents, yTotalEvents, hourlyData, totalIn, totalOut),
    [totalEvents, yTotalEvents, hourlyData, totalIn, totalOut]
  );

  const day = filterMode === "today"
    ? today
    : filterMode === "yesterday"
      ? yesterday
      : filterMode === "range"
        ? `${filterFrom} s/d ${filterTo}`
        : `${filterFrom} s/d ${filterTo}`;

  return {
    day,
    today,
    summary,
    daily,
    perSecond,
    hourlyData,
    totalEvents,
    uniqueVisitors,
    totalIn,
    totalOut,
    changePercents,
    insights,
    lastUpdatedAt,
    error,
    reload: load,
    filterMode,
    setFilterMode: handleSetFilterMode,
    filterFrom,
    setFilterFrom,
    filterTo,
    setFilterTo,
  };
}
