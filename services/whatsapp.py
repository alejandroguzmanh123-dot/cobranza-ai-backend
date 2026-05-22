import os
import httpx
from dotenv import load_dotenv

load_dotenv()

WA_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WA_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WA_API_URL = f"https://graph.facebook.com/v20.0/{WA_PHONE_ID}/messages"


async def enviar_mensaje_texto(telefono: str, mensaje: str) -> dict:
    """Envia un mensaje de texto via WhatsApp Cloud API."""
    numero = telefono.replace("+", "").replace(" ", "").replace("-", "")

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "text",
        "text": {"preview_url": False, "body": mensaje},
    }
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(WA_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def descargar_media(media_id: str) -> tuple[bytes, str]:
    """Descarga el archivo multimedia de WhatsApp y retorna (bytes, mime_type)."""
    headers = {"Authorization": f"Bearer {WA_TOKEN}"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        meta_resp = await client.get(
            f"https://graph.facebook.com/v20.0/{media_id}",
            headers=headers,
        )
        meta_resp.raise_for_status()
        meta = meta_resp.json()
        media_url = meta["url"]
        mime_type = meta.get("mime_type", "image/jpeg")

        file_resp = await client.get(media_url, headers=headers)
        file_resp.raise_for_status()
        return file_resp.content, mime_type
