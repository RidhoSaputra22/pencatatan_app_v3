/**
 * Reusable labelled input using DaisyUI.
 */
import React, { useState } from "react";

/**
 * Input component styled after ui-laravel/input.blade.php
 * @param {object} props
 * @param {string} props.label
 * @param {string} props.type
 * @param {string} props.placeholder
 * @param {string} props.value
 * @param {function} props.onChange
 * @param {string} props.error
 * @param {boolean} props.required
 * @param {string} props.helpText
 * @param {string} props.className
 */
export default function Input({
  label,
  type = "text",
  placeholder = "",
  value = "",
  onChange,
  error = null,
  required = false,
  helpText = null,
  className = "",
  name,
  ...rest
}) {
  const [showPassword, setShowPassword] = useState(false);
  const inputType = type === "password" && showPassword ? "text" : type;
  const inputId = name || label || Math.random().toString(36).slice(2, 10);

  return (
    <div className="form-control w-full">
      {label && (
        <label className="label" htmlFor={inputId}>
          <span className="label-text font-medium">
            {label}
            {required && <span className="text-error ml-1">*</span>}
          </span>
        </label>
      )}
      {helpText && !error && (
        <label className="label">
          <span className="text-sm font-light label-text-alt text-base-content/70">
            - {helpText}
          </span>
        </label>
      )}
      {type === "password" ? (
        <div className="relative">
          <input
            type={inputType}
            id={inputId}
            name={name}
            placeholder={placeholder}
            value={value}
            onChange={onChange}
            required={required}
            className={`input input-bordered w-full pr-12${error ? " input-error" : ""} ${className}`}
            {...rest}
          />
          <button
            type="button"
            tabIndex={-1}
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-base-content/60 hover:text-base-content transition-colors"
          >
            {showPassword ? (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                />
              </svg>
            ) : (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                />
              </svg>
            )}
          </button>
        </div>
      ) : (
        <input
          type={type}
          id={inputId}
          name={name}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          required={required}
          className={`input input-bordered w-full${error ? " input-error" : ""} ${className}`}
          {...rest}
        />
      )}
      {error && (
        <label className="label">
          <span className="label-text-alt text-error">{error}</span>
        </label>
      )}
    </div>
  );
}
