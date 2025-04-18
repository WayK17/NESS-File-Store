# plugins/genlink.py

import re
import os
import json
import base64
import logging
from pyrogram.types import Message
from pyrogram import filters, Client, enums
from pyrogram.errors import ChannelInvalid, UsernameInvalid, UsernameNotModified, MessageNotModified # Añadido MessageNotModified
from config import ADMINS, LOG_CHANNEL, PUBLIC_FILE_STORE, WEBSITE_URL, WEBSITE_URL_MODE
# Asumimos que get_user y get_short_link existen en users_api o donde corresponda
try:
    from plugins.users_api import get_user, get_short_link
except ImportError:
    # Crear un logger básico si no se ha configurado antes
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.error("No se pudo importar desde plugins.users_api. La función de acortador fallará.")
    # Definir funciones dummy si falla la importación
    async def get_user(user_id): return {} # Devuelve dict vacío
    async def get_short_link(user, link): return None # Devuelve None

# Asegurarse de que el logger esté definido
if 'logger' not in locals():
     logging.basicConfig(level=logging.INFO)
     logger = logging.getLogger(__name__)

# --- Función allowed (sin cambios) ---
async def allowed(_, __, message):
    # Permite admins o todos si PUBLIC_FILE_STORE=True
    if PUBLIC_FILE_STORE: return True
    if message.from_user and message.from_user.id in ADMINS: return True
    return False

# --- Función auxiliar para generar y acortar ---
async def generate_and_shorten_link(bot_username, user_id, payload_encoded, website_mode=False, website_url=""):
    """Genera enlace normal/web y lo acorta si es posible."""
    if website_mode:
        share_link = f"{website_url}?Tech_VJ={payload_encoded}" # Mismo parámetro?
    else:
        share_link = f"https://t.me/{bot_username}?start={payload_encoded}"

    user = await get_user(user_id) # Necesita la DB de users_api
    final_link = share_link
    is_shortened = False

    if user and user.get("base_site") and user.get("shortener_api"):
        logger.debug(f"Intentando acortar enlace ({share_link}) para usuario {user_id}")
        try:
            short_link = await get_short_link(user, share_link)
            if short_link and short_link.startswith("http"):
                final_link = short_link
                is_shortened = True
                logger.debug(f"Enlace acortado: {final_link}")
            else:
                logger.warning(f"Acortador no devolvió enlace válido para {user_id}. Devuelto: {short_link}")
        except Exception as short_err:
             logger.error(f"Error al acortar enlace para {user_id}: {short_err}")
    else:
         logger.debug(f"No se acortará el enlace para {user_id}.")

    return final_link, is_shortened


# =====================================================================
# GENERACIÓN ENLACE POR MEDIA DIRECTA (AHORA GENERA NORMAL Y PREMIUM)
# =====================================================================
@Client.on_message((filters.document | filters.video | filters.audio) & filters.private & filters.create(allowed))
async def incoming_gen_link(bot: Client, message: Message):
    user_id = message.from_user.id
    logger.info(f"Generando enlaces Normal/Premium para media directa de {user_id}")

    try:
        post = await message.copy(LOG_CHANNEL)
        post_id = str(post.id)
        bot_username = (await bot.get_me()).username

        # --- Crear payloads (Normal y Premium) ---
        payload_normal_str = f"normal:file_{post_id}"
        payload_premium_str = f"premium:file_{post_id}"

        # --- Codificar ambos ---
        payload_normal_enc = base64.urlsafe_b64encode(payload_normal_str.encode("ascii")).decode("ascii").rstrip("=")
        payload_premium_enc = base64.urlsafe_b64encode(payload_premium_str.encode("ascii")).decode("ascii").rstrip("=")

        # --- Generar y acortar ambos enlaces ---
        link_normal, shortened_normal = await generate_and_shorten_link(bot_username, user_id, payload_normal_enc, WEBSITE_URL_MODE, WEBSITE_URL)
        link_premium, shortened_premium = await generate_and_shorten_link(bot_username, user_id, payload_premium_enc, WEBSITE_URL_MODE, WEBSITE_URL)

        # --- Construir mensaje de respuesta ---
        prefix_normal = "🖇️ Corto (Normal)" if shortened_normal else "🔗 Original (Normal)"
        prefix_premium = "💎 Corto (Premium)" if shortened_premium else "✨ Original (Premium)"

        reply_text = (
            f"<b>✅ Enlaces Generados:</b>\n\n"
            f"{prefix_normal} :\n`{link_normal}`\n\n"
            f"{prefix_premium} :\n`{link_premium}`"
        )
        await message.reply_text(reply_text, quote=True)

    except Exception as e:
        logger.error(f"Error en incoming_gen_link para user {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ Ocurrió un error al generar los enlaces.")


# =====================================================================
# GENERACIÓN ENLACE POR COMANDO /link (AHORA GENERA NORMAL Y PREMIUM)
# =====================================================================
@Client.on_message(filters.command(['link']) & filters.create(allowed))
async def gen_link_s(bot: Client, message: Message):
    replied = message.reply_to_message
    if not replied:
        return await message.reply('<i>⚠️ Responde A Un Mensaje Para Obtener Enlaces Compartibles.</i>')

    user_id = message.from_user.id
    logger.info(f"Generando enlaces Normal/Premium con /link para {user_id}")

    try:
        post = await replied.copy(LOG_CHANNEL)
        post_id = str(post.id)
        bot_username = (await bot.get_me()).username

        # --- Crear payloads (Normal y Premium) ---
        payload_normal_str = f"normal:file_{post_id}"
        payload_premium_str = f"premium:file_{post_id}"

        # --- Codificar ambos ---
        payload_normal_enc = base64.urlsafe_b64encode(payload_normal_str.encode("ascii")).decode("ascii").rstrip("=")
        payload_premium_enc = base64.urlsafe_b64encode(payload_premium_str.encode("ascii")).decode("ascii").rstrip("=")

        # --- Generar y acortar ambos enlaces ---
        link_normal, shortened_normal = await generate_and_shorten_link(bot_username, user_id, payload_normal_enc, WEBSITE_URL_MODE, WEBSITE_URL)
        link_premium, shortened_premium = await generate_and_shorten_link(bot_username, user_id, payload_premium_enc, WEBSITE_URL_MODE, WEBSITE_URL)

        # --- Construir mensaje de respuesta ---
        prefix_normal = "🖇️ Corto (Normal)" if shortened_normal else "🔗 Original (Normal)"
        prefix_premium = "💎 Corto (Premium)" if shortened_premium else "✨ Original (Premium)"

        reply_text = (
            f"<b>✅ Enlaces Generados:</b>\n\n"
            f"{prefix_normal} :\n`{link_normal}`\n\n"
            f"{prefix_premium} :\n`{link_premium}`"
        )
        await message.reply_text(reply_text, quote=True)

    except Exception as e:
        logger.error(f"Error en gen_link_s para user {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ Ocurrió un error al generar los enlaces.")


# =====================================================================
# GENERACIÓN ENLACE POR COMANDO /batch (AHORA GENERA NORMAL Y PREMIUM)
# =====================================================================
@Client.on_message(filters.command(['batch']) & filters.create(allowed))
async def gen_link_batch(bot: Client, message: Message):
    user_id = message.from_user.id
    # --- CORRECCIÓN: Añadir definición de user_mention ---
    user_mention = message.from_user.mention
    logger.info(f"Generando enlaces BATCH Normal/Premium con /batch para {user_id}")

    # --- Bloque de Ayuda Añadido ---
    # Define el texto de ayuda (puedes modificar el formato y contenido a tu gusto)
    batch_help_text = """
<b>ℹ️ Cómo usar <code>/batch</code>:</b>

Genera enlaces de lote para un rango de mensajes.

<b>Formato:</b>
<blockquote><code>/batch [Enlace_Msg_Inicial] [Enlace_Msg_Final]</code></blockquote>

<b>Ejemplo:</b>
<blockquote><code>/batch https://t.me/c/123456/10 https://t.me/c/123456/25</code></blockquote>

<i>Asegúrate de que los enlaces sean del mismo chat y que el bot sea miembro.</i>
"""

    # Comprueba si se proporcionaron los argumentos correctos
    links = message.text.strip().split(" ")

    # Si no hay suficientes argumentos (< 3: /batch + link1 + link2)
    if len(links) < 3:
        return await message.reply_text(
            batch_help_text,
            quote=True,
            disable_web_page_preview=True
        )
    # Si hay demasiados argumentos (> 3)
    elif len(links) > 3:
         return await message.reply_text(
            f"❌ Demasiados argumentos.\n\n{batch_help_text}",
            quote=True,
            disable_web_page_preview=True
        )
    # --- Fin Bloque de Ayuda ---

    # Extraer los enlaces si el número de argumentos es correcto (3)
    cmd, first, last = links

    # --- Validación de links y obtención de IDs (sin cambios) ---
    regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
    match = regex.match(first);
    if not match: return await message.reply('❌ Enlace inicial inválido')
    f_chat_id = match.group(4); f_msg_id = int(match.group(5))
    if f_chat_id.isnumeric(): f_chat_id = int(("-100" + f_chat_id))
    match = regex.match(last);
    if not match: return await message.reply('❌ Enlace final inválido')
    l_chat_id = match.group(4); l_msg_id = int(match.group(5))
    if l_chat_id.isnumeric(): l_chat_id = int(("-100" + l_chat_id))
    if f_chat_id != l_chat_id: return await message.reply("❌ Los enlaces deben ser del mismo chat.")
    try:
        # Intenta obtener el chat_id numérico si es posible
        chat_id_int = int(f_chat_id) if isinstance(f_chat_id, str) and f_chat_id.lstrip('-').isdigit() else f_chat_id
        chat = await bot.get_chat(chat_id_int); chat_id = chat.id
    except Exception as e: logger.error(f"Error get_chat batch: {e}"); return await message.reply(f'❌ Error al obtener información del chat: {e}')

    # --- Iterar mensajes y crear JSON ---
    sts = await message.reply("⏳ **Generando lote...**")
    outlist = []; og_msg = 0; tot = 0; failed_msgs = 0
    start_id = min(f_msg_id, l_msg_id); end_id = max(f_msg_id, l_msg_id); total_estimate = end_id - start_id + 1
    FRMT = "**Generando...** {current}/{total} ({percent}%)"
    try:
        # --- LÍNEA YA CORREGIDA EN RESPUESTA ANTERIOR ---
        async for msg in bot.iter_messages(chat_id, end_id, start_id): # Usando end_id (no end_id + 1)
            tot += 1
            if tot % 25 == 0:
                 try: await sts.edit(FRMT.format(current=tot, total=total_estimate, percent=round((tot/total_estimate)*100)))
                 except MessageNotModified: pass # Ignorar si no se modificó
                 except Exception as edit_err: logger.warning(f"Error editando estado /batch: {edit_err}") # Loggear otros errores de edición
            if msg.empty or msg.service: continue
            # Añadir información necesaria al JSON
            file = { "channel_id": str(chat_id), "msg_id": msg.id }
            og_msg += 1
            outlist.append(file)
    except Exception as iter_err:
        logger.error(f"Error iter_messages batch {chat_id} desde {start_id} hasta {end_id}: {iter_err}", exc_info=True)
        failed_msgs = total_estimate - og_msg # Estimar fallos si la iteración se interrumpe
        # Informar al usuario del error de iteración
        await sts.edit(f"❌ Error al leer mensajes del chat: {iter_err}")
        # Podríamos decidir devolver aquí o continuar con los mensajes que sí se leyeron (si outlist no está vacío)
        if not outlist: return # Si no se leyó ningún mensaje, no continuar

    if not outlist: return await sts.edit("❌ No se encontraron mensajes válidos en el rango especificado.")
    logger.info(f"Lote generado para {user_id}. {og_msg} mensajes encontrados.") # Usar og_msg que cuenta los mensajes realmente añadidos

    # --- Guardar JSON, enviar a LOG_CHANNEL ---
    json_file_path = f"batch_{user_id}_{start_id}_{end_id}.json" # Nombre de archivo más descriptivo
    json_msg_id = None # Inicializar
    try:
        with open(json_file_path, "w+") as out: json.dump(outlist, out)
        # Enviar el documento a LOG_CHANNEL
        # --- CORRECCIÓN: Usar user_mention definida al inicio ---
        post = await bot.send_document(
            LOG_CHANNEL,
            json_file_path,
            file_name=f"BatchInfo_{chat_id}_{start_id}-{end_id}.json", # Nombre más descriptivo
            caption=f"Batch generado por {user_mention} ({user_id}). Rango: {start_id}-{end_id}. {og_msg} archivos." # Caption más informativo
        )
        json_msg_id = str(post.id) # Guardar el ID del mensaje que contiene el JSON
    except Exception as send_err:
        logger.error(f"Error enviando JSON batch a LOG_CHANNEL: {send_err}", exc_info=True)
        # Informar al usuario del error específico si es posible
        await sts.edit(f"❌ Error interno al guardar la información del lote: {send_err}")
        # No continuar si falla el guardado en log channel
        return
    finally:
        # Asegurarse de borrar el archivo JSON local
        if os.path.exists(json_file_path):
            try:
                os.remove(json_file_path)
            except OSError as rm_err:
                 logger.error(f"No se pudo eliminar el archivo JSON temporal {json_file_path}: {rm_err}")

    if not json_msg_id: return await sts.edit("❌ Error crítico: No se pudo obtener el ID de la información del lote.") # Salir si falló el envío a LOG_CHANNEL

    # --- Crear payloads (Normal y Premium) usando el ID del JSON ---
    payload_normal_str = f"normal:{json_msg_id}"
    payload_premium_str = f"premium:{json_msg_id}"

    # --- Codificar ambos ---
    payload_normal_enc = base64.urlsafe_b64encode(payload_normal_str.encode("ascii")).decode("ascii").rstrip("=")
    payload_premium_enc = base64.urlsafe_b64encode(payload_premium_str.encode("ascii")).decode("ascii").rstrip("=")

    # --- Construir ambos enlaces finales (con prefijo BATCH-) ---
    try:
        bot_username = (await bot.get_me()).username
    except Exception as me_err:
        logger.error(f"No se pudo obtener el username del bot: {me_err}")
        return await sts.edit("❌ Error interno al generar los enlaces finales.")

    link_normal_orig = f"https://t.me/{bot_username}?start=BATCH-{payload_normal_enc}"
    link_premium_orig = f"https://t.me/{bot_username}?start=BATCH-{payload_premium_enc}"

    # --- Generar y acortar ambos enlaces ---
    final_link_normal = link_normal_orig
    final_link_premium = link_premium_orig
    shortened_normal = False
    shortened_premium = False

    user = await get_user(user_id)
    if user and user.get("base_site") and user.get("shortener_api"):
        try:
            short_normal = await get_short_link(user, link_normal_orig)
            if short_normal and short_normal.startswith("http"):
                final_link_normal = short_normal
                shortened_normal = True
        except Exception as e: logger.error(f"Error acortando link batch normal: {e}")
        try:
            short_premium = await get_short_link(user, link_premium_orig)
            if short_premium and short_premium.startswith("http"):
                final_link_premium = short_premium
                shortened_premium = True
        except Exception as e: logger.error(f"Error acortando link batch premium: {e}")

    # --- Construir mensaje de respuesta ---
    prefix_normal = "🖇️ Corto (Normal)" if shortened_normal else "🔗 Original (Normal)"
    prefix_premium = "💎 Corto (Premium)" if shortened_premium else "✨ Original (Premium)"

    # Usar og_msg (mensajes realmente encontrados y añadidos) para el conteo final.
    reply_text = (
        f"<b>✅ Enlaces de Lote Generados:</b>\n\n"
        f"Contiene `{og_msg}` archivos." + (f" ({failed_msgs} errores al leer)" if failed_msgs > 0 else "") + "\n\n" # Mostrar errores si hubo
        f"{prefix_normal} :\n`{final_link_normal}`\n\n"
        f"{prefix_premium} :\n`{final_link_premium}`"
    )
    try:
        await sts.edit(reply_text)
    except Exception as final_edit_err:
         logger.warning(f"No se pudo editar el mensaje final de /batch: {final_edit_err}")
         # Si falla la edición, enviar como nuevo mensaje
         await message.reply_text(reply_text, quote=True)


# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
