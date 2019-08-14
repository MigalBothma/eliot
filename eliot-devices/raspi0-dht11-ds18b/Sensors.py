import RPi.GPIO as GPIO
import dht11
import time
import datetime
from w1thermsensor import W1ThermSensor
import iothub_client

from iothub_client import IoTHubClient, IoTHubClientError, IoTHubTransportProvider, IoTHubClientResult
from iothub_client import IoTHubMessage, IoTHubMessageDispositionResult, IoTHubError, DeviceMethodReturnValue

# initialize GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()

# create past 5 reading lists of DHT-11
past5_humidity_readings = []
past5_temperature_readings = []
average_humidity = 0
average_temperature = 0

# read data using pin 14
instance = dht11.DHT11(pin=17)

# Setup Azure IoT hub Connection string
CONNECTION_STRING = "HostName=ELTECH.azure-devices.net;DeviceId=raspi;SharedAccessKey=E8VEXmNy8/9vZo8aSTk+L+X5WT0Dp1T0MP8QcxrHs8s="

# Using the MQTT protocol.
PROTOCOL = IoTHubTransportProvider.MQTT
MESSAGE_TIMEOUT = 10000

# Define the JSON message to send to IoT Hub.
TEMPERATURE = 0
HUMIDITY = 0
MSG_TXT = "{\"temperature\": %.2f,\"humidity\": %.2f, \"ds18_Temp\": %.2f}"

def send_confirmation_callback(message, result, user_context):
    print ( "IoT Hub responded to message with status: %s" % (result) )

def iothub_client_init():
    # Create an IoT Hub client
    client = IoTHubClient(CONNECTION_STRING, PROTOCOL)
    return client

def iothub_client_telemetry_run():
    try:
        client = iothub_client_init()
        print ( "IoT Hub device sending periodic messages, press Ctrl-C to exit" )
        print("-----------------------------------------------------------------")

        while True:
            result = instance.read()
            sensor = W1ThermSensor()
            ign_reading = False
            
            if result.is_valid():
                ds18b_temp = sensor.get_temperature()
                
                print("DHT 11 - Last valid input: " + str(datetime.datetime.now()))
                print("DHT 11 - Temperature: %d C" % result.temperature)
                print("DHT 11 - Humidity: %d %%" % result.humidity)
                print("DS18B20 - Temperature: %d C" % ds18b_temp)

                # Treat outliers on DHT-11
                if len(past5_humidity_readings) >= 5:
                    average_humidity = sum(past5_humidity_readings) / len(past5_humidity_readings)
                    print("past5_humidity_readings average : %d %%"% average_humidity)
                    if result.humidity > average_humidity*1.15 or result.humidity < average_humidity*0.85:
                        ign_reading = True
                        print("discarding DHT-11 humidity value")
                    else:
                        past5_humidity_readings.pop(0)
                        
                if len(past5_temperature_readings) >= 5:
                    average_temperature = sum(past5_temperature_readings) / len(past5_temperature_readings)
                    print("past5_temperature_readings average : %d C"% average_temperature)
                    if result.temperature > average_temperature*1.15 or result.temperature < average_temperature*0.85:
                        ign_reading = True
                        print("discarding DHT-11 temperature value")
                    else:
                        past5_temperature_readings.pop(0)

                # Store latest value in Past5
                if not ign_reading:
                    past5_temperature_readings.append(result.temperature)
                    past5_humidity_readings.append(result.humidity)
                    
                    temperature = result.temperature
                    humidity = result.humidity
                else:
                    temperature = int(average_temperature)
                    humidity = int(average_humidity)
                    past5_temperature_readings.append(average_temperature)
                    past5_humidity_readings.append(average_humidity)
                    
                # Build the message with telemetry values.
                temperature1 = ds18b_temp
                msg_txt_formatted = MSG_TXT % (temperature, humidity, ds18b_temp)
                message = IoTHubMessage(msg_txt_formatted)

                # Add a custom application property to the message.
                # An IoT hub can filter on these properties without access to the message body.
                prop_map = message.properties()
                if temperature > 30:
                    prop_map.add("Temperature High Alert", "true")
                elif temperature < 16:
                    prop_map.add("Temperature Low Alert", "true")
                else:
                    prop_map.add("temperatureAlert", "false")

                # Send the message.
                print( "Sending message: %s" % message.get_string() )
                client.send_event_async(message, send_confirmation_callback, None)
                time.sleep(60)
                print("-----------------------------------------------------------------")
            else:
                time.sleep(1) # Retry time

    except IoTHubError as iothub_error:
        print ( "Unexpected error %s from IoTHub" % iothub_error )
        return
    except KeyboardInterrupt:
        print ( "IoTHubClient sample stopped" )

if __name__ == '__main__':
    print ( "ELIoT Raspi Zero - v1.0 Humidity and Temperature" )
    print ( "Press Ctrl-C to exit" )
    iothub_client_telemetry_run()

