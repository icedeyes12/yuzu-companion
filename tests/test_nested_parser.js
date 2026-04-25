// FILE: tests/test_nested_parser.js
// DESCRIPTION: Test nested container parser (run in browser console)

function runNestedParserTests() {
    const parser = new NestedContainerParser();
    const results = [];
    
    // Test 1: Codeblock inside codeblock
    const test1 = '```\nouter code\n```inner```\nouter continues\n```';
    const result1 = parser.parse(test1);
    results.push({
        name: 'Codeblock in codeblock',
        input: test1,
        output: result1,
        pass: !result1.includes('```inner```') && result1.includes('&#96;')
    });
    
    // Test 2: Quote inside quote
    const test2 = '> outer quote\n> > inner quote\n> outer continues';
    const result2 = parser.parse(test2);
    results.push({
        name: 'Quote in quote',
        input: test2,
        output: result2,
        pass: result2.includes('quote-depth-')
    });
    
    // Test 3: Normal codeblock (should pass through)
    const test3 = '```python\nprint("hello")\n```';
    const result3 = parser.parse(test3);
    results.push({
        name: 'Normal codeblock',
        input: test3,
        output: result3,
        pass: result3 === test3
    });
    
    // Test 4: Table inside codeblock
    const test4 = '```\n| a | b |\n|---|---|\n| 1 | 2 |\n```';
    const result4 = parser.parse(test4);
    results.push({
        name: 'Table in codeblock',
        input: test4,
        output: result4,
        pass: !result4.includes('&#96;') || result4.includes('| a | b |')
    });
    
    // Test 5: Mixed nesting
    const test5 = '```\nouter\n```javascript\nconsole.log("nested")\n```\nouter continues\n```';
    const result5 = parser.parse(test5);
    results.push({
        name: 'Mixed nesting',
        input: test5,
        output: result5,
        pass: result5.includes('&#96;javascript')
    });
    
    console.log('=== Nested Container Parser Tests ===');
    results.forEach(r => {
        console.log(`${r.pass ? '✓' : '✗'} ${r.name}`);
        if (!r.pass) {
            console.log('  Input:', r.input);
            console.log('  Output:', r.output);
        }
    });
    
    return results;
}

// Run tests if parser is available
if (typeof NestedContainerParser !== 'undefined') {
    runNestedParserTests();
} else {
    console.log('NestedContainerParser not loaded. Load it first.');
}
