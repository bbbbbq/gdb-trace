#include <stdio.h>
#include <string.h>

struct Entry {
    const char *name;
    int score;
};

static int render_line(const struct Entry *entry, int index) {
    char label[64];
    int written = snprintf(label, sizeof(label), "%s_%d", entry->name, index);
    if (written < 0) {
        return -1;
    }

    if ((entry->score & 1) == 0) {
        return printf("even:%s=%d\n", label, entry->score);
    }
    return printf("odd:%s=%d\n", label, entry->score);
}

static int emit_summary(const struct Entry *entries, size_t count) {
    int total = printf("begin=%zu\n", count);
    if (total < 0) {
        return -1;
    }

    for (size_t index = 0; index < count; ++index) {
        total += render_line(&entries[index], (int)index);
        if (strstr(entries[index].name, "beta") != NULL) {
            total += printf("tag:%s\n", entries[index].name);
        }
    }
    return printf("total=%d,count=%zu\n", total, count);
}

int main(void) {
    static const struct Entry entries[] = {
        {"alpha", 4},
        {"beta", 7},
        {"gamma", 10},
    };

    int written = emit_summary(entries, sizeof(entries) / sizeof(entries[0]));
    return written > 0 ? 0 : 1;
}
