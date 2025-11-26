/**
 * Sample JavaScript file for tree-sitter exploration.
 * Includes ES6+ features.
 */

// Module imports
import { something } from './module.js';
export const CONSTANT = 42;

// Traditional function
function traditionalFunction(a, b) {
    return a + b;
}

// Arrow functions
const arrowFunction = (x) => x * 2;
const arrowWithBlock = (x, y) => {
    const sum = x + y;
    return sum;
};

// Class definition
class Calculator {
    #privateField = 0;
    static staticField = 'static';

    constructor(name) {
        this.name = name;
        this.value = 0;
    }

    add(a, b) {
        return a + b;
    }

    static multiply(a, b) {
        return a * b;
    }

    get currentValue() {
        return this.value;
    }

    set currentValue(val) {
        this.value = val;
    }

    async fetchData(url) {
        const response = await fetch(url);
        return response.json();
    }

    *generator() {
        yield 1;
        yield 2;
    }
}

// Inheritance
class AdvancedCalculator extends Calculator {
    constructor(name, precision) {
        super(name);
        this.precision = precision;
    }

    add(a, b) {
        return super.add(a, b).toFixed(this.precision);
    }
}

// Destructuring
const { x, y, ...rest } = { x: 1, y: 2, z: 3, w: 4 };
const [first, second, ...others] = [1, 2, 3, 4, 5];

// Template literals
const template = `Hello ${name}, value is ${value}`;

// Spread and rest
const merged = { ...obj1, ...obj2 };
function withRest(...args) {
    return args.reduce((a, b) => a + b, 0);
}

// Promises and async/await
const promise = new Promise((resolve, reject) => {
    setTimeout(() => resolve('done'), 1000);
});

async function asyncFunction() {
    try {
        const result = await promise;
        return result;
    } catch (error) {
        console.error(error);
    }
}

// Higher-order functions
const numbers = [1, 2, 3, 4, 5];
const doubled = numbers.map(n => n * 2);
const sum = numbers.reduce((acc, n) => acc + n, 0);
const evens = numbers.filter(n => n % 2 === 0);

// Export
export { Calculator, traditionalFunction };
export default AdvancedCalculator;
