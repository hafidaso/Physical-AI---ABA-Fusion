import time
import threading
import tkinter as tk
from tkinter import messagebox
import paho.mqtt.client as mqtt

# --- Configuration MQTT (HiveMQ Cloud) ---
MQTT_HOST = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1775653497883"
MQTT_PASS = "1B%.CwaP:Kdr2I93k*Ap"
MQTT_TOPIC = "robot/control"

TIME_FOR_3_35M = 3.0  # Travel time (3 seconds)
TIME_FOR_90_TURN = 2.2  # Turn time (2.2 seconds)

is_running = False

def execute_square():
    global is_running
    is_running = True
    update_status("🤖 الروبوت في حركة: جاري تنفيذ المربع...", "orange")
    btn_start.config(state=tk.DISABLED) # نوقفو الزر حتى يسالي

    try:
        for side in range(1, 5):
            if not is_running: break
            
            # 1. المضي قُدمًا لقطع 3.35 متر
            update_status(f"🚀 الضلع {side}/4: كيزيد لقبلت (لمدة {TIME_FOR_3_35M}s)", "green")
            client.publish(MQTT_TOPIC, "FORWARD")
            time.sleep(TIME_FOR_3_35M)
            
            if not is_running: break
            
            # 2. الدوران بـ 90 درجة لمدة ثانية واحدة
            update_status(f"🔄 الشوكة {side}/4: كيدور لـ ليمن (لمدة {TIME_FOR_90_TURN}s)", "blue")
            client.publish(MQTT_TOPIC, "RIGHT") # أو "LEFT" على حساب فين بغيتيه يدور
            time.sleep(TIME_FOR_90_TURN)

        # نهاية المسار
        client.publish(MQTT_TOPIC, "STOP")
        update_status("✅ تم إكمال المربع بنجاح والروبوت واقف!", "darkgreen")

    except Exception as e:
        print(f"Erreur: {e}")
        
    finally:
        is_running = False
        btn_start.config(state=tk.NORMAL)

def start_sequence():
    if not is_running:
        # تشغيل في الخلفية لضمان سلاسة الواجهة
        t = threading.Thread(target=execute_square)
        t.daemon = True
        t.start()

def stop_emergency():
    global is_running
    is_running = False
    client.publish(MQTT_TOPIC, "STOP")
    update_status("🛑 توقف اضطراري! الروبوت محبوس.", "red")

def update_status(text, color):
    lbl_status.config(text=text, fg=color)

# --- الاتصال بـ MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set()

try:
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()
except Exception as e:
    messagebox.showerror("Connection Error", f"لم نتمكن من الاتصال بـ MQTT:\n{e}")

# --- إعداد واجهة المستخدم (GUI) ---
root = tk.Tk()
root.title("Télécommande Robot MQTT")
root.geometry("450x300")
root.configure(bg="#f0f0f0")

# العنوان
lbl_title = tk.Label(root, text="لوحة التحكم في مسار الروبوت", font=("Helvetica", 14, "bold"), bg="#f0f0f0")
lbl_title.pack(pady=15)

# زر البدء (START)
btn_start = tk.Button(root, text="▶ START (إبدأ المربع)", font=("Helvetica", 12, "bold"), 
                      bg="#2ecc71", fg="white", width=22, height=2, command=start_sequence)
btn_start.pack(pady=10)

# زر التوقف الإضطراري (STOP)
btn_stop = tk.Button(root, text="🛑 STOP إيقاف عاجل", font=("Helvetica", 12, "bold"), 
                     bg="#e74c3c", fg="white", width=22, height=1, command=stop_emergency)
btn_stop.pack(pady=5)

# خانة الحالة الإخبارية
lbl_status = tk.Label(root, text="💤 الروبوت مستعد وفي انتظار الضغط على Start...", 
                      font=("Helvetica", 11, "italic"), fg="gray", bg="#f0f0f0", wraplength=400)
lbl_status.pack(pady=25)

# عند إغلاق النافذة
def on_closing():
    stop_emergency()
    client.loop_stop()
    client.disconnect()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
