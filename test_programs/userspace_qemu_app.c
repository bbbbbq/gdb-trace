#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Payload {
    const char *name;
    const char *weight_text;
};

static int normalize_token(const char *input, char *output, size_t size) {
    size_t length = strlen(input);
    if (length + 4 >= size) {
        return -1;
    }
    memcpy(output, input, length);
    output[length] = '_';
    output[length + 1] = 'o';
    output[length + 2] = 'k';
    output[length + 3] = '\0';
    return (int)length;
}

static int parse_weight(const char *text) {
    char *end = NULL;
    long value = strtol(text, &end, 10);
    if (end == text) {
        return -17;
    }
    return (int)(value * 3 + (end - text));
}

static int compose_record(const char *name, int score, char *buffer, size_t size) {
    return snprintf(buffer, size, "%s:%d", name, score);
}

static int accumulate_scores(const struct Payload *payloads, size_t count) {
    int total = 0;
    char normalized[64];
    char record[128];

    for (size_t index = 0; index < count; ++index) {
        int normalized_length = normalize_token(payloads[index].name, normalized, sizeof(normalized));
        int weight = parse_weight(payloads[index].weight_text);
        int formatted = compose_record(normalized, weight, record, sizeof(record));

        if (normalized_length < 0 || weight < 0 || formatted < 0) {
            return -1;
        }

        total += formatted;
        if (strstr(record, "beta") != NULL) {
            total += weight / 2;
        } else {
            total += normalized_length;
        }
    }

    return total;
}

static int process_payload(void) {
    static const struct Payload payloads[] = {
        {"alpha", "11"},
        {"beta", "7"},
        {"gamma", "5"},
        {"delta", "13"},
    };

    int total = accumulate_scores(payloads, sizeof(payloads) / sizeof(payloads[0]));
    if ((total & 1) == 0) {
        return total + parse_weight("19");
    }
    return total - parse_weight("3");
}

int main(void) {
    int result = process_payload();
    return result > 0 ? 0 : 1;
}
