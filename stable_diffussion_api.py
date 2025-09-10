import os
import base64
import requests

class StableDiffusionClient:
    def __init__(self, host="http://localhost:3014", portrait_dir="./portraits", background_dir="./backgrounds"):
        self.api_url = f"{host}/sdapi/v1/txt2img"
        self.portrait_dir = portrait_dir
        self.background_dir = background_dir

        # Ensure directories exist
        os.makedirs(self.portrait_dir, exist_ok=True)
        os.makedirs(self.background_dir, exist_ok=True)

    def _load_prompt(self, filename: str) -> str:
        """Load prompt text from file."""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Prompt file not found: {filename}")
        with open(filename, "r", encoding="utf-8") as f:
            return f.read().strip()

    def _generate_image(self, prompt: str, width: int, height: int, output_dir: str, prefix: str = "img"):
        """Send generation request to Stable Diffusion API and save the result."""
        payload = {
            "prompt": prompt,
            "steps": 50,
            "cfg_scale": 7,
            "width": width,
            "height": height,
            "sampler_index": "Euler",
            "send_images": True
        }

        response = requests.post(self.api_url, json=payload)
        response.raise_for_status()
        r = response.json()

        for i, img_str in enumerate(r.get("images", [])):
            image_data = base64.b64decode(img_str)
            filename = os.path.join(output_dir, f"{prefix}_{i}.png")
            with open(filename, "wb") as f:
                f.write(image_data)
            print(f"✅ Saved: {filename}")

    def generate_portrait(self, prompt_file="prompt_portraits.txt"):
        """Generate portrait (512x512)."""
        prompt = self._load_prompt(prompt_file)
        self._generate_image(prompt, width=512, height=512, output_dir=self.portrait_dir, prefix="portrait")

    def generate_background(self, prompt_file="prompt_background.txt"):
        """Generate background (1600x600)."""
        prompt = self._load_prompt(prompt_file)
        self._generate_image(prompt, width=1600, height=600, output_dir=self.background_dir, prefix="background")

    def generate_both(self):
        """Generate both portrait and background in sequence."""
        self.generate_portrait()
        self.generate_background()


if __name__ == "__main__":
    client = StableDiffusionClient()
    client.generate_both()
