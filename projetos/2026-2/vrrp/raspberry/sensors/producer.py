import fcntl
import json
import time
import os
import random

STORAGE_FILE = os.path.expanduser("~/sensors/storage.jsonl")
DEVICE_ID = "3BPlus"
ONE_MINUTE_IN_SEC = 60

def read_dht11():
    try:
        raise NotImplementedError
    except Exception:
        return round(random.uniform(20.0, 28.0), 1), round(random.uniform(45.0, 65.0), 1)

def read_bss138():
    try:
        raise NotImplementedError
    except Exception:
        return round(random.uniform(3.3, 5.0), 1)

def read_ldr():
    try:
        raise NotImplementedError
    except Exception:
        return round(random.uniform(300, 800), 1), round((random.uniform(300, 800) / 1023) * 500, 1) 

def read_ds1302():
    try:
        raise NotImplementedError
    except Exception:
        return int(time.time())

def read_mq2():
    try:
        raise NotImplementedError
    except Exception:
        return round(random.uniform(200, 450) * 0.4, 1), round(random.uniform(200, 450), 1)

def read_bmp280():
    try:
        raise NotImplementedError
    except Exception:
        return round(random.uniform(1010.0, 1018.0), 1), round(random.uniform(21.0, 26.0), 1)

def read_hcsr04():
    try:
        raise NotImplementedError
    except Exception:
        return round(random.uniform(10, 150), 1)

def read_acs712():
    try:
        raise NotImplementedError
    except Exception:
        return round(random.uniform(1.8, 3.0), 2), round((random.uniform(1.8, 3.0) / 3.3) * 1023, 1)

def read_tcs3200():
    try:
        raise NotImplementedError
    except Exception:
        return round(random.uniform(700, 950), 1)


def read_sensors():
    now = int(time.time())

    dht_temp, dht_hum = read_dht11()
    bss_v = read_bss138()
    ldr_adc, ldr_lux = read_ldr()
    rtc_epoch = read_ds1302()
    mq2_ppm, mq2_adc = read_mq2()
    bmp_hpa, bmp_temp = read_bmp280()
    hcsr_adc = read_hcsr04()
    acs_v, acs_adc = read_acs712()
    tcs_adc = read_tcs3200()

    return {
        "device": DEVICE_ID,
        "sensors": [
            {
                "external_id": "DTH11",
                "module": "ASAIR DHT11 (Temp & Humidity)",
                "values": [
                    {"unit": "temperature", "value": dht_temp, "timestamp": now},
                    {"unit": "humidity", "value": dht_hum, "timestamp": now}
                ]
            },
            {
                "external_id": "BSS138",
                "module": "Logic Level Converter (BSS138)",
                "values": [
                    {"unit": "voltage", "value": bss_v, "timestamp": now}
                ]
            },
            {
                "external_id": "LDR",
                "module": "LDR Photoresistor",
                "values": [
                    {"unit": "analog", "value": ldr_adc, "timestamp": now},
                    {"unit": "illuminance", "value": ldr_lux, "timestamp": now}
                ]
            },
            {
                "external_id": "DS1302",
                "module": "DS1302 Real Time Clock (RTC)",
                "values": [
                    {"unit": "uv", "value": rtc_epoch, "timestamp": now}
                ]
            },
            {
                "external_id": "MQ2",
                "module": "MQ-2 Gas / Smoke Sensor",
                "values": [
                    {"unit": "voc", "value": mq2_ppm, "timestamp": now},
                    {"unit": "analog", "value": mq2_adc, "timestamp": now}
                ]
            },
            {
                "external_id": "BMP280",
                "module": "BMP280 Barometric Pressure & Temp",
                "values": [
                    {"unit": "pressure", "value": bmp_hpa, "timestamp": now},
                    {"unit": "temperature", "value": bmp_temp, "timestamp": now}
                ]
            },
            {
                "external_id": "HCSR04",
                "module": "HC-SR04 Ultrasonic Distance Sensor",
                "values": [
                    {"unit": "analog", "value": hcsr_adc, "timestamp": now}
                ]
            },
            {
                "external_id": "ACS172",
                "module": "ACS712 Current Sensor",
                "values": [
                    {"unit": "voltage", "value": acs_v, "timestamp": now},
                    {"unit": "analog", "value": acs_adc, "timestamp": now}
                ]
            },
            {
                "external_id": "TCS3200",
                "module": "TCS3200 Color Sensor",
                "values": [
                    {"unit": "analog", "value": tcs_adc, "timestamp": now}
                ]
            }
        ]
    }

def push_to_storage(data):
    with open(STORAGE_FILE, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(data) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

def main():
    print("PRODUCER STARTED...")
    while True:
        try:
            data = read_sensors()
            push_to_storage(data)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Appended line")
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Append error {e}")

        time.sleep(ONE_MINUTE_IN_SEC)

if __name__ == "__main__":
    print(f"Starting Local Logger for device: {DEVICE_ID}")
    print(f"Output File: {STORAGE_FILE}")

    main()
