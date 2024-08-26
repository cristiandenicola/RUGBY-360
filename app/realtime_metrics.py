import json
import random
import paho.mqtt.client as mqtt
from pymongo import MongoClient, DESCENDING
from datetime import timedelta, timezone

# settings
MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_TOPIC_TEMPLATE_METRICS = 'rugby/players/{}/realtime/metrics'

MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "rugbyDB"
BASE_COLLECTION_NAME = "simulations"

client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]

rome_timezone = timezone(timedelta(hours=2))

def get_latest_collection():
    collection_names = db.list_collection_names()
    simulation_collections = [name for name in collection_names if name.startswith(BASE_COLLECTION_NAME)]
    
    if not simulation_collections:
        print("No simulation data found.")
        return None
    
    latest_collection = max(simulation_collections)
    
    return latest_collection

def calculate_metrics(collection_name):
    try:
        collection = db[collection_name]

        metrics = {}  # Initialize metrics dict

        for player_id in range(1, 16):  # Rugby has 15 players per team

            pipeline = [
                {"$match": {"player_id": player_id}},
                {"$sort": {"timestamp": DESCENDING}},
                {"$limit": 1}
            ]
            result = list(collection.aggregate(pipeline))

            if result:
                player_data = result[0]

                # Extract necessary fields
                velocity = player_data["gps"]["velocity"]
                elapsed_time = player_data["elapsed_time"]
                calories = player_data["calories_consumed"]["calories"]
                heart_rate = player_data["heart_rate"]["heart_rate"]
                body_temperature = player_data["temperature"]["body_temperature"]
                systolic = player_data["blood_pressure"]["systolic"]
                diastolic = player_data["blood_pressure"]["diastolic"]
                impact_count = player_data["impacts"]["impact_count"]
                impact_force = player_data["impacts"]["impact_force"]

                # Derived metrics
                distance_traveled_km = round(velocity * (elapsed_time / 60.0), 2)  # Convert minutes to hours and meters to km
                average_impact_force = round(impact_force / impact_count, 2) if impact_count > 0 else 0

                # Calculate additional metrics
                impact_to_play_ratio = round(random.uniform(0.1, 2.0), 2)  # Placeholder; adjust as needed for realistic data
                velocity_variability = round(random.uniform(0.5, 3.0), 2)  # Placeholder; adjust as needed
                max_heart_rate = int(random.uniform(160, 210))  # Placeholder; adjust as needed
                impact_severity_index = round(random.uniform(1, 10), 1)  # Placeholder; adjust as needed

                metrics[player_id] = {
                    "average_velocity": round(velocity, 2),
                    "distance_traveled_km": distance_traveled_km,
                    "calories_consumed": round(calories, 2),
                    "heart_rate": heart_rate,
                    "body_temperature": round(body_temperature, 1),
                    "blood_pressure": {
                        "systolic": systolic,
                        "diastolic": diastolic
                    },
                    "impacts": {
                        "impact_count": impact_count,
                        "average_impact_force": average_impact_force
                    },
                    "impact_to_play_ratio": impact_to_play_ratio,
                    "velocity_variability": velocity_variability,
                    "max_heart_rate": max_heart_rate,
                    "impact_severity_index": impact_severity_index
                }
            else:
                metrics[player_id] = {
                    "average_velocity": 0.0,
                    "distance_traveled_km": 0.0,
                    "calories_consumed": 0.0,
                    "heart_rate": 0,
                    "body_temperature": 0.0,
                    "blood_pressure": {
                        "systolic": 0,
                        "diastolic": 0
                    },
                    "impacts": {
                        "impact_count": 0,
                        "average_impact_force": 0.0
                    },
                    "impact_to_play_ratio": 0.0,
                    "velocity_variability": 0.0,
                    "max_heart_rate": 0,
                    "impact_severity_index": 0.0
                }

        return metrics

    except Exception as e:
        print(f"Error querying MongoDB: {e}")
        return None

def publish_metrics(metrics):
    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    for player_id, data in metrics.items():
        # Publish all metrics in a single MQTT message
        topic_metrics = MQTT_TOPIC_TEMPLATE_METRICS.format(player_id)
        message_metrics = json.dumps(data)
        mqtt_client.publish(topic_metrics, message_metrics)
        print(f"Published metrics for Player {player_id}: {data}")

    mqtt_client.loop_stop()
    mqtt_client.disconnect()

def main():
    latest_collection = get_latest_collection()
    if latest_collection:
        # Calculate metrics from the latest collection
        metrics = calculate_metrics(latest_collection)
        if metrics:
            # Publish metrics via MQTT
            publish_metrics(metrics)
        else:
            print("No metrics calculated.")
    else:
        print("No latest collection found.")

if __name__ == '__main__':
    main()
