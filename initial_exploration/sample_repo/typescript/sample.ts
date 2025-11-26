/**
 * Sample TypeScript file for tree-sitter exploration.
 * Includes TypeScript-specific constructs.
 */

// Type aliases
type ID = string | number;
type Callback<T> = (value: T) => void;

// Interfaces
interface User {
    id: ID;
    name: string;
    email?: string;
    readonly createdAt: Date;
}

interface Repository<T> {
    find(id: ID): Promise<T | null>;
    save(item: T): Promise<T>;
    delete(id: ID): Promise<boolean>;
}

// Extending interfaces
interface AdminUser extends User {
    permissions: string[];
    role: 'admin' | 'superadmin';
}

// Enums
enum Status {
    Pending = 'PENDING',
    Active = 'ACTIVE',
    Inactive = 'INACTIVE',
}

const enum Direction {
    Up,
    Down,
    Left,
    Right,
}

// Generic class
class GenericRepository<T extends { id: ID }> implements Repository<T> {
    private items: Map<ID, T> = new Map();

    async find(id: ID): Promise<T | null> {
        return this.items.get(id) ?? null;
    }

    async save(item: T): Promise<T> {
        this.items.set(item.id, item);
        return item;
    }

    async delete(id: ID): Promise<boolean> {
        return this.items.delete(id);
    }
}

// Abstract class
abstract class BaseService<T> {
    protected repository: Repository<T>;

    constructor(repository: Repository<T>) {
        this.repository = repository;
    }

    abstract validate(item: T): boolean;

    async getById(id: ID): Promise<T | null> {
        return this.repository.find(id);
    }
}

// Decorators (experimental)
function logged(target: any, key: string, descriptor: PropertyDescriptor) {
    const original = descriptor.value;
    descriptor.value = function (...args: any[]) {
        console.log(`Calling ${key}`);
        return original.apply(this, args);
    };
    return descriptor;
}

// Class with decorators
class UserService extends BaseService<User> {
    constructor() {
        super(new GenericRepository<User>());
    }

    validate(user: User): boolean {
        return user.name.length > 0;
    }

    @logged
    async createUser(name: string): Promise<User> {
        const user: User = {
            id: Date.now().toString(),
            name,
            createdAt: new Date(),
        };
        return this.repository.save(user);
    }
}

// Utility types
type PartialUser = Partial<User>;
type RequiredUser = Required<User>;
type ReadonlyUser = Readonly<User>;
type UserKeys = keyof User;

// Conditional types
type NonNullable<T> = T extends null | undefined ? never : T;
type ReturnType<T> = T extends (...args: any[]) => infer R ? R : never;

// Mapped types
type Nullable<T> = { [P in keyof T]: T[P] | null };

// Function overloads
function process(value: string): string;
function process(value: number): number;
function process(value: string | number): string | number {
    return value;
}

// Namespace
namespace Validators {
    export function isEmail(value: string): boolean {
        return value.includes('@');
    }

    export function isNotEmpty(value: string): boolean {
        return value.length > 0;
    }
}

// Module augmentation
declare module './module' {
    interface ExistingInterface {
        newProperty: string;
    }
}

// Export
export { User, UserService, Status, Validators };
export type { ID, Callback, Repository };
