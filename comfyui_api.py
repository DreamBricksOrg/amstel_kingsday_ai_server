import websocket
import requests
import uuid
import json
import urllib.request
import urllib.parse
import random
import datetime
from PIL import Image
import io
import os
import copy
from utils import generate_timestamped_filename


class ComfyUiAPI:
    def __init__(self, server_address, img_temp_folder, workflow_path, node_id_ksampler, node_id_image_load):
        self.server_address = server_address
        self.img_temp_folder = img_temp_folder
        self.node_id_ksampler = node_id_ksampler
        self.node_id_image_load = node_id_image_load
        self.session = requests.Session()  # conexão HTTP reutilizável

        # Carrega workflow uma vez e usa cópia depois
        with open(workflow_path, "r", encoding="utf-8") as f:
            self.workflow_template = json.load(f)

    def queue_prompt(self, prompt: dict, client_id: str) -> dict:
        payload = {"prompt": prompt, "client_id": client_id}
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())

    def get_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        params = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
        with urllib.request.urlopen(f"http://{self.server_address}/view?{params}") as response:
            return response.read()

    def get_history(self, prompt_id: str) -> dict:
        with urllib.request.urlopen(f"http://{self.server_address}/history/{prompt_id}") as response:
            return json.loads(response.read())

    def get_images(self, ws, prompt: dict, client_id: str) -> dict:
        prompt_id = self.queue_prompt(prompt, client_id)['prompt_id']
        output_images = {}

        while True:
            message_raw = ws.recv()
            if isinstance(message_raw, str):
                message = json.loads(message_raw)
                if message['type'] == 'executing':
                    data = message['data']
                    print("Executing...")
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break
            else:
                continue  # skip previews (binary)

        history_data = self.get_history(prompt_id)[prompt_id]
        for node_id, node_output in history_data['outputs'].items():
            if 'images' in node_output:
                output_images[node_id] = [
                    self.get_image(img['filename'], img['subfolder'], img['type'])
                    for img in node_output['images']
                ]

        return output_images

    def upload_file(self, file, subfolder: str = "", overwrite: bool = False) -> str:
        try:
            files = {"image": file}
            data = {"overwrite": "true"} if overwrite else {}

            if subfolder:
                data["subfolder"] = subfolder

            response = self.session.post(f"http://{self.server_address}/upload/image", files=files, data=data)

            if response.status_code == 200:
                response_data = response.json()
                path = response_data["name"]
                if response_data.get("subfolder"):
                    path = f"{response_data['subfolder']}/{path}"
                return path
            else:
                print(f"[Upload Error] {response.status_code} - {response.reason}")
                return None
        except Exception as e:
            print(f"[Upload Exception] {e}")
            return None

    def save_image(self, images: dict) -> str:
        for node_id, image_list in images.items():
            for image_data in image_list:
                image = Image.open(io.BytesIO(image_data))
                image_filename = generate_timestamped_filename(self.img_temp_folder, "kingsday", "png")
                image.save(image_filename, optimize=True)
                return image_filename  # Retorna apenas a primeira imagem

    def generate_image(self, image_path: str) -> str:
        timing = {}
        client_id = str(uuid.uuid4())  # Garante isolamento por requisição

        start_time = datetime.datetime.now()
        with open(image_path, "rb") as f:
            comfyui_path_image = self.upload_file(f, "", True)
        timing["upload"] = datetime.datetime.now()

        prompt = copy.deepcopy(self.workflow_template)
        prompt[self.node_id_ksampler]["inputs"]["seed"] = random.randint(1, 1_000_000_000)
        prompt[self.node_id_image_load]["inputs"]["image"] = comfyui_path_image

        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={client_id}")
        timing["start_execution"] = datetime.datetime.now()

        images = self.get_images(ws, prompt, client_id)
        timing["execution_done"] = datetime.datetime.now()
        ws.close()

        image_file_path = self.save_image(images)
        timing["save"] = datetime.datetime.now()

        print("[Timing Info]")
        print(f"Upload time:        {(timing['upload'] - start_time).total_seconds()}s")
        print(f"Execution wait:     {(timing['start_execution'] - timing['upload']).total_seconds()}s")
        print(f"Processing time:    {(timing['execution_done'] - timing['start_execution']).total_seconds()}s")
        print(f"Saving time:        {(timing['save'] - timing['execution_done']).total_seconds()}s")
        print(f"Total:              {(timing['save'] - start_time).total_seconds()}s")

        return image_file_path
