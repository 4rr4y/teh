# Primes below 50, by trial division
fn is_prime(n) {
    if n < 2 { return false; }
    let d = 2;
    while d * d <= n {
        if n % d == 0 { return false; }
        d = d + 1;
    }
    return true;
}
let found = [];
let candidates = range(2, 50);
let k = 0;
while k < len(candidates) {
    if is_prime(candidates[k]) { push(found, candidates[k]); }
    k = k + 1;
}
print(join(found, " "));
print("count:", len(found));
