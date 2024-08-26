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
    # Dynamic coefficients based on elapsed time (e.g., increased heart rate, decreased speed)
    fatigue_coefficient = max(1.0, min(1.5, 1.0 + 0.01 * (elapsed_time - 60)))
    heart_rate_coefficient = fatigue_coefficient if elapsed_time > 60 else 1.0
    gps_velocity_coefficient = 1 / fatigue_coefficient if elapsed_time > 60 else 1.0

    # Generic metrics for all players
    metrics = {
        "player_id": player_id,
        "role": role,
        "heart_rate": {"heart_rate": int(random.uniform(120, 200) * heart_rate_coefficient)},
        "temperature": {"body_temperature": round(random.uniform(36.5, 39.0), 1)},
        "blood_pressure": {
            "systolic": random.randint(110, 180),
            "diastolic": random.randint(70, 120)
        },
        "calories_consumed": {"calories": round(random.uniform(250, 500), 1)},
        "gps": {
            "x": random.randint(0, 120),
            "y": random.randint(0, 50),
            "velocity": round(random.uniform(0, 40) * gps_velocity_coefficient, 1)
        },
        "impacts": {
            "impact_count": random.randint(1, 20),
            "impact_force": round(random.uniform(5, 50), 1)  # Increased range for impact force
        },
        "timestamp": datetime.now(rome_timezone).isoformat(),
        "elapsed_time": elapsed_time
    }

    # Role-specific modifications
    if role in ['pilone', 'tallonatore']:
        metrics["strength"] = {"max_force": round(random.uniform(400, 800), 1)}
    elif role in ['seconda_linea', 'flanker', 'numero_otto']:
        metrics["agility"] = {"agility_score": round(random.uniform(50, 100), 1)}
    elif role in ['mediano_di_mischia', 'mediano_d_apertura', 'centro']:
        metrics["passing_accuracy"] = {"accuracy": round(random.uniform(60, 100), 1)}
    elif role in ['ala', 'estremo']:
        metrics["speed"] = {"top_speed": round(random.uniform(20, 45), 1)}

    # Impact to play ratio: Number of impacts per 10 minutes of active play
    metrics["impact_to_play_ratio"] = {"ratio": round(random.uniform(0.1, 2.0), 2)}

    # Velocity variability: Simulated as the standard deviation of velocity readings
    metrics["velocity_variability"] = {"variability": round(random.uniform(0.5, 3.0), 2)}

    # Max heart rate simulated as the highest recorded value in a realistic range
    metrics["max_heart_rate"] = {"max_heart_rate": int(random.uniform(160, 210))}

    # Impact severity index: Derived from the force and frequency of impacts
    metrics["impact_severity_index"] = {"severity_index": round(random.uniform(1, 10), 1)}

    return metrics

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
