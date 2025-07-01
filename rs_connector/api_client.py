import os
import requests


class APIClient:
    def __init__(self, api_url=None, robot_id=None):
        self.api_url = api_url or "https://robotstreamer.com/api/robot"
        self.robot_id = robot_id

    def post_status(self, status):
        if not self.robot_id:
            print("[APIClient] No robot_id set, skipping post_status.")
            return
        url = f"{self.api_url}/{self.robot_id}/status"
        try:
            resp = requests.post(url, json=status)
            print(f"[APIClient] Status post: {resp.status_code}")
        except Exception as e:
            print(f"[APIClient] Error posting status: {e}")

    def get_commands(self):
        if not self.robot_id:
            print("[APIClient] No robot_id set, skipping get_commands.")
            return []
        url = f"{self.api_url}/{self.robot_id}/commands"
        try:
            resp = requests.get(url)
            if resp.ok:
                return resp.json()
        except Exception as e:
            print(f"[APIClient] Error getting commands: {e}")
        return []
