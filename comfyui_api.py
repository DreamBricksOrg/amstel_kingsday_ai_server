#This is an example that uses the websockets api to know when a prompt execution is done
#Once the prompt execution is done it downloads the images using the /history endpoint

import websocket #NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import requests
import uuid
import json
import urllib.request
import urllib.parse
import random
from PIL import Image
import io
import os
from utils import generate_timestamped_filename

#server_address = "127.0.0.1:7821"

class ComfyUiAPI:
    def __init__(self, server_address, img_temp_folder, workflow_path, node_id_ksampler, node_id_image_load):
        self.server_address = server_address
        self.img_temp_folder = img_temp_folder
        self.workflow_path = workflow_path
        self.node_id_ksampler = node_id_ksampler
        self.node_id_image_load = node_id_image_load
        self.client_id = str(uuid.uuid4())


    def queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req =  urllib.request.Request("http://{}/prompt".format(self.server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(self.server_address, url_values)) as response:
            return response.read()

    def get_history(self, prompt_id):
        with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, prompt_id)) as response:
            return json.loads(response.read())

    def get_images(self, ws, prompt):
        prompt_id = self.queue_prompt(prompt)['prompt_id']
        output_images = {}
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break #Execution is done
            else:
                # If you want to be able to decode the binary stream for latent previews, here is how you can do it:
                # bytesIO = BytesIO(out[8:])
                # preview_image = Image.open(bytesIO) # This is your preview in PIL image format, store it in a global
                continue #previews are binary data

        history = self.get_history(prompt_id)[prompt_id]
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            images_output = []
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output

        return output_images


    def upload_file(self, file, subfolder="", overwrite=False):
        path = None
        try:
            # Wrap file in formdata so it includes filename
            body = {"image": file}
            data = {}

            if overwrite:
                data["overwrite"] = "true"

            if subfolder:
                data["subfolder"] = subfolder

            resp = requests.post(f"http://{self.server_address}/upload/image", files=body, data=data)

            if resp.status_code == 200:
                data = resp.json()
                # Add the file to the dropdown list and update the widget value
                path = data["name"]
                if "subfolder" in data:
                    if data["subfolder"] != "":
                        path = data["subfolder"] + "/" + path


            else:
                print(f"{resp.status_code} - {resp.reason}")
        except Exception as error:
            print(error)
        return path


    def save_image(self, images):
        for node_id in images:
            for i, image_data in enumerate(images[node_id]):
                image = Image.open(io.BytesIO(image_data))
                #image.show()
                #image_filename = os.path.join(self.img_temp_folder, f"{node_id}-{i}.png")
                image_filename = generate_timestamped_filename(self.img_temp_folder, "orfeu", "png")
                image.save(image_filename)

                return image_filename


    def generate_image(self, image_path):
        # upload an image
        with open(image_path, "rb") as f:
            comfyui_path_image = self.upload_file(f, "", True)

        # load workflow from file
        with open(self.workflow_path, "r", encoding="utf-8") as f:
            workflow_data = f.read()

        prompt = json.loads(workflow_data)

        #set the text prompt for our positive CLIPTextEncode
        #prompt["6"]["inputs"]["text"] = "masterpiece, man, van gogh, impressionism"

        #set the seed for our KSampler node
        seed = random.randint(1, 1000000000)
        #prompt[self.node_id_ksampler]["inputs"]["seed"] = seed

        # set the image name for our LoadImage node
        prompt[self.node_id_image_load]["inputs"]["image"] = comfyui_path_image

        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(self.server_address, self.client_id))
        images = self.get_images(ws, prompt)
        ws.close() # for in case this example is used in an environment where it will be repeatedly called, like in a Gradio app. otherwise, you'll randomly receive connection timeouts

        image_path = self.save_image(images)

        return image_path


if __name__ == '__main__':
    #workflow_path = r"C:\Users\DB\Downloads\basic2_api.json"
    test_workflow_path = r"C:\Users\DB\Downloads\orfeu_config_api_v06.json"
    test_image_path = r"C:\Users\DB\Downloads\dudu.jpg"
    #test_comfyui_api(workflow_path, image_path)
    import parameters as param
    import datetime
    start = datetime.datetime.now()
    api = ComfyUiAPI(param.STABLE_SWARM_API_SERVER, param.IMAGE_TEMP_FOLDER, param.WORKFLOW_PATH, param.WORKFLOW_NODE_ID_KSAMPLER, param.WORKFLOW_NODE_ID_IMAGE_LOAD)
    print(api.generate_image(test_image_path))
    duration = datetime.datetime.now() - start
    print(f"duration: {duration.total_seconds()} seconds")
