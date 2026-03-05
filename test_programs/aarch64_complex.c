#include <stddef.h>

typedef int (*worker_fn)(int, int);

static int helper_mix(int base, int factor) {
    int total = 0;
    for (int i = 0; i < factor; ++i) {
        total += base + i;
    }
    return total;
}

static int helper_recursive(int value) {
    if (value <= 1) {
        return value;
    }
    return helper_recursive(value - 1) + helper_recursive(value - 2);
}

static int worker_primary(int seed, int branch) {
    int mixed = helper_mix(seed, branch + 2);
    if ((mixed & 1) == 0) {
        return mixed + helper_recursive(branch);
    }
    return mixed - helper_recursive(branch);
}

static int worker_fallback(int seed, int branch) {
    if (branch < 0) {
        return seed - 11;
    }
    return seed + helper_mix(branch, 3);
}

static int dispatch(worker_fn worker, int seed, int branch) {
    if (branch > 3) {
        return worker(seed, branch) + helper_mix(branch, 2);
    }
    return worker(seed, branch) - helper_recursive(4);
}

static int parse_and_route(int argc) {
    worker_fn worker = worker_primary;
    int branch = argc + 2;
    if ((argc % 2) == 0) {
        worker = worker_fallback;
        branch += 3;
    }
    return dispatch(worker, argc * 5 + 1, branch);
}

int main(int argc, char **argv) {
    int result = parse_and_route(argc);
    if (argv[0] == NULL) {
        return worker_fallback(result, -1);
    }
    return result & 1;
}
