# plugins/genlink.py

# ... (Imports sin cambios: re, os, json, base64, logging, pyrogram, config, users_api, etc.) ...
import re
import os
import json
import base64
import logging
from pyrogram.types import Message
from pyrogram import filters, Client, enums
from pyrogram.errors import ChannelInvalid, UsernameInvalid, UsernameNotModified
from config import ADMINS, LOG_CHANNEL, PUBLIC_FILE_STORE, WEBSITE_URL, WEBSITE_URL_MODE
# Asumimos que get_user y get_short_link existen en users_api o donde corresponda
try:
    from plugins.users_api import get_user, get_short_link
except ImportError:
    logger.error("No se pudo importar desde plugins.users_api. La función de acortador fallará.")
    # Definir funciones dummy si falla la importación
    async def get_user(user_id): return {} # Devuelve dict vacío
    async def get_short_link(user, link): return None # Devuelve None

logger = logging.getLogger(__name__)

# --- Función allowed (sin cambios) ---
async def allowed(_, __, message):
    # ... (tu lógica actual, permitiendo admins o todos si PUBLIC_FILE_STORE=True) ...
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
        return await message.reply('⚠️ Responde a un mensaje para obtener enlaces compartibles.')

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
    logger.info(f"Generando enlaces BATCH Normal/Premium con /batch para {user_id}")

    # --- Validar formato (ahora solo comando + link1 + link2) ---
    links = message.text.strip().split(" ")
    if len(links) != 3:
        return await message.reply("⚠️ Formato incorrecto.\nUso: `/batch <link_mensaje_inicial> <link_mensaje_final>`")

    cmd, first, last = links

    # --- Validación de links y obtención de IDs (sin cambios) ---
    # ... (tu código original para validar regex, obtener chat_id, msg_ids) ...
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
        chat_id_int = int(f_chat_id) if isinstance(f_chat_id, str) and f_chat_id.lstrip('-').isdigit() else f_chat_id
        chat = await bot.get_chat(chat_id_int); chat_id = chat.id
    except Exception as e: logger.error(f"Error get_chat batch: {e}"); return await message.reply(f'❌ Error: {e}')

    # --- Iterar mensajes y crear JSON (sin cambios funcionales) ---
    sts = await message.reply("⏳ **Generando lote...**")
    # ... (tu código original para iterar, crear outlist, FRMT) ...
    outlist = []; og_msg = 0; tot = 0; failed_msgs = 0
    start_id = min(f_msg_id, l_msg_id); end_id = max(f_msg_id, l_msg_id); total_estimate = end_id - start_id + 1
    FRMT = "**Generando...** {current}/{total} ({percent}%)"
    try:
        async for msg in bot.iter_messages(chat_id, end_id + 1, start_id):
            tot += 1
            if tot % 25 == 0:
                 try: await sts.edit(FRMT.format(current=tot, total=total_estimate, percent=round((tot/total_estimate)*100)))
                 except: pass
            if msg.empty or msg.service: continue
            file = { "channel_id": str(chat_id), "msg_id": msg.id }; og_msg += 1; outlist.append(file)
    except Exception as iter_err: logger.error(f"Error iter_messages batch {chat_id}: {iter_err}"); failed_msgs = total_estimate - og_msg

    if not outlist: return await sts.edit("❌ No se encontraron mensajes válidos.")
    logger.info(f"Lote generado para {user_id}. {og_msg} mensajes.")

    # --- Guardar JSON, enviar a LOG_CHANNEL (sin cambios) ---
    json_file_path = f"batch_{user_id}.json"
    json_msg_id = None # Inicializar
    try:
        with open(json_file_path, "w+") as out: json.dump(outlist, out)
        post = await bot.send_document(LOG_CHANNEL, json_file_path, file_name="BatchInfo.json", caption=f"Batch generado por {user_id}")
        json_msg_id = str(post.id)
    except Exception as send_err: logger.error(f"Error enviando JSON batch a LOG_CHANNEL: {send_err}"); return await sts.edit("❌ Error guardando info del lote.")
    finally:
        if os.path.exists(json_file_path): os.remove(json_file_path)

    if not json_msg_id: return await sts.edit("❌ Error obteniendo ID de la info del lote.") # Salir si falló el envío a LOG_CHANNEL

    # --- Crear payloads (Normal y Premium) usando el ID del JSON ---
    payload_normal_str = f"normal:{json_msg_id}"
    payload_premium_str = f"premium:{json_msg_id}"

    # --- Codificar ambos ---
    payload_normal_enc = base64.urlsafe_b64encode(payload_normal_str.encode("ascii")).decode("ascii").rstrip("=")
    payload_premium_enc = base64.urlsafe_b64encode(payload_premium_str.encode("ascii")).decode("ascii").rstrip("=")

    # --- Construir ambos enlaces finales (con prefijo BATCH-) ---
    bot_username = (await bot.get_me()).username
    link_normal_orig = f"https://t.me/{bot_username}?start=BATCH-{payload_normal_enc}"
    link_premium_orig = f"https://t.me/{bot_username}?start=BATCH-{payload_premium_enc}"

    # --- Generar y acortar ambos enlaces ---
    # (Usamos una versión simplificada aquí, asumiendo que generate_and_shorten_link podría modificarse o usarse directo)
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

    reply_text = (
        f"<b>✅ Enlaces de Lote Generados:</b>\n\n"
        f"Contiene `{og_msg}` archivos." + (f" ({failed_msgs} errores al leer)" if failed_msgs else "") + "\n\n"
        f"{prefix_normal} :\n`{final_link_normal}`\n\n"
        f"{prefix_premium} :\n`{final_link_premium}`"
    )
    await sts.edit(reply_text)

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
