import React, { useState } from "react";

/**
 * Select component styled after ui-laravel/select.blade.php
 * @param {object} props
 * @param {string} props.label
 * @param {Array<{value:string,label:string}>} props.options
 * @param {string} props.value
 * @param {function} props.onChange
 * @param {string} props.placeholder
 * @param {string} props.error
 * @param {boolean} props.required
 * @param {boolean} props.searchable
 * @param {string} props.searchPlaceholder
 * @param {string} props.className
 */
export default function Select({
  label,
  options = [],
  value = "",
  onChange,
  placeholder = "Pilih...",
  error = null,
  required = false,
  searchable = false,
  searchPlaceholder = "Cari...",
  className = "",
  name,
  ...rest
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const filteredOptions = searchable
    ? options.filter((o) =>
        o.label.toLowerCase().includes(searchTerm.toLowerCase()),
      )
    : options;

  return (
    <div className={`form-control w-full ${className}`}>
      {label && (
        <label className="label" htmlFor={name}>
          <span className="label-text">
            {label}
            {required && <span className="text-error ml-1">*</span>}
          </span>
        </label>
      )}
      {searchable && (
        <input
          type="text"
          className="input input-bordered mb-2"
          placeholder={searchPlaceholder}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      )}
      <select
        id={name}
        name={name}
        value={value}
        onChange={onChange}
        required={required}
        className={`select select-bordered w-full${error ? " select-error" : ""}`}
        {...rest}
      >
        <option value="" disabled>
          {placeholder}
        </option>
        {filteredOptions.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && (
        <label className="label">
          <span className="label-text-alt text-error">{error}</span>
        </label>
      )}
    </div>
  );
}
