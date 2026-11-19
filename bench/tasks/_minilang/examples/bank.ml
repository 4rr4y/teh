# Accounts as closures: each keeps its own balance
fn account(owner, balance) {
    let history = [];
    fn deposit(amount) {
        balance = balance + amount;
        push(history, "+" + str(amount));
        return balance;
    }
    fn withdraw(amount) {
        if amount > balance { return "refused: " + owner + " has only " + str(balance); }
        balance = balance - amount;
        push(history, "-" + str(amount));
        return balance;
    }
    fn report() { return owner + ": " + str(balance) + " " + str(history); }
    return [deposit, withdraw, report];
}
let ada = account("Ada", 100);
let bob = account("Bob", 20);
ada[0](50);
print(ada[1](30));
print(bob[1](25));
bob[0](5);
print(ada[2]());
print(bob[2]());
