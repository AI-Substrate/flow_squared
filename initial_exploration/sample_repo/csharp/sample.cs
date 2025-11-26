/**
 * Sample C# file for tree-sitter exploration.
 * Includes modern C# constructs.
 */

using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Sample
{
    // Record type (C# 9+)
    public record UserRecord(string Id, string Name, string? Email = null);

    // Enum
    public enum Status
    {
        Pending,
        Active,
        Inactive
    }

    // Interface with default implementation
    public interface IRepository<T> where T : class
    {
        Task<T?> FindAsync(string id);
        Task SaveAsync(T item);
        Task<bool> DeleteAsync(string id);

        // Default implementation
        async Task<IEnumerable<T>> FindAllAsync(IEnumerable<string> ids)
        {
            var results = new List<T>();
            foreach (var id in ids)
            {
                var item = await FindAsync(id);
                if (item != null) results.Add(item);
            }
            return results;
        }
    }

    // Class with various features
    public class User : IEquatable<User>
    {
        // Auto-properties
        public string Id { get; init; }
        public string Name { get; set; }
        public string? Email { get; set; }
        public Status Status { get; private set; } = Status.Pending;

        // Expression-bodied property
        public bool IsActive => Status == Status.Active;

        // Constructor
        public User(string id, string name)
        {
            Id = id ?? throw new ArgumentNullException(nameof(id));
            Name = name ?? throw new ArgumentNullException(nameof(name));
        }

        // Method with expression body
        public void Activate() => Status = Status.Active;

        // Async method
        public async Task<string> FetchDataAsync(string url)
        {
            await Task.Delay(100);
            return $"Data from {url}";
        }

        // Pattern matching
        public string GetStatusMessage() => Status switch
        {
            Status.Pending => "Waiting for activation",
            Status.Active => "User is active",
            Status.Inactive => "User has been deactivated",
            _ => throw new InvalidOperationException()
        };

        // IEquatable implementation
        public bool Equals(User? other)
        {
            if (other is null) return false;
            return Id == other.Id;
        }

        public override bool Equals(object? obj) => Equals(obj as User);
        public override int GetHashCode() => Id.GetHashCode();

        // Deconstruction
        public void Deconstruct(out string id, out string name)
        {
            id = Id;
            name = Name;
        }
    }

    // Generic class with constraints
    public class InMemoryRepository<T> : IRepository<T> where T : class
    {
        private readonly Dictionary<string, T> _items = new();
        private readonly Func<T, string> _keySelector;

        public InMemoryRepository(Func<T, string> keySelector)
        {
            _keySelector = keySelector;
        }

        public Task<T?> FindAsync(string id)
        {
            _items.TryGetValue(id, out var item);
            return Task.FromResult(item);
        }

        public Task SaveAsync(T item)
        {
            var key = _keySelector(item);
            _items[key] = item;
            return Task.CompletedTask;
        }

        public Task<bool> DeleteAsync(string id)
        {
            return Task.FromResult(_items.Remove(id));
        }
    }

    // Abstract class
    public abstract class BaseService<T> where T : class
    {
        protected readonly IRepository<T> Repository;

        protected BaseService(IRepository<T> repository)
        {
            Repository = repository;
        }

        public abstract Task<bool> ValidateAsync(T item);

        public virtual async Task<T?> GetByIdAsync(string id)
        {
            return await Repository.FindAsync(id);
        }
    }

    // Inheritance
    public class UserService : BaseService<User>
    {
        public UserService(IRepository<User> repository) : base(repository) { }

        public override Task<bool> ValidateAsync(User item)
        {
            return Task.FromResult(!string.IsNullOrEmpty(item.Name));
        }

        // LINQ example
        public async Task<IEnumerable<User>> GetActiveUsersAsync(IEnumerable<string> ids)
        {
            var users = await Repository.FindAllAsync(ids);
            return users.Where(u => u.IsActive)
                       .OrderBy(u => u.Name)
                       .ToList();
        }
    }

    // Extension methods
    public static class UserExtensions
    {
        public static string ToDisplayString(this User user)
        {
            return $"{user.Name} ({user.Id})";
        }

        public static async Task<User> WithEmailAsync(this User user, string email)
        {
            await Task.Delay(10); // Simulate async operation
            user.Email = email;
            return user;
        }
    }

    // Attribute
    [AttributeUsage(AttributeTargets.Method)]
    public class LogAttribute : Attribute
    {
        public string Message { get; }
        public LogAttribute(string message) => Message = message;
    }

    // Static class
    public static class Validators
    {
        public static bool IsValidEmail(string? email)
            => !string.IsNullOrEmpty(email) && email.Contains('@');

        public static bool IsNotEmpty(string? value)
            => !string.IsNullOrWhiteSpace(value);
    }

    // Partial class
    public partial class PartialUser
    {
        public string Id { get; set; } = string.Empty;
    }

    public partial class PartialUser
    {
        public string Name { get; set; } = string.Empty;
    }

    // Main program
    public class Program
    {
        public static async Task Main(string[] args)
        {
            var repo = new InMemoryRepository<User>(u => u.Id);
            var service = new UserService(repo);

            var user = new User("1", "Alice") { Email = "alice@example.com" };
            await repo.SaveAsync(user);

            // Null-conditional and null-coalescing
            var found = await repo.FindAsync("1");
            var name = found?.Name ?? "Unknown";

            // Tuple
            var (id, userName) = user;

            // Using declaration
            await using var stream = new System.IO.MemoryStream();

            Console.WriteLine($"User: {user.ToDisplayString()}");
        }
    }
}
