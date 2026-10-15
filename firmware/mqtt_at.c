/*
 * mqtt_at.c — ESP-AT 指令封装（真实固件版，需对接 UART 驱动）
 *
 * 仅给出结构骨架；AT 发送/接收需替换为板子的 HAL_UART_Transmit/Receive。
 * 关键指令：
 *   AT+CWMODE=1                     Station 模式
 *   AT+CWJAP="ssid","psk"           连 WiFi
 *   AT+MQTTUSERCFG=...              配置 MQTT 用户
 *   AT+MQTTCONN="broker",port,...   连 Broker
 *   AT+MQTTPUB="iot/sensor","<json>",...,0,0   发布
 */
#include "mqtt_at.h"
#include <stdio.h>
#include <string.h>

static int at_send(const char *cmd)
{
    /* 真实板子：HAL_UART_Transmit(&huart2, cmd, len, timeout); 并等待 "OK" */
    printf("[AT] %s\n", cmd);
    return 0;
}

bool mqtt_connect(const char *ssid, const char *psk, const char *broker, int port)
{
    char cmd[128];
    at_send("AT+CWMODE=1");
    snprintf(cmd, sizeof(cmd), "AT+CWJAP=\"%s\",\"%s\"", ssid, psk);
    at_send(cmd);
    snprintf(cmd, sizeof(cmd), "AT+MQTTCONN=\"%s\",%d,0,0", broker, port);
    at_send(cmd);
    return true;
}

bool mqtt_publish_frame(const sensor_frame_t *f)
{
    char buf[160], cmd[200];
    frame_to_json(f, buf, sizeof(buf));
    snprintf(cmd, sizeof(cmd),
             "AT+MQTTPUB=\"iot/sensor\",\"%s\",0,0", buf);
    at_send(cmd);
    return true;
}

void uart_send_frame(const sensor_frame_t *f)
{
    char buf[160];
    frame_to_json(f, buf, sizeof(buf));
    at_send(buf);   /* 串口透传，调试用 */
}
