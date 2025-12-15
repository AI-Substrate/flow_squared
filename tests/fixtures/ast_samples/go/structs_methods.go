package calculator

type Calculator struct {
	value int
}

func NewCalculator(initial int) *Calculator {
	return &Calculator{value: initial}
}

func (c *Calculator) Add(x int) int {
	c.value += x
	return c.value
}

func (c *Calculator) Value() int {
	return c.value
}
