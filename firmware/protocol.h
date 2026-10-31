/*
 * protocol.h — 传感器节点 <-> 上位机 / 云端 的数据帧协议
 *
 * 与 simulator/sensor_sim.py 输出的 JSON 字段保持一致，
 * 这样软件模拟器和真实固件可以共用同一套上位机 / 异常检测服务。
 *
 * 一帧示例（换行分隔的 JSON，UART 115200 8N1 或 MQTT 主题 iot/sensor）：
 *   {"id":"node-A","name":"实验室-01","ts":1710000000000,
 *    "temp":24.12,"hum":55.3,"lux":418.0,"anomaly":false}
 */
#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

#define NODE_ID      "node-A"
#define NODE_NAME    "实验室-01"

/* 一个采样帧 */
typedef struct {
    char     id[16];      /* 节点 ID */
    char     name[24];    /* 节点名称 */
    int64_t  ts;          /* 时间戳 (ms) */
    float    temp;        /* 温度 °C */
    float    hum;         /* 湿度 % */
    float    lux;         /* 光照 lux */
    uint8_t  anomaly;     /* 异常标志（由边缘侧判定，固件默认 0） */
} sensor_frame_t;

/* UTF-8 fields must be terminated. ts is Unix milliseconds; anomaly is JSON boolean.
 * Returns bytes excluding NUL, or -1 for invalid frame/insufficient buffer.
 * On error a nonempty supplied buffer is cleared; caller must not publish it.
 * 512 bytes accommodates all escaped fixed-capacity string fields and floats.
 */
int frame_to_json(const sensor_frame_t *f, char *buf, int buflen);

#endif /* PROTOCOL_H */

