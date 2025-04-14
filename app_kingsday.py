import os
import asyncio
from flask import Flask, request, render_template, redirect, url_for
from comfyui_api import ComfyUiAPI
import parameters as param
from werkzeug.utils import secure_filename
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/inputs'
app.config['OUTPUT_FOLDER'] = 'static/outputs'

executor = ThreadPoolExecutor()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

api = ComfyUiAPI(
    server_address=param.STABLE_SWARM_API_SERVER,
    img_temp_folder=app.config['OUTPUT_FOLDER'],
    workflow_path=param.WORKFLOW_PATH,
    node_id_ksampler=param.WORKFLOW_NODE_ID_KSAMPLER,
    node_id_image_load=param.WORKFLOW_NODE_ID_IMAGE_LOAD
)

def process_image(image_path):
    return api.generate_image(image_path)

@app.route('/', methods=['GET'])
def index():
    image_url = request.args.get('image_url')
    return render_template("index.html", image_url=image_url)

@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return "Nenhuma imagem enviada", 400

    file = request.files['image']
    if file.filename == '':
        return "Nome de arquivo inválido", 400

    filename = secure_filename(file.filename)
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(input_path)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result_path = loop.run_until_complete(run_async_process(input_path))

    relative_path = os.path.relpath(result_path, 'static').replace("\\", "/")
    return redirect(url_for('index', image_url=relative_path))

async def run_async_process(image_path):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, process_image, image_path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
