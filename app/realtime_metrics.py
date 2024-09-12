import os
import json
import paho.mqtt.client as mqtt
from pymongo import MongoClient, DESCENDING
from datetime import timedelta, timezone

# settings (can be overridden by environment variables)
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC_TEMPLATE_METRICS = 'rugby/players/{}/realtime/metrics'
MQTT_TOPIC_IMPACTS = 'rugby/players/impacts'

MONGO_URI = os.getenv('MONGO_URI', "mongodb://localhost:27017/")
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

        # Pipeline to fetch aggregated metrics for all players at once
        pipeline = [
            {"$match": {"player_id": {"$in": list(range(1, 16))}}},
            {"$group": {
                "_id": "$player_id",
                "avg_velocity": {"$avg": "$gps.velocity"},
                "avg_impact_force": {"$avg": {"$cond": [{"$ne": ["$impacts.impact_force", 0]}, "$impacts.impact_force", None]}},
                "max_heart_rate": {"$max": "$heart_rate.heart_rate"},
                "latest_data": {"$last": "$$ROOT"}
            }}
        ]

        results = list(collection.aggregate(pipeline))

        metrics = {}

        for result in results:
            player_id = result["_id"]
            latest_data = result["latest_data"]

            # Extract metrics
            avg_velocity = result["avg_velocity"] if result["avg_velocity"] else 0.0
            avg_force = result["avg_impact_force"] if result["avg_impact_force"] else 0.0
            max_heart_rate = result["max_heart_rate"] if result["max_heart_rate"] else 0

            # Calculate velocity variability
            velocities = [d["gps"]["velocity"] for d in collection.find({"player_id": player_id}, {"gps.velocity": 1, "_id": 0})]
            velocity_diffs = [abs(velocities[i] - velocities[i - 1]) for i in range(1, len(velocities))]
            velocity_variability = sum(velocity_diffs) / len(velocity_diffs) if velocity_diffs else 0.0

            if latest_data:
                # Extract necessary fields
                elapsed_time = latest_data["elapsed_time"]
                calories = latest_data["calories_consumed"]["calories"]
                heart_rate = latest_data["heart_rate"]["heart_rate"]
                body_temperature = latest_data["temperature"]["body_temperature"]
                systolic = latest_data["blood_pressure"]["systolic"]
                diastolic = latest_data["blood_pressure"]["diastolic"]
                impact_count = latest_data["impacts"]["impact_count"]

                # Derived metrics
                distance_traveled = avg_velocity * (elapsed_time / 60.0)  # Convert minutes to hours for km
                distance_km = round(distance_traveled, 2)
                impact_to_play_ratio = impact_count / 80

                metrics[player_id] = {
                    "player_id": player_id,
                    "average_velocity": round(avg_velocity, 2),
                    "distance_traveled_km": round(distance_km, 2),
                    "calories_consumed": round(calories, 2),
                    "heart_rate": heart_rate,
                    "body_temperature": round(body_temperature, 1),
                    "blood_pressure": {
                        "systolic": systolic,
                        "diastolic": diastolic
                    },
                    "impacts": {
                        "impact_count": impact_count,
                        "average_impact_force": avg_force
                    },
                    "impact_to_play_ratio": impact_to_play_ratio,
                    "velocity_variability": round(velocity_variability, 2),
                    "max_heart_rate": max_heart_rate
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
                    "max_heart_rate": 0
                }

        return metrics

    except Exception as e:
        print(f"Error querying MongoDB: {e}")
        return None

def publish_metrics(metrics):
    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    try:
        for player_id, data in metrics.items():
            # Publish all metrics in a single MQTT message
            topic_metrics = MQTT_TOPIC_TEMPLATE_METRICS.format(player_id)
            message_metrics = json.dumps(data)
            mqtt_client.publish(topic_metrics, message_metrics)
            print(f"Published metrics for Player {player_id}: {data}")
    except Exception as e:
        print(f"Failed to publish metrics: {e}")
    finally:
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
