import json
import queue
import threading
import time
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

class TelemetrySender:
    """
    Gère l'enregistrement des données de télémétrie, leur envoi réseau, 
    et écoute le robot physique (Digital Twin) via MQTT.
    """
    def __init__(self, webhook_url: str = "http://127.0.0.1:5000/webhook", 
                 mqtt_broker: str = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud", 
                 mqtt_port: int = 8883,
                 mqtt_topic_pub: str = "warehouse/agv/telemetry",
                 mqtt_topic_twin: str = "hafida/robot/twin/telemetry",
                 mqtt_topic_cmd: str = "hafida/robot/twin/command",
                 mqtt_topic_twin2: str = "hafida/robot/twin2/telemetry",
                 mqtt_topic_cmd2: str = "hafida/robot/twin2/command",
                 mqtt_username: str = "hivemq.webclient.1775653497883",
                 mqtt_password: str = "1B%.CwaP:Kdr2I93k*Ap"):
        self.webhook_url = webhook_url
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic_pub = mqtt_topic_pub
        self.mqtt_topic_twin = mqtt_topic_twin
        self.mqtt_topic_cmd = mqtt_topic_cmd
        self.mqtt_topic_twin2 = mqtt_topic_twin2
        self.mqtt_topic_cmd2 = mqtt_topic_cmd2
        
        self.queue = queue.Queue()
        self.running = True
        
        self.last_webhook_status = "IDLE"
        self.last_mqtt_status = "IDLE"
        
        self.twin_data = {}
        self.data_lock = threading.Lock()
        
        self.mqtt_client = None
        if mqtt is not None:
            try:
                import ssl
                try:
                    self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
                except AttributeError:
                    self.mqtt_client = mqtt.Client()
                
                if mqtt_username and mqtt_password:
                    self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
                
                if self.mqtt_port == 8883:
                    self.mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
                    self.mqtt_client.tls_insecure_set(True)
                
                self.mqtt_client.on_connect = self._on_connect
                self.mqtt_client.on_message = self._on_message
                
                self.mqtt_client.connect_async(self.mqtt_broker, self.mqtt_port, 60)
                self.mqtt_client.loop_start()
                self.last_mqtt_status = "CONNECTING"
            except Exception as e:
                self.last_mqtt_status = f"FAILED: {e}"
        else:
            self.last_mqtt_status = "LIBRARY MISSING"

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _on_connect(self, client, userdata, flags, rc, *args):
        # Handle different versions of paho-mqtt callbacks
        if rc == 0:
            self.last_mqtt_status = "CONNECTED & SUBSCRIBED"
            client.subscribe([(self.mqtt_topic_twin, 0), (self.mqtt_topic_twin2, 0)])
        else:
            self.last_mqtt_status = f"CONN_ERR: {rc}"
            
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            device_id = payload.get("device")
            if device_id:
                with self.data_lock:
                    self.twin_data[device_id] = payload
        except Exception as e:
            print(f"[MQTT] Erreur décodage message entrant: {e}")

    def get_physical_twin_data(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Renvoie les dernières données reçues d'un robot physique (ESP32) spécifique."""
        with self.data_lock:
            return self.twin_data.get(device_id)

    def send_motor_command(self, topic: str, m1: int, m2: int, m3: int, m4: int):
        """Envoie une commande moteur directe au robot ESP32 sur le topic spécifié."""
        if self.mqtt_client is not None and self.mqtt_client.is_connected():
            cmd = f"{m1},{m2},{m3},{m4}"
            self.mqtt_client.publish(topic, cmd)

    def send_string_command(self, topic: str, cmd: str):
        """Envoie une commande textuelle (FORWARD, LEFT, etc.) au robot ESP32."""
        if self.mqtt_client is not None and self.mqtt_client.is_connected():
            self.mqtt_client.publish(topic, cmd)

    def submit_telemetry(self, payload: Dict[str, Any]):
        """Ajoute un message de télémétrie à la file d'attente."""
        self.queue.put(payload)

    def stop(self):
        """Arrête proprement le thread en arrière-plan."""
        self.running = False
        self.queue.put(None)
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except:
                pass
        self.worker_thread.join(timeout=1.0)

    def _worker_loop(self):
        """Boucle principale du thread."""
        while self.running:
            try:
                payload = self.queue.get(timeout=0.5)
                if payload is None:
                    break
                
                self._log_to_file(payload)
                self._send_to_webhook(payload)
                self._publish_to_mqtt(payload)
                
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Telemetry Error] Exception in worker thread: {e}")

    def _log_to_file(self, payload: Dict[str, Any]):
        try:
            with open("telemetry_logs.json", "a") as f:
                f.write(json.dumps(payload) + "\n")
        except:
            pass

    def _send_to_webhook(self, payload: Dict[str, Any]):
        if requests is None:
            self.last_webhook_status = "ERR: requests missing"
            return
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=1.0)
            if response.status_code in [200, 201]:
                self.last_webhook_status = f"OK ({response.status_code})"
            else:
                self.last_webhook_status = f"ERR ({response.status_code})"
        except requests.exceptions.RequestException:
            self.last_webhook_status = "ERR: Connection Refused"

    def _publish_to_mqtt(self, payload: Dict[str, Any]):
        if self.mqtt_client is None:
            return
        try:
            if self.mqtt_client.is_connected():
                self.mqtt_client.publish(self.mqtt_topic_pub, json.dumps(payload))
        except:
            pass
