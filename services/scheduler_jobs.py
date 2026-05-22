import logging
from services.supabase_client import (
    get_deudas_proximas_a_vencer,
    get_deudas_vencidas_hoy,
    registrar_mensaje,
)
from services.claude_ai import generar_recordatorio, generar_solicitud_comprobante
from services.whatsapp import enviar_mensaje_texto

logger = logging.getLogger(__name__)


async def enviar_recordatorios_diarios():
    """Job diario: envia recordatorios a clientes con deudas proximas a vencer (1-3 dias)."""
    logger.info("Iniciando job: recordatorios diarios")
    try:
        deudas = await get_deudas_proximas_a_vencer(dias=3)
        logger.info(f"Deudas proximas encontradas: {len(deudas)}")

        for deuda in deudas:
            try:
                cliente = deuda.get("clientes", {})
                telefono = cliente.get("telefono")
                if not telefono:
                    continue

                from datetime import date
                hoy = date.today()
                from datetime import datetime
                venc = datetime.fromisoformat(deuda["fecha_vencimiento"]).date()
                dias_rest = (venc - hoy).days

                mensaje = await generar_recordatorio(
                    nombre_cliente=cliente.get("nombre", "Cliente"),
                    monto_pendiente=float(deuda["monto_total"]) - float(deuda["monto_pagado"]),
                    fecha_vencimiento=deuda["fecha_vencimiento"],
                    moneda=deuda.get("moneda", "MXN"),
                    dias_restantes=dias_rest,
                )

                wa_resp = await enviar_mensaje_texto(telefono, mensaje)
                wa_msg_id = wa_resp.get("messages", [{}])[0].get("id")

                await registrar_mensaje(
                    deuda_id=deuda["id"],
                    cobrador_id=deuda["cobrador_id"],
                    cliente_id=deuda["cliente_id"],
                    tipo="recordatorio",
                    contenido=mensaje,
                    wa_message_id=wa_msg_id,
                )
                logger.info(f"Recordatorio enviado a {telefono} para deuda {deuda['id']}")

            except Exception as e:
                logger.error(f"Error enviando recordatorio para deuda {deuda.get('id')}: {e}")

    except Exception as e:
        logger.error(f"Error en job recordatorios_diarios: {e}")


async def solicitar_comprobantes_vencidos():
    """Job diario: el dia del vencimiento solicita el comprobante de pago."""
    logger.info("Iniciando job: solicitar comprobantes del dia")
    try:
        deudas = await get_deudas_vencidas_hoy()
        logger.info(f"Deudas que vencen hoy: {len(deudas)}")

        for deuda in deudas:
            try:
                cliente = deuda.get("clientes", {})
                telefono = cliente.get("telefono")
                if not telefono:
                    continue

                cobrador = deuda.get("cobradores", {})
                cuenta_banco = deuda.get("cuenta_banco") or cobrador.get("cuenta_banco")

                mensaje = await generar_solicitud_comprobante(
                    nombre_cliente=cliente.get("nombre", "Cliente"),
                    monto_pendiente=float(deuda["monto_total"]) - float(deuda["monto_pagado"]),
                    cuenta_banco=cuenta_banco,
                    moneda=deuda.get("moneda", "MXN"),
                )

                wa_resp = await enviar_mensaje_texto(telefono, mensaje)
                wa_msg_id = wa_resp.get("messages", [{}])[0].get("id")

                await registrar_mensaje(
                    deuda_id=deuda["id"],
                    cobrador_id=deuda["cobrador_id"],
                    cliente_id=deuda["cliente_id"],
                    tipo="solicitud_comprobante",
                    contenido=mensaje,
                    wa_message_id=wa_msg_id,
                )
                logger.info(f"Solicitud comprobante enviada a {telefono}")

            except Exception as e:
                logger.error(f"Error solicitando comprobante para deuda {deuda.get('id')}: {e}")

    except Exception as e:
        logger.error(f"Error en job solicitar_comprobantes: {e}")
