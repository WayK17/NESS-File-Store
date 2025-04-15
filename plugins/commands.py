# plugins/commands.py

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import logging
import random
import asyncio
import datetime # Necesario para calcular la expiración
import re
import json
import base64
from urllib.parse import quote_plus

from validators import domain
from pyrogram import Client, filters, enums
from pyrogram.errors import (ChatAdminRequired, FloodWait, UserNotParticipant,
                             ChatWriteForbidden, MessageIdInvalid, MessageNotModified)
from pyrogram.types import (Message, InlineKeyboardMarkup, InlineKeyboardButton,
                            CallbackQuery, InputMediaPhoto, WebAppInfo) # Importaciones específicas

# Importaciones locales (asegúrate que las rutas sean correctas)
from Script import script
from plugins.dbusers import db
from plugins.users_api import get_user, update_user_info # Relacionado con acortador
from config import (
    ADMINS, LOG_CHANNEL, CLONE_MODE, PICS, VERIFY_MODE, VERIFY_TUTORIAL,
    STREAM_MODE, URL, CUSTOM_FILE_CAPTION, BATCH_FILE_CAPTION,
    AUTO_DELETE_MODE, AUTO_DELETE_TIME, AUTO_DELETE, FORCE_SUB_ENABLED,
    FORCE_SUB_CHANNEL, FORCE_SUB_INVITE_LINK, SKIP_FORCE_SUB_FOR_ADMINS
)

# Importar desde utils.py en la carpeta principal
try:
    from utils import (check_user_membership, verify_user, check_token,
                       check_verification, get_token)
except ImportError:
    logging.error("¡ADVERTENCIA! No se encontraron funciones en utils.py. Algunas características pueden fallar.")
    async def check_user_membership(c, u, ch): return True
    async def verify_user(c, u, t): pass
    async def check_token(c, u, t): return False
    async def check_verification(c, u): return True
    async def get_token(c, u, l): return "ERROR_TOKEN_NOT_FOUND"

# Importar desde TechVJ (con fallback)
try:
    from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size
except ImportError:
    logging.warning("No se pudo importar desde TechVJ.utils.file_properties.")
    def get_name(msg): return "archivo"
    def get_hash(msg): return "dummyhash"
    def get_media_file_size(msg): return getattr(getattr(msg, msg.media.value, None), 'file_size', 0)

# Configuración del Logger
logger = logging.getLogger(__name__)

# Variable global
BATCH_FILES = {}

# --- Funciones Auxiliares ---
def get_size(size):
    """Obtiene el tamaño en formato legible."""
    try:
        units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
        size = float(size)
        i = 0
        while size >= 1024.0 and i < len(units) - 1:
            i += 1
            size /= 1024.0
        return "%.2f %s" % (size, units[i])
    except Exception as e:
        logger.error(f"Error en get_size: {e}")
        return "N/A"

def formate_file_name(file_name):
    """Limpia el nombre de archivo."""
    if not isinstance(file_name, str): return "archivo_desconocido"
    original_name = file_name
    try:
        file_name = re.sub(r'[\[\]\(\)]', '', file_name)
        parts = file_name.split()
        filtered_parts = filter(lambda x: x and not x.startswith(('http', '@', 'www.')), parts)
        cleaned_name = ' '.join(filtered_parts)
        return cleaned_name if cleaned_name else original_name
    except Exception as e:
        logger.error(f"Error formateando nombre '{original_name}': {e}")
        return original_name

# --- Manejador del Comando /start ---
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client: Client, message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    logger.info(f"/start de {user_id} ({message.from_user.mention})")

    # Registro de usuario si es nuevo
    username = client.me.username
    if not await db.is_user_exist(user_id):
        # ... (código de registro) ...
        logger.info(f"Usuario {user_id} es nuevo. Añadiendo.")
        await db.add_user(user_id, first_name)
        if LOG_CHANNEL:
             try: await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(user_id, message.from_user.mention))
             except Exception as log_err: logger.error(f"Error enviando a LOG_CHANNEL {LOG_CHANNEL}: {log_err}")
        else: logger.warning("LOG_CHANNEL no definido.")

    # Manejo de /start sin payload (Bienvenida)
    if len(message.command) == 1:
        # ... (código de bienvenida) ...
        logger.info(f"Enviando bienvenida normal a {user_id}")
        buttons_list = [[InlineKeyboardButton('Únete a Nuestro Canal', url='https://t.me/NessCloud')],[InlineKeyboardButton('⚠️ Grupo de Soporte', url='https://t.me/NESS_Soporte')]]
        if not CLONE_MODE: buttons_list.append([InlineKeyboardButton('🤖 Clonar Bot', callback_data='clone')])
        reply_markup = InlineKeyboardMarkup(buttons_list); me = client.me
        try: photo_url = random.choice(PICS) if PICS else "..."; await message.reply_photo(photo=photo_url, caption=script.START_TXT.format(message.from_user.mention, me.mention), reply_markup=reply_markup)
        except Exception: await message.reply_text(script.START_TXT.format(message.from_user.mention, me.mention), reply_markup=reply_markup)
        return

    # --- PROCESAMIENTO CON PAYLOAD ---
    payload_encoded_full = message.command[1]
    logger.info(f"/start con payload '{payload_encoded_full}' de {user_id}")

    # Borrar mensaje "Únete" anterior
    # ... (código de borrado sin cambios) ...
    try:
        user_info = await db.get_user_info(user_id); pending_msg_id = user_info.get("pending_join_msg_id") if user_info else None
        if pending_msg_id: logger.debug(f"Borrando msg {pending_msg_id} para {user_id}"); await client.delete_messages(user_id, pending_msg_id); await db.update_user_info(user_id, {"pending_join_msg_id": None})
    except MessageIdInvalid: logger.info(f"Msg 'Únete' {pending_msg_id} ya no existía."); await db.update_user_info(user_id, {"pending_join_msg_id": None})
    except Exception as db_err: logger.error(f"Error DB borrando msg pendiente {user_id}: {db_err}")

    # Verificación Force Subscribe
    # ... (código de ForceSub sin cambios) ...
    should_skip_fsub = not FORCE_SUB_ENABLED or (SKIP_FORCE_SUB_FOR_ADMINS and user_id in ADMINS)
    if not should_skip_fsub and FORCE_SUB_CHANNEL and FORCE_SUB_INVITE_LINK:
        try:
            if not await check_user_membership(client, user_id, FORCE_SUB_CHANNEL):
                logger.info(f"Usuario {user_id} NO miembro. Mostrando msg ForceSub.")
                buttons = [[InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)], [InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{username}?start={payload_encoded_full}")]]
                join_message = await message.reply_text(script.FORCE_MSG.format(mention=message.from_user.mention), reply_markup=InlineKeyboardMarkup(buttons), quote=True, disable_web_page_preview=True)
                await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id}); return
        except Exception as fs_err: logger.error(f"Error CRÍTICO en ForceSub {user_id}: {fs_err}", exc_info=True)

    # Decodificación y Chequeos Premium/Verify
    # ... (código de decodificación y chequeos sin cambios) ...
    logger.info(f"Usuario {user_id} pasó verificaciones iniciales. Procesando payload: {payload_encoded_full}")
    is_batch = False; base64_to_decode = payload_encoded_full; link_type = "normal"; original_payload_id = ""
    if payload_encoded_full.startswith("BATCH-"): is_batch = True; base64_to_decode = payload_encoded_full[len("BATCH-"):]
    try:
        padding = 4 - (len(base64_to_decode) % 4); padding = 0 if padding == 4 else padding
        payload_decoded = base64.urlsafe_b64decode(base64_to_decode + "=" * padding).decode("ascii")
        original_payload_id = payload_decoded
        if payload_decoded.startswith("premium:"): link_type = "premium"; original_payload_id = payload_decoded[len("premium:"):]
        elif payload_decoded.startswith("normal:"): link_type = "normal"; original_payload_id = payload_decoded[len("normal:"):]
        elif payload_decoded.startswith("verify-"): link_type = "special"; original_payload_id = payload_decoded
        else: logger.warning(f"Payload '{payload_decoded}' sin prefijo."); original_payload_id = payload_decoded
        logger.debug(f"Tipo: {link_type}. ID original: {original_payload_id}")
    except Exception as decode_err: logger.error(f"Error decodificando {base64_to_decode} para {user_id}: {decode_err}"); return await message.reply_text("❌ Enlace inválido.")
    is_premium_user = await db.check_premium_status(user_id); is_admin_user = user_id in ADMINS
    logger.debug(f"User {user_id}: premium={is_premium_user}, admin={is_admin_user}")
    if link_type == "premium" and not is_premium_user and not is_admin_user:
        logger.info(f"User normal {user_id} denegado para link premium '{original_payload_id}'.")
        try: await message.reply_text(script.PREMIUM_REQUIRED_MSG.format(mention=message.from_user.mention), quote=True)
        except AttributeError: await message.reply_text("❌ Acceso denegado. Premium.", quote=True)
        return
    elif link_type == "premium" and is_admin_user and not is_premium_user: logger.info(f"Admin {user_id} accediendo a link premium.")
    try:
        apply_verify_check = VERIFY_MODE and not original_payload_id.startswith("verify-")
        if apply_verify_check and not await check_verification(client, user_id):
            logger.info(f"User {user_id} necesita verificación para {link_type} link.")
            verify_url = await get_token(client, user_id, f"https://t.me/{username}?start=")
            btn_list = [[InlineKeyboardButton("Verify", url=verify_url)]];
            if VERIFY_TUTORIAL: btn_list.append([InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)])
            await message.reply_text("<b>Not verified!</b>", protect_content=True, reply_markup=InlineKeyboardMarkup(btn_list)); return
    except Exception as e: logger.error(f"Error check_verification {user_id}: {e}"); return await message.reply_text(f"**Error verificando: {e}**")

    # --- SI PASÓ TODOS LOS CHEQUEOS: Procesar el original_payload_id ---
    logger.info(f"Usuario {user_id} ({link_type}) procesando ID '{original_payload_id}' (Batch: {is_batch})")

    # Lógica para 'verify-'
    if original_payload_id.startswith("verify-"):
        # ... (código verify sin cambios) ...
        logger.debug(f"Manejando 'verify' payload para {user_id}")
        try: parts = original_payload_id.split("-"); userid = parts[1]; token = parts[2]; assert str(user_id) == userid; assert await check_token(client, userid, token); await message.reply_text(f"<b>Hey {message.from_user.mention}, Verificado!</b>...", protect_content=True); await verify_user(client, userid, token)
        except Exception as verify_e: logger.error(f"Error verify: {verify_e}"); await message.reply_text("<b>Enlace inválido/Error.</b>", protect_content=True)
        return

    # Lógica para BATCH
    elif is_batch:
        batch_json_msg_id = original_payload_id
        logger.info(f"Manejando 'BATCH'. ID JSON: {batch_json_msg_id}")
        sts = await message.reply_text("**🔺 Procesando lote...**", quote=True)
        msgs = BATCH_FILES.get(batch_json_msg_id)
        if not msgs:
             # ... (código para cargar JSON desde LOG_CHANNEL sin cambios) ...
             try: log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL; batch_list_msg = await client.get_messages(log_channel_int, int(batch_json_msg_id)); assert batch_list_msg and batch_list_msg.document; file_path = await client.download_media(batch_list_msg.document.file_id); try: with open(file_path, 'r') as fd: msgs = json.load(fd); BATCH_FILES[batch_json_msg_id] = msgs; finally: os.remove(file_path)
             except Exception as batch_load_err: logger.error(f"Error cargando BATCH {batch_json_msg_id}: {batch_load_err}", exc_info=True); return await sts.edit_text("❌ Error cargando info.")
        if not msgs: return await sts.edit_text("❌ Error: Info lote vacía.")

        filesarr = []; logger.info(f"Enviando {len(msgs)} mensajes BATCH {batch_json_msg_id} a {user_id}")

        # --- Bucle de envío BATCH con lógica de caption restaurada ---
        for i, msg_info in enumerate(msgs):
             try:
                 channel_id = int(msg_info.get("channel_id"))
                 msgid = int(msg_info.get("msg_id"))
                 original_msg = await client.get_messages(channel_id, msgid)
                 if not original_msg: continue

                 # --- INICIO: Lógica Restaurada Caption/Botones BATCH ---
                 f_caption_batch = ""
                 title_batch = ""
                 size_batch = ""
                 stream_reply_markup_batch = None

                 if original_msg.media:
                     media_batch = getattr(original_msg, original_msg.media.value, None)
                     if media_batch:
                         f_caption_orig_batch = getattr(original_msg, 'caption', '')
                         if f_caption_orig_batch and hasattr(f_caption_orig_batch, 'html'): f_caption_orig_batch = f_caption_orig_batch.html
                         old_title_batch = getattr(media_batch, "file_name", "")
                         title_batch = formate_file_name(old_title_batch) if old_title_batch else ""
                         size_batch = get_size(getattr(media_batch, "file_size", 0))

                         if BATCH_FILE_CAPTION: # Usar formato de config si existe
                             try:
                                 f_caption_batch = BATCH_FILE_CAPTION.format(file_name=title_batch, file_size=size_batch, file_caption=f_caption_orig_batch if f_caption_orig_batch else "")
                             except Exception as cap_fmt_err_batch:
                                 logger.warning(f"Error formateando BATCH_FILE_CAPTION: {cap_fmt_err_batch}.")
                                 f_caption_batch = f_caption_orig_batch if f_caption_orig_batch else f"<code>{title_batch}</code>" # Fallback
                         elif f_caption_orig_batch: # Usar caption original si no hay formato config
                              f_caption_batch = f_caption_orig_batch
                         else: # Usar solo nombre de archivo como último recurso
                              f_caption_batch = f"<code>{title_batch}</code>" if title_batch else ""

                     if STREAM_MODE and (original_msg.video or original_msg.document): # Botones Stream
                         try:
                             stream_url = f"{URL}watch/{str(original_msg.id)}/{quote_plus(get_name(original_msg))}?hash={get_hash(original_msg)}"
                             download_url = f"{URL}{str(original_msg.id)}/{quote_plus(get_name(original_msg))}?hash={get_hash(original_msg)}"
                             stream_buttons = [[InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download_url), InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream_url)],
                                              [InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream_url))]]
                             stream_reply_markup_batch = InlineKeyboardMarkup(stream_buttons)
                         except Exception as stream_err: logger.error(f"Error generando botones stream BATCH: {stream_err}")
                 # --- FIN: Lógica Restaurada Caption/Botones BATCH ---

                 # Copiar el mensaje usando el caption y botones preparados
                 sent_msg = await original_msg.copy(
                     chat_id=user_id,
                     caption=f_caption_batch if original_msg.media else None,
                     reply_markup=stream_reply_markup_batch
                 )
                 filesarr.append(sent_msg)

                 # Pausa corta
                 if i % 5 == 0: await asyncio.sleep(0.1)

             except FloodWait as fw_err:
                 logger.warning(f"FloodWait BATCH item {i}. Esperando {fw_err.value}s")
                 await asyncio.sleep(fw_err.value + 2)
                 try: # Reintentar
                      original_msg = await client.get_messages(channel_id, msgid)
                      # Reintentar copia simple aquí (o añadir lógica caption/botones de nuevo)
                      sent_msg = await original_msg.copy(user_id); filesarr.append(sent_msg)
                 except Exception as retry_err: logger.error(f"Error BATCH item {i} (retry): {retry_err}")
             except Exception as loop_err: logger.error(f"Error BATCH item {i}: {loop_err}")
        # --- FIN DEL BUCLE for ---

        try: await sts.delete()
        except Exception: pass

        if AUTO_DELETE_MODE and filesarr: # Auto-Delete BATCH (Sin cambios)
            # ... (código auto-delete BATCH) ...
            logger.info(f"Auto-Delete BATCH para {user_id} iniciado.")
            try:
                 k = await client.send_message(chat_id=user_id,text=(f"<blockquote><b><u>❗️❗️❗️IMPORTANTE❗️️❗️❗️</u></b>\n\nEste mensaje será eliminado en <b><u>{AUTO_DELETE} minutos</u> 🫥 <i></b>(Debido a problemas de derechos de autor)</i>.\n\n<b><i>Por favor, reenvía este mensaje a tus mensajes guardados o a cualquier chat privado.</i></b></blockquote>"),parse_mode=enums.ParseMode.HTML)
                 await asyncio.sleep(AUTO_DELETE_TIME); deleted_count = 0
                 for x in filesarr:
                     try: await x.delete(); deleted_count += 1
                     except Exception: pass
                 await k.edit_text(f"<b>✅ {deleted_count} mensajes del lote eliminados.</b>"); logger.info(f"Auto-Delete BATCH {user_id}: {deleted_count}/{len(filesarr)} borrados.")
            except Exception as auto_del_err: logger.error(f"Error Auto-Delete BATCH {user_id}: {auto_del_err}")
        else: logger.info(f"Auto-Delete BATCH desactivado/sin archivos {user_id}.")
        return

    # Lógica para Archivo Único
    else:
        logger.info(f"Manejando Archivo Único. Payload original ID: {original_payload_id}")
        try:
            if not original_payload_id.startswith("file_"): decode_file_id = int(original_payload_id)
            else: decode_file_id = int(original_payload_id.split("_", 1)[1])

            log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
            original_msg = await client.get_messages(log_channel_int, decode_file_id)
            if not original_msg: raise MessageIdInvalid("Mensaje original no encontrado")

            # --- INICIO: Lógica Restaurada Caption/Botones Archivo Único ---
            f_caption = ""
            reply_markup = None
            title = ""
            size = ""

            if original_msg.media:
                media = getattr(original_msg, original_msg.media.value, None)
                if media:
                    title = formate_file_name(getattr(media, "file_name", ""))
                    size = get_size(getattr(media, "file_size", 0))
                    f_caption_orig = getattr(original_msg, 'caption', '')
                    if f_caption_orig and hasattr(f_caption_orig, 'html'): f_caption_orig = f_caption_orig.html

                    if CUSTOM_FILE_CAPTION:
                        try:
                            f_caption = CUSTOM_FILE_CAPTION.format(
                                file_name=title if title else "N/A",
                                file_size=size if size else "N/A",
                                file_caption=f_caption_orig if f_caption_orig else ""
                            )
                            logger.debug(f"Caption formateado con CUSTOM_FILE_CAPTION: {f_caption[:50]}...")
                        except Exception as e:
                            logger.error(f"Error al formatear CUSTOM_FILE_CAPTION: {e}. Usando fallback.")
                            f_caption = f"<code>{title}</code>" if title else "Archivo"
                    elif f_caption_orig:
                        f_caption = f_caption_orig
                        logger.debug("Usando caption original del mensaje.")
                    else:
                        f_caption = f"<code>{title}</code>" if title else ""
                        logger.debug(f"Usando nombre de archivo como caption: {f_caption}")

                    if STREAM_MODE and (original_msg.video or original_msg.document):
                        try:
                            stream_url = f"{URL}watch/{str(original_msg.id)}/{quote_plus(get_name(original_msg))}?hash={get_hash(original_msg)}"
                            download_url = f"{URL}{str(original_msg.id)}/{quote_plus(get_name(original_msg))}?hash={get_hash(original_msg)}"
                            stream_buttons = [
                                [InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download_url), InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream_url)],
                                [InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream_url))]
                             ]
                            reply_markup = InlineKeyboardMarkup(stream_buttons)
                            logger.debug("Botones de Stream generados.")
                        except Exception as stream_err:
                           logger.error(f"Error generando botones de stream: {stream_err}")
                           reply_markup = None
                else:
                     logger.warning(f"Mensaje {original_msg.id} tiene media pero no se pudo obtener objeto media.")
                     f_caption = "⚠️ Error al obtener detalles."
            else:
                 logger.debug(f"Mensaje {original_msg.id} no tiene media.")
                 f_caption = None
            # --- FIN: Lógica Restaurada Caption/Botones Archivo Único ---

            # Copiar el mensaje usando caption/botones preparados
            sent_file_msg = await original_msg.copy(
                chat_id=user_id, caption=f_caption,
                reply_markup=reply_markup, protect_content=False
            )

            # Auto-Delete para Archivo Único (Sin cambios)
            if AUTO_DELETE_MODE:
                # ... (código auto-delete Archivo Único) ...
                 logger.info(f"Auto-Delete Single File para {user_id} iniciado.")
                 try:
                     k = await client.send_message(chat_id=user_id, text=(f"<blockquote><b><u>❗️❗️❗️IMPORTANTE❗️️❗️❗️</u></b>\n\nEste mensaje será eliminado en <b><u>{AUTO_DELETE} minutos</u> 🫥 <i></b>(Debido a problemas de derechos de autor)</i>.\n\n<b><i>Por favor, reenvía este mensaje a tus mensajes guardados o a cualquier chat privado.</i></b></blockquote>"), parse_mode=enums.ParseMode.HTML)
                     await asyncio.sleep(AUTO_DELETE_TIME)
                     try: await sent_file_msg.delete()
                     except Exception: pass
                     try: await k.edit_text("<b>✅ El mensaje anterior fue eliminado automáticamente.</b>")
                     except Exception: pass
                     logger.info(f"Auto-Delete Single File completado {user_id}.")
                 except Exception as auto_del_err: logger.error(f"Error Auto-Delete Single File {user_id}: {auto_del_err}")
            else: logger.debug(f"Auto-Delete Single File desactivado {user_id}.")
            return

        except MessageIdInvalid as e: logger.error(f"Msg ID {decode_file_id} no encontrado {LOG_CHANNEL}: {e}."); await message.reply_text("❌ Archivo no disponible.")
        except (ValueError, IndexError, AttributeError) as payload_err: logger.error(f"Error procesando payload '{original_payload_id}': {payload_err}"); await message.reply_text("❌ Enlace inválido.")
        except Exception as e: logger.error(f"Error crítico Archivo Único {user_id}: {e}", exc_info=True); await message.reply_text("❌ Error inesperado.")
        return

# --- Comandos /api, /base_site, /stats (Formateados) ---
@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    # Función formateada
    user_id = m.from_user.id
    try:
        user = await get_user(user_id)
        user_base_site = user.get("base_site", "N/Configurado") if user else "N/A"
        user_shortener_api = user.get("shortener_api", "N/Configurada") if user else "N/A"
    except Exception as e: logger.error(f"Error get_user api {user_id}: {e}"); return await m.reply_text("❌ Error config API.")
    cmd = m.command
    if len(cmd) == 1:
        try: s = script.SHORTENER_API_MESSAGE.format(base_site=user_base_site, shortener_api=user_shortener_api); await m.reply_text(s)
        except AttributeError: await m.reply_text("Error: Texto no encontrado.")
        except Exception as fmt_err: logger.error(f"Error fmt API_MSG: {fmt_err}"); await m.reply_text("Error info API.")
    elif len(cmd) == 2:
        api_key = cmd[1].strip(); update_value = None if api_key.lower() == "none" else api_key
        if update_value == "": return await m.reply_text("❌ API no puede ser vacía.")
        log_msg = "eliminando" if update_value is None else f"actualizando a: {api_key[:5]}..."; logger.info(f"User {user_id} {log_msg} Shortener API.")
        try: await update_user_info(user_id, {"shortener_api": update_value}); reply_msg = "<b>✅ API eliminada.</b>" if update_value is None else "<b>✅ API actualizada.</b>"; await m.reply_text(reply_msg)
        except Exception as e: logger.error(f"Error update API {user_id}: {e}"); await m.reply_text("❌ Error actualizando API.")
    else: await m.reply_text("Formato:\n`/api` (ver)\n`/api KEY` (set)\n`/api None` (del)")

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    # Función formateada
    user_id = m.from_user.id
    try: user = await get_user(user_id); current_site = user.get("base_site", "Ninguno") if user else "N/A"
    except Exception as e: logger.error(f"Error get_user base_site {user_id}: {e}"); return await m.reply_text("❌ Error config.")
    cmd = m.command
    help_text = (f"⚙️ **Sitio Base Acortador**\n\nActual: `{current_site}`\n\n➡️ `/base_site url.com`\n➡️ `/base_site None`")
    if len(cmd) == 1: await m.reply_text(text=help_text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site_input = cmd[1].strip().lower()
        if base_site_input == "none":
            logger.info(f"User {user_id} eliminando base_site.")
            try: await update_user_info(user_id, {"base_site": None}); await m.reply_text("<b>✅ Sitio Base eliminado.</b>")
            except Exception as e: logger.error(f"Error del base_site {user_id}: {e}"); await m.reply_text("❌ Error eliminando.")
        else:
            try: is_valid_domain = domain(base_site_input)
            except Exception as val_err: logger.error(f"Error validando {base_site_input}: {val_err}"); is_valid_domain = False
            if not is_valid_domain: return await m.reply_text(help_text + "\n\n❌ Dominio inválido.", disable_web_page_preview=True)
            logger.info(f"User {user_id} actualizando base_site a: {base_site_input}")
            try: await update_user_info(user_id, {"base_site": base_site_input}); await m.reply_text(f"<b>✅ Sitio Base actualizado a:</b> `{base_site_input}`")
            except Exception as e: logger.error(f"Error update base_site {user_id}: {e}"); await m.reply_text("❌ Error actualizando.")
    else: await m.reply_text("Formato incorrecto.\n" + help_text, disable_web_page_preview=True)

@Client.on_message(filters.command("stats") & filters.private)
async def simple_stats_command(client, message):
    # Función formateada
    if message.from_user.id not in ADMINS: return await message.reply_text("❌ **Acceso denegado.** Solo admins.")
    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING); total_users = await db.total_users_count()
        stats_text = (f"📊 **Estadísticas:**\n\n👥 Usuarios: `{total_users}`"); await message.reply_text(stats_text, quote=True) # Texto ligeramente cambiado
    except Exception as e: logger.error(f"Error en /stats: {e}"); await message.reply_text(" Ocurrió un error.")

# --- Manejador de Callbacks (Formateado) ---
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    # Función formateada
    user_id = query.from_user.id; q_data = query.data; logger.debug(f"Callback de {user_id}: {q_data}")
    try: me_mention = client.me.mention if client.me else (await client.get_me()).mention
    except Exception as e: logger.error(f"Error get_me cb: {e}"); me_mention = "Bot"
    message = query.message
    try:
        if q_data == "close_data": logger.debug(f"Cerrando msg {message.id} para {user_id}"); await message.delete()
        elif q_data == "about":
             logger.debug(f"Mostrando 'About' {user_id}"); btns = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]; markup = InlineKeyboardMarkup(btns)
             await query.edit_message_text(script.ABOUT_TXT.format(me_mention), reply_markup=markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        elif q_data == "start":
             logger.debug(f"Mostrando 'Start' {user_id}"); btns = [[InlineKeyboardButton('Canal Principal', url='https://t.me/NessCloud'), InlineKeyboardButton('Grupo de Soporte', url='https://t.me/NESS_Soporte')],[InlineKeyboardButton('❓ Ayuda', callback_data='help'), InlineKeyboardButton('ℹ️ Acerca de', callback_data='about')]]
             if not CLONE_MODE: btns.append([InlineKeyboardButton('🤖 Clonar Bot', callback_data='clone')])
             markup = InlineKeyboardMarkup(btns)
             try: await query.edit_message_text(script.START_TXT.format(query.from_user.mention, me_mention), reply_markup=markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
             except MessageNotModified: pass
             except Exception: logger.warning("Fallo edit text cb 'start', intentando edit media."); try: await query.edit_message_media(media=InputMediaPhoto(random.choice(PICS) if PICS else "..."), reply_markup=markup); await query.edit_message_caption(caption=script.START_TXT.format(query.from_user.mention, me_mention), reply_markup=markup, parse_mode=enums.ParseMode.HTML); except Exception as e_media: logger.error(f"Fallo edit media cb 'start': {e_media}")
        elif q_data == "clone":
             logger.debug(f"Mostrando 'Clone' {user_id}"); btns = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]; markup = InlineKeyboardMarkup(btns)
             await query.edit_message_text(script.CLONE_TXT.format(query.from_user.mention), reply_markup=markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        elif q_data == "help":
             logger.debug(f"Mostrando 'Help' {user_id}"); btns = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]; markup = InlineKeyboardMarkup(btns)
             await query.edit_message_text(script.HELP_TXT, reply_markup=markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        else: logger.warning(f"Callback no reconocido: {q_data}"); await query.answer("Opción no implementada.", show_alert=False)
    except MessageNotModified: logger.debug(f"Msg no modificado cb '{q_data}'"); await query.answer()
    except Exception as e: logger.error(f"Error procesando cb '{q_data}' user {user_id}: {e}", exc_info=True); await query.answer("Error procesando.", show_alert=True)

# --- Comandos Premium (Formateados) ---
@Client.on_message(filters.command("addpremium") & filters.private & filters.user(ADMINS))
async def add_premium_command(client, message: Message):
    # Función formateada
    if len(message.command) < 2: return await message.reply_text("⚠️ Uso: `/addpremium <user_id> [días]`\n(Default: permanente)")
    try: target_user_id = int(message.command[1])
    except ValueError: return await message.reply_text("❌ ID inválido.")
    days = None
    if len(message.command) > 2:
        try: days = int(message.command[2]); assert days > 0
        except (ValueError, AssertionError): return await message.reply_text("❌ Días debe ser número positivo.")
    if not await db.is_user_exist(target_user_id): return await message.reply_text(f"❌ Usuario {target_user_id} no encontrado.")
    try:
        if await db.set_premium(target_user_id, days):
            d_txt = f"por {days} días" if days else "permanentemente"; await message.reply_text(f"✅ Premium activado: `{target_user_id}` {d_txt}!"); await client.send_message(target_user_id, f"🎉 Acceso Premium activado {d_txt}.")
        else: await message.reply_text(f"❌ Error activando premium {target_user_id}.")
    except Exception as e: logger.error(f"Error set_premium {target_user_id}: {e}"); await message.reply_text("❌ Error interno.")

@Client.on_message(filters.command("delpremium") & filters.private & filters.user(ADMINS))
async def del_premium_command(client, message: Message):
    # Función formateada
    if len(message.command) != 2: return await message.reply_text("⚠️ Uso: `/delpremium <user_id>`")
    try: target_user_id = int(message.command[1])
    except ValueError: return await message.reply_text("❌ ID inválido.")
    if not await db.is_user_exist(target_user_id): return await message.reply_text(f"❌ Usuario {target_user_id} no encontrado.")
    try:
        if await db.remove_premium(target_user_id): await message.reply_text(f"✅ Premium desactivado: `{target_user_id}`."); await client.send_message(target_user_id, "ℹ️ Tu acceso Premium ha sido desactivado.")
        else: await message.reply_text(f"❌ Error desactivando premium {target_user_id}.")
    except Exception as e: logger.error(f"Error remove_premium {target_user_id}: {e}"); await message.reply_text("❌ Error interno.")

# No modifiques nada, solo añade la función que envíe el caption que se eliminó, pero no modifiques lo que ya esta, solo añadele, y también los comandos premium añadele con un texto para que el usuario sepa como usarlo.
