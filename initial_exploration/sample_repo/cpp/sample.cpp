/**
 * Sample C++ file for tree-sitter exploration.
 * Includes modern C++ constructs.
 */

#include <iostream>
#include <memory>
#include <vector>
#include <string>
#include <functional>
#include <optional>
#include <map>

namespace sample {

// Forward declaration
class User;

// Type alias
using ID = std::string;
using UserPtr = std::shared_ptr<User>;

// Enum class
enum class Status {
    Pending,
    Active,
    Inactive
};

// Template class
template<typename T>
class Repository {
public:
    virtual ~Repository() = default;
    virtual std::optional<T> find(const ID& id) = 0;
    virtual void save(const T& item) = 0;
    virtual bool remove(const ID& id) = 0;
};

// Class definition
class User {
public:
    // Constructors
    User() = default;
    User(ID id, std::string name)
        : id_(std::move(id)), name_(std::move(name)), status_(Status::Pending) {}

    // Copy and move
    User(const User&) = default;
    User(User&&) noexcept = default;
    User& operator=(const User&) = default;
    User& operator=(User&&) noexcept = default;

    // Destructor
    virtual ~User() = default;

    // Getters
    [[nodiscard]] const ID& id() const { return id_; }
    [[nodiscard]] const std::string& name() const { return name_; }
    [[nodiscard]] Status status() const { return status_; }
    [[nodiscard]] const std::optional<std::string>& email() const { return email_; }

    // Setters
    void set_name(std::string name) { name_ = std::move(name); }
    void set_status(Status status) { status_ = status; }
    void set_email(std::string email) { email_ = std::move(email); }

    // Operator overload
    bool operator==(const User& other) const {
        return id_ == other.id_;
    }

    // Friend function
    friend std::ostream& operator<<(std::ostream& os, const User& user);

private:
    ID id_;
    std::string name_;
    Status status_{Status::Pending};
    std::optional<std::string> email_;
};

// Friend function definition
std::ostream& operator<<(std::ostream& os, const User& user) {
    os << "User{id=" << user.id_ << ", name=" << user.name_ << "}";
    return os;
}

// Inheritance
class AdminUser : public User {
public:
    AdminUser(ID id, std::string name, std::vector<std::string> permissions)
        : User(std::move(id), std::move(name))
        , permissions_(std::move(permissions)) {}

    [[nodiscard]] const std::vector<std::string>& permissions() const {
        return permissions_;
    }

    void add_permission(std::string permission) {
        permissions_.push_back(std::move(permission));
    }

private:
    std::vector<std::string> permissions_;
};

// Template specialization
template<>
class Repository<User> {
public:
    std::optional<User> find(const ID& id) {
        auto it = users_.find(id);
        if (it != users_.end()) {
            return it->second;
        }
        return std::nullopt;
    }

    void save(const User& user) {
        users_[user.id()] = user;
    }

    bool remove(const ID& id) {
        return users_.erase(id) > 0;
    }

private:
    std::map<ID, User> users_;
};

// Variadic template
template<typename... Args>
void log(Args&&... args) {
    (std::cout << ... << args) << std::endl;
}

// Constexpr function
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

// Lambda examples
inline auto create_greeter(const std::string& greeting) {
    return [greeting](const std::string& name) {
        return greeting + ", " + name + "!";
    };
}

// Concepts (C++20)
template<typename T>
concept Printable = requires(T t) {
    { std::cout << t } -> std::same_as<std::ostream&>;
};

template<Printable T>
void print(const T& value) {
    std::cout << value << std::endl;
}

// RAII wrapper
class FileHandle {
public:
    explicit FileHandle(const std::string& filename)
        : filename_(filename), open_(true) {
        std::cout << "Opening: " << filename_ << std::endl;
    }

    ~FileHandle() {
        if (open_) {
            std::cout << "Closing: " << filename_ << std::endl;
        }
    }

    // Non-copyable
    FileHandle(const FileHandle&) = delete;
    FileHandle& operator=(const FileHandle&) = delete;

    // Moveable
    FileHandle(FileHandle&& other) noexcept
        : filename_(std::move(other.filename_)), open_(other.open_) {
        other.open_ = false;
    }

private:
    std::string filename_;
    bool open_;
};

} // namespace sample

// Main function
int main() {
    using namespace sample;

    auto user = User("1", "Alice");
    user.set_email("alice@example.com");

    Repository<User> repo;
    repo.save(user);

    if (auto found = repo.find("1")) {
        log("Found user: ", found->name());
    }

    constexpr int fact5 = factorial(5);
    static_assert(fact5 == 120, "Factorial of 5 should be 120");

    auto greeter = create_greeter("Hello");
    std::cout << greeter("World") << std::endl;

    return 0;
}
