// Utility functions for cross-file call detection.
// Line 1: DateFormatter.cs file
namespace Utils;

/// <summary>
/// Utility class with formatting functions.
/// Line 7: DateFormatter class definition
/// </summary>
public static class DateFormatter
{
    /// <summary>
    /// Format a DateTime for display.
    /// LSP should find references from Program.cs.
    /// Line 14: FormatDate method definition
    /// </summary>
    public static string FormatDate(DateTime? dt = null)
    {
        var d = dt ?? DateTime.Now;
        return d.ToString("yyyy-MM-dd");  // Line 20
    }

    /// <summary>
    /// Validate a string is not empty.
    /// LSP should find references from AuthService.cs.
    /// Line 26: ValidateString method definition
    /// </summary>
    public static bool ValidateString(string value)
    {
        return !string.IsNullOrWhiteSpace(value);  // Line 31
    }
}
