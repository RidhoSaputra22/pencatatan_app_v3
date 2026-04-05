/**
 * Token management utilities
 */

const TOKEN_KEY = "auth_token";

/**
 * Get the authentication token from localStorage
 * @returns {string|null}
 */
export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Store the authentication token in localStorage
 * @param {string} token
 */
export function setToken(token) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Remove the authentication token from localStorage
 */
export function removeToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Check if user is authenticated (has token)
 * @returns {boolean}
 */
export function isAuthenticated() {
  return !!getToken();
}

/**
 * Get today's date in ISO format (YYYY-MM-DD)
 * @returns {string}
 */
export function todayISO() {
  return formatDate(new Date());
}

/**
 * Get yesterday's date in ISO format (YYYY-MM-DD)
 * @returns {string}
 */
export function yesterdayISO() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return formatDate(d);
}

/**
 * Format date to YYYY-MM-DD
 * @param {Date} date
 * @returns {string}
 */
export function formatDate(date) {
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/**
 * Format datetime to readable string
 * @param {string|Date} datetime
 * @returns {string}
 */
export function formatDateTime(datetime) {
  const date = new Date(datetime);
  return new Intl.DateTimeFormat("id-ID", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/**
 * Format number with thousand separator
 * @param {number} num
 * @returns {string}
 */
export function formatNumber(num) {
  return new Intl.NumberFormat("id-ID").format(num);
}

/**
 * Debounce function
 * @param {Function} func
 * @param {number} wait
 * @returns {Function}
 */
export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Combine class names
 * @param {...string} classes
 * @returns {string}
 */
export function cn(...classes) {
  return classes.filter(Boolean).join(" ");
}
