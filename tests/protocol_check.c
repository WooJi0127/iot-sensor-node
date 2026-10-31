#include "protocol.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    sensor_frame_t frame = {0};
    char output[512], small[4] = "abc";
    strcpy(frame.id, "node-A");
    strcpy(frame.name, "a\"b\\c\n");
    frame.ts = 1700000000000LL;
    frame.temp = 24.5f; frame.hum = 50; frame.lux = 300;
    frame.anomaly = 1;
    if (frame_to_json(&frame, small, sizeof small) >= 0 || small[0] != '\0') return 1;
    if (frame_to_json(&frame, output, sizeof output) <= 0) return 2;
    puts(output);
    frame.temp = NAN;
    if (frame_to_json(&frame, output, sizeof output) >= 0 || output[0] != '\0') return 3;
    frame.temp = 24;
    memset(frame.id, 'x', sizeof frame.id);  /* missing terminator */
    if (frame_to_json(&frame, output, sizeof output) >= 0) return 4;
    if (frame_to_json(NULL, output, sizeof output) >= 0) return 5;
    if (frame_to_json(&frame, NULL, 0) >= 0) return 6;
    return 0;
}
