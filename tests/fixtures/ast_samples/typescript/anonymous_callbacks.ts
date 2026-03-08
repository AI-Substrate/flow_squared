// Fixture: Anonymous callbacks and named arrow functions
// Tests SKIP_WHEN_ANONYMOUS for arrow_function, function, function_expression, generator_function

// Anonymous arrow function callbacks — should be SKIPPED
describe('UserService', () => {
    beforeEach(() => {
        console.log('setup');
    });

    it('should create user', () => {
        const user = createUser();
        expect(user).toBeDefined();
    });
});

// Named arrow function — should be EXTRACTED as callable "handleClick"
const handleClick = () => {
    console.log('clicked');
};

// Named arrow function — should be EXTRACTED as callable "fetchData"
const fetchData = async (url: string) => {
    return fetch(url);
};

// Anonymous function expression — should be SKIPPED
const items = [1, 2, 3].map(function(x) {
    return x * 2;
});

// Named function declaration INSIDE anonymous callback — should be EXTRACTED
describe('nested', () => {
    function helperInsideCallback() {
        return 42;
    }

    it('uses helper', () => {
        expect(helperInsideCallback()).toBe(42);
    });
});

// Named function declaration at top level — should be EXTRACTED
function topLevelFunction(a: number, b: number): number {
    return a + b;
}

// Promise chain with anonymous callbacks — should be SKIPPED
fetch('/api').then((response) => {
    return response.json();
}).then((data) => {
    console.log(data);
});

// Export default anonymous arrow — should be SKIPPED (file-level captures it)
export default () => {
    return 'default export';
};
