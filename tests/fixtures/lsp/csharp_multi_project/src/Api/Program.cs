using Api.Models;

// Cross-file method call - SolidLSP should detect this
var user = new User { Username = "testuser" };
var isValid = user.Validate();
Console.WriteLine($"Valid: {isValid}");
