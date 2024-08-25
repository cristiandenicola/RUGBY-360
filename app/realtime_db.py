import json
import paho.mqtt.client as mqtt
from pymongo import MongoClient, DESCENDING
from datetime import timedelta, timezone

# MQTT settings
MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_TOPIC_TEMPLATE_METRICS = 'rugby/players/{}/realtime/metrics'

# MongoDB settings
MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "rugbyDB"
BASE_COLLECTION_NAME = "simulations"

# MongoDB client
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]

rome_timezone = timezone(timedelta(hours=2))

def get_latest_collection():
    # Get all collection names
    collection_names = db.list_collection_names()
    # Filter for simulation collections
    simulation_collections = [name for name in collection_names if name.startswith(BASE_COLLECTION_NAME)]
    
    if not simulation_collections:
        print("No simulation data found.")
        return None
    
    # Find the latest collection by sorting
    latest_collection = max(simulation_collections)
    return latest_collection

def calculate_metrics(collection_name):
    try:
        collection = db[collection_name]

        # Query to calculate metrics for each player
        metrics = {}
        for player_id in range(1, 16):  # Rugby has 15 players per team
            # Aggregating all necessary metrics
            pipeline = [
                {"$match": {"player_id": player_id}},
                {"$sort": {"timestamp": DESCENDING}},
                {"$limit": 1}
            ]
            result = list(collection.aggregate(pipeline))
            if result:
                player_data = result[0]
                metrics[player_id] = {
                    "average_velocity": round(player_data["gps"]["velocity"], 2),
                    "distance_traveled_km": round(player_data["gps"]["velocity"] * (player_data["elapsed_time"] / 60.0), 2),  # Convert minutes to hours for km
                    "calories_consumed": round(player_data["calories_consumed"]["calories"], 2),
                    "heart_rate": player_data["heart_rate"]["heart_rate"],
                    "body_temperature": player_data["temperature"]["body_temperature"],
                    "blood_pressure": {
                        "systolic": player_data["blood_pressure"]["systolic"],
                        "diastolic": player_data["blood_pressure"]["diastolic"]
                    },
                    "impacts": {
                        "impact_count": player_data["impacts"]["impact_count"],
                        "impact_force": player_data["impacts"]["impact_force"]
                    }
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
                        "impact_force": 0.0
                    }
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
