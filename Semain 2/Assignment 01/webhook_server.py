import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Check path
        if self.path == '/webhook':
            # Get content length
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                # Parse JSON
                payload = json.loads(post_data.decode('utf-8'))
                
                # Format print
                print("\n" + "="*50)
                print(f"📡 RECEIVED TELEMETRY - {payload.get('agv_id', 'UNKNOWN')}")
                print(f"  Mission ID : {payload.get('mission_id')}")
                print(f"  State      : {payload.get('state')}")
                print(f"  Battery    : {payload.get('battery_pct')}%")
                print(f"  Speed      : {payload.get('speed_mps')} m/s")
                print(f"  Position   : x={payload.get('position', {}).get('x')}m, "
                      f"y={payload.get('position', {}).get('y')}m, "
                      f"zone={payload.get('position', {}).get('zone')}")
                print(f"  Target Zone: {payload.get('target_zone')}")
                print(f"  Obstacle   : {payload.get('distance_front_cm')} cm")
                print(f"  Motor Temp : {payload.get('temperature_c')} °C")
                print(f"  Network    : {payload.get('connectivity_status')}")
                print("="*50)
                
                # Respond success
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response_data = {"status": "success", "message": "Telemetry received"}
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response_data = {"status": "error", "message": "Invalid JSON format"}
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    # Suppress default server log output in console to keep telemetry output clean
    def log_message(self, format, *args):
        return

def run_server(port=5000):
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, WebhookHandler)
    print(f"🚀 Telemetry Webhook Server running at http://127.0.0.1:{port}/webhook")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Webhook Server...")
        httpd.server_close()

if __name__ == '__main__':
    run_server()
