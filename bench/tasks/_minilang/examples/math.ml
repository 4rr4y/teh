# Operators and precedence
print(2 ^ 3 ^ 2, -2 ^ 2, (-2) ^ 2);
print(7 / 2, 6 / 3, 7 % 3, -7 % 3);
print(10 - 4 - 3, 10 - (4 - 3), 2 * (3 + 4));
print(1 == 1.0, 1 == true, "a" < "b", [1, [2]] == [1, [2]]);
print(nil or "default", 0 and "zero is true");
let squares = [];
let n = 0;
while n < 5 {
    push(squares, n ^ 2);
    n = n + 1;
}
print(squares, max(squares), min(3, -1, 2), abs(-4.5));
