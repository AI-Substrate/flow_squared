// Main application demonstrating cross-file method calls.
// Line 1: Program.cs file
using Auth;
using Utils;

/// <summary>
/// Main entry point with cross-file calls.
/// Line 8: Main function (implicit top-level statements)
/// Line 12: → AuthService.Create (cross-file, function→static)
/// Line 13: → auth.Login (cross-file, function→instance method)
/// Line 14: → DateFormatter.FormatDate (cross-file, function→static method)
/// </summary>
var auth = AuthService.Create();
var result = auth.Login("testuser");
var date = DateFormatter.FormatDate();
Console.WriteLine($"Login: {result}, Date: {date}");

/// <summary>
/// Process a user with cross-file call.
/// Line 20: ProcessUser method definition
/// Line 24: ProcessUser → AuthService constructor (cross-file)
/// Line 25: ProcessUser → auth.Login (cross-file)
/// </summary>
static bool ProcessUser(string username)
{
    var auth = new AuthService();
    return auth.Login(username);
}
