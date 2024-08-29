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
    1: 'prop',
    2: 'prop',
    3: 'hooker',
    4: 'lock',
    5: 'lock',
    6: 'flanker',
    7: 'flanker',
    8: 'number_eight',
    9: 'scrum_half',
    10: 'fly_half',
    11: 'center',
    12: 'center',
    13: 'wing',
    14: 'wing',
    15: 'full_back'
}

# Dictionary to track the impact counter for each player
impact_counters = {player_id: 0 for player_id in ROLES.keys()}

# Dictionary to track the calories for each player
calorie_counters = {player_id: 0.0 for player_id in ROLES.keys()}

# Dictionary to track the top speed for each player
top_speed = {player_id: 0.0 for player_id in ROLES.keys()}

# MongoDB client
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]

# Timezone for Rome
rome_timezone = timezone(timedelta(hours=2))

def generate_metrics(player_id, role, elapsed_time):
    global impact_counters, calorie_counters, top_speed  # Access the global dictionaries
    
    # Randomly decide if an impact occurs (40% probability)
    impact_occurs = random.random() < 0.4  # 40% probability

    if impact_occurs:
        # Increment the impact counter for the player if an impact occurs
        impact_counters[player_id] += 1

    # Dynamic coefficients based on elapsed time (e.g., increased heart rate, decreased speed)
    fatigue_coefficient = max(1.0, min(1.5, 1.0 + 0.01 * (elapsed_time - 60)))
    gps_velocity_coefficient = 1 / fatigue_coefficient if elapsed_time > 60 else 1.0

    # Speed based on the player's role
    if role in ['prop', 'hooker']:
        gps_velocity = round(random.uniform(0, 10) * gps_velocity_coefficient, 1)
    elif role in ['lock', 'flanker', 'number_eight']:
        gps_velocity = round(random.uniform(0, 20) * gps_velocity_coefficient, 1)
    elif role in ['scrum_half', 'fly_half', 'center']:
        gps_velocity = round(random.uniform(0, 30) * gps_velocity_coefficient, 1)
    elif role in ['wing', 'full_back']:
        gps_velocity = round(random.uniform(0, 40) * gps_velocity_coefficient, 1)

    # Save the top speed
    if gps_velocity > top_speed[player_id]:
        top_speed[player_id] = gps_velocity

    # Calculate heart rate based on speed and number of impacts
    base_heart_rate = 100  # Base heart rate
    heart_rate_increase_due_to_velocity = gps_velocity * 1.5  # Increase in heart rate due to speed
    heart_rate_increase_due_to_impacts = impact_counters[player_id] * 2  # Increase in heart rate due to impacts
    heart_rate = int(base_heart_rate + heart_rate_increase_due_to_velocity + heart_rate_increase_due_to_impacts)

    # Calculate calories based on heart rate and gps_velocity
    calorie_increment = (heart_rate / 150.0) * (gps_velocity / 10.0) * 5.0  # Arbitrary formula for calorie calculation
    calorie_counters[player_id] += calorie_increment

    # Calculate the max heart rate
    max_heart_rate = heart_rate  # Set max_heart_rate to the current value

    # Calculate body temperature based on heart rate and speed
    base_temperature = 36.5  # Base body temperature
    temperature_increase_due_to_heart_rate = (heart_rate - 120) * 0.01  # Each increase of 1 bpm adds 0.01°C
    temperature_increase_due_to_velocity = gps_velocity * 0.02  # Each increase of 1 m/s adds 0.02°C
    body_temperature = round(base_temperature + temperature_increase_due_to_heart_rate + temperature_increase_due_to_velocity, 1)

    # Calculate blood pressure based on heart rate
    base_systolic = 110  # Base systolic pressure
    base_diastolic = 70  # Base diastolic pressure
    systolic_increase_due_to_heart_rate = (heart_rate - 120) * 0.5  # Heart rate affects systolic pressure
    diastolic_increase_due_to_heart_rate = (heart_rate - 120) * 0.3  # Heart rate affects diastolic pressure
    systolic = int(base_systolic + systolic_increase_due_to_heart_rate)
    diastolic = int(base_diastolic + diastolic_increase_due_to_heart_rate)

    # Calculate impact force based on speed and frequency of impacts
    if impact_occurs:
        impact_force = round(gps_velocity * (1 + impact_counters[player_id] * 0.1), 1)  # Impact force increases with speed and number of impacts
    else:
        impact_force = 0.0

    metrics = {
        "timestamp": datetime.now(rome_timezone).isoformat(),
        "elapsed_time": elapsed_time,
        "player_id": player_id,
        "role": role,
        "heart_rate": {"heart_rate": heart_rate},
        "temperature": {"body_temperature": body_temperature},
        "blood_pressure": {
            "systolic": systolic,
            "diastolic": diastolic
        },
        "calories_consumed": {"calories": round(calorie_counters[player_id], 1)},
        "gps": {
            "x": random.randint(0, 120),
            "y": random.randint(0, 50),
            "velocity": gps_velocity,
            "top_speed": top_speed[player_id]
        },
        "impacts": {
            "impact_count": impact_counters[player_id], 
            "impact_force": impact_force
        }
    }

    # Impact to play ratio: calculated as the number of impacts per 10 minutes of active play
    if elapsed_time > 0:
        impact_to_play_ratio = impact_counters[player_id] / (elapsed_time / 10)
    else:
        impact_to_play_ratio = 0.0
    metrics["impact_to_play_ratio"] = {"ratio": round(impact_to_play_ratio, 2)}

    # Velocity variability: calculated as the variability of the speed relative to the average speed
    mean_velocity = sum(top_speed.values()) / len(top_speed.values())
    velocity_variability = abs(gps_velocity - mean_velocity) / mean_velocity if mean_velocity != 0 else 0
    metrics["velocity_variability"] = {"variability": round(velocity_variability, 2)}

    # Assign the calculated max heart rate
    metrics["max_heart_rate"] = {"max_heart_rate": max_heart_rate}

    # Impact severity index: derived from the force and frequency of impacts
    impact_severity_index = impact_counters[player_id] * (impact_force / 10.0)
    metrics["impact_severity_index"] = {"severity_index": round(impact_severity_index, 1)}

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
                print(f"Published sensor data for Player {player_id} to topic '{mqtt_topic}'")
                ##print(f"Published and stored data for Player {player_id} ({role})")

            elapsed_time += 1  # Increment elapsed time
            time.sleep(1)  # Simulate one second of real time

    except KeyboardInterrupt:
        print("\nStopping sensor simulation...")
        mqtt_client.loop_stop()  # Stop the MQTT thread
        mqtt_client.disconnect()

if __name__ == '__main__':
    main()
