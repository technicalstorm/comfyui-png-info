import os
import json
import folder_paths
from PIL import Image
import piexif
import piexif.helper
from server import PromptServer
from aiohttp import web

WEB_DIRECTORY = "."

class pnginfo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # We use a simple list here. Using 'image_upload' in the JS 
                # will still allow drag-and-drop, but this stops the 'Red Node' 
                # validation error because we aren't using the strict Image type.
                "image": ([], {}), 
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "extract"
    CATEGORY = "pnginfo"
    OUTPUT_NODE = True

    def extract(self, image=None):
        # Fail gracefully without turning the node red
        if not image:
            return {"ui": {"text": ["No image selected."]}, "result": ("No image selected.",)}
        
        text = self.get_metadata(image)
        return {"ui": {"text": [text]}, "result": (text,)}

    def get_metadata(self, image, delete_after=False):
        if not image:
            return "No image selected."
            
        # Manually find the path since we bypassed the automatic validation
        # Check input directory
        input_dir = folder_paths.get_input_directory()
        full_path = os.path.join(input_dir, image)

        if not os.path.exists(full_path):
            return "File already processed and removed from input folder."

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
            
            result_text = self._parse_metadata(raw) if raw else "No metadata found."

            if delete_after:
                img.close()
                try:
                    os.remove(full_path)
                except Exception as e:
                    print(f"[pnginfo] Cleanup failed: {e}")

            return result_text
        except Exception as e:
            return f"Error: {str(e)}"

    def _parse_metadata(self, raw):
        try:
            data = json.loads(raw)
            prompts = []
            seed = steps = cfg = sampler = scheduler = "?"
            width = height = "?"
            
            nodes = data if "class_type" in str(data) else data.get("prompt", data)
            for node in nodes.values():
                ctype = node.get("class_type", "")
                inputs = node.get("inputs", {})
                if "CLIPTextEncode" in ctype:
                    txt = inputs.get("text", "")
                    if txt: prompts.append(txt)
                elif "Sampler" in ctype:
                    seed = inputs.get("seed") or inputs.get("noise_seed") or seed
                    steps = inputs.get("steps", steps)
                    cfg = inputs.get("cfg", cfg)
                    sampler = inputs.get("sampler_name", sampler)
                    scheduler = inputs.get("scheduler", scheduler)
                elif ctype in ["EmptyLatentImage", "EmptyImage"]:
                    width, height = inputs.get("width", width), inputs.get("height", height)

            output = []
            for i, p in enumerate(prompts):
                label = "❌ Negative" if any(x in p.lower()[:30] for x in ["bad", "lowres", "text"]) else "✅ Positive"
                output.append(f"{label}: {p}")
            output.append("-" * 30)
            output.append(f"⚙️ {width}x{height} | Seed: {seed} | Steps: {steps} | CFG: {cfg} | {sampler}/{scheduler}")
            return "\n\n".join(output)
        except:
            return raw

@PromptServer.instance.routes.post("/pnginfo/fetch_metadata")
async def fetch_metadata_api(request):
    data = await request.json()
    image_name = data.get("image")
    node_id = data.get("node_id")
    instance = pnginfo()
    text = instance.get_metadata(image_name, delete_after=True)
    PromptServer.instance.send_sync("pnginfo-metadata-update", {"node_id": node_id, "text": text})
    return web.Response(status=200)

NODE_CLASS_MAPPINGS = {"pnginfo": pnginfo}