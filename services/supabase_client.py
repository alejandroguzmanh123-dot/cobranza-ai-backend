import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _client = create_client(url, key)
    return _client


async def get_deudas_proximas_a_vencer(dias: int = 3) -> list[dict]:
    """Retorna deudas que vencen en los proximos dias y siguen pendientes."""
    from datetime import date, timedelta
    hoy = date.today()
    limite = hoy + timedelta(days=dias)
    sb = get_supabase()
    resp = (
        sb.table("deudas")
        .select("*, clientes(nombre, telefono), cobradores(nombre)")
        .in_("estado", ["pendiente", "en_proceso"])
        .gte("fecha_vencimiento", hoy.isoformat())
        .lte("fecha_vencimiento", limite.isoformat())
        .execute()
    )
    return resp.data or []


async def get_deudas_vencidas_hoy() -> list[dict]:
    """Retorna deudas que vencen HOY."""
    from datetime import date
    hoy = date.today().isoformat()
    sb = get_supabase()
    resp = (
        sb.table("deudas")
        .select("*, clientes(nombre, telefono), cobradores(nombre, cuenta_banco)")
        .in_("estado", ["pendiente", "en_proceso"])
        .eq("fecha_vencimiento", hoy)
        .execute()
    )
    return resp.data or []


async def registrar_mensaje(
    deuda_id: str,
    cobrador_id: str,
    cliente_id: str,
    tipo: str,
    contenido: str,
    wa_message_id: str | None = None,
    estado_envio: str = "enviado",
) -> dict:
    sb = get_supabase()
    from datetime import datetime, timezone
    resp = sb.table("mensajes").insert({
        "deuda_id": deuda_id,
        "cobrador_id": cobrador_id,
        "cliente_id": cliente_id,
        "canal": "whatsapp",
        "tipo": tipo,
        "contenido": contenido,
        "estado_envio": estado_envio,
        "wa_message_id": wa_message_id,
        "enviado_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    return resp.data[0] if resp.data else {}


async def registrar_comprobante(
    deuda_id: str,
    cobrador_id: str,
    cliente_id: str,
    storage_path: str,
    monto_declarado: float | None = None,
    validacion_ia: dict | None = None,
) -> dict:
    sb = get_supabase()
    estado = "pendiente_revision"
    if validacion_ia and not validacion_ia.get("es_comprobante_valido"):
        estado = "rechazado"
    resp = sb.table("comprobantes").insert({
        "deuda_id": deuda_id,
        "cobrador_id": cobrador_id,
        "cliente_id": cliente_id,
        "storage_path": storage_path,
        "monto_declarado": monto_declarado,
        "estado": estado,
        "validacion_ia": validacion_ia,
    }).execute()
    return resp.data[0] if resp.data else {}


async def get_deuda_por_telefono(telefono: str) -> dict | None:
    """Busca la deuda pendiente mas reciente de un cliente por telefono."""
    sb = get_supabase()
    resp = (
        sb.table("clientes")
        .select("*, deudas(*)")
        .eq("telefono", telefono)
        .eq("activo", True)
        .execute()
    )
    if not resp.data:
        return None
    cliente = resp.data[0]
    deudas_pendientes = [
        d for d in (cliente.get("deudas") or [])
        if d["estado"] in ("pendiente", "en_proceso")
    ]
    if not deudas_pendientes:
        return None
    deuda = sorted(deudas_pendientes, key=lambda d: d["created_at"])[-1]
    deuda["cliente"] = {k: v for k, v in cliente.items() if k != "deudas"}
    return deuda
