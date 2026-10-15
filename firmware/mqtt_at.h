/*
 * mqtt_at.h — 通过 ESP8266/ESP-AT 模组上报 MQTT
 *
 * 简化接口：连接 WiFi、连接 MQTT Broker、发布一帧 JSON。
 * 真实固件中通过 UART 发送 AT 指令并解析 OK/ERROR 响应。
 */
#ifndef MQTT_AT_H
#define MQTT_AT_H

#include <stdbool.h>
#include "protocol.h"

/* 连接 WiFi 与 MQTT Broker */
bool mqtt_connect(const char *ssid, const char *psk, const char *broker, int port);

/* 发布一帧传感器数据到主题 iot/sensor */
bool mqtt_publish_frame(const sensor_frame_t *f);

/* 也可以走纯 UART 透传（调试用），把帧直接打到串口 */
void uart_send_frame(const sensor_frame_t *f);

#endif /* MQTT_AT_H */
