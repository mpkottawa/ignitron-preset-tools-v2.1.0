#include "SparkDualModeBridge.h"

#include <Arduino.h>
#include <BLE2902.h>
#include <BLEDevice.h>
#include <string>

namespace {
volatile bool clientConnected = false;
SparkDualModeRxCallback rxCallback = nullptr;
SparkDualModeSessionCallback sessionCallback = nullptr;
BLEServer *server = nullptr;
BLEService *service = nullptr;
BLECharacteristic *writeCharacteristic = nullptr;
BLECharacteristic *notifyCharacteristic = nullptr;
BLEAdvertising *advertising = nullptr;

class ServerCallbacks : public BLEServerCallbacks {
public:
    void onConnect(BLEServer *activeServer) override {
        (void)activeServer;
        clientConnected = true;
        Serial.println("BT_DUAL_BLE CONNECT");
        if (sessionCallback) {
            sessionCallback(true);
        }
    }

    void onDisconnect(BLEServer *activeServer) override {
        (void)activeServer;
        clientConnected = false;
        if (sessionCallback) {
            sessionCallback(false);
        }
        Serial.println("BT_DUAL_BLE DISCONNECT advertising=restart");
        sparkDualModeRestartAdvertising("ble_disconnect");
    }
};

class WriteCallbacks : public BLECharacteristicCallbacks {
public:
    void onWrite(BLECharacteristic *characteristic) override {
        const std::string value = characteristic->getValue();
        if (value.empty() || !rxCallback) {
            return;
        }
        rxCallback(reinterpret_cast<const uint8_t *>(value.data()),
                   value.size());
        Serial.printf("BT_DUAL_BLE RX bytes=%u\n",
                      (unsigned int)value.size());
    }
};

ServerCallbacks serverCallbacks;
WriteCallbacks writeCallbacks;
} // namespace

void sparkDualModeRestartAdvertising(const char *reason) {
    if (!advertising || clientConnected) {
        return;
    }
    advertising->start();
    Serial.printf("BT_DUAL_ADV reason=%s started=1\n", reason);
}

void sparkDualModeStart(SparkDualModeRxCallback receiveCallback,
                        SparkDualModeSessionCallback activeSessionCallback) {
    rxCallback = receiveCallback;
    sessionCallback = activeSessionCallback;
    if (server) {
        sparkDualModeRestartAdvertising("reuse");
        return;
    }

    Serial.println("BT_DUAL_INIT name=Spark 40 BLE service=FFC0 before_spp=1");
    BLEDevice::init("Spark 40 BLE");
    BLEDevice::setMTU(500);

    server = BLEDevice::createServer();
    server->setCallbacks(&serverCallbacks);
    service = server->createService(BLEUUID((uint16_t)0xFFC0));
    writeCharacteristic = service->createCharacteristic(
        BLEUUID((uint16_t)0xFFC1),
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE |
            BLECharacteristic::PROPERTY_WRITE_NR);
    writeCharacteristic->setCallbacks(&writeCallbacks);

    notifyCharacteristic = service->createCharacteristic(
        BLEUUID((uint16_t)0xFFC2),
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
    notifyCharacteristic->addDescriptor(new BLE2902());
    service->start();

    advertising = BLEDevice::getAdvertising();
    advertising->addServiceUUID(service->getUUID());
    advertising->setScanResponse(true);
    sparkDualModeRestartAdvertising("initial");
}

void sparkDualModeStop() {
    if (!advertising) {
        return;
    }
    advertising->stop();
    clientConnected = false;
    Serial.println("BT_DUAL_ADV stopped");
}

bool sparkDualModeConnected() {
    return clientConnected;
}

void sparkDualModeNotify(const uint8_t *data, size_t length) {
    if (!clientConnected || !notifyCharacteristic || !data || length == 0) {
        return;
    }
    notifyCharacteristic->setValue(const_cast<uint8_t *>(data), length);
    notifyCharacteristic->notify();
}
