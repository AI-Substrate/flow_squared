package com.example.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.stream.Collectors;

/**
 * Service class for user management operations.
 * Provides CRUD operations with validation and async support.
 *
 * @author Example Team
 * @version 1.0
 * @since 2024-01-01
 */
public class UserService {

    private final UserRepository userRepository;
    private final EmailService emailService;
    private final CacheManager cacheManager;

    /**
     * Represents a user entity.
     */
    public record User(
        UUID id,
        String email,
        String name,
        UserRole role,
        LocalDateTime createdAt,
        LocalDateTime updatedAt,
        boolean active
    ) {
        /**
         * Create a new user with default values.
         */
        public static User create(String email, String name, UserRole role) {
            LocalDateTime now = LocalDateTime.now();
            return new User(
                UUID.randomUUID(),
                email,
                name,
                role,
                now,
                now,
                true
            );
        }

        /**
         * Create an updated copy with new modification time.
         */
        public User withUpdatedAt() {
            return new User(id, email, name, role, createdAt, LocalDateTime.now(), active);
        }
    }

    /**
     * User roles for authorization.
     */
    public enum UserRole {
        GUEST(0),
        USER(1),
        MODERATOR(2),
        ADMIN(3),
        SUPERADMIN(4);

        private final int level;

        UserRole(int level) {
            this.level = level;
        }

        public int getLevel() {
            return level;
        }

        public boolean hasPermission(UserRole required) {
            return this.level >= required.level;
        }
    }

    /**
     * Custom exception for user-related errors.
     */
    public static class UserException extends RuntimeException {
        private final ErrorCode code;

        public UserException(ErrorCode code, String message) {
            super(message);
            this.code = code;
        }

        public ErrorCode getCode() {
            return code;
        }
    }

    /**
     * Error codes for user operations.
     */
    public enum ErrorCode {
        USER_NOT_FOUND,
        EMAIL_ALREADY_EXISTS,
        INVALID_EMAIL,
        INVALID_NAME,
        PERMISSION_DENIED
    }

    /**
     * Construct a new UserService with dependencies.
     *
     * @param userRepository Repository for user persistence.
     * @param emailService Service for sending emails.
     * @param cacheManager Manager for caching user data.
     */
    public UserService(
            UserRepository userRepository,
            EmailService emailService,
            CacheManager cacheManager) {
        this.userRepository = userRepository;
        this.emailService = emailService;
        this.cacheManager = cacheManager;
    }

    /**
     * Find a user by their unique identifier.
     *
     * @param id The user's UUID.
     * @return Optional containing the user if found.
     */
    public Optional<User> findById(UUID id) {
        // Check cache first
        User cached = cacheManager.get("user:" + id, User.class);
        if (cached != null) {
            return Optional.of(cached);
        }

        // Load from repository
        Optional<User> user = userRepository.findById(id);
        user.ifPresent(u -> cacheManager.put("user:" + id, u));
        return user;
    }

    /**
     * Find a user by email address.
     *
     * @param email The email address to search.
     * @return Optional containing the user if found.
     */
    public Optional<User> findByEmail(String email) {
        return userRepository.findByEmail(email.toLowerCase().trim());
    }

    /**
     * Create a new user account.
     *
     * @param email User's email address.
     * @param name User's display name.
     * @param role User's role.
     * @return The created user.
     * @throws UserException if validation fails or email exists.
     */
    public User createUser(String email, String name, UserRole role) {
        validateEmail(email);
        validateName(name);

        if (findByEmail(email).isPresent()) {
            throw new UserException(ErrorCode.EMAIL_ALREADY_EXISTS,
                "A user with this email already exists");
        }

        User user = User.create(email.toLowerCase().trim(), name.trim(), role);
        User saved = userRepository.save(user);

        // Send welcome email asynchronously
        emailService.sendWelcomeEmail(saved.email(), saved.name());

        return saved;
    }

    /**
     * Update an existing user.
     *
     * @param id The user's ID.
     * @param name New display name (optional).
     * @param role New role (optional).
     * @return The updated user.
     * @throws UserException if user not found.
     */
    public User updateUser(UUID id, String name, UserRole role) {
        User existing = findById(id)
            .orElseThrow(() -> new UserException(ErrorCode.USER_NOT_FOUND,
                "User not found: " + id));

        String newName = name != null ? name.trim() : existing.name();
        UserRole newRole = role != null ? role : existing.role();

        if (name != null) {
            validateName(newName);
        }

        User updated = new User(
            existing.id(),
            existing.email(),
            newName,
            newRole,
            existing.createdAt(),
            LocalDateTime.now(),
            existing.active()
        );

        User saved = userRepository.save(updated);
        cacheManager.invalidate("user:" + id);
        return saved;
    }

    /**
     * Deactivate a user account.
     *
     * @param id The user's ID.
     * @return True if deactivated successfully.
     */
    public boolean deactivateUser(UUID id) {
        return findById(id)
            .map(user -> {
                User deactivated = new User(
                    user.id(), user.email(), user.name(), user.role(),
                    user.createdAt(), LocalDateTime.now(), false
                );
                userRepository.save(deactivated);
                cacheManager.invalidate("user:" + id);
                return true;
            })
            .orElse(false);
    }

    /**
     * Get all active users with a specific role.
     *
     * @param role The role to filter by.
     * @return List of matching users.
     */
    public List<User> findActiveByRole(UserRole role) {
        return userRepository.findAll().stream()
            .filter(User::active)
            .filter(user -> user.role() == role)
            .collect(Collectors.toList());
    }

    /**
     * Asynchronously search users by name.
     *
     * @param query Search query for name matching.
     * @return CompletableFuture with matching users.
     */
    public CompletableFuture<List<User>> searchByNameAsync(String query) {
        return CompletableFuture.supplyAsync(() ->
            userRepository.findAll().stream()
                .filter(user -> user.name().toLowerCase()
                    .contains(query.toLowerCase()))
                .limit(50)
                .collect(Collectors.toList())
        );
    }

    private void validateEmail(String email) {
        if (email == null || !email.matches("^[\\w-\\.]+@[\\w-]+\\.[a-z]{2,}$")) {
            throw new UserException(ErrorCode.INVALID_EMAIL,
                "Invalid email format");
        }
    }

    private void validateName(String name) {
        if (name == null || name.trim().length() < 2) {
            throw new UserException(ErrorCode.INVALID_NAME,
                "Name must be at least 2 characters");
        }
    }
}

// Placeholder interfaces for compilation
interface UserRepository {
    Optional<UserService.User> findById(UUID id);
    Optional<UserService.User> findByEmail(String email);
    UserService.User save(UserService.User user);
    List<UserService.User> findAll();
}

interface EmailService {
    void sendWelcomeEmail(String email, String name);
}

interface CacheManager {
    <T> T get(String key, Class<T> type);
    void put(String key, Object value);
    void invalidate(String key);
}
