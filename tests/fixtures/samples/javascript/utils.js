/**
 * Utility functions for common operations.
 * @module utils
 */

/**
 * Debounce function execution to limit rapid calls.
 * @param {Function} fn - The function to debounce.
 * @param {number} delay - Delay in milliseconds.
 * @returns {Function} Debounced function.
 */
function debounce(fn, delay) {
  let timeoutId = null;

  return function debounced(...args) {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      fn.apply(this, args);
      timeoutId = null;
    }, delay);
  };
}

/**
 * Throttle function execution to a maximum rate.
 * @param {Function} fn - The function to throttle.
 * @param {number} limit - Minimum time between calls in ms.
 * @returns {Function} Throttled function.
 */
function throttle(fn, limit) {
  let lastCall = 0;
  let timeoutId = null;

  return function throttled(...args) {
    const now = Date.now();
    const remaining = limit - (now - lastCall);

    if (remaining <= 0) {
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      lastCall = now;
      fn.apply(this, args);
    } else if (timeoutId === null) {
      timeoutId = setTimeout(() => {
        lastCall = Date.now();
        timeoutId = null;
        fn.apply(this, args);
      }, remaining);
    }
  };
}

/**
 * Deep clone an object or array.
 * @param {*} obj - The value to clone.
 * @returns {*} A deep copy of the value.
 */
function deepClone(obj) {
  if (obj === null || typeof obj !== "object") {
    return obj;
  }

  if (obj instanceof Date) {
    return new Date(obj.getTime());
  }

  if (obj instanceof RegExp) {
    return new RegExp(obj.source, obj.flags);
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => deepClone(item));
  }

  const cloned = {};
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      cloned[key] = deepClone(obj[key]);
    }
  }

  return cloned;
}

/**
 * Safely get a nested property from an object.
 * @param {Object} obj - The source object.
 * @param {string} path - Dot-notation path to the property.
 * @param {*} defaultValue - Value to return if property is undefined.
 * @returns {*} The property value or default.
 */
function getNestedValue(obj, path, defaultValue = undefined) {
  if (!obj || typeof path !== "string") {
    return defaultValue;
  }

  const keys = path.split(".");
  let result = obj;

  for (const key of keys) {
    if (result === null || result === undefined) {
      return defaultValue;
    }
    result = result[key];
  }

  return result === undefined ? defaultValue : result;
}

/**
 * Format a number with thousands separators.
 * @param {number} num - The number to format.
 * @param {string} locale - Locale for formatting (default: 'en-US').
 * @returns {string} Formatted number string.
 */
function formatNumber(num, locale = "en-US") {
  if (typeof num !== "number" || isNaN(num)) {
    return "0";
  }
  return new Intl.NumberFormat(locale).format(num);
}

/**
 * Generate a random string of specified length.
 * @param {number} length - Desired string length.
 * @param {string} charset - Characters to use (default: alphanumeric).
 * @returns {string} Random string.
 */
function randomString(
  length = 16,
  charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
) {
  let result = "";
  const charsetLength = charset.length;

  for (let i = 0; i < length; i++) {
    result += charset.charAt(Math.floor(Math.random() * charsetLength));
  }

  return result;
}

/**
 * Retry an async function with exponential backoff.
 * @param {Function} fn - Async function to retry.
 * @param {number} maxRetries - Maximum number of attempts.
 * @param {number} baseDelay - Base delay in ms (doubles each retry).
 * @returns {Promise<*>} Result of the function.
 */
async function retryWithBackoff(fn, maxRetries = 3, baseDelay = 1000) {
  let lastError;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      if (attempt < maxRetries - 1) {
        const delay = baseDelay * Math.pow(2, attempt);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError;
}

module.exports = {
  debounce,
  throttle,
  deepClone,
  getNestedValue,
  formatNumber,
  randomString,
  retryWithBackoff,
};
