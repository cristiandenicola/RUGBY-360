import json
import random
import paho.mqtt.client as mqtt
from pymongo import MongoClient, DESCENDING
from datetime import timedelta, timezone

# settings
MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_TOPIC_TEMPLATE_METRICS = 'rugby/players/{}/realtime/metrics'
MQTT_TOPIC_IMPACTS = 'rugby/players/impacts'

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

def calculate_impact_results(collection_name):
    try:
        collection = db[collection_name]

        metrics = {}  # Initialize metrics dict

        pipeline_impacts_above_threshold = [
                {"$match": {"impacts.impact_force": {"$gt": 5.5}}},  # Only impacts > 5.3
                {"$project": {"player_id": 1, "impacts.impact_force": 1, "timestamp": 1}}  # Return player_id and force
            ]
        impacts_result = list(collection.aggregate(pipeline_impacts_above_threshold))
        return impacts_result
    except Exception as e:
        print(f"Error querying MongoDB: {e}")
        return None

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


            pipeline_avg_velocity = [
                {"$match": {"player_id": player_id}},
                {"$group": {"_id": None, "avg_velocity": {"$avg": "$gps.velocity"}}}
            ]
            avg_velocity_result = list(collection.aggregate(pipeline_avg_velocity))
            avg_velocity = avg_velocity_result[0]["avg_velocity"] if avg_velocity_result else 0.0

            pipeline_avg_force = [
                {"$match": {"player_id": player_id}},
                {"$match": {"impacts.impact_force": {"$ne": 0}}},
                {"$group": {"_id": None, "avg_force": {"$avg": "$impacts.impact_force"}}}
            ]

            avg_force_result = list(collection.aggregate(pipeline_avg_force))
            avg_force = avg_force_result[0]["avg_force"] if avg_force_result else 0.0

            pipeline_velocity_diff = [
                {"$match": {"player_id": player_id}},
                {"$sort": {"timestamp": 1}},  # Ordina i documenti per timestamp in ordine crescente
                {"$group": {
                    "_id": None,
                    "velocities": {"$push": "$gps.velocity"}  # Crea una lista di tutte le velocità
                }}
            ]
            velocity_diff_result = list(collection.aggregate(pipeline_velocity_diff))
            if velocity_diff_result:
                velocities = velocity_diff_result[0]["velocities"]
                velocity_diffs = [abs(velocities[i] - velocities[i - 1]) for i in range(1, len(velocities))]
                velocity_variability = sum(velocity_diffs) / len(velocity_diffs) if velocity_diffs else 0.0
            else:
                velocity_variability = 0.0


            if result:
                player_data = result[0]

                # Extract necessary fields
                velocity = avg_velocity
                elapsed_time = player_data["elapsed_time"]
                calories = player_data["calories_consumed"]["calories"]
                heart_rate = player_data["heart_rate"]["heart_rate"]
                body_temperature = player_data["temperature"]["body_temperature"]
                systolic = player_data["blood_pressure"]["systolic"]
                diastolic = player_data["blood_pressure"]["diastolic"]
                impact_count = player_data["impacts"]["impact_count"]
                impact_force =  avg_force

                # Derived metrics
                distance_traveled = velocity * (elapsed_time / 60.0)  # Convert minutes to hours for km
                distance_km = round(distance_traveled, 2)

                # Calculate additional metrics
                impact_to_play_ratio = impact_count/80  
                max_heart_rate = int(random.uniform(160, 210))
                impact_severity_index = round(random.uniform(1, 10), 1)  # Placeholder; adjust as needed


                metrics[player_id] = {
                    "player_id": player_id,
                    "average_velocity": round(velocity, 2),
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
                        "average_impact_force": impact_force
                    },
                    "impact_to_play_ratio": impact_to_play_ratio,
                    "velocity_variability": velocity_variability,
                    "max_heart_rate": max_heart_rate,
                    "impact_severity_index": impact_severity_index,
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

def publish_impacts(impacts_result):
    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    message_impacts = json.dumps(impacts_result)
    mqtt_client.publish(MQTT_TOPIC_IMPACTS, message_impacts)
    print(f"Published impacts: {impacts_result}")

    mqtt_client.loop_stop()
    mqtt_client.disconnect()

def main():
    latest_collection = get_latest_collection()
    if latest_collection:
        # Calculate metrics from the latest collection
        metrics = calculate_metrics(latest_collection)
        impacts_result = calculate_impact_results(latest_collection)
        if metrics:
            # Publish metrics via MQTT
            publish_metrics(metrics)
            print()
            print(impacts_result)

        else:
            print("No metrics calculated.")
    else:
        print("No latest collection found.")

if __name__ == '__main__':
    main()
