import json
import subprocess
import threading
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, timedelta

from awsiot import mqtt5_client_builder
from awscrt import mqtt5

app = Flask(__name__)

# Properties for connecting to AWSIOTCore
connection_success_event = threading.Event()
stopped_event = threading.Event()
received_all_event = threading.Event()
endpoint_AWS = "a2xyhr7rc9cefs-ats.iot.us-east-1.amazonaws.com"
cert_filepath_AWS = "cert/Control.cert.pem"
pri_key_filepath_AWS = "cert/Control.private.key"
clientId_AWS = "Control"
message_topic_commands_AWS = "command"
client = None
iot_connected = False
TIMEOUT_CONNECT_AWS = 100

# Connection to AWS
def connect_to_aws():
    global client, iot_connected
    print("==== Creating MQTT5 Client ====\n")
    client = mqtt5_client_builder.mtls_from_path(
        endpoint=endpoint_AWS,
        cert_filepath=cert_filepath_AWS,
        pri_key_filepath=pri_key_filepath_AWS,
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

    iot_connected = True

def on_publish_received_AWS(publish_packet_data):
    publish_packet = publish_packet_data.publish_packet
    print("==== Received message from topic '{}': {} ====\n".format(
        publish_packet.topic, publish_packet.payload.decode('utf-8')))

def on_lifecycle_stopped_AWS(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    print("Lifecycle Stopped\n")
    stopped_event.set()

def on_lifecycle_attempting_connect_AWS(lifecycle_attempting_connect_data: mqtt5.LifecycleAttemptingConnectData):
    print("Lifecycle Connection Attempt\nConnecting to endpoint: '{}' with client ID'{}'".format(
        endpoint_AWS, clientId_AWS))

def on_lifecycle_connection_success_AWS(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    connack_packet = lifecycle_connect_success_data.connack_packet
    print("Lifecycle Connection Success with reason code:{}\n".format(
        repr(connack_packet.reason_code)))
    connection_success_event.set()

def on_lifecycle_connection_failure_AWS(lifecycle_connection_failure: mqtt5.LifecycleConnectFailureData):
    print("Lifecycle Connection Failure with exception:{}".format(
        lifecycle_connection_failure.exception))

def on_lifecycle_disconnection_AWS(lifecycle_disconnect_data: mqtt5.LifecycleDisconnectData):
    print("Lifecycle Disconnected with reason code:{}".format(
        lifecycle_disconnect_data.disconnect_packet.reason_code if lifecycle_disconnect_data.disconnect_packet else "None"))


@app.route("/")
def index():
    # Inicializamos estructura de seguridad por si el archivo está vacío o no existe
    data = {"Items": []}

    try:
        with open("../datos.json") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Aviso: '../datos.json' vacío o no encontrado ({str(e)}). Cargando valores por defecto.")

    items = data.get("Items", [])

    # --- MODIFICACIÓN REQUERIDA: AGRUPAR POR CASA Y QUEDARSE CON EL ÚLTIMO ESTADO ---
    ultimos_estados_por_casa = {}

    for item in items:
        casa_name = item.get("house", {}).get("S")
        if not casa_name:
            continue

        payload = item.get("payload", {}).get("M", {})
        ts_str = payload.get("timestamp", {}).get("N")
        if not ts_str:
            continue
        
        ts_actual = int(ts_str)

        # Si no conocemos la casa, o el timestamp actual es mayor que el que teníamos guardado
        if casa_name not in ultimos_estados_por_casa or ts_actual > ultimos_estados_por_casa[casa_name]["timestamp"]:
            ultimos_estados_por_casa[casa_name] = {
                "timestamp": ts_actual,
                "payload": payload
            }

    # Obtener lista de casas únicas detectadas para el desplegable
    houses = list(ultimos_estados_por_casa.keys())

    # Seleccionar la casa (por url o la primera de la lista)
    if houses:
        selected_house = request.args.get("house", houses[0])
    else:
        selected_house = None

    # Inicializar listas/valores por defecto para limpiar la UI si no hay datos de la casa
    timestamps = []
    temperature = []
    humidity = []
    distance = []
    
    # Estructura limpia para mapear el estado de las luces en el HTML
    luces = {
        "red_led": "OFF",
        "yellow_led": "OFF",
        "green_led": "OFF",
        "white_led": "OFF",
        "rgb_status": "off",
        "rgb_color": "254, 130, 30"
    }

    # Si la casa seleccionada tiene un registro válido agrupado, extraemos la info
    if selected_house and selected_house in ultimos_estados_por_casa:
        casa_payload = ultimos_estados_por_casa[selected_house]["payload"]
        ts = ultimos_estados_por_casa[selected_house]["timestamp"]
        dt = datetime.fromtimestamp(ts)
        
        # Guardamos el formato de hora para las gráficas
        timestamps.append(dt.strftime("%d/%m %H:%M:%S"))

        # Extraer estados de sensores ambientales
        temp_raw = casa_payload.get("temperature", {}).get("S")
        if temp_raw:
            temperature.append(float(temp_raw.replace("C", "")))
        else:
            temperature.append(None)

        hum_raw = casa_payload.get("humidity", {}).get("S")
        if hum_raw:
            humidity.append(float(hum_raw.replace("%", "")))
        else:
            humidity.append(None)

        dist_raw = casa_payload.get("distance", {}).get("S")
        if dist_raw:
            distance.append(float(dist_raw.replace(" cm", "")))
        else:
            distance.append(None)

        # Extraer estados de las luces (Actuadores para los círculos de Bulma)
        luces["red_led"] = casa_payload.get("red_led", {}).get("S", "OFF")
        luces["yellow_led"] = casa_payload.get("yellow_led", {}).get("S", "OFF")
        luces["green_led"] = casa_payload.get("green_led", {}).get("S", "OFF")
        luces["white_led"] = casa_payload.get("white_led", {}).get("S", "OFF")
        luces["rgb_status"] = casa_payload.get("rgb_status", {}).get("S", "off")
        luces["rgb_color"] = casa_payload.get("rgb_color", {}).get("S", "254, 130, 30")

    return render_template(
        "index.html",
        timestamps=timestamps,
        temperature=temperature,
        humidity=humidity,
        distance=distance,
        houses=houses,
        selected_house=selected_house,
        luces=luces
    )

@app.route("/send", methods=["POST"])
def send():
    message = request.form.get("message")
    house = request.form.get("house")

    try:
        data = json.loads(message)
        data["house"] = house
        final_message = json.dumps(data)

        if iot_connected:
            print(f"JSON enviado a IoT: '{message_topic_commands_AWS}': {final_message}")
            publish_future = client.publish(
                mqtt5.PublishPacket(
                    topic=message_topic_commands_AWS,
                    payload=final_message,
                    qos=mqtt5.QoS.AT_LEAST_ONCE
                )
            )
            publish_completion_data = publish_future.result(TIMEOUT_CONNECT_AWS)
            print("PubAck received with {}\n".format(repr(publish_completion_data.puback.reason_code)))

    except Exception as e:
        print("Error procesando JSON:", e)

    if house and house != "None":
        return redirect(url_for("index", house=house))
    else:
        return redirect(url_for("index"))

@app.route("/refresh")
def refresh():
    print("Entro en refresh")
    house = request.args.get("house") # Cambiado a args para leer correctamente de la URL
    
    now = datetime.now()
    start_of_day = datetime(now.year, now.month, now.day)
    end_of_day = start_of_day + timedelta(days=1)

    start_ts = int(start_of_day.timestamp())
    end_ts = int(end_of_day.timestamp())

    # =========================================================================
    # VARIABLES CON CREDENCIALES AWS
    # =========================================================================
    AWS_ACCESS_KEY_ID = "ASIAZTVFSTICDXHB6SKD"
    AWS_SECRET_ACCESS_KEY = "sFe3Nv/3AXMMq/JLMJKQZXPbYJov5+PE1MSCyd0G"
    AWS_SESSION_TOKEN = "IQoJb3JpZ2luX2VjECoaCXVzLXdlc3QtMiJGMEQCIFGgObum5V2bgGU7TeLSGM1D2VgCimnHEM+tbaNY9kmJAiAbfgySFzbIgBFS6uGKc8nVW7gukyiU9HRhjl2Ja9phgiq+Agjz//////////8BEAQaDDY2MDY5ODQ3MDkxNiIMLSf44pckWZWQdP9xKpICZLVugH9HVwZv6pnMWqOJuUTZOsdZ/0nH/9oz7TvGmRX4ZbCz+EJzDsXbllO4P9Zh2KxV0X3yVWbiiO508E94u0UTe7qMOnH2KMppBsliNm/fQAK4KylUyyvZ4Znv2sCpfKUkAN0pNvViEXed2gxLDQjmjqJccSFOVYO+436Vb3DvErw92aWqTYvVBLigXrARP+IVDQuEWVMvR6d0bgSNVX72wCFITCGxti/SuvNejW62iE9uLaiudcsjinDb54qz1ekg2258OJbAAQHOjYrKSgRwrLKRfNy9VjHJIAZgQyQaH8UpZ7Bm1tcrt2wgITeqzqpH/zMACszDPCSwRbs14Xjk1RP0Pw3FYg0jWPG+WzkcpjDkjfDQBjqeAdl5+AqVKoG6trSARfjVWx0Mvuhh3q+EIfr4cHgVSOwaAQXo8HYLLHaeXr17La55C9wOooKuX4KbP+wbgf7eZPeJ9j7o4vV27H/M95tRGSFS3K5VIj1dn9Q+/TGP4ObIhAj9aN0suE+/KPXlVe+F1qmLZPfO5cDG4I2+QD/8X2DW2XrK4pms/1L+th3dfq4W2qHALnqHDVgF1CpV/RrJ"
    # =========================================================================

    # Inyectamos de forma segura las variables dentro del string antes de ejecutar el escaneo
    command = f"""AWS_ACCESS_KEY_ID="{AWS_ACCESS_KEY_ID}" \
    AWS_SECRET_ACCESS_KEY="{AWS_SECRET_ACCESS_KEY}" \
    AWS_SESSION_TOKEN="{AWS_SESSION_TOKEN}" \
    AWS_DEFAULT_REGION="us-east-1" \
    aws dynamodb scan \
    --table-name telemetry \
    --filter-expression "#ts BETWEEN :start AND :end" \
    --expression-attribute-names '{{"#ts":"timestamp"}}' \
    --expression-attribute-values '{{":start":{{"N":"{start_ts}"}},":end":{{"N":"{end_ts}"}}}}' \
    --output json > ../datos.json"""

    print("Comando ejecutado:")
    print(command)

    subprocess.run(command, shell=True)

    if house and house != "None":
        return redirect(url_for("index", house=house))
    return redirect(url_for("index"))

if __name__ == "__main__":
    try:
        connect_to_aws()
        print("Connected to AWS IoT")
    except Exception as e:
        print("Error conectando IOTCore: ", str(e))

    app.run(host="0.0.0.0", port=5001)
