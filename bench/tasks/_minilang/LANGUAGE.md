# minilang

A small scripting language, run by `python3 -m minilang FILE` (and formatted by `python3 -m minilang --format FILE`).

```
# Comments run to the end of the line
let names = ["Ada", "Grace", "Barbara"];
fn greet(name) {
    return "Hello, " + name + "!";
}
let i = 0;
while i < len(names) {
    print(greet(names[i]));
    i = i + 1;
}
```

## Values

- **nil**, **true**, **false**
- **numbers**: whole (`42`) or with a fraction (`3.25`). Whole numbers stay whole under `+ - * %`, under `/` when
  they divide exactly (`6 / 3` is `2`, `7 / 2` is `3.5`), and under `^` with a whole, non-negative power.
- **strings**: in double quotes, with the escapes `\n`, `\t`, `\"` and `\\`. A string can't span lines.
- **lists**: `[1, "two", [3]]`. Lists are shared, not copied: `let b = a;` makes `b` the same list as `a`.
- **functions**: declared (`fn name(a, b) { ... }`) or as expressions (`let f = fn(x) { return x * 2; };`).

Only `false` and `nil` are false in conditions: `0`, `""` and `[]` are true.

## Operators, loosest first

| Operators | Notes |
|---|---|
| `or` | the left value if it's true, otherwise the right value; the right side runs only when needed |
| `and` | the left value if it's false, otherwise the right value; the right side runs only when needed |
| `==` `!=` | any values. Numbers compare by value (`1 == 1.0`); values of different types are never equal; lists compare item by item |
| `<` `<=` `>` `>=` | two numbers or two strings |
| `+` `-` | `+` also joins two strings or two lists |
| `*` `/` `%` | `"ab" * 3` is `"ababab"`; `%` has the sign of the right side, as in Python |
| `-x` `not x` | unary minus, and not |
| `^` | power, right-associative: `2 ^ 3 ^ 2` is `2 ^ 9`; `-2 ^ 2` is `-(2 ^ 2)`, -4 |
| `f(x)` `xs[i]` | calls and indexes; `xs[-1]` is the last item |

## Statements

- `let name = value;` declares a variable in the current block. Declaring the same name twice in one block is an error;
  an inner block may declare a name that hides an outer one.
- `name = value;` and `xs[i] = value;` change an existing variable, or a list item. Assigning to an undeclared name
  is an error.
- `if cond { ... } else if cond { ... } else { ... }`
- `while cond { ... }`
- `fn name(params) { ... }` and `return value;` (or `return;`, which returns nil, as does falling off the end).
- Any expression followed by `;`.

Every `{ ... }` is a block with its own scope. Functions see the variables of the scope they were created in, even
after it has finished (closures), and changes they make to those variables are seen by everyone sharing them.

## Built-in functions

| Function | Does |
|---|---|
| `print(a, b, ...)` | prints its arguments separated by spaces. Strings print without quotes, except inside lists |
| `len(x)` | the length of a string or list |
| `str(x)`, `num(s)`, `type(x)` | a value as `print` shows it; a string as a number; `"nil"`, `"bool"`, `"number"`, `"string"`, `"list"` or `"function"` |
| `range(n)`, `range(a, b)`, `range(a, b, step)` | lists of whole numbers, as Python's range: `range(2, 5)` is `[2, 3, 4]` |
| `push(xs, x)`, `pop(xs)` | adds to the end of a list (and returns the list); removes and returns the last item |
| `join(xs, sep)`, `split(s, sep)` | `join([1, 2], "-")` is `"1-2"`; `split("a,b", ",")` is `["a", "b"]` |
| `abs(x)`, `min(...)`, `max(...)` | `min` and `max` take numbers, or one list of numbers |

## Errors

Errors stop the program with a message and, where known, the line: `error: line 3: undefined name 'x'`. Lexing,
parsing and running each raise their own error class (`LexError`, `ParseError`, `EvalError`), all `LangError`s.

## The formatter

`--format` prints a program in one standard layout: 4-space indents, one statement per line, `} else {` on one line,
and only the parentheses the meaning needs: `(a + b) * c` keeps them, `a + (b * c)` loses them. Formatting a
formatted program changes nothing.
