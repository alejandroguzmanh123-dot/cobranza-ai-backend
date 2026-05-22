import os
import base64
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client: anthropic.Anthropic | None = None


def get_claude() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


async def generar_recordatorio(
    nombre_cliente: str,
    monto_pendiente: float,
    fecha_vencimiento: str,
    moneda: str = "MXN",
    dias_restantes: int = 3,
) -> str:
    client = get_claude()
    prompt = (
        f"Eres un asistente de cobranza profesional y amable.\n"
        f"Genera un recordatorio breve para: {nombre_cliente}, "
        f"monto: {monto_pendiente:.2f} {moneda}, "
        f"vencimiento: {fecha_vencimiento}, dias: {dias_restantes}."
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


async def generar_solicitud_comprobante(
    nombre_cliente: str,
    monto_pendiente: float,
    cuenta_banco: str | None,
    moneda: str = "MXN",
) -> str:
    client = get_claude()
    cuenta_info = f"\nCuenta bancaria: {cuenta_banco}" if cuenta_banco else ""
    prompt = (
        f"Eres un asistente de cobranza profesional.\n"
        f"Solicita comprobante de pago a {nombre_cliente}, "
        f"monto: {monto_pendiente:.2f} {moneda}.{cuenta_info}"
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


async def validar_comprobante_imagen(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    client = get_claude()
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                {"type": "text", "text": "Analiza si esta imagen es un comprobante de pago bancario. Responde JSON: {\\n  'es_comprobante_valido': true/false,\\n  'confianza': 'alta/media/baja',\\n  'monto_detectado': numero_o_null,\\n  'banco_detectado': 'nombre_o_null',\\n  'fecha_detectada': 'fecha_o_null',\\n  'motivo_rechazo': 'razon_o_null'\\n}"},
            ],
        }],
    )
    import json
    text = response.content[0].text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {"es_comprobante_valido": False, "confianza": "baja", "monto_detectado": None, "banco_detectado": None, "fecha_detectada": None, "motivo_rechazo": "No se pudo analizar la imagen"}
