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
    Manages telemetry logging and network transmission in a background thread.
    Uses a thread-safe queue to ensure the Pygame thread is never blocked.
    """
    def __init__(self, webhook_url: str = "http://127.0.0.1:5000/webhook", 
                 mqtt_broker: str = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud", 
                 mqtt_port: int = 8883,
                 mqtt_topic: str = "warehouse/agv/telemetry",
                 mqtt_username: str = "hivemq.webclient.1775653497883",
                 mqtt_password: str = "1B%.CwaP:Kdr2I93k*Ap"):
        self.webhook_url = webhook_url
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = mqtt_topic
        
        self.queue = queue.Queue()
        self.running = True
        
        self.last_webhook_status = "IDLE"
        self.last_mqtt_status = "IDLE"
        
        # Initialize MQTT client
        self.mqtt_client = None
        if mqtt is not None:
            try:
                import ssl
                # Handle paho-mqtt v2.0+ callback API version requirement
                try:
                    self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
                except AttributeError:
                    self.mqtt_client = mqtt.Client()
                
                # Set username and password
                if mqtt_username and mqtt_password:
                    self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
                
                # Set TLS if secure port
                if self.mqtt_port == 8883:
                    self.mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
                    self.mqtt_client.tls_insecure_set(True)
                
                # Non-blocking connection attempt
                self.mqtt_client.connect_async(self.mqtt_broker, self.mqtt_port, 60)
                self.mqtt_client.loop_start()
                self.last_mqtt_status = "CONNECTING"
            except Exception as e:
                self.last_mqtt_status = f"FAILED: {e}"
        else:
            self.last_mqtt_status = "LIBRARY MISSING"

        # Start the background thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def submit_telemetry(self, payload: Dict[str, Any]):
        """Pushes a telemetry payload onto the queue for background processing."""
        self.queue.put(payload)

    def stop(self):
        """Cleanly stops the background thread and releases resources."""
        self.running = False
        # Push a sentinel to unblock queue.get()
        self.queue.put(None)
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except:
                pass
        self.worker_thread.join(timeout=1.0)

    def _worker_loop(self):
        """Worker thread processing queue items and performing I/O operations."""
        while self.running:
            try:
                payload = self.queue.get(timeout=0.5)
                if payload is None:
                    break
                
                # 1. Log to local file (JSON Lines format)
                self._log_to_file(payload)
                
                # 2. Send via Webhook
                self._send_to_webhook(payload)
                
                # 3. Send via MQTT
                self._publish_to_mqtt(payload)
                
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Telemetry Error] Exception in worker thread: {e}")

    def _log_to_file(self, payload: Dict[str, Any]):
        """Appends the telemetry payload to telemetry_logs.json."""
        try:
            with open("telemetry_logs.json", "a") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as e:
            print(f"[Telemetry Error] Failed to write to telemetry_logs.json: {e}")

    def _send_to_webhook(self, payload: Dict[str, Any]):
        """Posts payload to local Webhook URL."""
        if requests is None:
            self.last_webhook_status = "ERR: requests missing"
            return
            
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=1.0)
            if response.status_code == 200 or response.status_code == 201:
                self.last_webhook_status = f"OK ({response.status_code})"
            else:
                self.last_webhook_status = f"ERR ({response.status_code})"
        except requests.exceptions.RequestException:
            # Silence the error to prevent console clutter during normal running without a receiver
            self.last_webhook_status = "ERR: Connection Refused"

    def _publish_to_mqtt(self, payload: Dict[str, Any]):
        """Publishes payload to MQTT Broker."""
        if self.mqtt_client is None:
            return
            
        try:
            # Check connection state
            if self.mqtt_client.is_connected():
                self.mqtt_client.publish(self.mqtt_topic, json.dumps(payload))
                self.last_mqtt_status = "CONNECTED & PUBLISHING"
            else:
                # Loop start is running connect_async, it should auto-reconnect
                self.last_mqtt_status = "DISCONNECTED (Retrying...)"
        except Exception as e:
            self.last_mqtt_status = f"ERR: {e}"
