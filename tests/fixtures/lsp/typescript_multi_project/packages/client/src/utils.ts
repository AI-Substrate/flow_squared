/**
 * Utility functions for cross-file call detection.
 * Line 3: utils.ts file
 */

/**
 * Format a date for display.
 * LSP should find references from app.ts.
 * Line 8: formatDate function definition
 */
export function formatDate(date: Date | null = null): string {
    const d = date ?? new Date();
    return d.toISOString().split('T')[0];  // Line 14
}

/**
 * Validate a string is not empty.
 * LSP should find references from auth.ts.
 * Line 19: validateString function definition
 */
export function validateString(value: string): boolean {
    return value.trim().length > 0;  // Line 23
}
