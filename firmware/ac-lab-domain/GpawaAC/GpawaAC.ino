// Board: ESP32S3 Dev Module, Arduino-ESP32 3.x
#include <Arduino.h>
SET_LOOP_TASK_STACK_SIZE(32768);
void firmwareSetup();
void firmwareLoop();
void setup(){firmwareSetup();}
void loop(){firmwareLoop();}
