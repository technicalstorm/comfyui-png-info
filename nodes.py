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
        # Graceful failure if image is None or empty
        if image is None or image == "":
            return {"ui": {"text": ["No image selected."]}, "result": ("No image selected.",)}
            
        text = self.get_metadata(image)
        return {"ui": {"text": [text]}, "result": (text,)}

    def get_metadata(self, image):
        if not image:
            return "No image selected."
            
        try:
            full_path = folder_paths.get_annotated_filepath(image)
        except Exception:
            return f"Invalid path: {image}"

        if not os.path.exists(full_path):
            return "File not found. It may have been deleted or moved."

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
                    data = json.loads(raw)
                    return self._parse_comfy_json(data)
                except:
                    return raw
            return "No metadata found in this image."
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def _parse_comfy_json(self, data):
        prompts = []
        loras = []
        models = []
        seed = steps = cfg = scheduler = sampler = "?"
        width = height = "?"

        # Handle both raw prompt dicts and full workflow exports
        nodes = data if "class_type" in str(data) else data.get("prompt", data)

        for node_id, node in nodes.items():
            ctype = node.get("class_type", "")
            inputs = node.get("inputs", {})

            if "CLIPTextEncode" in ctype:
                text = inputs.get("text", "")
                if text and text.strip():
                    prompts.append(text.strip())

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
                l_strength = inputs.get("strength_model", "1.0")
                loras.append(f"{l_name} ({l_strength})")

            elif ctype in ["EmptyLatentImage", "EmptyImage", "UpscaleLatent", "UpscaleImage"]:
                width = inputs.get("width", width)
                height = inputs.get("height", height)

        output = []
        if models: output.append(f"📦 Model: {', '.join(models)}")
        
        for i, p in enumerate(prompts):
            # Basic logic to guess positive/negative
            label = "✅ Positive" if i == 0 else f"❌ Negative ({i})"
            low_p = p.lower()
            if any(x in low_p[:30] for x in ["bad", "embedding:", "worst", "low quality"]):
                label = "❌ Negative"
            output.append(f"{label}: {p}")

        if loras: output.append(f"🎨 LoRAs: {', '.join(loras)}")
        
        output.append("-" * 30)
        output.append(f"⚙️ Resolution: {width} x {height}")
        output.append(f"🎲 Seed: {seed}")
        output.append(f"🚀 Steps: {steps} | CFG: {cfg}")
        output.append(f"⏲ Sampler: {sampler} | Scheduler: {scheduler}")
        
        return "\n\n".join(output)

@PromptServer.instance.routes.post("/pnginfo/fetch_metadata")
async def fetch_metadata_api(request):
    try:
        data = await request.json()
        image_name = data.get("image")
        node_id = data.get("node_id")
        
        instance = pnginfo()
        text = instance.get_metadata(image_name)
        
        PromptServer.instance.send_sync("pnginfo-metadata-update", {"node_id": node_id, "text": text})
        return web.Response(status=200)
    except Exception as e:
        return web.Response(status=500, text=str(e))

NODE_CLASS_MAPPINGS = {"pnginfo": pnginfo}