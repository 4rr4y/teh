# Strings: escapes, splitting and joining
let csv = "name,score\nada,91\ngrace,88";
let lines = split(csv, "\n");
let total = 0;
let i = 1;
while i < len(lines) {
    let fields = split(lines[i], ",");
    total = total + num(fields[1]);
    print(fields[0] + "\t" + fields[1]);
    i = i + 1;
}
print("mean:", total / (len(lines) - 1));
print("quote: \"done\"", ["a\"b", 1.5, nil, true]);
