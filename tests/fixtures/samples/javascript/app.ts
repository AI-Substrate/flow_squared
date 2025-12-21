/**
 * Application configuration and initialization module.
 * Provides type-safe configuration management and app lifecycle.
 */

import { EventEmitter } from "events";

/** Possible application states */
export type AppState = "idle" | "starting" | "running" | "stopping" | "stopped";

/** Log levels in order of severity */
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

/** Application configuration options */
export interface AppConfig {
  /** Application name for logging and identification */
  name: string;
  /** Application version string */
  version: string;
  /** Environment: development, staging, or production */
  environment: "development" | "staging" | "production";
  /** Port to listen on */
  port: number;
  /** Enable debug mode */
  debug: boolean;
  /** Logging configuration */
  logging: {
    level: LogLevel;
    format: "json" | "pretty";
    destination: "console" | "file";
  };
  /** Optional feature flags */
  features?: Record<string, boolean>;
}

/** Default configuration values */
const defaultConfig: AppConfig = {
  name: "app",
  version: "1.0.0",
  environment: "development",
  port: 3000,
  debug: false,
  logging: {
    level: LogLevel.INFO,
    format: "pretty",
    destination: "console",
  },
};

/**
 * Merge partial configuration with defaults.
 * @param partial - Partial configuration to merge.
 * @returns Complete configuration with defaults applied.
 */
export function mergeConfig(partial: Partial<AppConfig>): AppConfig {
  return {
    ...defaultConfig,
    ...partial,
    logging: {
      ...defaultConfig.logging,
      ...partial.logging,
    },
    features: {
      ...partial.features,
    },
  };
}

/**
 * Validate application configuration.
 * @param config - Configuration to validate.
 * @throws Error if configuration is invalid.
 */
export function validateConfig(config: AppConfig): void {
  if (!config.name || config.name.length === 0) {
    throw new Error("Application name is required");
  }

  if (config.port < 1 || config.port > 65535) {
    throw new Error(`Invalid port number: ${config.port}`);
  }

  const validEnvironments = ["development", "staging", "production"];
  if (!validEnvironments.includes(config.environment)) {
    throw new Error(`Invalid environment: ${config.environment}`);
  }
}

/** Application lifecycle events */
interface AppEvents {
  starting: () => void;
  started: () => void;
  stopping: () => void;
  stopped: () => void;
  error: (error: Error) => void;
}

/**
 * Main application class managing lifecycle and configuration.
 */
export class Application extends EventEmitter {
  private _config: AppConfig;
  private _state: AppState = "idle";
  private _startTime?: Date;

  /**
   * Create a new Application instance.
   * @param config - Application configuration.
   */
  constructor(config: Partial<AppConfig> = {}) {
    super();
    this._config = mergeConfig(config);
    validateConfig(this._config);
  }

  /** Get current application state */
  get state(): AppState {
    return this._state;
  }

  /** Get application configuration (read-only) */
  get config(): Readonly<AppConfig> {
    return this._config;
  }

  /** Get application uptime in milliseconds */
  get uptime(): number {
    if (!this._startTime) return 0;
    return Date.now() - this._startTime.getTime();
  }

  /**
   * Start the application.
   * @returns Promise that resolves when app is running.
   */
  async start(): Promise<void> {
    if (this._state !== "idle" && this._state !== "stopped") {
      throw new Error(`Cannot start app in state: ${this._state}`);
    }

    this._state = "starting";
    this.emit("starting");

    try {
      await this.initialize();
      this._state = "running";
      this._startTime = new Date();
      this.emit("started");
      this.log(LogLevel.INFO, `Application ${this._config.name} started`);
    } catch (error) {
      this._state = "stopped";
      this.emit("error", error);
      throw error;
    }
  }

  /**
   * Stop the application gracefully.
   * @param timeout - Maximum time to wait for shutdown in ms.
   * @returns Promise that resolves when app is stopped.
   */
  async stop(timeout: number = 5000): Promise<void> {
    if (this._state !== "running") {
      throw new Error(`Cannot stop app in state: ${this._state}`);
    }

    this._state = "stopping";
    this.emit("stopping");

    try {
      await Promise.race([
        this.cleanup(),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("Shutdown timeout")), timeout)
        ),
      ]);
    } finally {
      this._state = "stopped";
      this.emit("stopped");
      this.log(LogLevel.INFO, `Application ${this._config.name} stopped`);
    }
  }

  /**
   * Check if a feature is enabled.
   * @param feature - Feature name to check.
   * @returns True if feature is enabled.
   */
  isFeatureEnabled(feature: string): boolean {
    return this._config.features?.[feature] === true;
  }

  /** Initialize application resources (override in subclass) */
  protected async initialize(): Promise<void> {
    // Subclasses can override to add initialization logic
  }

  /** Cleanup application resources (override in subclass) */
  protected async cleanup(): Promise<void> {
    // Subclasses can override to add cleanup logic
  }

  /** Log a message at the specified level */
  protected log(level: LogLevel, message: string, data?: unknown): void {
    if (level < this._config.logging.level) return;

    const entry = {
      timestamp: new Date().toISOString(),
      level: LogLevel[level],
      message,
      app: this._config.name,
      data,
    };

    if (this._config.logging.format === "json") {
      console.log(JSON.stringify(entry));
    } else {
      console.log(`[${entry.timestamp}] ${entry.level}: ${message}`);
    }
  }
}

// Type-safe event emitter extension
declare module "./app" {
  interface Application {
    on<K extends keyof AppEvents>(event: K, listener: AppEvents[K]): this;
    emit<K extends keyof AppEvents>(
      event: K,
      ...args: Parameters<AppEvents[K]>
    ): boolean;
  }
}
