namespace MyApp.Services
{
    public class UserService
    {
        private readonly ILogger _logger;

        public UserService(ILogger logger)
        {
            _logger = logger;
        }

        public User GetUser(int id)
        {
            return new User { Id = id };
        }
    }
}
