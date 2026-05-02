import asyncio
import httpx
import json
import uuid

from typing import Dict, Any, Literal, Union
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app.core.setting import setting

import requests
import os

def extract_file(source: str, prefix: Literal["image", "video", "voice"]) -> str:
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        os.makedirs("downloads", exist_ok=True)
        name = Path(parsed.path).stem or "file"
        extension = Path(parsed.path).suffix

        if not extension:
            if prefix == "image":
                extension = ".jpg"
            elif prefix == "video":
                extension = ".mp4"
            elif prefix == "voice":
                extension = ".mp3"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}_{name}{extension}"

        temp_path = os.path.join("downloads", filename)

        with requests.get(source, stream=True) as resp:
            resp.raise_for_status()

            with open(temp_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)

        return temp_path

    elif os.path.exists(source):
        return source

    else:
        raise ValueError("Source harus berupa URL atau path file lokal yang valid")    
    
async def upload_file_kie(source: str, prefix: Literal["image", "video", "voice"] = "image"):
    url = "https://kieai.redpandaai.co/api/file-stream-upload"
    max_attempts = 10
    file_uuid = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    upload_path = None
    downloaded_temp_path = None

    try:
        upload_path = extract_file(source, prefix)
        if upload_path != source:
            downloaded_temp_path = upload_path

        with open(upload_path, "rb") as f:
            file_content = f.read()

        files = {
            "file": ("uploads", file_content)
        }

        if prefix == "image":
            filename = f"{prefix}_{file_uuid}_{timestamp}.jpg"
        elif prefix == "video":
            filename = f"{prefix}_{file_uuid}_{timestamp}.mp4"
        elif prefix == "voice":
            filename = f"{prefix}_{file_uuid}_{timestamp}.mp3"
        else:
            filename = f"{prefix}_{file_uuid}_{timestamp}.jpg"

        payload = {
            "uploadPath": "data",
            "fileName": filename
        }
        headers = {
            "Authorization": f"Bearer {setting.KIE_API_KEY}"
        }

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, data=payload, files=files, headers=headers)
                response.raise_for_status()

                response_json = response.json()
                download_url = response_json.get("data", {}).get("downloadUrl")
                if not download_url:
                    raise ValueError(f"downloadUrl missing in response: {response_json}")

                return download_url

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code if e.response else "unknown"
                print(f"⚠️ KIE upload retry {attempt}/{max_attempts} - HTTP status error ({status_code}): {e}")
            except httpx.RequestError as e:
                print(f"⚠️ KIE upload retry {attempt}/{max_attempts} - network/request error: {e}")
            except (ValueError, KeyError, TypeError) as e:
                print(f"⚠️ KIE upload retry {attempt}/{max_attempts} - parse/response error: {e}")
            except Exception as e:
                print(f"⚠️ KIE upload retry {attempt}/{max_attempts} - unexpected error: {e}")

            if attempt < max_attempts:
                await asyncio.sleep(min(2 ** attempt, 10))

        raise RuntimeError(f"KIE upload failed after {max_attempts} attempts for source: {source}")

    except FileNotFoundError:
        raise RuntimeError(f"File not found: {source}")
    finally:
        if downloaded_temp_path and os.path.exists(downloaded_temp_path):
            try:
                os.remove(downloaded_temp_path)
            except Exception as cleanup_error:
                print(f"⚠️ Failed to remove temp upload file: {downloaded_temp_path} - {cleanup_error}")