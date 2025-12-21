/**
 * React component library for user interface elements.
 * Provides accessible, customizable UI components with hooks.
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
  createContext,
  useContext,
} from "react";

// ============================================================================
// Types and Interfaces
// ============================================================================

/** Button variant styles */
type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

/** Button sizes */
type ButtonSize = "sm" | "md" | "lg";

/** Button component props */
interface ButtonProps {
  /** Button content */
  children: React.ReactNode;
  /** Visual style variant */
  variant?: ButtonVariant;
  /** Button size */
  size?: ButtonSize;
  /** Disabled state */
  disabled?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Click handler */
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  /** Optional CSS class */
  className?: string;
  /** Accessible label */
  ariaLabel?: string;
  /** Button type */
  type?: "button" | "submit" | "reset";
}

/** Theme context value */
interface ThemeContextValue {
  isDark: boolean;
  toggleTheme: () => void;
  colors: {
    primary: string;
    secondary: string;
    background: string;
    text: string;
  };
}

// ============================================================================
// Contexts
// ============================================================================

/** Default theme values */
const lightTheme = {
  primary: "#0066cc",
  secondary: "#6c757d",
  background: "#ffffff",
  text: "#212529",
};

const darkTheme = {
  primary: "#4dabf7",
  secondary: "#adb5bd",
  background: "#1a1a1a",
  text: "#f8f9fa",
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

/**
 * Hook to access theme context.
 * @throws Error if used outside ThemeProvider.
 */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}

// ============================================================================
// Components
// ============================================================================

/**
 * Theme provider component for application-wide theming.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== "undefined") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    }
    return false;
  });

  const toggleTheme = useCallback(() => {
    setIsDark((prev) => !prev);
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({
      isDark,
      toggleTheme,
      colors: isDark ? darkTheme : lightTheme,
    }),
    [isDark, toggleTheme]
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

/**
 * Accessible button component with loading and variant support.
 */
export function Button({
  children,
  variant = "primary",
  size = "md",
  disabled = false,
  loading = false,
  onClick,
  className = "",
  ariaLabel,
  type = "button",
}: ButtonProps) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const { colors } = useTheme();

  const sizeStyles = useMemo(() => {
    switch (size) {
      case "sm":
        return { padding: "4px 8px", fontSize: "12px" };
      case "lg":
        return { padding: "12px 24px", fontSize: "18px" };
      default:
        return { padding: "8px 16px", fontSize: "14px" };
    }
  }, [size]);

  const variantStyles = useMemo(() => {
    switch (variant) {
      case "secondary":
        return {
          backgroundColor: colors.secondary,
          color: "#fff",
        };
      case "danger":
        return {
          backgroundColor: "#dc3545",
          color: "#fff",
        };
      case "ghost":
        return {
          backgroundColor: "transparent",
          color: colors.primary,
          border: `1px solid ${colors.primary}`,
        };
      default:
        return {
          backgroundColor: colors.primary,
          color: "#fff",
        };
    }
  }, [variant, colors]);

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      if (!disabled && !loading && onClick) {
        onClick(event);
      }
    },
    [disabled, loading, onClick]
  );

  return (
    <button
      ref={buttonRef}
      type={type}
      disabled={disabled || loading}
      onClick={handleClick}
      aria-label={ariaLabel}
      aria-busy={loading}
      className={className}
      style={{
        ...sizeStyles,
        ...variantStyles,
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: disabled ? 0.6 : 1,
        borderRadius: "4px",
        border: variant === "ghost" ? undefined : "none",
        transition: "all 0.2s ease",
      }}
    >
      {loading ? <span aria-hidden="true">Loading...</span> : children}
    </button>
  );
}

// ============================================================================
// Custom Hooks
// ============================================================================

/**
 * Hook for managing async operations with loading and error states.
 */
export function useAsync<T>(
  asyncFn: () => Promise<T>,
  dependencies: React.DependencyList = []
) {
  const [state, setState] = useState<{
    data: T | null;
    loading: boolean;
    error: Error | null;
  }>({
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let mounted = true;

    const execute = async () => {
      setState((prev) => ({ ...prev, loading: true, error: null }));

      try {
        const result = await asyncFn();
        if (mounted) {
          setState({ data: result, loading: false, error: null });
        }
      } catch (err) {
        if (mounted) {
          setState({
            data: null,
            loading: false,
            error: err instanceof Error ? err : new Error(String(err)),
          });
        }
      }
    };

    execute();

    return () => {
      mounted = false;
    };
  }, dependencies);

  return state;
}

/**
 * Hook for debouncing a value.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Hook for tracking previous value.
 */
export function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>();

  useEffect(() => {
    ref.current = value;
  }, [value]);

  return ref.current;
}
