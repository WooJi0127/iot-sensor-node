/* Bounded JSON serialization. Negative return always invalidates the output. */
#include "protocol.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static int escape_json(const char *src, size_t size, char *dst) {
    size_t out = 0;
    for (size_t i = 0; i < size; ++i) {
        unsigned char ch = (unsigned char)src[i];
        if (!ch) { dst[out] = '\0'; return 0; }
        if (ch == '"' || ch == '\\') {
            dst[out++] = '\\'; dst[out++] = (char)ch;
        } else if (ch < 32) {
            snprintf(dst + out, 7, "\\u%04x", ch); out += 6;
        } else {
            dst[out++] = (char)ch; /* identifiers/names must be valid UTF-8 */
        }
    }
    return -1; /* field not terminated within its declared capacity */
}

int frame_to_json(const sensor_frame_t *f, char *buf, int buflen) {
    char id[6 * 16 + 1], name[6 * 24 + 1];
    if (!buf || buflen <= 0) return -1;
    buf[0] = '\0';
    if (!f || f->ts < 0 || !isfinite(f->temp) || !isfinite(f->hum) ||
        !isfinite(f->lux) || escape_json(f->id, sizeof f->id, id) ||
        escape_json(f->name, sizeof f->name, name)) return -1;
    int length = snprintf(buf, (size_t)buflen,
        "{\"id\":\"%s\",\"name\":\"%s\",\"ts\":%lld,"
        "\"temp\":%.2f,\"hum\":%.2f,\"lux\":%.1f,\"anomaly\":%s}",
        id, name, (long long)f->ts, (double)f->temp, (double)f->hum,
        (double)f->lux, f->anomaly ? "true" : "false");
    if (length < 0 || length >= buflen) { buf[0] = '\0'; return -1; }
    return length;
}
