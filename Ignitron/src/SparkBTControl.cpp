/*
 * SparkBTControl.cpp
 *
 *  Created on: 19.08.2021
 *      Author: stangreg
 */

#include "SparkBTControl.h"
#include <LittleFS.h>
#include <esp_a2dp_api.h>
#include <esp_avrc_api.h>
#include <esp_bt_device.h>
#include <esp_gap_ble_api.h>
#include <esp_gap_bt_api.h>
#include <esp_gatt_common_api.h>
#include <esp_gatts_api.h>

bool SparkBTControl::isAppConnectedSerial_ = false;
string SparkBTControl::serialPeerAddress_ = "";

namespace {
volatile bool serialClientConnectedForDiscovery = false;
volatile bool serialDiscoveryRestoreScheduled = false;
volatile bool serialAudioProfileStarting = false;
volatile bool serialAudioProfileReady = false;
volatile bool serialAudioConnected = false;
volatile esp_a2d_connection_state_t serialAudioConnectionState =
    ESP_A2D_CONNECTION_STATE_DISCONNECTED;
volatile bool serialAudioReconnectScheduled = false;
volatile bool serialAvrcControllerReady = false;
volatile bool serialAvrcTargetReady = false;
SparkDataControl *serialSessionDataControl = nullptr;
volatile bool serialBleClientConnected = false;
volatile bool serialBleNotificationsEnabled = false;
volatile bool serialBleAdvertising = false;
volatile bool serialBleAdvertisingDataReady = false;
volatile bool serialBleServiceReady = false;
volatile bool serialBleRegistered = false;

string formatBtAddress(const uint8_t *address);

esp_gatt_if_t serialBleGattInterface = ESP_GATT_IF_NONE;
uint16_t serialBleConnectionId = 0;

enum SerialBleAttributeIndex {
    SERIAL_BLE_SERVICE,
    SERIAL_BLE_WRITE_DECLARATION,
    SERIAL_BLE_WRITE_VALUE,
    SERIAL_BLE_NOTIFY_DECLARATION,
    SERIAL_BLE_NOTIFY_VALUE,
    SERIAL_BLE_NOTIFY_CCCD,
    SERIAL_BLE_ATTRIBUTE_COUNT
};

uint16_t serialBleHandles[SERIAL_BLE_ATTRIBUTE_COUNT] = {};
uint16_t serialBlePrimaryServiceUuid = ESP_GATT_UUID_PRI_SERVICE;
uint16_t serialBleCharacteristicDeclarationUuid = ESP_GATT_UUID_CHAR_DECLARE;
uint16_t serialBleClientConfigUuid = ESP_GATT_UUID_CHAR_CLIENT_CONFIG;
uint16_t serialBleServiceUuid = 0xFFC0;
uint16_t serialBleWriteUuid = 0xFFC1;
uint16_t serialBleNotifyUuid = 0xFFC2;
uint8_t serialBleWriteProperties = ESP_GATT_CHAR_PROP_BIT_READ |
                                   ESP_GATT_CHAR_PROP_BIT_WRITE |
                                   ESP_GATT_CHAR_PROP_BIT_WRITE_NR;
uint8_t serialBleNotifyProperties = ESP_GATT_CHAR_PROP_BIT_READ |
                                    ESP_GATT_CHAR_PROP_BIT_NOTIFY;
uint8_t serialBleWriteValue[200] = {};
uint8_t serialBleNotifyValue[200] = {};
uint8_t serialBleClientConfig[2] = {0, 0};
uint8_t serialBleAdvertisedServiceUuid[2] = {0xC0, 0xFF};

esp_gatts_attr_db_t serialBleAttributeTable[SERIAL_BLE_ATTRIBUTE_COUNT] = {
    {{ESP_GATT_AUTO_RSP},
     {ESP_UUID_LEN_16, reinterpret_cast<uint8_t *>(&serialBlePrimaryServiceUuid),
      ESP_GATT_PERM_READ, sizeof(serialBleServiceUuid),
      sizeof(serialBleServiceUuid),
      reinterpret_cast<uint8_t *>(&serialBleServiceUuid)}},

    {{ESP_GATT_AUTO_RSP},
     {ESP_UUID_LEN_16,
      reinterpret_cast<uint8_t *>(&serialBleCharacteristicDeclarationUuid),
      ESP_GATT_PERM_READ, sizeof(serialBleWriteProperties),
      sizeof(serialBleWriteProperties), &serialBleWriteProperties}},

    {{ESP_GATT_AUTO_RSP},
     {ESP_UUID_LEN_16, reinterpret_cast<uint8_t *>(&serialBleWriteUuid),
      ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE,
      sizeof(serialBleWriteValue), 0, serialBleWriteValue}},

    {{ESP_GATT_AUTO_RSP},
     {ESP_UUID_LEN_16,
      reinterpret_cast<uint8_t *>(&serialBleCharacteristicDeclarationUuid),
      ESP_GATT_PERM_READ, sizeof(serialBleNotifyProperties),
      sizeof(serialBleNotifyProperties), &serialBleNotifyProperties}},

    {{ESP_GATT_AUTO_RSP},
     {ESP_UUID_LEN_16, reinterpret_cast<uint8_t *>(&serialBleNotifyUuid),
      ESP_GATT_PERM_READ, sizeof(serialBleNotifyValue), 0,
      serialBleNotifyValue}},

    {{ESP_GATT_AUTO_RSP},
     {ESP_UUID_LEN_16,
      reinterpret_cast<uint8_t *>(&serialBleClientConfigUuid),
      ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE,
      sizeof(serialBleClientConfig), sizeof(serialBleClientConfig),
      serialBleClientConfig}},
};

esp_ble_adv_data_t serialBleAdvertisingData = {
    false, true, false, 0, 0, 0, 0, nullptr, 0, nullptr,
    sizeof(serialBleAdvertisedServiceUuid), serialBleAdvertisedServiceUuid,
    ESP_BLE_ADV_FLAG_GEN_DISC | ESP_BLE_ADV_FLAG_DMT_CONTROLLER_SPT |
        ESP_BLE_ADV_FLAG_DMT_HOST_SPT};

esp_ble_adv_params_t serialBleAdvertisingParameters = {
    0x20, 0x40, ADV_TYPE_IND, BLE_ADDR_TYPE_PUBLIC, {}, BLE_ADDR_TYPE_PUBLIC,
    ADV_CHNL_ALL, ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY};

void maybeStartSerialBleAdvertising() {
    if (!serialBleAdvertisingDataReady || !serialBleServiceReady ||
        serialBleClientConnected || serialBleAdvertising) {
        return;
    }
    const esp_err_t result =
        esp_ble_gap_start_advertising(&serialBleAdvertisingParameters);
    Serial.printf("BT_BLE_BRIDGE advertise_request=%d\n", (int)result);
}

void serialBleGapCallback(esp_gap_ble_cb_event_t event,
                          esp_ble_gap_cb_param_t *parameter) {
    if (event == ESP_GAP_BLE_ADV_DATA_SET_COMPLETE_EVT) {
        serialBleAdvertisingDataReady = parameter->adv_data_cmpl.status == ESP_BT_STATUS_SUCCESS;
        Serial.printf("BT_BLE_BRIDGE adv_data status=%d\n",
                      (int)parameter->adv_data_cmpl.status);
        maybeStartSerialBleAdvertising();
    } else if (event == ESP_GAP_BLE_ADV_START_COMPLETE_EVT) {
        serialBleAdvertising = parameter->adv_start_cmpl.status == ESP_BT_STATUS_SUCCESS;
        Serial.printf("BT_BLE_BRIDGE advertising status=%d\n",
                      (int)parameter->adv_start_cmpl.status);
    } else if (event == ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT) {
        serialBleAdvertising = false;
    }
}

void serialBleGattCallback(esp_gatts_cb_event_t event, esp_gatt_if_t gattIf,
                           esp_ble_gatts_cb_param_t *parameter) {
    if (event == ESP_GATTS_REG_EVT) {
        if (parameter->reg.status != ESP_GATT_OK) {
            Serial.printf("BT_BLE_BRIDGE register status=%d\n",
                          (int)parameter->reg.status);
            return;
        }
        serialBleGattInterface = gattIf;
        serialBleRegistered = true;
        // Classic and BLE share one controller identity in this hybrid mode.
        // Keep the Audio name on both transports so enabling the companion
        // service cannot rename the proven SPP endpoint during inquiry.
        const esp_err_t nameResult =
            esp_ble_gap_set_device_name("Spark 40 Audio");
        const esp_err_t advResult =
            esp_ble_gap_config_adv_data(&serialBleAdvertisingData);
        const esp_err_t tableResult = esp_ble_gatts_create_attr_tab(
            serialBleAttributeTable, gattIf, SERIAL_BLE_ATTRIBUTE_COUNT, 0);
        Serial.printf(
            "BT_BLE_BRIDGE registered name=%d adv=%d table=%d\n",
            (int)nameResult, (int)advResult, (int)tableResult);
    } else if (event == ESP_GATTS_CREAT_ATTR_TAB_EVT) {
        if (parameter->add_attr_tab.status != ESP_GATT_OK ||
            parameter->add_attr_tab.num_handle != SERIAL_BLE_ATTRIBUTE_COUNT) {
            Serial.printf("BT_BLE_BRIDGE table status=%d handles=%u\n",
                          (int)parameter->add_attr_tab.status,
                          (unsigned int)parameter->add_attr_tab.num_handle);
            return;
        }
        memcpy(serialBleHandles, parameter->add_attr_tab.handles,
               sizeof(serialBleHandles));
        const esp_err_t result =
            esp_ble_gatts_start_service(serialBleHandles[SERIAL_BLE_SERVICE]);
        serialBleServiceReady = result == ESP_OK;
        Serial.printf("BT_BLE_BRIDGE service status=%d heap=%u\n", (int)result,
                      (unsigned int)ESP.getFreeHeap());
        maybeStartSerialBleAdvertising();
    } else if (event == ESP_GATTS_CONNECT_EVT) {
        serialBleConnectionId = parameter->connect.conn_id;
        serialBleClientConnected = true;
        serialBleAdvertising = false;
        Serial.printf("BT_BLE_BRIDGE CONNECT peer=%s\n",
                      formatBtAddress(parameter->connect.remote_bda).c_str());
    } else if (event == ESP_GATTS_DISCONNECT_EVT) {
        serialBleClientConnected = false;
        serialBleNotificationsEnabled = false;
        serialBleAdvertising = false;
        Serial.printf("BT_BLE_BRIDGE DISCONNECT reason=%u advertising=restart\n",
                      (unsigned int)parameter->disconnect.reason);
        maybeStartSerialBleAdvertising();
    } else if (event == ESP_GATTS_WRITE_EVT && !parameter->write.is_prep) {
        if (parameter->write.handle ==
            serialBleHandles[SERIAL_BLE_NOTIFY_CCCD]) {
            serialBleNotificationsEnabled =
                parameter->write.len >= 2 && parameter->write.value[0] == 1 &&
                parameter->write.value[1] == 0;
            Serial.printf("BT_BLE_BRIDGE notifications=%d\n",
                          serialBleNotificationsEnabled ? 1 : 0);
        } else if (parameter->write.handle ==
                       serialBleHandles[SERIAL_BLE_WRITE_VALUE] &&
                   parameter->write.len > 0) {
            ByteVector message(parameter->write.value,
                               parameter->write.value + parameter->write.len);
            SparkDataControl::queueMessage(message);
        }
    }
}

void startSerialBleBridge() {
    // A real Spark exposes the FFC0 control service during discovery. Keep the
    // proven Classic SPP transport active, while adding the same BLE endpoint
    // through Bluedroid, the host BluetoothSerial already initialized.
    if (serialBleRegistered) {
        maybeStartSerialBleAdvertising();
        return;
    }
    Serial.println("BT_BLE_BRIDGE starting service=FFC0 payload=23/31");
    serialBleAdvertisingDataReady = false;
    serialBleServiceReady = false;
    serialBleAdvertising = false;
    const esp_err_t gapResult =
        esp_ble_gap_register_callback(serialBleGapCallback);
    const esp_err_t gattResult =
        esp_ble_gatts_register_callback(serialBleGattCallback);
    const esp_err_t appResult = esp_ble_gatts_app_register(0x40);
    const esp_err_t mtuResult = esp_ble_gatt_set_local_mtu(500);
    Serial.printf("BT_BLE_BRIDGE init gap=%d gatt=%d app=%d mtu=%d\n",
                  (int)gapResult, (int)gattResult, (int)appResult,
                  (int)mtuResult);
}

void stopSerialBleBridge() {
    if (!serialBleRegistered) {
        return;
    }
    const esp_err_t result = esp_ble_gap_stop_advertising();
    serialBleClientConnected = false;
    serialBleNotificationsEnabled = false;
    serialBleAdvertising = false;
    Serial.printf("BT_BLE_BRIDGE stopped status=%d\n", (int)result);
}

void resetSerialSession(bool connected) {
    if (serialSessionDataControl) {
        serialSessionDataControl->resetAmpClientSession();
    }
    Serial.printf("BT_SERIAL_SESSION connected=%d reset=1\n",
                  connected ? 1 : 0);
}

string formatBtAddress(const uint8_t *address) {
    if (!address) {
        return "none";
    }
    char text[18];
    snprintf(text, sizeof(text), "%02X:%02X:%02X:%02X:%02X:%02X",
             address[0], address[1], address[2], address[3], address[4],
             address[5]);
    return string(text);
}

void printBondedDevices() {
    const int total = esp_bt_gap_get_bond_device_num();
    Serial.printf("BT_BONDS count=%d\n", total);
    if (total <= 0) {
        return;
    }

    const int capacity = 20;
    esp_bd_addr_t devices[capacity];
    int requested = total < capacity ? total : capacity;
    const esp_err_t result =
        esp_bt_gap_get_bond_device_list(&requested, devices);
    Serial.printf("BT_BONDS result=%d listed=%d\n", (int)result, requested);
    if (result != ESP_OK) {
        return;
    }
    for (int i = 0; i < requested; ++i) {
        Serial.printf("BT_BOND index=%d address=%s\n", i,
                      formatBtAddress(devices[i]).c_str());
    }
}

void configureSparkAudioClassOfDevice() {
    // BluetoothSerial identifies itself as a computer by default. That works
    // for generic SPP clients, but the Spark app stops considering the bonded
    // device a compatible amp after the first connection. Match the Class of
    // Device advertised by a real Spark 2 Audio endpoint (0x240404):
    // Audio/Video, wearable-headset minor class, Audio + Rendering services.
    esp_bt_cod_t requested = {};
    requested.major = ESP_BT_COD_MAJOR_DEV_AV;
    requested.minor = 0x01;
    requested.service = ESP_BT_COD_SRVC_AUDIO | ESP_BT_COD_SRVC_RENDERING;

    const esp_err_t setResult =
        esp_bt_gap_set_cod(requested, ESP_BT_INIT_COD);
    esp_bt_cod_t effective = {};
    const esp_err_t getResult = esp_bt_gap_get_cod(&effective);
    const uint32_t raw = (effective.service << ESP_BT_COD_SRVC_BIT_OFFSET) |
                         (effective.major << ESP_BT_COD_MAJOR_DEV_BIT_OFFSET) |
                         (effective.minor << 2);
    Serial.printf(
        "BT_COD set=%d get=%d value=0x%06lX major=%u minor=%u service=0x%03lX\n",
        (int)setResult, (int)getResult, (unsigned long)raw,
        (unsigned int)effective.major, (unsigned int)effective.minor,
        (unsigned long)effective.service);
}

void restoreSerialDiscoverability(const char *reason) {
#ifdef ESP_IDF_VERSION_MAJOR
    const esp_err_t result = esp_bt_gap_set_scan_mode(
        ESP_BT_CONNECTABLE, ESP_BT_GENERAL_DISCOVERABLE);
#else
    const esp_err_t result = esp_bt_gap_set_scan_mode(
        ESP_BT_SCAN_MODE_CONNECTABLE_DISCOVERABLE);
#endif
    Serial.printf(
        "BT_SCANMODE reason=%s status=%d connectable=1 discoverable=1 bonds=%d\n",
        reason, (int)result, esp_bt_gap_get_bond_device_num());
}

void delayedSerialDiscoverabilityRestore(void *parameter) {
    (void)parameter;
    // The Classic Bluetooth stack can update its scan mode after delivering
    // ESP_SPP_CLOSE_EVT. Reapply it after that cleanup has completed.
    vTaskDelay(pdMS_TO_TICKS(750));
    if (!serialClientConnectedForDiscovery) {
        restoreSerialDiscoverability("client_close_delayed");
    } else {
        Serial.println("BT_SCANMODE reason=client_close_delayed skipped=connected");
    }
    serialDiscoveryRestoreScheduled = false;
    vTaskDelete(nullptr);
}

void scheduleSerialDiscoverabilityRestore() {
    if (serialDiscoveryRestoreScheduled) {
        return;
    }
    serialDiscoveryRestoreScheduled = true;
    const BaseType_t result =
        xTaskCreate(delayedSerialDiscoverabilityRestore, "bt-discoverable", 2048,
                    nullptr, 1, nullptr);
    if (result != pdPASS) {
        serialDiscoveryRestoreScheduled = false;
        Serial.printf("BT_SCANMODE reason=client_close_delayed schedule_error=%d\n",
                      (int)result);
    }
}

void discardSerialAudio(const uint8_t *data, uint32_t length) {
    (void)data;
    (void)length;
}

void delayedSerialAudioReconnect(void *parameter) {
    (void)parameter;
    // Let Android finish noticing the newly available SDP records before the
    // pedal reconnects the audio profile that makes it visible to Spark.
    vTaskDelay(pdMS_TO_TICKS(1000));
    if (!serialAudioProfileReady ||
        serialAudioConnectionState != ESP_A2D_CONNECTION_STATE_DISCONNECTED) {
        Serial.printf("BT_A2DP RECONNECT skipped ready=%d state=%d\n",
                      serialAudioProfileReady ? 1 : 0,
                      (int)serialAudioConnectionState);
        serialAudioReconnectScheduled = false;
        vTaskDelete(nullptr);
        return;
    }

    int bondedCount = esp_bt_gap_get_bond_device_num();
    if (bondedCount != 1) {
        // Never guess which phone to wake when more than one has been paired.
        // A first-time or multi-phone setup remains discoverable and can be
        // selected normally from Android/Spark.
        Serial.printf("BT_A2DP RECONNECT skipped bonds=%d\n", bondedCount);
        serialAudioReconnectScheduled = false;
        vTaskDelete(nullptr);
        return;
    }

    esp_bd_addr_t bondedDevice = {};
    int requested = 1;
    const esp_err_t listResult =
        esp_bt_gap_get_bond_device_list(&requested, &bondedDevice);
    esp_err_t connectResult = ESP_FAIL;
    if (listResult == ESP_OK && requested == 1 && serialAudioProfileReady &&
        serialAudioConnectionState == ESP_A2D_CONNECTION_STATE_DISCONNECTED) {
        connectResult = esp_a2d_sink_connect(bondedDevice);
    }
    Serial.printf("BT_A2DP RECONNECT peer=%s list=%d connect=%d\n",
                  formatBtAddress(bondedDevice).c_str(), (int)listResult,
                  (int)connectResult);
    serialAudioReconnectScheduled = false;
    vTaskDelete(nullptr);
}

void scheduleSerialAudioReconnect() {
    if (serialAudioReconnectScheduled) {
        return;
    }
    serialAudioReconnectScheduled = true;
    const BaseType_t result =
        xTaskCreate(delayedSerialAudioReconnect, "bt-audio-reconnect", 3072,
                    nullptr, 1, nullptr);
    if (result != pdPASS) {
        serialAudioReconnectScheduled = false;
        Serial.printf("BT_A2DP RECONNECT task_error=%d\n", (int)result);
    }
}

void serialAvrcControllerCallback(esp_avrc_ct_cb_event_t event,
                                  esp_avrc_ct_cb_param_t *param) {
    (void)param;
    if (event == ESP_AVRC_CT_CONNECTION_STATE_EVT) {
        Serial.printf("BT_AVRCP CT connection=%d\n",
                      param && param->conn_stat.connected ? 1 : 0);
    }
}

void serialAvrcTargetCallback(esp_avrc_tg_cb_event_t event,
                              esp_avrc_tg_cb_param_t *param) {
    (void)param;
    if (event == ESP_AVRC_TG_CONNECTION_STATE_EVT) {
        Serial.printf("BT_AVRCP TG connection=%d\n",
                      param && param->conn_stat.connected ? 1 : 0);
    }
}

void serialAudioCallback(esp_a2d_cb_event_t event, esp_a2d_cb_param_t *param) {
    if (!param) {
        return;
    }
    if (event == ESP_A2D_PROF_STATE_EVT) {
        serialAudioProfileStarting = false;
        serialAudioProfileReady =
            param->a2d_prof_stat.init_state == ESP_A2D_INIT_SUCCESS;
        Serial.printf("BT_A2DP PROFILE ready=%d state=%d\n",
                      serialAudioProfileReady ? 1 : 0,
                      (int)param->a2d_prof_stat.init_state);
        if (serialAudioProfileReady) {
            configureSparkAudioClassOfDevice();
            restoreSerialDiscoverability("a2dp_ready");
            scheduleSerialAudioReconnect();
        }
    } else if (event == ESP_A2D_CONNECTION_STATE_EVT) {
        serialAudioConnectionState = param->conn_stat.state;
        serialAudioConnected =
            param->conn_stat.state == ESP_A2D_CONNECTION_STATE_CONNECTED;
        Serial.printf("BT_A2DP CONNECTION state=%d connected=%d peer=%s reason=%d\n",
                      (int)param->conn_stat.state,
                      serialAudioConnected ? 1 : 0,
                      formatBtAddress(param->conn_stat.remote_bda).c_str(),
                      (int)param->conn_stat.disc_rsn);
        if (param->conn_stat.state == ESP_A2D_CONNECTION_STATE_DISCONNECTED) {
            restoreSerialDiscoverability("a2dp_disconnect");
            scheduleSerialAudioReconnect();
        }
    } else if (event == ESP_A2D_AUDIO_STATE_EVT) {
        Serial.printf("BT_A2DP AUDIO state=%d\n", (int)param->audio_stat.state);
    }
}

void startSerialAudioProfile() {
    if (serialAudioProfileStarting || serialAudioProfileReady) {
        return;
    }
    serialAudioProfileStarting = true;

    // Match Espressif's supported A2DP sink startup order. Android uses the
    // AudioSink/AVRCP SDP records to find an already-paired Spark immediately,
    // instead of relying on the Spark app's very short Classic inquiry.
    const esp_err_t avrcControllerInit = esp_avrc_ct_init();
    const esp_err_t avrcControllerCallback =
        esp_avrc_ct_register_callback(serialAvrcControllerCallback);
    serialAvrcControllerReady = avrcControllerInit == ESP_OK;

    const esp_err_t avrcTargetInit = esp_avrc_tg_init();
    const esp_err_t avrcTargetCallback =
        esp_avrc_tg_register_callback(serialAvrcTargetCallback);
    serialAvrcTargetReady = avrcTargetInit == ESP_OK;
    esp_avrc_rn_evt_cap_mask_t eventCapabilities = {};
    esp_avrc_rn_evt_bit_mask_operation(ESP_AVRC_BIT_MASK_OP_SET,
                                       &eventCapabilities,
                                       ESP_AVRC_RN_VOLUME_CHANGE);
    const esp_err_t avrcCapabilities =
        esp_avrc_tg_set_rn_evt_cap(&eventCapabilities);

    const esp_err_t initResult = esp_a2d_sink_init();
    const esp_err_t callbackResult =
        esp_a2d_register_callback(serialAudioCallback);
    const esp_err_t dataResult =
        esp_a2d_sink_register_data_callback(discardSerialAudio);
    Serial.printf(
        "BT_A2DP INIT avrc_ct=%d/%d avrc_tg=%d/%d caps=%d a2dp=%d callback=%d data=%d\n",
        (int)avrcControllerInit, (int)avrcControllerCallback,
        (int)avrcTargetInit, (int)avrcTargetCallback, (int)avrcCapabilities,
        (int)initResult, (int)callbackResult, (int)dataResult);
    if (initResult != ESP_OK) {
        serialAudioProfileStarting = false;
    }
}

void stopSerialAudioProfile() {
    if (!serialAudioProfileStarting && !serialAudioProfileReady) {
        return;
    }
    const esp_err_t result = esp_a2d_sink_deinit();
    const esp_err_t avrcTargetResult = serialAvrcTargetReady
                                           ? esp_avrc_tg_deinit()
                                           : ESP_OK;
    const esp_err_t avrcControllerResult = serialAvrcControllerReady
                                               ? esp_avrc_ct_deinit()
                                               : ESP_OK;
    Serial.printf(
        "BT_A2DP STOP status=%d avrc_tg=%d avrc_ct=%d connected=%d\n",
        (int)result, (int)avrcTargetResult, (int)avrcControllerResult,
        serialAudioConnected ? 1 : 0);
    serialAudioProfileStarting = false;
    serialAudioProfileReady = false;
    serialAudioConnected = false;
    serialAudioConnectionState = ESP_A2D_CONNECTION_STATE_DISCONNECTED;
    serialAvrcControllerReady = false;
    serialAvrcTargetReady = false;
    delay(50);
}
} // namespace

// ClientCallbacks SparkBTControl::clientCB;

SparkBTControl::SparkBTControl() {
    // advDevCB = new AdvertisedDeviceCallbacks();
    advDevice_ = nullptr;
    spark_dc_ = nullptr;
}

SparkBTControl::SparkBTControl(SparkDataControl *dc) {
    // advDevCB = new AdvertisedDeviceCallbacks();
    advDevice_ = nullptr;
    spark_dc_ = dc;
}

SparkBTControl::~SparkBTControl() {
    Serial.println("Deleting BLE objects");
    if (advDevice_) {
        delete advDevice_;
        advDevice_ = nullptr;
    }
    if (btSerial) {
        delete btSerial;
        btSerial = nullptr;
    }
}

// Initializing BLE connection with NimBLE
void SparkBTControl::initBLE(notify_callback notifyCallback) {
    // NimBLEDevice::init("");
    advDevice_ = new NimBLEAdvertisedDevice();
    notifyCB_ = notifyCallback;
#ifdef ENABLE_IPT_AMP_BLOCKLIST
    loadBlockedAmp();
#endif

    /** Optional: set the transmit power, default is 3db */
    NimBLEDevice::setPower(ESP_PWR_LVL_P9); /** +9db */

    /** create new scan */
    NimBLEScan *scan = NimBLEDevice::getScan();

    /** create a callback that gets called when advertisers are found */
    scan->setAdvertisedDeviceCallbacks(this, false);

    /** Set scan interval (how often) and window (how long) in milliseconds */
    scan->setInterval(45);
    scan->setWindow(15);

    /** Active scan will gather scan response data from advertisers
     but will use more energy from both devices
     */
    scan->setActiveScan(true);
    /** Start scanning for advertisers for the scan time specified (in seconds) 0 = forever
     Optional callback for when scanning stops.
     */
    Serial.println("Starting scan");
    scan->start(kScanTime, scanEndedCB);
}

void SparkBTControl::loadBlockedAmp() {
    blockedAmpAddresses_.clear();
    blockedAmpNames_.clear();
    File file = LittleFS.open(blockedAmpFileName_.c_str(), FILE_READ);
    if (!file) {
        return;
    }

    while (file.available()) {
        String line = file.readStringUntil('\n');
        line.trim();
        if (line.length() == 0) {
            continue;
        }

        int separator = line.indexOf('|');
        String address = separator >= 0 ? line.substring(0, separator) : line;
        String name = separator >= 0 ? line.substring(separator + 1) : "";
        address.trim();
        address.toLowerCase();
        name.trim();
        if (address.length() == 0 || isAmpBlocked(address.c_str())) {
            continue;
        }

        blockedAmpAddresses_.push_back(address.c_str());
        blockedAmpNames_.push_back(name.c_str());
        if (name.length() > 0) {
            Serial.printf("Blocked Spark amp: %s (%s)\n", name.c_str(), address.c_str());
        } else {
            Serial.printf("Blocked Spark amp: %s\n", address.c_str());
        }
    }
    file.close();
}

bool SparkBTControl::isAmpBlocked(const string &address) const {
    for (const string &blockedAddress : blockedAmpAddresses_) {
        if (blockedAddress == address) {
            return true;
        }
    }
    return false;
}

string SparkBTControl::blockedAmpName(const string &address) const {
    for (size_t i = 0; i < blockedAmpAddresses_.size(); ++i) {
        if (blockedAmpAddresses_[i] == address && i < blockedAmpNames_.size()) {
            return blockedAmpNames_[i];
        }
    }
    return "";
}

bool SparkBTControl::getBlockedAmp(size_t index, string &name,
                                   string &address) const {
    if (index >= blockedAmpAddresses_.size() || index >= blockedAmpNames_.size()) {
        return false;
    }
    address = blockedAmpAddresses_[index];
    name = blockedAmpNames_[index].empty() ? "Spark amp" : blockedAmpNames_[index];
    return true;
}

bool SparkBTControl::saveBlockedAmps() {
    if (blockedAmpAddresses_.empty()) {
        return !LittleFS.exists(blockedAmpFileName_.c_str()) ||
               LittleFS.remove(blockedAmpFileName_.c_str());
    }

    File file = LittleFS.open(blockedAmpFileName_.c_str(), FILE_WRITE);
    if (!file) {
        return false;
    }
    for (size_t i = 0; i < blockedAmpAddresses_.size(); ++i) {
        file.print(blockedAmpAddresses_[i].c_str());
        file.print('|');
        file.println(blockedAmpNames_[i].c_str());
    }
    file.close();
    return true;
}

bool SparkBTControl::blockConnectedAmp(const string &ampName, string &blockedName,
                                       string &blockedAddress) {
    const bool clientConnected = client_ && client_->isConnected();
    if (clientConnected) {
        lastConnectedAmpAddress_ = client_->getPeerAddress().toString();
    }

    if (lastConnectedAmpAddress_.empty()) {
        Serial.println("Cannot block amp: no Spark amp is connected.");
        return false;
    }

    if (!clientConnected) {
        Serial.println("Spark link changed during block request; using last confirmed connected amp.");
    }

    blockedAddress = lastConnectedAmpAddress_;
    blockedName = ampName.empty() ? "Spark amp" : ampName;

    bool alreadyBlocked = false;
    size_t existingIndex = 0;
    string previousName;
    for (size_t i = 0; i < blockedAmpAddresses_.size(); ++i) {
        if (blockedAmpAddresses_[i] == blockedAddress) {
            existingIndex = i;
            previousName = blockedAmpNames_[i];
            blockedAmpNames_[i] = blockedName;
            alreadyBlocked = true;
            break;
        }
    }
    if (!alreadyBlocked) {
        blockedAmpAddresses_.push_back(blockedAddress);
        blockedAmpNames_.push_back(blockedName);
    }

    if (!saveBlockedAmps()) {
        if (alreadyBlocked) {
            blockedAmpNames_[existingIndex] = previousName;
        } else {
            blockedAmpAddresses_.pop_back();
            blockedAmpNames_.pop_back();
        }
        Serial.println("Cannot save blocked amp list.");
        return false;
    }

    Serial.printf("Blocked Spark amp: %s (%s)\n",
                  blockedName.c_str(), blockedAddress.c_str());
    if (clientConnected) {
        client_->disconnect();
    }
    isAmpConnected_ = false;
    isConnectionFound_ = false;
    return true;
}

bool SparkBTControl::removeBlockedAmp(size_t index, string &name,
                                      string &address) {
    if (!getBlockedAmp(index, name, address)) {
        return false;
    }

    string storedName = blockedAmpNames_[index];
    blockedAmpAddresses_.erase(blockedAmpAddresses_.begin() + index);
    blockedAmpNames_.erase(blockedAmpNames_.begin() + index);
    if (!saveBlockedAmps()) {
        blockedAmpAddresses_.insert(blockedAmpAddresses_.begin() + index, address);
        blockedAmpNames_.insert(blockedAmpNames_.begin() + index, storedName);
        Serial.println("Cannot update blocked amp list.");
        return false;
    }

    Serial.printf("Unblocked Spark amp: %s (%s)\n", name.c_str(), address.c_str());
    return true;
}

bool SparkBTControl::clearBlockedAmp() {
    blockedAmpAddresses_.clear();
    blockedAmpNames_.clear();
    if (LittleFS.exists(blockedAmpFileName_.c_str()) &&
        !LittleFS.remove(blockedAmpFileName_.c_str())) {
        Serial.println("Cannot clear blocked amp address.");
        return false;
    }
    Serial.println("Blocked Spark amp cleared.");
    return true;
}

void SparkBTControl::setAdvertisedDevice(NimBLEAdvertisedDevice *device) {
    advDevice_ = device;
}

void SparkBTControl::scanEndedCB(NimBLEScanResults results) {
    Serial.println("Scan ended.");
}

void SparkBTControl::startScan() {
    spark_dc_->resetStatus();
    NimBLEDevice::getScan()->start(kScanTime, scanEndedCB);
    Serial.println("Scan initiated");
}

bool SparkBTControl::connectToServer() {
    /** Check if we have a client we should reuse first **/
    if (NimBLEDevice::getClientListSize()) {
        /** Special case when we already know this device, we send false as the
         second argument in connect() to prevent refreshing the service database.
         This saves considerable time and power.
         */
        client_ = NimBLEDevice::getClientByPeerAddress(advDevice_->getAddress());
        if (client_) {
            if (!client_->connect(advDevice_, false)) {
                Serial.println("Reconnect failed");
                isAmpConnected_ = false;
                return false;
            }
            Serial.println("Reconnected client");
        }
        /** We don't already have a client that knows this device,
         we will check for a client that is disconnected that we can use.
         */
        else {
            client_ = NimBLEDevice::getDisconnectedClient();
        }
    }

    /** No client to reuse? Create a new one. */
    if (!client_) {
        if (NimBLEDevice::getClientListSize() >= NIMBLE_MAX_CONNECTIONS) {
            Serial.println(
                "Max clients reached - no more connections available");
            isAmpConnected_ = false;
            return false;
        }

        client_ = NimBLEDevice::createClient();

        client_->setClientCallbacks(this, false);
        /** Set initial connection parameters: These settings are 15ms interval, 0 latency, 120ms timout.
         These settings are safe for 3 clients to connect reliably, can go faster if you have less
         connections. Timeout should be a multiple of the interval, minimum is 100ms.
         Min interval: 12 * 1.25ms = 15, Max interval: 12 * 1.25ms = 15, 0 latency, 51 * 10ms = 510ms timeout
         */
        // client_->setConnectionParams(12, 12, 0, 51);
        client_->setConnectionParams(18, 30, 0, 600);
        /** Set how long we are willing to wait for the connection to complete (seconds), default is 30. */
        client_->setConnectTimeout(30);
        client_->getMTU();
        if (!client_->connect(advDevice_)) {
            /** Created a client but failed to connect, don't need to keep it as it has no data */
            NimBLEDevice::deleteClient(client_);
            Serial.println("Failed to connect, deleted client");
            isAmpConnected_ = false;
            return false;
        }
    }

    if (!client_->isConnected()) {
        if (!client_->connect(advDevice_)) {
            Serial.println("Failed to connect");
            isAmpConnected_ = false;
            return false;
        }
    }

    Serial.print("Connected to: ");
    Serial.println(client_->getPeerAddress().toString().c_str());
    lastConnectedAmpAddress_ = client_->getPeerAddress().toString();
    isAmpConnected_ = true;
    return true;
}

bool SparkBTControl::subscribeToNotifications(notify_callback notifyCallback) {

    // Subscribe to notifications from Spark
    NimBLERemoteService *service = nullptr;
    NimBLERemoteCharacteristic *characteristic = nullptr;

    if (client_) {
        service = client_->getService(SPARK_BLE_SERVICE_UUID);
        if (service) { // make sure it's not null
            characteristic = service->getCharacteristic(SPARK_BLE_NOTIF_CHAR_UUID);

            if (characteristic) { // make sure it's not null
                if (characteristic->canNotify()) {
                    Serial.printf(
                        "Subscribing to service notifications of %s\n",
                        SPARK_BLE_NOTIF_CHAR_UUID.c_str());
                    Serial.println("Notifications turned on");
                    // Descriptor 2902 needs to be activated in order to receive notifications
                    characteristic->getDescriptor(BLEUUID((uint16_t)0x2902))->writeValue(kNotificationOn, 2, true);
                    // Subscribing to Spark characteristic
                    if (!characteristic->subscribe(true, notifyCB_)) {
                        Serial.println("Subscribe failed, disconnecting");
                        // Disconnect if subscribe failed
                        client_->disconnect();
                        return false;
                    }
                }

            } else {
                Serial.printf("%s characteristic not found.\n",
                              SPARK_BLE_NOTIF_CHAR_UUID);
                return false;
            }

            Serial.println("Done with this device.");
            return true;
        } // pSrv
        else {
            Serial.printf("Service %s not found.\n", SPARK_BLE_SERVICE_UUID);
            return false;
        }
    } // client_
    else {
        Serial.print("Client not found! Need reconnection");
        isAmpConnected_ = false;
        return false;
    }
}

// To send messages to Spark via Bluetooth LE
bool SparkBTControl::writeBLE(ByteVector &cmd, bool withDelay, bool response) {
    // DEBUG_PRINTLN("Sending message:");
    // DEBUG_PRINTVECTOR(cmd);
    // DEBUG_PRINTLN();
    if (client_ && client_->isConnected()) {
        DEBUG_PRINTLN("Connection ok");
        NimBLERemoteService *service = nullptr;
        NimBLERemoteCharacteristic *characteristic = nullptr;

        service = client_->getService(SPARK_BLE_SERVICE_UUID);
        if (service) {
            characteristic = service->getCharacteristic(SPARK_BLE_WRITE_CHAR_UUID);

            if (characteristic) {
                // if (characteristic->canWrite()) {
                // for (auto block : cmd) {

                // This it to split messages into sizes of max. max_send_size.
                // As we have chosen 173, usually no further splitting is requried.
                // SparkMessage already creates messages split into 173 byte chunks
                DEBUG_PRINT("Sending block:");
                DEBUG_PRINTVECTOR(cmd);
                DEBUG_PRINTLN();
                bool return_value = true;
                ByteVector send_cmd;
                while (cmd.size() > 0) {
                    int cmd_size = cmd.size();
                    int cut_point = min(cmd_size, bleMaxMsgSize_);
                    if (cut_point > 0) {
                        send_cmd.assign(cmd.begin(), cmd.begin() + cut_point);
                        cmd.assign(cmd.begin() + cut_point, cmd.end());
                        return_value = characteristic->writeValue(send_cmd.data(), send_cmd.size(), response);
                    }
                }
                if (return_value) {
                    // Delay seems to be required in order to not lose any packages.
                    // Seems to be more stable with a short delay
                    // also seems to be not working for Spark Mini without a delay.s
                    // TEST SPark GO
                    if (withDelay) {
                        delay(80);
                    }
                } else {
                    Serial.println("There was an error with writing!");
                    // Disconnect if write failed
                    client_->disconnect();
                    isAmpConnected_ = false;
                    return false;
                }
                //} // For each block
                //}  // if can write
            } // if characteristic
            else {
                Serial.printf("Characteristic %s not found. Disconnecting client.\n",
                              SPARK_BLE_WRITE_CHAR_UUID);
                // Disconnect if write failed
                client_->disconnect();
                isAmpConnected_ = false;
                return false;
            }
        } // if service
        else {
            Serial.printf("%s service not found. Disconnecting client.\n", SPARK_BLE_SERVICE_UUID);
            // Disconnect if write failed
            client_->disconnect();
            isAmpConnected_ = false;
            return false;
        }
        DEBUG_PRINTLN("Done with this command!");
        return true;
    } else {
        isAmpConnected_ = false;
        return false;
    }
}

void SparkBTControl::onResult(NimBLEAdvertisedDevice *advertisedDevice) {

    if (advertisedDevice->isAdvertisingService(
            NimBLEUUID(SPARK_BLE_SERVICE_UUID))) {
#ifdef ENABLE_IPT_AMP_BLOCKLIST
        string advertisedAddress = advertisedDevice->getAddress().toString();
        if (isAmpBlocked(advertisedAddress)) {
            string name = blockedAmpName(advertisedAddress);
            if (!name.empty()) {
                Serial.printf("Ignoring blocked Spark amp: %s (%s)\n",
                              name.c_str(), advertisedAddress.c_str());
            } else {
                Serial.printf("Ignoring blocked Spark amp: %s\n", advertisedAddress.c_str());
            }
            return;
        }
#endif
        Serial.println("Found Spark, connecting.");
        /** stop scan before connecting */
        // Commented as workaround, might need to get back here, is currently with DataControl;
        NimBLEDevice::getScan()->stop();
        /** Save the device reference in a global for the client to use*/
        setAdvertisedDevice(advertisedDevice);
        /** Ready to connect now */
        isConnectionFound_ = true;
        // delay(500);
    }
}

void SparkBTControl::startServer() {
    Serial.println("Starting NimBLE Server");

    /** sets device name */
    NimBLEDevice::init(btNameBle);

    /** Optional: set the transmit power, default is 3db */
    NimBLEDevice::setPower(ESP_PWR_LVL_P9); /** +9db */
    NimBLEDevice::setSecurityAuth(
        /*BLE_SM_PAIR_AUTHREQ_BOND | BLE_SM_PAIR_AUTHREQ_MITM |*/ BLE_SM_PAIR_AUTHREQ_SC);

    server_ = NimBLEDevice::createServer();
    server_->setCallbacks(this);
    // Present one stable app endpoint. Restart advertising only after NimBLE
    // has fully removed the previous client and completed disconnect cleanup.
    server_->advertiseOnDisconnect(true);

    sparkService_ = server_->createService(
        SPARK_BLE_SERVICE_UUID);
    sparkWriteCharacteristic_ =
        sparkService_->createCharacteristic(
            SPARK_BLE_WRITE_CHAR_UUID,
            NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);

    uint8_t initialWriteValue[] = {0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77, 0x77,
                                   0x77, 0x77, 0x77};

    sparkWriteCharacteristic_->setValue(initialWriteValue);
    sparkWriteCharacteristic_->setCallbacks(this);

    sparkNotificationCharacteristic_ =
        sparkService_->createCharacteristic(
            SPARK_BLE_NOTIF_CHAR_UUID,
            NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);
    uint8_t initialNotificationValue[] = {0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88, 0x88,
                                          0x88, 0x88, 0x88, 0x88};
    sparkNotificationCharacteristic_->setValue(initialNotificationValue);
    sparkNotificationCharacteristic_->setCallbacks(this);

    /** Start the services when finished creating all Characteristics and Descriptors */
    sparkService_->start();
    advertising_ = NimBLEDevice::getAdvertising();

    advertising_->addServiceUUID(sparkService_->getUUID());

    /** Add the services to the advertisment data **/
    /** If your device is battery powered you may consider setting scan response
     *  to false as it will extend battery life at the expense of less data sent.
     */
    advertising_->setScanResponse(true);
    const bool advertisingStarted = advertising_->start();

    Serial.printf("Advertising Started status=%d\n",
                  advertisingStarted ? 1 : 0);
}

void SparkBTControl::onWrite(NimBLECharacteristic *pCharacteristic) {

    // This method will be triggered if receiving data in AMP mode.
    DEBUG_PRINT(pCharacteristic->getUUID().toString().c_str());
    DEBUG_PRINTLN(": onWrite()");
    string rxValue = pCharacteristic->getValue();
    ByteVector byteVector;
    byteVector.clear();

    if (rxValue.length() > 0) {
        for (int i = 0; i < rxValue.length(); i++) {
            byteVector.push_back((byte)(rxValue[i]));
        }
    }
    // Add message to Queue for processing
    spark_dc_->queueMessage(byteVector);
}

void SparkBTControl::onSubscribe(NimBLECharacteristic *pCharacteristic,
                                 ble_gap_conn_desc *desc, uint16_t subValue) {
    string str = "Address: ";
    str += string(NimBLEAddress(desc->peer_ota_addr)).c_str();
    if (subValue == 0) {
        str += " Unsubscribed to ";
    } else if (subValue == 1) {
        str += " Subscribed to notifications for ";
    } else if (subValue == 2) {
        str += " Subscribed to indications for ";
    } else if (subValue == 3) {
        str += " Subscribed to notifications and indications for ";
    }
    str += string(pCharacteristic->getUUID());

    Serial.println(str.c_str());
};

void SparkBTControl::notifyClients(const vector<CmdData> &msg) {
    if (server_) {
        NimBLEService *service = server_->getServiceByUUID(SPARK_BLE_SERVICE_UUID);
        if (service) {
            NimBLECharacteristic *characteristic = service->getCharacteristic(
                SPARK_BLE_NOTIF_CHAR_UUID);
            if (characteristic) {
                for (auto block : msg) {
                    /*DEBUG_PRINTLN("Sending data:");
                    DEBUG_PRINTVECTOR(block);
                    DEBUG_PRINTLN();*/
                    characteristic->setValue(&block.data.data()[0], block.data.size());
                    characteristic->notify();
                }
                DEBUG_PRINTLN("Clients notified.");
            }
        }
    }

    if (serialBleClientConnected && serialBleNotificationsEnabled &&
        serialBleGattInterface != ESP_GATT_IF_NONE) {
        for (const auto &block : msg) {
            if (block.data.empty()) {
                continue;
            }
            const esp_err_t result = esp_ble_gatts_send_indicate(
                serialBleGattInterface, serialBleConnectionId,
                serialBleHandles[SERIAL_BLE_NOTIFY_VALUE], block.data.size(),
                const_cast<uint8_t *>(block.data.data()), false);
            if (result != ESP_OK) {
                Serial.printf("BT_BLE_BRIDGE TX_ERROR status=%d bytes=%u\n",
                              (int)result,
                              (unsigned int)block.data.size());
                break;
            }
        }
    }

    if (btSerial && btSerial->hasClient()) {
        DEBUG_PRINTLN("Sending message via BT Serial:");
        for (auto chunk : msg) {
            ByteVector chunkData = chunk.data;
            if (chunkData.empty()) {
                continue;
            }
            const size_t written =
                btSerial->write(chunkData.data(), chunkData.size());
            if (written != chunkData.size()) {
                Serial.printf("BT_TX_ERROR requested=%u written=%u client=%d\n",
                              (unsigned int)chunkData.size(),
                              (unsigned int)written,
                              btSerial->hasClient() ? 1 : 0);
                break;
            }
            DEBUG_PRINTF("Free Heap size: %d\n", ESP.getFreeHeap());
        }
    }
}

// AMP Mode
void SparkBTControl::onConnect(NimBLEServer *pServer_,
                               ble_gap_conn_desc *desc) {
    // Android can retain service and notification state between app sessions.
    // Start every GATT connection with a clean Spark protocol parser/queue.
    if (spark_dc_) {
        spark_dc_->resetAmpClientSession();
    }
    isAppConnectedBLE_ = true;
    Serial.printf(
        "BT_BLE CONNECT handle=%u bonded=%d encrypted=%d authenticated=%d\n",
        (unsigned int)desc->conn_handle, desc->sec_state.bonded ? 1 : 0,
        desc->sec_state.encrypted ? 1 : 0,
        desc->sec_state.authenticated ? 1 : 0);
    // A Spark amp exposes one app connection at a time. Advertising resumes
    // automatically after disconnect via advertiseOnDisconnect(true).
}

// APP mode
void SparkBTControl::onConnect(NimBLEClient *pClient_) {
    NimBLEClientCallbacks::onConnect(pClient_);
    spark_dc_->getAmpName();
}

// AMP mode when App is disconnected
void SparkBTControl::onDisconnect(NimBLEServer *pServer_) {
    Serial.println("BT_BLE DISCONNECT cleanup=complete advertising=auto");
    isAppConnectedBLE_ = false;
    notificationCount = 0;
    if (spark_dc_) {
        spark_dc_->resetAmpClientSession();
    }
}

// APP mode when Amp is disconnected
void SparkBTControl::onDisconnect(NimBLEClient *pClient_) {
    isAmpConnected_ = false;
    isConnectionFound_ = false;
    if (!(NimBLEDevice::getScan()->isScanning())) {
        startScan();
    }
    NimBLEClientCallbacks::onDisconnect(pClient_);
}

void SparkBTControl::stopScan() {
    if (isScanning()) {
        Serial.println("Scan stopped");
        NimBLEDevice::getScan()->stop();
    } else {
        Serial.print("Scan is not running");
    }
}

void SparkBTControl::serialCallback(esp_spp_cb_event_t event, esp_spp_cb_param_t *param) {
    if (event == ESP_SPP_START_EVT) {
        Serial.printf("BT_SPP START status=%d scn=%u handle=%u\n",
                      (int)param->start.status, (unsigned int)param->start.scn,
                      (unsigned int)param->start.handle);
        if (param->start.status == ESP_SPP_SUCCESS) {
            // The Spark app performs only a short Classic inquiry for Gen-1
            // amps, so keep the endpoint explicitly discoverable.
            restoreSerialDiscoverability("spp_start");
            startSerialAudioProfile();
        }
    } else if (event == ESP_SPP_SRV_OPEN_EVT) {
        resetSerialSession(true);
        serialClientConnectedForDiscovery = true;
        serialPeerAddress_ = formatBtAddress(param->srv_open.rem_bda);
        Serial.println("Client Connected");
        Serial.printf("BT_SPP OPEN status=%d handle=%u peer=%s bonds=%d\n",
                      (int)param->srv_open.status,
                      (unsigned int)param->srv_open.handle,
                      serialPeerAddress_.c_str(),
                      esp_bt_gap_get_bond_device_num());
        isAppConnectedSerial_ = true;
    } else if (event == ESP_SPP_CLOSE_EVT) {
        serialClientConnectedForDiscovery = false;
        resetSerialSession(false);
        Serial.println("Client disconnected");
        Serial.printf("BT_SPP CLOSE status=%d handle=%u async=%d peer=%s\n",
                      (int)param->close.status,
                      (unsigned int)param->close.handle,
                      param->close.async ? 1 : 0,
                      serialPeerAddress_.empty()
                          ? "none"
                          : serialPeerAddress_.c_str());
        isAppConnectedSerial_ = false;
        serialPeerAddress_.clear();
        // BluetoothSerial enables discoverability when SPP is initialized but
        // does not restore it after a client closes. Some Android versions do
        // not reconnect to the still-bonded pedal unless the server becomes
        // explicitly connectable and discoverable again.
        restoreSerialDiscoverability("client_close");
        scheduleSerialDiscoverabilityRestore();
    } else if (event == ESP_SPP_CONG_EVT) {
        Serial.printf("BT_SPP CONGESTION status=%d congested=%d handle=%u\n",
                      (int)param->cong.status, param->cong.cong ? 1 : 0,
                      (unsigned int)param->cong.handle);
    } else if (event == ESP_SPP_UNINIT_EVT) {
        Serial.printf("BT_SPP STOP status=%d\n", (int)param->uninit.status);
    }
}

void SparkBTControl::startBTSerial() {
    // Spark 40 is a Classic SPP device in the current Spark app. Advertising
    // the companion FFC0 BLE service at the same time makes Classic inquiry
    // responses arrive after the app's three-second scan timeout. Keep SRL
    // mode Classic-only; BLE remains available as its separate user-selected
    // pedal mode.
    serialSessionDataControl = spark_dc_;
    btSerial = new BluetoothSerial();
    btSerial->register_callback(serialCallback);
    btSerial->onAuthComplete([](boolean success) {
        Serial.printf("BT_AUTH success=%d bonds=%d\n", success ? 1 : 0,
                      esp_bt_gap_get_bond_device_num());
        printBondedDevices();
        if (success) {
            // Pairing may update the controller scan state. Keep the endpoint
            // visible so the app can rediscover the still-bonded pedal on its
            // next launch without requiring Android to forget it first.
            restoreSerialDiscoverability("auth_complete");
        }
    });
    // btStart();
    if (btSerial->begin(btNameSerial.c_str(), false)) {
        Serial.printf("Started BT Serial with name %s \n",
                      btNameSerial.c_str());
        btSerial->flush();
        printSerialDiagnostics();
    } else {
        Serial.println("BT Serial start failed!");
    }
}

void SparkBTControl::printSerialDiagnostics() {
    if (!btSerial) {
        Serial.println("BT_DIAG mode=INACTIVE client=0 peer=none");
        return;
    }
    const uint8_t *localAddress = esp_bt_dev_get_address();
    Serial.printf("BT_DIAG mode=SERIAL ready=%d client=%d local=%s peer=%s\n",
                  btSerial->isReady(false, 0) ? 1 : 0,
                  btSerial->hasClient() ? 1 : 0,
                  formatBtAddress(localAddress).c_str(),
                  serialPeerAddress_.empty() ? "none"
                                             : serialPeerAddress_.c_str());
    printBondedDevices();
}

void SparkBTControl::prepareForRestart() {
    if (!btSerial) {
        Serial.println("BT_SHUTDOWN mode=INACTIVE");
        return;
    }

    const bool hadClient = btSerial->hasClient();
    Serial.printf("BT_SHUTDOWN begin client=%d peer=%s\n", hadClient ? 1 : 0,
                  serialPeerAddress_.empty() ? "none"
                                             : serialPeerAddress_.c_str());
    if (hadClient) {
        const bool disconnected = btSerial->disconnect();
        Serial.printf("BT_SHUTDOWN disconnect=%d\n", disconnected ? 1 : 0);
        delay(100);
    }
    stopSerialAudioProfile();
    serialSessionDataControl = nullptr;
    btSerial->end();
    delete btSerial;
    btSerial = nullptr;
    isAppConnectedSerial_ = false;
    serialPeerAddress_.clear();
    Serial.println("BT_SHUTDOWN complete");
}

void SparkBTControl::stopBTSerial() {
    // Stop Bluetooth Serial
    stopSerialAudioProfile();
    serialSessionDataControl = nullptr;
    btSerial->end();
    delete btSerial;
    btSerial = nullptr;
    Serial.println("BT Serial stopped");
}

const bool SparkBTControl::isAppConnected() const {
    return isAppConnectedBLE_ || isAppConnectedSerial_;
}

void SparkBTControl::stopBLEServer() {

    if (server_) {
        Serial.println("Switching off BLE server");
        server_->stopAdvertising();
    }
}
