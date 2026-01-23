// Authentication service with method call chains.
// Line 1: AuthService.cs file
namespace Auth;

using Utils;

/// <summary>
/// Authentication service demonstrating various call patterns.
/// Line 9: AuthService class definition
/// </summary>
public class AuthService
{
    private string? _token;

    /// <summary>
    /// Constructor calling private setup.
    /// Line 16: constructor definition
    /// Line 20: constructor → Setup (same-file, private)
    /// </summary>
    public AuthService()
    {
        Setup();
    }

    /// <summary>
    /// Private setup method.
    /// Line 26: Setup method definition
    /// </summary>
    private void Setup()
    {
        _token = "default";
    }

    /// <summary>
    /// Login with method chain.
    /// Line 35: Login method definition
    /// Line 39: Login → Validate (same-file, public→private)
    /// </summary>
    public bool Login(string user)
    {
        return Validate(user);
    }

    /// <summary>
    /// Validate credentials with chain.
    /// Line 45: Validate method definition
    /// Line 49: Validate → CheckToken (same-file, chain)
    /// Line 50: Validate → DateFormatter.ValidateString (cross-file)
    /// </summary>
    private bool Validate(string user)
    {
        var tokenOk = CheckToken(user);
        var nameOk = DateFormatter.ValidateString(user);
        return tokenOk && nameOk;
    }

    /// <summary>
    /// Check token validity.
    /// Line 56: CheckToken method definition
    /// </summary>
    private bool CheckToken(string user)
    {
        return _token != null && user.Length > 0;
    }

    /// <summary>
    /// Factory method calling constructor.
    /// Line 65: Create method definition
    /// Line 69: Create → constructor (same-file, static→constructor)
    /// </summary>
    public static AuthService Create()
    {
        return new AuthService();
    }
}
