/**
 * Format a date for display.
 * SolidLSP should find references to this function from index.tsx.
 */
export function formatDate(date: Date): string {
    return date.toISOString().split('T')[0];
}
