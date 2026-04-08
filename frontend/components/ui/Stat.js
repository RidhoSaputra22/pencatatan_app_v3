import React from "react";

/**
 * Stat card component styled after ui-laravel/stat.blade.php
 * @param {object} props
 * @param {string} props.title
 * @param {string|number} props.value
 * @param {string} props.description
 * @param {React.ReactNode} props.icon
 * @param {"primary"|"success"|"error"|"info"|"warning"|"neutral"} props.tone
 * @param {"up"|"down"|"neutral"} props.trend
 * @param {string} props.trendValue
 * @param {string} props.className
 */
const toneClass = {
  primary: {
    border: "border-l-primary",
    value: "text-primary",
    icon: "text-primary",
  },
  success: {
    border: "border-l-success",
    value: "text-success",
    icon: "text-success",
  },
  error: {
    border: "border-l-error",
    value: "text-error",
    icon: "text-error",
  },
  info: {
    border: "border-l-info",
    value: "text-info",
    icon: "text-info",
  },
  warning: {
    border: "border-l-warning",
    value: "text-warning",
    icon: "text-warning",
  },
  neutral: {
    border: "border-l-slate-400",
    value: "text-slate-700",
    icon: "text-slate-500",
  },
};

const toneIcon = {
  primary: (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="h-7 w-7"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h16.5M3.75 3H2.25m18 0h1.5m-3 13.5H6.75m12 0-1 3m1-3 1 3m-13.5-3-1 3m0 0-.5 1.5m.5-1.5h9.5m-9.5 0-.5 1.5m4.25-10.5 3-3 2.25 2.25 4.5-5.25"
      />
    </svg>
  ),
  success: (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="h-7 w-7"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4.5 10.5 12 3m0 0 7.5 7.5M12 3v18"
      />
    </svg>
  ),
  error: (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="h-7 w-7"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 13.5 12 21m0 0-7.5-7.5M12 21V3"
      />
    </svg>
  ),
  info: (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="h-7 w-7"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z"
      />
    </svg>
  ),
  warning: (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="h-7 w-7"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 0h10.5A2.25 2.25 0 0 1 19.5 12.75v6A2.25 2.25 0 0 1 17.25 21h-10.5A2.25 2.25 0 0 1 4.5 18.75v-6a2.25 2.25 0 0 1 2.25-2.25Z"
      />
    </svg>
  ),
  neutral: (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="h-7 w-7"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10.5 6h9.75M3.75 6h3.75m3 12h9.75m-16.5 0h3.75m-.75-6h13.5m-16.5 0h.75"
      />
    </svg>
  ),
};

export default function Stat({
  title,
  value,
  description = null,
  icon = null,
  tone = "primary",
  trend = null,
  trendValue = null,
  className = "",
  ...rest
}) {
  const currentTone = toneClass[tone] || toneClass.primary;
  const resolvedIcon = icon || toneIcon[tone] || toneIcon.primary;

  return (
    <div
      className={`card h-full border border-base-200 border-l-4 bg-base-100 p-5 shadow-md ${currentTone.border} ${className}`}
      {...rest}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium text-base-content/60">{title}</span>
        <span className={`${currentTone.icon} shrink-0`}>{resolvedIcon}</span>
      </div>
      <div className={`mt-3 text-4xl font-bold tracking-tight ${currentTone.value}`}>
        {value}
      </div>
      {(description || trendValue) && (
        <div className="mt-4 flex items-center justify-between gap-3">
          <span className="text-xs text-base-content/40">{description}</span>
          {trendValue && (
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                trend === "up"
                  ? "bg-success/10 text-success"
                  : trend === "down"
                    ? "bg-error/10 text-error"
                    : "bg-base-200 text-base-content/70"
              }`}
            >
              {trend === "up" && (
                <svg
                  className="h-3 w-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                  />
                </svg>
              )}
              {trend === "down" && (
                <svg
                  className="h-3 w-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"
                  />
                </svg>
              )}
              {trendValue}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
