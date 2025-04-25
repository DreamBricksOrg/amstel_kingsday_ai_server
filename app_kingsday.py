import os
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, render_template, redirect, url_for, jsonify
from comfyui_api import ComfyUiAPI
import parameters as param
from werkzeug.utils import secure_filename
from concurrent.futures import ThreadPoolExecutor
from flask_cors import CORS
import shutil
import time
import uuid

from utils import generate_timestamped_filename

app = Flask(__name__)
CORS(app)
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
    node_id_image_load=param.WORKFLOW_NODE_ID_IMAGE_LOAD,
    node_id_text_input=param.WORKFLOW_NODE_ID_TEXT_INPUT
)

def process_image(image_path, is_king):
    return api.generate_image(image_path, is_king=is_king)

@app.route('/', methods=['GET'])
def index():
    image_url = request.args.get('image_url')
    return render_template("index.html", image_url=image_url)

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'image' not in request.files:
        return jsonify({'error': 'Nenhuma imagem enviada'}), 400

    file = request.files['image']
    gender_choice = request.form['choice']
    print(choice)
    is_king = gender_choice == "king"

    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo inválido'}), 400

    filename = generate_timestamped_filename(app.config['UPLOAD_FOLDER'], f"kingsday_in_{str(uuid.uuid4())}", "jpg")

    # input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filename)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result_path = loop.run_until_complete(run_async_process(filename, is_king))

    relative_path = os.path.relpath(result_path, 'static').replace("\\", "/")
    image_url = f'/static/{relative_path}'

    return jsonify({'message': 'Imagem processada com sucesso', 'image_url': image_url}), 200

async def run_async_process(image_path, is_king):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, process_image, image_path, is_king)


def remove_old_files(minutes=10):
    directories = ['static/outputs', 'static/inputs']
    current_time = time.time()

    for directory in directories:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)

                if os.path.isfile(file_path):
                    creation_time = os.path.getctime(file_path)
                    time_difference = (current_time - creation_time) / 60

                    if time_difference > minutes:
                        os.remove(file_path)
                        print(f'O arquivo "{filename}" foi excluído de "{directory}".')
                    else:
                        print(f'O arquivo "{filename}" em "{directory}" foi criado há menos de {minutes} minutos.')
        else:
            print(f'O diretório "{directory}" não existe.')


# scheduler = BackgroundScheduler()
# scheduler.add_job(remove_old_files, 'interval', minutes=15)
# scheduler.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
