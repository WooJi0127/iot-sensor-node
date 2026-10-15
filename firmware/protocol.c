/*
 * protocol.c — 帧序列化（与 simulator 输出字段一致）
 */
#include "protocol.h"
#include <stdio.h>

void frame_to_json(const sensor_frame_t *f, char *buf, int buflen)
{
    snprintf(buf, buflen,
             "{\"id\":\"%s\",\"name\":\"%s\",\"ts\":%lld,"
             "\"temp\":%.2f,\"hum\":%.2f,\"lux\":%.1f,\"anomaly\":%d}",
             f->id, f->name, (long long)f->ts,
             f->temp, f->hum, f->lux, f->anomaly);
}
