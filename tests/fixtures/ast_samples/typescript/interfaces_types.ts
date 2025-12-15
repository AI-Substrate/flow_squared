interface User {
    id: number;
    name: string;
    email?: string;
}

type Status = 'active' | 'inactive' | 'pending';

interface Repository<T> {
    find(id: number): Promise<T | null>;
    save(entity: T): Promise<T>;
}
