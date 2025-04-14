import os
from datetime import datetime
import zipfile
import io

def create_zip_of_images(folder_path):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:

        for root, dirs, files in os.walk(folder_path):
            for file in files:

                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    file_path = os.path.join(root, file)
                    zip_file.write(file_path, os.path.relpath(file_path, folder_path))

    zip_buffer.seek(0)

    return zip_buffer


def generate_timestamped_filename(base_folder: str, prefix: str, extension: str) -> str:
    """
    Generates a filename with the current timestamp in the format:
    {prefix}_YYYYMMDD_HHMMSS.{extension}

    Parameters:
    - base_folder (str): The folder where the file should be saved.
    - prefix (str): The prefix for the filename.
    - extension (str): The file extension (without the dot).

    Returns:
    - str: The full file path with the formatted filename.
    """
    # Get current date and time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Construct the filename
    filename = f"{prefix}_{timestamp}.{extension}"

    # Return the full path
    return os.path.join(base_folder, filename)