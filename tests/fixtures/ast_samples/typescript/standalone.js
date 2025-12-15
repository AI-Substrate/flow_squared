function processData(data) {
    return data.map(item => item.value);
}

const helper = (x) => x * 2;

export { processData, helper };
