import os
import logging
import uuid
from fastapi import APIRouter, Request, Response, HTTPException
from dotenv import load_dotenv

from services.whatsapp import descargar_media, enviar_mensaje_texto
from services.claude_ai import validar_comprobante_imagen
from services.supabase_client import (
    get_deuda_por_telefono,
    registrar_comprobante,
    registrar_mensaje,
    get_supabase,
)

load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "cobranza_webhook_verify_2024")


@router.get("")
async def verificar_webhook(request: Request):
    """Verificacion del webhook de Meta."""
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verificado exitosamente")
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Token de verificacion invalido")


@router.post("")
async def recibir_mensaje(request: Request):
    """Recibe mensajes entrantes de WhatsApp."""
    try:
        body = await request.json()
        logger.info(f"Webhook recibido: {body}")

        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "ok", "message": "sin mensajes"}

        for msg in messages:
            await procesar_mensaje(msg, value)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error procesando webhook: {e}")
        return {"status": "error", "detail": str(e)}


async def procesar_mensaje(msg: dict, value: dict):
    """Procesa un mensaje individual de WhatsApp."""
    msg_type = msg.get("type")
    telefono = msg.get("from", "")

    logger.info(f"Mensaje de {telefono}, tipo: {msg_type}")

    # Buscar deuda pendiente de este numero
    deuda = await get_deuda_por_telefono(telefono)
    if not deuda:
        logger.info(f"No se encontro deuda pendiente para {telefono}")
        return

    if msg_type == "image":
        await procesar_comprobante(msg, deuda, telefono)
    elif msg_type == "text":
        # Por ahora solo registramos el texto recibido
        texto = msg.get("text", {}).get("body", "")
        logger.info(f"Texto recibido de {telefono}: {texto}")
        await registrar_mensaje(
            deuda_id=deuda["id"],
            cobrador_id=deuda["cobrador_id"],
            cliente_id=deuda["cliente"]["id"],
            tipo="personalizado",
            contenido=f"[CLIENTE] {texto}",
            estado_envio="entregado",
        )


async def procesar_comprobante(msg: dict, deuda: dict, telefono: str):
    """Descarga, valida y registra un comprobante de pago."""
    try:
        image_data = msg.get("image", {})
        media_id = image_data.get("id")

        if not media_id:
            return

        # Descargar imagen
        logger.info(f"Descargando comprobante media_id={media_id}")
        image_bytes, mime_type = await descargar_media(media_id)

        # Validar con Claude Sonnet
        logger.info("Validando comprobante con IA...")
        validacion = await validar_comprobante_imagen(image_bytes, mime_type)
        logger.info(f"Resultado validacion: {validacion}")

        # Subir imagen a Supabase Storage
        sb = get_supabase()
        cobrador_id = deuda["cobrador_id"]
        filename = f"{cobrador_id}/{deuda['id']}/{uuid.uuid4()}.jpg"

        sb.storage.from_("comprobantes").upload(
            path=filename,
            file=image_bytes,
            file_options={"content-type": mime_type},
        )

        # Registrar comprobante en BD
        monto = validacion.get("monto_detectado")
        await registrar_comprobante(
            deuda_id=deuda["id"],
            cobrador_id=cobrador_id,
            cliente_id=deuda["cliente"]["id"],
            storage_path=filename,
            monto_declarado=float(monto) if monto else None,
            validacion_ia=validacion,
        )

        # Responder al cliente
        if validacion.get("es_comprobante_valido"):
            respuesta = (
                "Recibimos tu comprobante de pago. "
                "Lo revisaremos y te confirmaremos a la brevedad. Gracias!"
            )
        else:
            motivo = validacion.get("motivo_rechazo", "imagen no reconocida como comprobante")
            respuesta = (
                f"La imagen que enviaste no parece ser un comprobante de pago ({motivo}). "
                "Por favor envia una captura clara de tu transferencia o recibo bancario."
            )

        await enviar_mensaje_texto(telefono, respuesta)
        logger.info(f"Comprobante procesado para deuda {deuda['id']}, valido={validacion.get('es_comprobante_valido')}")

    except Exception as e:
        logger.error(f"Error procesando comprobante de {telefono}: {e}")
