/* PC output adapter and explicit, unimplemented ESP-AT reference interfaces. */
#include "mqtt_at.h"
#include <stdio.h>

bool mqtt_connect(const char *ssid, const char *psk, const char *broker, int port) {
    (void)ssid; (void)psk; (void)broker; (void)port;
#ifdef PC_BUILD
    return true; /* stdout adapter only; does not establish a connection */
#else
    /* TODO: HAL UART transport, credential escaping, ESP-AT version-specific
       MQTT config, response parser, timeouts and retries. No fake success. */
    return false;
#endif
}

bool mqtt_publish_frame(const sensor_frame_t *frame) {
    char output[512];
    if (frame_to_json(frame, output, sizeof output) < 0) return false;
#ifdef PC_BUILD
    return puts(output) >= 0;
#else
    /* TODO: ESP-AT payload escaping/length and publish acknowledgement. */
    return false;
#endif
}

void uart_send_frame(const sensor_frame_t *frame) {
    (void)frame;
    /* PC already emits one JSON line via mqtt_publish_frame.
       Board integration must provide the real UART driver. */
}
