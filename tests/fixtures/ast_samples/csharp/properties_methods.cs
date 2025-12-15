public class Person
{
    public string Name { get; set; }
    public int Age { get; private set; }

    public string FirstName { get; set; }
    public string LastName { get; set; }

    public string FullName => $"{FirstName} {LastName}";

    public void UpdateAge(int newAge)
    {
        if (newAge > 0) Age = newAge;
    }
}
