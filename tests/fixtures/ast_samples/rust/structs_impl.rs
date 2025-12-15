pub struct Calculator {
    value: i32,
}

impl Calculator {
    pub fn new(initial: i32) -> Self {
        Self { value: initial }
    }

    pub fn add(&mut self, x: i32) -> i32 {
        self.value += x;
        self.value
    }
}

impl Default for Calculator {
    fn default() -> Self {
        Self::new(0)
    }
}
