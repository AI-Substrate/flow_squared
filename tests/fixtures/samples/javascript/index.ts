/**
 * Main entry point aggregating application and UI components.
 *
 * This module demonstrates cross-file relationships for fs2 experimentation:
 * - Cross-file imports from app.ts (Application, AppConfig, etc.)
 * - Cross-file imports from component.tsx (useTheme, ThemeProvider)
 *
 * Note: utils.js is intentionally excluded as it uses CommonJS exports,
 * which are incompatible with ES module imports in TypeScript.
 */

// Cross-file imports from app.ts
import {
  Application,
  AppConfig,
  AppState,
  LogLevel,
  mergeConfig,
  validateConfig,
} from "./app";

// Cross-file imports from component.tsx
import { useTheme, ThemeProvider, Button, useAsync, useDebounce } from "./component";

/**
 * Application factory with default configuration.
 *
 * @param overrides - Configuration overrides to apply.
 * @returns Configured Application instance.
 */
export function createApplication(overrides: Partial<AppConfig> = {}): Application {
  const config = mergeConfig({
    name: "fs2-demo",
    version: "1.0.0",
    environment: "development",
    ...overrides,
  });

  validateConfig(config);

  return new Application(config);
}

/**
 * Re-export all public types and components for consumers.
 */
export {
  // From app.ts
  Application,
  AppConfig,
  AppState,
  LogLevel,
  mergeConfig,
  validateConfig,
  // From component.tsx
  useTheme,
  ThemeProvider,
  Button,
  useAsync,
  useDebounce,
};

/**
 * Default export for convenient importing.
 */
export default Application;
