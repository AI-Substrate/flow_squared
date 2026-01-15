namespace Api.Models;

/// <summary>
/// User model with validation logic.
/// SolidLSP should find references to Validate() from Program.cs.
/// </summary>
public class User
{
    public string Username { get; set; } = "";

    public bool Validate()
    {
        return !string.IsNullOrEmpty(Username);
    }
}
