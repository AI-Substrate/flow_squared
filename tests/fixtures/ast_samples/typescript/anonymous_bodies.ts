// Fixture: Anonymous body/heritage/type nodes
// Tests SKIP_WHEN_ANONYMOUS for interface_body, class_body, class_heritage,
// enum_body, function_type, implements_clause

// Interface with body — interface_body should be SKIPPED, interface_declaration EXTRACTED
interface UserService {
    getUser(id: number): Promise<User>;
    saveUser(user: User): Promise<void>;
}

// Interface with function_type in members — function_type should be SKIPPED
interface EventHandler {
    onEvent: (event: Event) => void;
    onError: (error: Error) => boolean;
}

// Class with body and heritage — class_body and class_heritage SKIPPED,
// class_declaration and methods EXTRACTED
class UserRepository implements UserService {
    private users: Map<number, User> = new Map();

    async getUser(id: number): Promise<User> {
        return this.users.get(id);
    }

    async saveUser(user: User): Promise<void> {
        this.users.set(user.id, user);
    }
}

// Enum with body — enum_body should be SKIPPED, enum_declaration EXTRACTED
enum Status {
    Active = 'active',
    Inactive = 'inactive',
    Pending = 'pending',
}

// Class with implements clause — implements_clause should be SKIPPED
class AdminService implements UserService {
    async getUser(id: number): Promise<User> {
        return null;
    }

    async saveUser(user: User): Promise<void> {
        // admin save
    }
}

// Type alias with function type — should be EXTRACTED as type
type Callback = (data: string) => void;
type Predicate<T> = (item: T) => boolean;

// Interface extending another — class_heritage should be SKIPPED
interface AdminUser extends User {
    role: string;
    permissions: string[];
}

// Standalone type references
interface User {
    id: number;
    name: string;
}
