pub trait Repository<T> {
    fn find(&self, id: u64) -> Option<&T>;
    fn save(&mut self, entity: T) -> Result<(), String>;
}

pub struct InMemoryRepo<T> {
    items: Vec<T>,
}

impl<T> Repository<T> for InMemoryRepo<T> {
    fn find(&self, id: u64) -> Option<&T> {
        self.items.get(id as usize)
    }

    fn save(&mut self, entity: T) -> Result<(), String> {
        self.items.push(entity);
        Ok(())
    }
}
