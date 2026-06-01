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
    Gère l'enregistrement des données de télémétrie et leur envoi réseau en arrière-plan.
    Utilise une file d'attente sécurisée (Thread-safe) pour ne jamais bloquer la simulation principale.
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
        
        # Initialisation du client MQTT
        self.mqtt_client = None
        if mqtt is not None:
            try:
                import ssl
                # Gestion de la version de l'API de rappel pour paho-mqtt v2.0+
                try:
                    self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
                except AttributeError:
                    self.mqtt_client = mqtt.Client()
                
                # Configuration de l'identifiant et du mot de passe de connexion
                if mqtt_username and mqtt_password:
                    self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
                
                # Sécurisation avec TLS si le port 8883 est utilisé
                if self.mqtt_port == 8883:
                    self.mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
                    self.mqtt_client.tls_insecure_set(True)
                
                # Connexion asynchrone non bloquante
                self.mqtt_client.connect_async(self.mqtt_broker, self.mqtt_port, 60)
                self.mqtt_client.loop_start()
                self.last_mqtt_status = "CONNECTING"
            except Exception as e:
                self.last_mqtt_status = f"FAILED: {e}"
        else:
            self.last_mqtt_status = "LIBRARY MISSING"

        # Lancement du thread d'arrière-plan
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def submit_telemetry(self, payload: Dict[str, Any]):
        """Ajoute un message de télémétrie à la file d'attente pour qu'il soit traité en tâche de fond."""
        self.queue.put(payload)

    def stop(self):
        """Arrête proprement le thread en arrière-plan et libère toutes les ressources."""
        self.running = False
        # On envoie une valeur vide (sentinelle) pour débloquer la file d'attente
        self.queue.put(None)
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except:
                pass
        self.worker_thread.join(timeout=1.0)

    def _worker_loop(self):
        """Boucle principale du thread qui dépile les messages et effectue les envois."""
        while self.running:
            try:
                payload = self.queue.get(timeout=0.5)
                if payload is None:
                    break
                
                # 1. Enregistrement dans le fichier de logs local (format JSON Lines)
                self._log_to_file(payload)
                
                # 2. Envoi par Webhook HTTP
                self._send_to_webhook(payload)
                
                # 3. Publication sur le serveur MQTT
                self._publish_to_mqtt(payload)
                
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Telemetry Error] Exception in worker thread: {e}")

    def _log_to_file(self, payload: Dict[str, Any]):
        """Ajoute une ligne contenant le JSON à la fin du fichier telemetry_logs.json."""
        try:
            with open("telemetry_logs.json", "a") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as e:
            print(f"[Telemetry Error] Failed to write to telemetry_logs.json: {e}")

    def _send_to_webhook(self, payload: Dict[str, Any]):
        """Envoie les données par une requête HTTP POST vers l'URL Webhook locale."""
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
            # On ne lève pas d'erreur pour éviter d'encombrer la console si le serveur récepteur n'est pas allumé
            self.last_webhook_status = "ERR: Connection Refused"

    def _publish_to_mqtt(self, payload: Dict[str, Any]):
        """Publie le message JSON sur le canal MQTT défini."""
        if self.mqtt_client is None:
            return
            
        try:
            # On vérifie si la connexion avec le serveur MQTT est active
            if self.mqtt_client.is_connected():
                self.mqtt_client.publish(self.mqtt_topic, json.dumps(payload))
                self.last_mqtt_status = "CONNECTED & PUBLISHING"
            else:
                # La reconnexion automatique est gérée par la bibliothèque en tâche de fond
                self.last_mqtt_status = "DISCONNECTED (Retrying...)"
        except Exception as e:
            self.last_mqtt_status = f"ERR: {e}"
