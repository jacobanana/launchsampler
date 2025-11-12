import mido
import threading
import time

class PortMonitor:
    def __init__(self, port_name):
        self.port_name = port_name
        self.running = True
        self.thread = None

    def start(self):
        """Start the monitoring thread"""
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)  # Wait up to 1 second for thread to finish

    def _monitor(self):
        """Monitor MIDI messages from the port"""
        try:
            with mido.open_input(self.port_name) as inport:
                print(f"Started monitoring port: {self.port_name}")
                while self.running:
                    # Check for messages with a timeout to allow stopping
                    try:
                        for msg in inport.iter_pending():
                            if not self.running:
                                break
                            # Filter out MIDI clock messages (type 'clock')
                            if msg.type != 'clock':
                                print(f"[{self.port_name}] {msg}")
                        time.sleep(0.01)  # Small delay to prevent busy waiting
                    except:
                        break
        except Exception as e:
            print(f"Error monitoring port {self.port_name}: {e}")
        finally:
            print(f"Stopped monitoring port: {self.port_name}")

def main():
    print("MIDI Monitor - Press Ctrl+C to exit")
    print("Checking for MIDI ports every 5 seconds...")

    # Dictionary to track active port monitors
    active_monitors = {}

    try:
        while True:
            # Get current available input ports
            current_ports = set(mido.get_input_names())
            active_ports = set(active_monitors.keys())

            # Find new ports to start monitoring
            new_ports = current_ports - active_ports
            for port_name in new_ports:
                print(f"New port detected: {port_name}")
                monitor = PortMonitor(port_name)
                monitor.start()
                active_monitors[port_name] = monitor

            # Find removed ports to stop monitoring
            removed_ports = active_ports - current_ports
            for port_name in removed_ports:
                print(f"Port removed: {port_name}")
                active_monitors[port_name].stop()
                del active_monitors[port_name]

            # Wait 5 seconds before next check
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nExiting MIDI monitor...")
        # Stop all active monitors
        for monitor in active_monitors.values():
            monitor.stop()

if __name__ == "__main__":
    main()
