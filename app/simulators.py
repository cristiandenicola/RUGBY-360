import time
import json
import random
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone

# MQTT settings
MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_TOPIC_TEMPLATE = 'rugby/players/{}/sensors'
MQTT_COORDINATES_TOPIC_TEMPLATE = 'rugby/players/{}/sensors/coordinates'

# MongoDB settings
MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "rugbyDB"
BASE_COLLECTION_NAME = "simulations"

# Definition of roles and player distribution in rugby
ROLES = {
    1: 'pilone',
    2: 'pilone',
    3: 'tallonatore',
    4: 'seconda_linea',
    5: 'seconda_linea',
    6: 'flanker',
    7: 'flanker',
    8: 'numero_otto',
    9: 'mediano_di_mischia',
    10: 'mediano_d_apertura',
    11: 'centro',
    12: 'centro',
    13: 'ala',
    14: 'ala',
    15: 'estremo'
}

# MongoDB client
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]

rome_timezone = timezone(timedelta(hours=2))

def generate_metrics(player_id, role, elapsed_time):
    # Coefficienti per modificare il comportamento dei giocatori verso la fine della simulazione
    if elapsed_time > 70:
        heart_rate_coefficient = 1.2  # Aumenta il battito cardiaco
        gps_velocity_coefficient = 0.6  # Riduce la velocità di movimento
    else:
        heart_rate_coefficient = 1.0
        gps_velocity_coefficient = 1.0

    if role in ['pilone', 'tallonatore']:
        return {
            "player_id": player_id,
            "role": role,
            "heart_rate": {"heart_rate": int(random.randint(130, 190) * heart_rate_coefficient)},
            "temperature": {"body_temperature": round(random.uniform(36.0, 39.0), 1)},
            "blood_pressure": {"systolic": random.randint(160, 240), "diastolic": random.randint(80, 100)},
            "calories_consumed": {"calories": round(random.uniform(15, 25), 1)},
            "gps": {"x": random.randint(0, 20), "y": random.randint(0, 50), "velocity": round(random.uniform(0, 10) * gps_velocity_coefficient, 1)},
            "impacts": {"impact_count": random.randint(5, 15), "impact_force": round(random.uniform(10, 25), 1)},
            "timestamp": datetime.now(rome_timezone).isoformat(),
            "elapsed_time": elapsed_time
        }
    elif role in ['seconda_linea', 'flanker', 'numero_otto']:
        return {
            "player_id": player_id,
            "role": role,
            "heart_rate": {"heart_rate": int(random.randint(130, 190) * heart_rate_coefficient)},
            "temperature": {"body_temperature": round(random.uniform(36.0, 39.0), 1)},
            "blood_pressure": {"systolic": random.randint(160, 240), "diastolic": random.randint(80, 100)},
            "calories_consumed": {"calories": round(random.uniform(20, 30), 1)},
            "gps": {"x": random.randint(20, 80), "y": random.randint(0, 50), "velocity": round(random.uniform(0, 15) * gps_velocity_coefficient, 1)},
            "impacts": {"impact_count": random.randint(10, 20), "impact_force": round(random.uniform(15, 30), 1)},
            "timestamp": datetime.now(rome_timezone).isoformat(),
            "elapsed_time": elapsed_time
        }
    elif role in ['mediano_di_mischia', 'mediano_d_apertura', 'centro']:
        return {
            "player_id": player_id,
            "role": role,
            "heart_rate": {"heart_rate": int(random.randint(140, 200) * heart_rate_coefficient)},
            "temperature": {"body_temperature": round(random.uniform(36.0, 39.0), 1)},
            "blood_pressure": {"systolic": random.randint(160, 240), "diastolic": random.randint(80, 100)},
            "calories_consumed": {"calories": round(random.uniform(20, 35), 1)},
            "gps": {"x": random.randint(40, 100), "y": random.randint(0, 50), "velocity": round(random.uniform(0, 20) * gps_velocity_coefficient, 1)},
            "impacts": {"impact_count": random.randint(5, 15), "impact_force": round(random.uniform(10, 25), 1)},
            "timestamp": datetime.now(rome_timezone).isoformat(),
            "elapsed_time": elapsed_time
        }
    elif role in ['ala', 'estremo']:
        return {
            "player_id": player_id,
            "role": role,
            "heart_rate": {"heart_rate": int(random.randint(140, 200) * heart_rate_coefficient)},
            "temperature": {"body_temperature": round(random.uniform(36.0, 39.0), 1)},
            "blood_pressure": {"systolic": random.randint(160, 240), "diastolic": random.randint(80, 100)},
            "calories_consumed": {"calories": round(random.uniform(15, 30), 1)},
            "gps": {"x": random.randint(50, 120), "y": random.randint(0, 50), "velocity": round(random.uniform(0, 25) * gps_velocity_coefficient, 1)},
            "impacts": {"impact_count": random.randint(3, 10), "impact_force": round(random.uniform(8, 20), 1)},
            "timestamp": datetime.now(rome_timezone).isoformat(),
            "elapsed_time": elapsed_time
        }

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to topics for all players
        for player_id in range(1, 16):  # Range from 1 to 15 (inclusive)
            client.subscribe(MQTT_TOPIC_TEMPLATE.format(player_id))
    else:
        print(f"Failed to connect to MQTT broker with result code {rc}")

def on_message(client, userdata, msg):
    for player_id, role in ROLES.items():
        topic = MQTT_TOPIC_TEMPLATE.format(player_id)
        if msg.topic == topic:
            data = json.loads(msg.payload.decode())
            # Create a simplified message with only x and y coordinates
            simplified_data = {
                "player_id": data["player_id"],
                "role": data["role"],
                "gps": {
                    "x": data["gps"]["x"],
                    "y": data["gps"]["y"]
                }
            }
            # Publish simplified data to coordinates topic
            coordinates_topic = MQTT_COORDINATES_TOPIC_TEMPLATE.format(player_id)
            client.publish(coordinates_topic, json.dumps(simplified_data))
            print(f"Published coordinates for Player {player_id} to topic '{coordinates_topic}'")

def store_simulation_data(simulation_name, data):
    collection_name = f"{BASE_COLLECTION_NAME}_{simulation_name}"
    collection = db[collection_name]
    try:
        collection.insert_one(data)
        print(f"Data inserted into MongoDB collection '{collection_name}': {data}")
    except Exception as e:
        print(f"Error inserting data into MongoDB: {e}")

def main():
    mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)  # Specify MQTT protocol version
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)

    mqtt_client.loop_start()  # Start a background thread to handle MQTT events

    try:
        elapsed_time = 0  # Initialize the simulation elapsed time
        simulation_name = datetime.now(rome_timezone).strftime("%Y%m%d_%H%M%S")  # Generate a unique name for the simulation

        while elapsed_time <= 80:  # Simulate a rugby match duration (80 minutes)
            for player_id in range(1, 16):  # Range from 1 to 15 (inclusive)
                role = ROLES[player_id]
                payload = generate_metrics(player_id, role, elapsed_time)

                mqtt_topic = MQTT_TOPIC_TEMPLATE.format(player_id)
                mqtt_client.publish(mqtt_topic, json.dumps(payload))
                store_simulation_data(simulation_name, payload)
                print(f"Published and stored data for Player {player_id} ({role})")

            elapsed_time += 1  # Increment elapsed time
            time.sleep(1)  # Simulate one second of real time

    except KeyboardInterrupt:
        print("\nStopping sensor simulation...")
        mqtt_client.loop_stop()  # Stop the MQTT thread
        mqtt_client.disconnect()

if __name__ == '__main__':
    main()
