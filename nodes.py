import os
import json
import folder_paths
from PIL import Image
import piexif
import piexif.helper
from server import PromptServer
from aiohttp import web

# We point this to the current directory so ComfyUI finds a .js file if we put one there,
# but for maximum simplicity, you can keep the .js in the same folder as nodes.py.
WEB_DIRECTORY = "."

class MetadataDisplay:
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        return {
            "required": {
                "image": (sorted(files), {"image_upload": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "extract"
    CATEGORY = "WLSH Nodes"
    OUTPUT_NODE = True

    def extract(self, image):
        text = self.get_metadata(image)
        return {"ui": {"text": [text]}, "result": (text,)}

    def get_metadata(self, image):
        full_path = folder_paths.get_annotated_filepath(image)
        if not os.path.exists(full_path):
            return "File not found."
        try:
            img = Image.open(full_path)
            raw = ""
            if full_path.lower().endswith((".png", ".webp")):
                raw = img.info.get("parameters") or img.info.get("prompt") or ""
            elif full_path.lower().endswith((".jpg", ".jpeg")):
                exif = img.info.get("exif")
                if exif:
                    exif_dict = piexif.load(exif)
                    uc = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment)
                    if uc: raw = piexif.helper.UserComment.load(uc)
            
            if raw:
                try:
                    return self._parse_comfy_json(json.loads(raw))
                except:
                    return raw
            return "No metadata found."
        except Exception as e:
            return f"Error: {str(e)}"

    def _parse_comfy_json(self, data):
        positive = ""
        negative = ""
        loras = []
        for node in data.values():
            ctype = node.get("class_type", "")
            inputs = node.get("inputs", {})
            if "CLIPTextEncode" in ctype:
                txt = inputs.get("text", "")
                if not positive: positive = txt
                else: negative = txt
            elif "LoraLoader" in ctype:
                loras.append(os.path.basename(str(inputs.get("lora_name", ""))))
        
        return f"PROMPT: {positive}\n\nNEGATIVE: {negative}\n\nLORAS: {', '.join(loras)}"

@PromptServer.instance.routes.post("/wlsh/fetch_metadata")
async def fetch_metadata_api(request):
    data = await request.json()
    image_name = data.get("image")
    node_id = data.get("node_id")
    instance = MetadataDisplay()
    text = instance.get_metadata(image_name)
    PromptServer.instance.send_sync("wlsh-metadata-update", {"node_id": node_id, "text": text})
    return web.Response(status=200)

PNGInfo