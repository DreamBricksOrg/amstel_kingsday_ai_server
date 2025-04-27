import os
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, render_template, redirect, url_for, jsonify
from werkzeug.exceptions import BadRequestKeyError
from concurrent.futures import ThreadPoolExecutor
from flask_cors import CORS
import time
import uuid
import logging

#from comfyui_api import ComfyUiAPI
from comfyui_api_aws import ComfyUiAPI

import parameters as param
from utils import generate_timestamped_filename, count_files_with_extension, count_files_by_hour, generate_file_activity_plot_base64, read_last_n_lines

# Configure logging to write to a file and to the std output
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create a file handler and set its format and level
log_filename = generate_timestamped_filename("logs", param.LOG_FILENAME_PREFIX, "log")
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Create a stream handler and set its format and level
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


logger = logging.getLogger(__name__)


app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = 'static/inputs'
app.config['OUTPUT_FOLDER'] = 'static/outputs'

executor = ThreadPoolExecutor()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

api = ComfyUiAPI(
    server_address=param.COMFYUI_API_SERVER,
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
    is_king = True
    gender_choice = "king"
    try:
        gender_choice = request.form['choice']
        is_king = gender_choice == "king"
    except BadRequestKeyError as e:
        logger.warning("No gender choice sent. Using King")

    if file.filename == '':
        logger.info(f"Invalid filename: '{file.filename}'.")
        return jsonify({'error': 'Nome de arquivo inválido'}), 400

    filename = generate_timestamped_filename(app.config['UPLOAD_FOLDER'], f"kingsday_in_{str(uuid.uuid4())}", "jpg")
    logger.info(f"Request to generate a {gender_choice} with image '{filename}'.")

    # input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filename)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result_path = loop.run_until_complete(run_async_process(filename, is_king))

    relative_path = os.path.relpath(result_path, 'static').replace("\\", "/")
    image_url = f'/static/{relative_path}'

    logger.info(f"Finished to generate a {gender_choice} with image '{file.filename}'.")
    return jsonify({'message': 'Imagem processada com sucesso', 'image_url': image_url}), 200


@app.route('/stats')
def stats():
    OUTPUT_DIR = "static/outputs"
    total_files = count_files_with_extension(OUTPUT_DIR, "png")
    activity = count_files_by_hour(OUTPUT_DIR)
    graph_base64 = generate_file_activity_plot_base64(activity, style="plot")
    last_log_lines = read_last_n_lines(log_filename, 100)

    return render_template('stats.html',
                           total_files=total_files,
                           graph_base64=graph_base64,
                           log_text=last_log_lines)


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
    logger.info("Application started (logging to file).")
    app.run(debug=True, host='0.0.0.0', port=param.SERVER_PORT)

