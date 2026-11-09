/*
 * SparkLEDControl.cpp
 *
 *  Created on: 23.08.2021
 *      Author: stangreg
 */

#include "SparkLEDControl.h"

SparkLEDControl::SparkLEDControl() {
    sparkDC = nullptr;
}

SparkLEDControl::SparkLEDControl(SparkDataControl *dc) {
    sparkDC = dc;
}

SparkLEDControl::~SparkLEDControl() {
}

void SparkLEDControl::begin() {
    init();
}

void SparkLEDControl::init() {
    // Preset LEDs
    pinMode(LED_PRESET1_GPIO, OUTPUT);
    pinMode(LED_PRESET2_GPIO, OUTPUT);
    pinMode(LED_PRESET3_GPIO, OUTPUT);
    pinMode(LED_PRESET4_GPIO, OUTPUT);
    pinMode(LED_BANK_DOWN_GPIO, OUTPUT);
    pinMode(LED_BANK_UP_GPIO, OUTPUT);

    // FX LEDS
    pinMode(LED_DRIVE_GPIO, OUTPUT);
    pinMode(LED_MOD_GPIO, OUTPUT);
    pinMode(LED_DELAY_GPIO, OUTPUT);
    pinMode(LED_REVERB_GPIO, OUTPUT);
    pinMode(LED_NOISEGATE_GPIO, OUTPUT);
    pinMode(LED_COMP_GPIO, OUTPUT);

#ifndef DEDICATED_PRESET_LEDS
    // For special corner case where the extra dedicated
    // Preset LED hardware *is* connected to the extra
    // GPIO ports, but the define that activates them is
    // undefined
    pinMode(OPTIONAL_GPIO_1, OUTPUT);
    pinMode(OPTIONAL_GPIO_2, OUTPUT);
    pinMode(OPTIONAL_GPIO_3, OUTPUT);
    pinMode(OPTIONAL_GPIO_4, OUTPUT);
#endif
    allLedOff();
}

void SparkLEDControl::updateLEDs() {

    operationMode = sparkDC->operationMode();
    activePreset = SparkPresetControl::getInstance().activePreset();
    activePresetNum = SparkPresetControl::getInstance().activePresetNum();

    switch (operationMode) {

    case SPARK_MODE_APP: {
        if (sparkDC->isInitBoot()) {
            allLedOff();
            break;
        }
        SubMode subMode = sparkDC->subMode();
        // Show only active LEDs
        switch (subMode) {
        case SUB_MODE_LOOPER:
        case SUB_MODE_SPK_LOOPER:
        case SUB_MODE_PRESET:
            updateLedAppPresetMode();
#ifndef DEDICATED_PRESET_LEDS
            // Do not break if DEDICATED_PRESET_LEDS is defined
            // Will thus fall through to next case and also update FX LEDs
            break;
#endif
        case SUB_MODE_FX:
            updateLedAppFXMode();
            break;

        case SUB_MODE_LOOP_CONFIG:
        case SUB_MODE_LOOP_CONTROL:
            updateLedLooperMode();
            break;

        case SUB_MODE_TUNER:
            updateLedTuner();
            break;
        }

    } break;

    case SPARK_MODE_AMP:
        updateLedAmp();
        break;
    case SPARK_MODE_KEYBOARD:
        updateLedKeyboard();
        break;
    }
}

void SparkLEDControl::updateLedAppPresetMode() {
#ifdef DEDICATED_PRESET_LEDS
    // Dedicated preset and FX LEDs are separate outputs. Set only the four
    // preset LEDs here so the FX LEDs keep their current level until
    // updateLedAppFXMode() applies the requested effect states below. Clearing
    // every LED on each loop briefly pulsed the FX outputs and was visible as
    // flicker on illuminated pedal labels.
    for (int presetNum = PRESET1_NUM; presetNum <= PRESET4_NUM; presetNum++) {
        switchLed(presetNum, presetNum == activePresetNum, false);
    }
#else
    // Apply the complete steady state directly. Clearing every output before
    // restoring the active LED creates a visible off pulse on every loop when
    // PWM brightness is enabled.
    for (int ledNum = 1; ledNum <= 6; ledNum++) {
        switchLed(ledNum, ledNum == activePresetNum, false);
    }
#endif
}

void SparkLEDControl::updateLedAppFXMode() {
    if (!activePreset.isEmpty) {
        for (int btnNumber = 1; btnNumber <= 6; btnNumber++) {
            FxLedButtonNumber fxButton = static_cast<FxLedButtonNumber>(btnNumber);
            FxType fxIndex = SparkHelper::getFXIndexFromButtonNumber(fxButton);
            Pedal currentFX = activePreset.pedals[(int)fxIndex];
            switchLed(btnNumber, currentFX.isOn, true);
        }
    }
}

void SparkLEDControl::updateLedAmp() {
    unsigned long currentMillis = millis();

    int presetNumToEdit = SparkPresetControl::getInstance().presetNumToEdit();
    const PresetEditMode presetEditMode = SparkPresetControl::getInstance().presetEditMode();

    if (presetEditMode != PRESET_EDIT_NONE) {

        if (presetNumToEdit == 0) {
            for (int i = 1; i <= 4; i++) {
                switchLed(i, true);
            }
        } else if (currentMillis - previousMillis >= blinkInterval_ms) {
            // save the last time you blinked the LED
            previousMillis = currentMillis;

            allLedOff();
            // if the LED is off turn it on and vice-versa:
            if (ledState == LOW) {
                ledState = HIGH;
                switchLed(presetNumToEdit, true);
            } else {
                ledState = LOW;
            }
        }

    } else {
        for (int ledNum = 1; ledNum <= 6; ledNum++) {
            switchLed(ledNum, ledNum == activePresetNum);
        }
    }
}

void SparkLEDControl::updateLedKeyboard() {

    uint8_t pressedKey = sparkDC->lastKeyboardButtonPressed();
    // Map index of pressed key from 1 to 6. A zero key selects no LED.
    const int index = pressedKey == 0 ? 0 : mapping.indexOfKey(pressedKey);
    for (int ledNum = 1; ledNum <= 6; ledNum++) {
        switchLed(ledNum, ledNum == index);
    }
}

void SparkLEDControl::updateLedLooperMode() {

    const bool onOff = sparkDC->looperControl().beatOnOff();
    ledState = onOff ? HIGH : LOW;

    const bool isRecRunning = sparkDC->looperControl().isRecRunning();
    const bool isPlaying = sparkDC->looperControl().isPlaying();
    const bool isRecAvailable = sparkDC->looperControl().isRecAvailable();
    const bool playStopOn = isPlaying || (isRecAvailable && onOff);

    // TODO: Check why LED is not on when Undo is available during Dub/Play. Seems that 0278 is ignored during play.
    const bool canUndo = sparkDC->looperControl().canUndo();
    const bool canRedo = sparkDC->looperControl().canRedo();
    const bool undoRedoOn = canUndo && !canRedo;

    // Write every output exactly once per update so PWM never sees a brief
    // clear-and-redraw transition.
    for (int ledNum = 1; ledNum <= 6; ledNum++) {
        bool on = false;
        if (ledNum == SPK_LOOPER_REC_DUB_LED_ID) {
            on = isRecRunning;
        } else if (ledNum == SPK_LOOPER_PLAY_STOP_LED_ID) {
            on = playStopOn;
        } else if (ledNum == SPK_LOOPER_UNDO_REDO_LED_ID) {
            on = undoRedoOn;
        } else if (ledNum == SPK_LOOPER_BPM_LED_ID) {
            on = onOff;
        }
        switchLed(ledNum, on);
    }
}

void SparkLEDControl::updateLedTuner() {
    SparkStatus &status = SparkStatus::getInstance();

    int noteOffsetCents = status.noteOffsetCents();
    int centsTolerance = 5;
    const bool tunerLeds[] = {
        noteOffsetCents > -50 && noteOffsetCents < -20,
        noteOffsetCents > -50 && noteOffsetCents < centsTolerance,
        noteOffsetCents > -centsTolerance,
        noteOffsetCents > 20,
    };

    for (int ledNum = 1; ledNum <= 6; ledNum++) {
        switchLed(ledNum, ledNum <= 4 ? tunerLeds[ledNum - 1] : false);
    }
}

void SparkLEDControl::allLedOff() {
    // Preset LEDs
    writeLed(LED_PRESET1_GPIO, false);
    writeLed(LED_PRESET2_GPIO, false);
    writeLed(LED_PRESET3_GPIO, false);
    writeLed(LED_PRESET4_GPIO, false);

    writeLed(LED_BANK_DOWN_GPIO, false);
    writeLed(LED_BANK_UP_GPIO, false);

    // FX LEDS
    writeLed(LED_DRIVE_GPIO, false);
    writeLed(LED_MOD_GPIO, false);
    writeLed(LED_DELAY_GPIO, false);
    writeLed(LED_REVERB_GPIO, false);

#ifndef DEDICATED_PRESET_LEDS
    // For special corner case where the extra dedicated
    // Preset LED hardware *is* connected to the extra
    // GPIO ports, but the define that activates them is
    // undefined.
    digitalWrite(OPTIONAL_GPIO_1, LOW);
    digitalWrite(OPTIONAL_GPIO_2, LOW);
    digitalWrite(OPTIONAL_GPIO_3, LOW);
    digitalWrite(OPTIONAL_GPIO_4, LOW);
#endif
}

void SparkLEDControl::writeLed(int gpio, bool on) {
    if (gpio == LED_GPIO_INVALID || gpio < 0 || gpio >= LED_GPIO_CACHE_SIZE) {
        return;
    }
    const int brightnessPercent = constrain(LED_BRIGHTNESS_PERCENT, 0, 100);
    const uint8_t pwmDuty =
        on ? (brightnessPercent * 255 + 50) / 100 : 0;

    // analogWrite() configures ESP32 LEDC. Reapplying the same duty every
    // pass can restart or disturb PWM often enough to create visible flicker.
    // Touch the hardware only when this GPIO's requested duty actually changes.
    if (ledDutyInitialized_[gpio] && lastLedDuty_[gpio] == pwmDuty) {
        return;
    }
    analogWrite(gpio, pwmDuty);
    lastLedDuty_[gpio] = pwmDuty;
    ledDutyInitialized_[gpio] = true;
}

void SparkLEDControl::switchLed(int num, bool on, bool fxMode) {
    unsigned long currentMillis = millis();
    int STATE;

    // Blink if enabled and in FX modification mode
    if (ENABLE_FX_BLINK && fxMode && sparkDC->operationMode() == SPARK_MODE_APP && sparkDC->subMode() == SUB_MODE_FX) {
        if (currentMillis - previousMillis >= blinkInterval_ms) {
            blinkInvert = !blinkInvert;
            previousMillis = currentMillis;
        }
        STATE = (on && !blinkInvert) ? HIGH : LOW;
    } else {
        STATE = (on) ? HIGH : LOW; // Normal non blink action
    }

    int ledGpio = SparkHelper::getLedGpio(num, fxMode);
    if (ledGpio != LED_GPIO_INVALID) {
        // Serial.printf("Pin %d [State=%d], invert=%d, fxMode=%d\n", ledGpio, STATE, blinkInvert, fxMode);
        writeLed(ledGpio, STATE == HIGH);
    }
}
