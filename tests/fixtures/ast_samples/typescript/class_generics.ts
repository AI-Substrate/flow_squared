class GenericRepository<T extends { id: number }> implements Repository<T> {
    private items: Map<number, T> = new Map();

    async find(id: number): Promise<T | null> {
        return this.items.get(id) ?? null;
    }

    async save(entity: T): Promise<T> {
        this.items.set(entity.id, entity);
        return entity;
    }
}
