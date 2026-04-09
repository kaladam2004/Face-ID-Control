import subprocess
import threading
import json
import re
import time
import logging
import shlex

logger = logging.getLogger(__name__)


class DahuaListener:
    def __init__(self, name, curl_cmd, callback=None, reconnect_delay=10):
        self.name = name
        self.curl_cmd = curl_cmd
        self.callback = callback
        self.reconnect_delay = reconnect_delay
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()
        logger.info(f"Started listener for {self.name}")

    def stop(self):
        self.running = False

    def _run(self):
        while self.running:
            try:
                logger.info(f"[{self.name}] Starting curl listener...")

                process = subprocess.Popen(
                    shlex.split(self.curl_cmd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                logger.info(f"[{self.name}] Connected!")

                block = []

                for line in process.stdout:
                    if not self.running:
                        break

                    line = line.strip()

                    if "--myboundary" in line:
                        if block:
                            self._process_block("\n".join(block))
                            block = []
                        continue

                    block.append(line)

                logger.warning(f"[{self.name}] Disconnected. Reconnecting...")
                time.sleep(self.reconnect_delay)

            except Exception as e:
                logger.exception(f"[{self.name}] Error: {e}")
                time.sleep(self.reconnect_delay)

    def _process_block(self, text):
        if "Code=_DoorFace_" not in text:
            return

        m = re.search(r"data=(\{.*\})", text, re.DOTALL)
        if not m:
            return

        try:
            data = json.loads(m.group(1))
        except:
            return

        event = {
            "source": self.name,
            "user_id": str(data.get("UserID", "")),
            "similarity": data.get("Similarity", 0),
            "alive": data.get("Alive", 0),
            "real_utc": data.get("RealUTC", 0),
            "door": data.get("Door", 0),
            "open_method": data.get("OpenDoorMethod", 0),
        }

        logger.info(f"[{self.name}] FACE EVENT: {event['user_id']}")

        if self.callback:
            self.callback(event)