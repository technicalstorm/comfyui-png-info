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
    CATEGORY = "pnginfo"
    OUTPUT_NODE = True

    def extract(self, image=None):
        # We still keep this for standard Comfy runs, but it will 
        # usually find the file already gone if triggered by on_change.
        text = self.get_metadata(image)
        return {"ui": {"text": [text]}, "result": (text,)}

    def get_metadata(self, image, delete_after=False):
        if not image:
            return "No image selected."
            
        try:
            full_path = folder_paths.get_annotated_filepath(image)
        except Exception:
            return f"Invalid path: {image}"

        if not os.path.exists(full_path):
            return "File already processed and removed."

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
            
            # Parse the data
            result_text = ""
            if raw:
                try:
                    data = json.loads(raw)
                    result_text = self._parse_comfy_json(data)
                except:
                    result_text = raw
            else:
                result_text = "No metadata found."

            # DELETE ON CHANGE LOGIC:
            if delete_after:
                img.close() # Ensure file handle is released before deletion
                try:
                    os.remove(full_path)
                except Exception as e:
                    print(f"[pnginfo] Cleanup failed: {e}")

            return result_text

        except Exception as e:
            return f"Error: {str(e)}"

    def _parse_comfy_json(self, data):
        prompts = []
        loras = []
        models = []
        seed = steps = cfg = scheduler = sampler = "?"
        width = height = "?"
        nodes = data if "class_type" in str(data) else data.get("prompt", data)

        for node_id, node in nodes.items():
            ctype = node.get("class_type", "")
            inputs = node.get("inputs", {})
            if "CLIPTextEncode" in ctype:
                text = inputs.get("text", "")
                if text and text.strip(): prompts.append(text.strip())
            elif "Sampler" in ctype:
                seed = inputs.get("seed") or inputs.get("noise_seed") or seed
                steps = inputs.get("steps", steps)
                cfg = inputs.get("cfg", cfg)
                sampler = inputs.get("sampler_name", sampler)
                scheduler = inputs.get("scheduler", scheduler)
            elif "CheckpointLoader" in ctype:
                models.append(os.path.basename(str(inputs.get("ckpt_name", ""))))
            elif "LoraLoader" in ctype:
                l_name = os.path.basename(str(inputs.get("lora_name", "")))
                loras.append(l_name)
            elif ctype in ["EmptyLatentImage", "EmptyImage"]:
                width = inputs.get("width", width)
                height = inputs.get("height", height)

        output = []
        for i, p in enumerate(prompts):
            label = "✅ Positive" if i == 0 else "❌ Negative"
            if any(x in p.lower()[:30] for x in ["bad", "embedding:", "worst"]): label = "❌ Negative"
            output.append(f"{label}: {p}")
        if models: output.append(f"📦 Model: {models[0]}")
        if loras: output.append(f"🎨 LoRAs: {', '.join(loras)}")
        output.append("-" * 30)
        output.append(f"⚙️ {width}x{height} | Seed: {seed} | Steps: {steps} | CFG: {cfg}")
        return "\n\n".join(output)

@PromptServer.instance.routes.post("/pnginfo/fetch_metadata")
async def fetch_metadata_api(request):
    data = await request.json()
    image_name = data.get("image")
    node_id = data.get("node_id")
    
    instance = pnginfo()
    # Pass True to trigger the immediate deletion
    text = instance.get_metadata(image_name, delete_after=True)
    
    PromptServer.instance.send_sync("pnginfo-metadata-update", {"node_id": node_id, "text": text})
    return web.Response(status=200)

NODE_CLASS_MAPPINGS = {"pnginfo": pnginfo}