#ifndef SPARK_DUAL_MODE_BRIDGE_H_
#define SPARK_DUAL_MODE_BRIDGE_H_

#include <stddef.h>
#include <stdint.h>

using SparkDualModeRxCallback = void (*)(const uint8_t *data, size_t length);
using SparkDualModeSessionCallback = void (*)(bool connected);

// Bluedroid-only bridge used by SRL mode. This interface intentionally exposes
// no BLE classes so the rest of Ignitron can continue using NimBLE safely.
void sparkDualModeStart(SparkDualModeRxCallback receiveCallback,
                        SparkDualModeSessionCallback sessionCallback);
void sparkDualModeStop();
void sparkDualModeRestartAdvertising(const char *reason);
bool sparkDualModeConnected();
void sparkDualModeNotify(const uint8_t *data, size_t length);

#endif
