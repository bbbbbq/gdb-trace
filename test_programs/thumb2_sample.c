static int leaf_add(int left, int right) {
    return left + right;
}

static int func_b(int value) {
    return leaf_add(value, 7);
}

static int func_a(int value) {
    int local = value * 2;
    return func_b(local) - 3;
}

int main(void) {
    int result = func_a(5);
    return result == 14 ? 0 : 1;
}

