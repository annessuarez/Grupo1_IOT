import serial
import time
from flask import Flask, render_template, request, jsonify

from awsiot import mqtt5_client_builder
from awscrt import mqtt5
import threading

import json

app = Flask(__name__)

# --- Setup de Comunicación Serie ---
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 9600

ser = None
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
except serial.SerialException as e:
    print(f"Error: No se pudo abrir el puerto serie '{SERIAL_PORT}'. {e}")
    print("Por favor, asegúrate de que el Arduino está conectado.")

# Eventos y propiedades para AWS
connection_success_event = threading.Event()
stopped_event = threading.Event()
received_all_event = threading.Event()
endpoint_AWS = "a2xyhr7rc9cefs-ats.iot.us-east-1.amazonaws.com"
cert_filepath_AWS = "cert/Casa1.cert.pem"
pri_key_filepath_AWS = "cert/Casa1.private.key"
clientId_AWS = "basicPubSub"
device_name_AWS = "Casa1"
message_topic_commands_AWS = "command"
message_topic_telemetry_AWS = "telemetry"
client = None
iot_connected = False
TIMEOUT_CONNECT_AWS = 100

# Conexión a AWS IoT Core
def connect_to_aws():
    global client, iot_connected

    print("==== Creating MQTT5 Client ====\n")
    client = mqtt5_client_builder.mtls_from_path(
        endpoint=endpoint_AWS,
        cert_filepath=cert_filepath_AWS,
        pri_key_filepath_AWS=pri_key_filepath_AWS,
        on_publish_received=on_publish_received_AWS,
        on_lifecycle_stopped=on_lifecycle_stopped_AWS,
        on_lifecycle_attempting_connect=on_lifecycle_attempting_connect_AWS,
        on_lifecycle_connection_success=on_lifecycle_connection_success_AWS,
        on_lifecycle_connection_failure=on_lifecycle_connection_failure_AWS,
        on_lifecycle_disconnection=on_lifecycle_disconnection_AWS,
        client_id=clientId_AWS)
    
    print("==== Starting client ====")
    client.start()

    if not connection_success_event.wait(TIMEOUT_CONNECT_AWS):
        raise TimeoutError("Connection timeout")

    print("==== Subscribing to topic '{}' ====".format(message_topic_commands_AWS))
    subscribe_future = client.subscribe(subscribe_packet=mqtt5.SubscribePacket(
        subscriptions=[mqtt5.Subscription(
            topic_filter=message_topic_commands_AWS,
            qos=mqtt5.QoS.AT_LEAST_ONCE)]
    ))
    suback = subscribe_future.result(TIMEOUT_CONNECT_AWS)
    print("Suback received with reason code:{}\n".format(suback.reason_codes))

    iot_connected = True

# Callback de Recepción de Mensajes desde AWS
def on_publish_received_AWS(publish_packet_data):
    publish_packet = publish_packet_data.publish_packet
    payload_str = publish_packet.payload.decode('utf-8')
    print("==== Received message from topic '{}': {} ====\n".format(publish_packet.topic, payload_str))

    try:
        command = json.loads(payload_str)
    except json.JSONDecodeError:
        print("Error: El payload recibido no es un JSON válido.")
        return

    if command.get('house') == device_name_AWS:
        print(f"Message for {device_name_AWS}\n")
        
        if command.get('device') == "LCD":
            print("Message for LCD\n")
            message = command.get('message', '')
            commandToHouse = f'lcd "{message}"'
            response = send_command(commandToHouse)
            print(f"Response from HOUSE: {response}")
            
        elif command.get('device') == "light":
            light_type = command.get('type')  
            action = command.get('action')      
            
            print(f"Procesando comando de iluminación: {light_type} -> {action}")
            commandToHouse = None

            if light_type in ["red", "green", "yellow", "white"]:
                commandToHouse = f"{light_type} {action}"
                
            elif light_type == "all":
                commandToHouse = f"lights {action}"
                
            elif light_type == "rgb":
                if action == "on":
                    color_val = command.get('color', '255, 255, 255')
                    commandToHouse = f"rgb: {color_val}"
                else:
                    commandToHouse = "lights off"

            if commandToHouse:
                response = send_command(commandToHouse)
                print(f"Response from HOUSE after light command: {response}")

# Callbacks de ciclo de vida de conexión MQTT5
def on_lifecycle_stopped_AWS(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    print("Lifecycle Stopped\n")
    stopped_event.set()

def on_lifecycle_attempting_connect_AWS(lifecycle_attempting_connect_data: mqtt5.LifecycleAttemptingConnectData):
    print("Lifecycle Connection Attempt\nConnecting to endpoint: '{}' with client ID'{}'".format(
        endpoint_AWS, clientId_AWS))

def on_lifecycle_connection_success_AWS(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    connack_packet = lifecycle_connect_success_data.connack_packet
    print("Lifecycle Connection Success with reason code:{}\n".format(repr(connack_packet.reason_code)))
    connection_success_event.set()

def on_lifecycle_connection_failure_AWS(lifecycle_connection_failure: mqtt5.LifecycleConnectFailureData):
    print("Lifecycle Connection Failure with exception:{}".format(lifecycle_connection_failure.exception))

def on_lifecycle_disconnection_AWS(lifecycle_disconnect_data: mqtt5.LifecycleDisconnectData):
    print("Lifecycle Disconnected with reason code:{}".format(
        lifecycle_disconnect_data.disconnect_packet.reason_code if lifecycle_disconnect_data.disconnect_packet else "None"))

def send_command(command):
    if not ser or not ser.is_open:
        return ["Serial port is not available."]
    
    print(f"Sending command: {command}")
    ser.write((command + '\n').encode('utf-8'))
    
    time.sleep(0.5) 
    
    responses = []
    while ser.in_waiting > 0:
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                responses.append(line)
        except UnicodeDecodeError:
            pass 
            
    print(f"Received response: {responses}")
    return responses if responses else ["No response from device."]

# --- Rutas del Servidor Flask ---

@app.route('/')
def index():
    return render_template(
        'index.html',
        endpoint_AWS=endpoint_AWS,
        cert_filepath_AWS=cert_filepath_AWS,
        pri_key_filepath_AWS=pri_key_filepath_AWS,
        clientId_AWS=clientId_AWS,
        device_name_AWS=device_name_AWS,
        message_topic_commands_AWS=message_topic_commands_AWS,
        message_topic_telemetry_AWS=message_topic_telemetry_AWS
    )

@app.route("/aws")
def aws_config():
    return render_template(
        "aws_config.html",
        title="AWS Configuration",
        endpoint_AWS=endpoint_AWS,
        cert_filepath_AWS=cert_filepath_AWS,
        pri_key_filepath_AWS=pri_key_filepath_AWS,
        clientId_AWS=clientId_AWS,
        device_name_AWS=device_name_AWS,
        message_topic_commands_AWS=message_topic_commands_AWS,
        message_topic_telemetry_AWS=message_topic_telemetry_AWS
    )

@app.route('/control', methods=['POST'])
def control():
    command = request.form.get('command')
    if not command:
        return jsonify({"status": "error", "message": "No command provided."}), 400
        
    if command.startswith("lcd"):
        message = request.form.get('message', '')
        command = f'lcd "{message}"'

    response = send_command(command)
    return jsonify({"status": "success", "command": command, "response": response})

@app.route('/sensors')
def get_sensors():
    if not ser or not ser.is_open:
        return jsonify({"error": "Serial port not available."})

    ser.flushInput()  
    response_lines = send_command("sensors")
    
    sensor_data = {}
    for line in response_lines:
        if "Result: " in line:
            try:
                key_part, value_part = line.split("Result: ", 1)[1].split(': ', 1)
                key = key_part.strip().lower().replace(" ", "_")
                sensor_data[key] = value_part.strip()
            except ValueError:
                value = line.split("Result: ", 1)[1]
                if "fire" in value.lower():
                    sensor_data["fire_safety"] = value
                elif "noise" in value.lower():
                    sensor_data["noise_status"] = value
                elif "intruder" in value.lower():
                    sensor_data["motion_status"] = value

    sensor_data["house"] = device_name_AWS
    sensor_data["timestamp"] = int(time.time())

    print(f"Parsed Sensor Data: {sensor_data}")
    mesage_json = json.dumps(sensor_data)

    if iot_connected:
        print(f"Publishing message to topic '{message_topic_telemetry_AWS}': {mesage_json}")
        publish_future = client.publish(
            mqtt5.PublishPacket(
                topic=message_topic_telemetry_AWS,
                payload=mesage_json,
                qos=mqtt5.QoS.AT_LEAST_ONCE
            )
        )

        publish_completion_data = publish_future.result(TIMEOUT_CONNECT_AWS)
        print("PubAck received with {}\n".format(repr(publish_completion_data.puback.reason_code)))

    return jsonify(sensor_data)

@app.route('/connect_iot', methods=['POST'])
def connect_iot():
    global endpoint_AWS, cert_filepath_AWS, pri_key_filepath_AWS
    global clientId_AWS, device_name_AWS, message_topic_commands_AWS, message_topic_telemetry_AWS

    endpoint_AWS = request.form.get("endpoint_AWS")
    cert_filepath_AWS = request.form.get("cert_filepath_AWS")
    pri_key_filepath_AWS = request.form.get("pri_key_filepath_AWS")
    clientId_AWS = request.form.get("clientId_AWS")
    device_name_AWS = request.form.get("device_name_AWS")
    message_topic_commands_AWS = request.form.get("message_topic_commands_AWS")
    message_topic_telemetry_AWS = request.form.get("message_topic_telemetry_AWS")

    try:
        connect_to_aws()
        return jsonify({"status": "success", "message": "Connected to AWS IoT"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    print("Starting Flask server. Open http://<your-pi-ip-address>:5000 in a browser.")
    app.run(host='0.0.0.0', port=5000)
