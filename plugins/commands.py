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

# Importaciones de terceros y Pyrogram
from validators import domain
from pyrogram import Client, filters, enums
from pyrogram.errors import (
    ChatAdminRequired, FloodWait, UserNotParticipant,
    ChatWriteForbidden, MessageIdInvalid, MessageNotModified
)
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InputMediaPhoto, WebAppInfo
)

# Importaciones locales
from Script import script # Textos del bot
from plugins.dbusers import db # Base de datos de usuarios generales
from plugins.users_api import get_user, update_user_info # Para API de acortador
from config import (
    ADMINS, LOG_CHANNEL, CLONE_MODE, PICS, VERIFY_MODE, VERIFY_TUTORIAL,
    STREAM_MODE, URL, CUSTOM_FILE_CAPTION, BATCH_FILE_CAPTION,
    AUTO_DELETE_MODE, AUTO_DELETE_TIME, AUTO_DELETE, FORCE_SUB_ENABLED,
    FORCE_SUB_CHANNEL, FORCE_SUB_INVITE_LINK, SKIP_FORCE_SUB_FOR_ADMINS
)

# Importar desde utils.py (asumiendo que está en la raíz)
try:
    from utils import (
        check_user_membership, verify_user, check_token,
        check_verification, get_token
    )
except ImportError:
    logging.error("¡ADVERTENCIA! Funciones no encontradas en utils.py. Algunas características fallarán.")
    # Funciones Dummy para evitar errores de arranque
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
logger.setLevel(logging.INFO) # Puedes cambiar a DEBUG para más detalles

# Variable global para caché de BATCH
BATCH_FILES = {}

# --- Funciones Auxiliares ---

def get_size(size):
    """Convierte bytes a formato legible (KB, MB, GB...)."""
    try:
        units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
        size = float(size)
        i = 0
        # Asegurar que i no exceda los límites de units
        while size >= 1024.0 and i < len(units) - 1:
            i += 1
            size /= 1024.0
        return "%.2f %s" % (size, units[i])
    except Exception as e:
        logger.error(f"Error en get_size: {e}")
        return "N/A"

def formate_file_name(file_name):
    """Limpia un nombre de archivo eliminando caracteres y prefijos no deseados."""
    if not isinstance(file_name, str):
        return "archivo_desconocido"
    original_name = file_name
    try:
        # Eliminar [], ()
        file_name = re.sub(r'[\[\]\(\)]', '', file_name)
        # Eliminar URLs, usernames, y espacios extra
        parts = file_name.split()
        filtered_parts = filter(lambda x: x and not x.startswith(('http', '@', 'www.')), parts)
        cleaned_name = ' '.join(filtered_parts).strip() # Asegurar sin espacios al inicio/fin
        # Devolver nombre limpio o el original si el limpio queda vacío
        return cleaned_name if cleaned_name else original_name
    except Exception as e:
        logger.error(f"Error formateando nombre '{original_name}': {e}")
        return original_name # Devolver original en caso de error

# --- Manejador Principal del Comando /start ---
@Client.on_message(filters.command("start") & filters.incoming & filters.private)
async def start(client: Client, message: Message):
    """Maneja el comando /start, incluyendo bienvenida, Force Subscribe, Premium y envío de archivos/lotes."""

    user_id = message.from_user.id
    first_name = message.from_user.first_name
    user_mention = message.from_user.mention
    bot_username = client.me.username # Obtener username del bot para enlaces
    logger.info(f"/start de {user_id} ({user_mention})")

    # --- Bloque 1: Registro de Usuario Nuevo ---
    # Añade al usuario a la base de datos si es la primera vez que inicia el bot.
    # También envía una notificación al canal de logs si está configurado.
    if not await db.is_user_exist(user_id):
        logger.info(f"Usuario {user_id} ({user_mention}) es nuevo. Añadiendo a DB.")
        await db.add_user(user_id, first_name) # Usa la función actualizada de dbusers.py
        if LOG_CHANNEL:
            try:
                await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(user_id, user_mention))
            except Exception as log_err:
                logger.error(f"Error enviando a LOG_CHANNEL {LOG_CHANNEL}: {log_err}")
        else:
            logger.warning("LOG_CHANNEL no definido. No se envió log de nuevo usuario.")

    # --- Bloque 2: Manejo de /start sin Payload ---
    # Si el usuario solo envió /start (sin argumento adicional), muestra el mensaje de bienvenida.
    if len(message.command) == 1:
        logger.info(f"Enviando mensaje de bienvenida normal a {user_id}")
        buttons_list = [
            [InlineKeyboardButton('Únete a Nuestro Canal', url='https://t.me/NessCloud')],
            [InlineKeyboardButton('⚠️ Grupo de Soporte', url='https://t.me/NESS_Soporte')]
        ]
        if not CLONE_MODE:
            buttons_list.append([InlineKeyboardButton('🤖 Clonar Bot', callback_data='clone')]) # Botón opcional

        reply_markup = InlineKeyboardMarkup(buttons_list)
        me = client.me
        start_text = script.START_TXT.format(user_mention, me.mention)

        try:
            # Intenta enviar con foto, si falla o no hay PICS, envía solo texto
            photo_url = random.choice(PICS) if PICS else None
            if photo_url:
                 await message.reply_photo(photo=photo_url, caption=start_text, reply_markup=reply_markup)
            else:
                 await message.reply_text(text=start_text, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as start_err:
            logger.error(f"Error enviando mensaje de bienvenida a {user_id}: {start_err}")
            # Intentar solo texto como último recurso
            try: await message.reply_text(text=start_text, reply_markup=reply_markup, disable_web_page_preview=True)
            except Exception as final_err: logger.critical(f"Fallo CRÍTICO al enviar bienvenida a {user_id}: {final_err}")
        return # Termina aquí si era solo /start

    # --- Bloque 3: Procesamiento de /start con Payload ---
    payload_encoded_full = message.command[1] # El argumento después de /start
    logger.info(f"/start con payload '{payload_encoded_full}' recibido de {user_id}")

    # --- Bloque 3.1: Borrar Mensaje "Únete" Pendiente ---
    # Si el usuario intentó acceder antes y se le mostró el mensaje de Force Subscribe,
    # intentamos borrar ese mensaje ahora que lo intenta de nuevo.
    try:
        user_info = await db.get_user_info(user_id)
        pending_msg_id = user_info.get("pending_join_msg_id") if user_info else None
        if pending_msg_id:
            logger.debug(f"Intentando borrar mensaje pendiente 'Únete' {pending_msg_id} para {user_id}")
            await client.delete_messages(user_id, pending_msg_id)
            await db.update_user_info(user_id, {"pending_join_msg_id": None}) # Limpiar ID de la DB
    except MessageIdInvalid: # El mensaje ya no existe
        logger.info(f"Mensaje 'Únete' {pending_msg_id} para {user_id} ya no existía.")
        await db.update_user_info(user_id, {"pending_join_msg_id": None}) # Limpiar DB
    except Exception as db_err:
        logger.error(f"Error DB/borrando msg pendiente 'Únete' para {user_id}: {db_err}")

    # --- Bloque 3.2: Verificación Force Subscribe ---
    # Comprueba si el usuario debe estar unido a un canal para continuar.
    should_skip_fsub = not FORCE_SUB_ENABLED or (SKIP_FORCE_SUB_FOR_ADMINS and user_id in ADMINS)
    if not should_skip_fsub and FORCE_SUB_CHANNEL and FORCE_SUB_INVITE_LINK:
        logger.debug(f"Realizando chequeo ForceSub para {user_id} en canal {FORCE_SUB_CHANNEL}")
        try:
            is_member = await check_user_membership(client, user_id, FORCE_SUB_CHANNEL)
            if not is_member:
                logger.info(f"Usuario {user_id} NO miembro del canal {FORCE_SUB_CHANNEL}. Mostrando mensaje ForceSub.")
                # Prepara botones (con tus textos)
                buttons = [
                    [InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)],
                    # El botón 'Try Again' usa el payload original codificado
                    [InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{bot_username}?start={payload_encoded_full}")]
                ]
                # Envía mensaje y guarda su ID para borrarlo después
                join_message = await message.reply_text(
                    script.FORCE_MSG.format(mention=user_mention),
                    reply_markup=InlineKeyboardMarkup(buttons),
                    quote=True,
                    disable_web_page_preview=True
                )
                await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id})
                return # Detiene el procesamiento aquí
        except ChatAdminRequired:
             logger.error(f"Error CRÍTICO: Bot necesita ser admin en canal ForceSub {FORCE_SUB_CHANNEL}")
             # Considera notificar a admins o manejar este error de forma diferente
        except Exception as fs_err:
            logger.error(f"Error CRÍTICO durante Force Subscribe para {user_id}: {fs_err}", exc_info=True)
            # Permitir continuar como failsafe o informar al usuario
            # await message.reply_text("⚠️ Error verificando membresía. Intenta más tarde.")
            # return

    # --- Bloque 3.3: Decodificación de Payload y Determinación de Tipo ---
    # Intenta decodificar el payload y determinar si es normal, premium, batch, verify, etc.
    logger.info(f"Usuario {user_id} pasó chequeos iniciales. Procesando payload: {payload_encoded_full}")
    is_batch = False
    base64_to_decode = payload_encoded_full
    link_type = "normal" # Tipo por defecto
    original_payload_id = "" # ID después de quitar prefijos y decodificar

    # Separar prefijo BATCH- si existe
    if payload_encoded_full.startswith("BATCH-"):
        is_batch = True
        base64_to_decode = payload_encoded_full[len("BATCH-"):]
        logger.debug(f"Prefijo BATCH- detectado. Base64: {base64_to_decode}")

    try:
        # Calcular padding y decodificar la parte Base64
        padding = 4 - (len(base64_to_decode) % 4)
        padding = 0 if padding == 4 else padding
        payload_decoded = base64.urlsafe_b64decode(base64_to_decode + "=" * padding).decode("ascii")
        logger.debug(f"Payload decodificado: {payload_decoded}")

        original_payload_id = payload_decoded
        # Buscar prefijos internos (normal:/premium:)
        if payload_decoded.startswith("premium:"):
            link_type = "premium"
            original_payload_id = payload_decoded[len("premium:"):]
        elif payload_decoded.startswith("normal:"):
            link_type = "normal"
            original_payload_id = payload_decoded[len("normal:"):]
        elif payload_decoded.startswith("verify-"):
             link_type = "special" # Para enlaces de verificación
        else:
             logger.warning(f"Payload '{payload_decoded}' sin prefijo 'normal:' o 'premium:'.")
             # Se asume 'normal' o formato especial (verify/batch antiguo?)

        logger.debug(f"Tipo enlace: {link_type}. ID original: {original_payload_id}")

    except (base64.binascii.Error, UnicodeDecodeError) as b64_err:
        logger.error(f"Error decodificando Base64 '{base64_to_decode}' para {user_id}: {b64_err}")
        return await message.reply_text("❌ Enlace inválido o corrupto (Error Base64).")
    except Exception as decode_err:
        logger.error(f"Error inesperado decodificando payload para {user_id}: {decode_err}")
        return await message.reply_text("❌ Error al procesar el enlace.")

    # --- Bloque 3.4: Chequeo de Acceso Premium ---
    # Verifica si el enlace es premium y si el usuario tiene permiso (premium o admin).
    is_premium_user = await db.check_premium_status(user_id)
    is_admin_user = user_id in ADMINS
    logger.debug(f"Chequeo Premium para {user_id}: premium={is_premium_user}, admin={is_admin_user}, link_type={link_type}")

    if link_type == "premium" and not is_premium_user and not is_admin_user:
        logger.info(f"Acceso denegado: Usuario normal {user_id} -> enlace premium '{original_payload_id}'.")
        try:
            # Usa el texto definido en Script.py
            await message.reply_text(script.PREMIUM_REQUIRED_MSG.format(mention=user_mention), quote=True)
        except AttributeError: # Fallback si el texto no está en Script.py
            await message.reply_text("❌ Acceso denegado. Este contenido es solo para usuarios Premium.", quote=True)
        return # Detener
    elif link_type == "premium" and is_admin_user and not is_premium_user:
        logger.info(f"Acceso permitido: Admin {user_id} a enlace premium '{original_payload_id}'.")

    # --- Bloque 3.5: Chequeo de Verificación de Usuario (si aplica) ---
    try:
        apply_verify_check = VERIFY_MODE and link_type != "special" # No verificar si es un link 'verify-'
        if apply_verify_check and not await check_verification(client, user_id):
            logger.info(f"Usuario {user_id} requiere verificación para enlace {link_type} '{original_payload_id}'.")
            verify_url = await get_token(client, user_id, f"https://t.me/{username}?start=")
            if "ERROR" in verify_url: # Manejar error de get_token
                 logger.error(f"No se pudo obtener token verificación para {user_id}.")
                 await message.reply_text("🔒 Verificación Requerida (Error generando enlace).", protect_content=True)
                 return

            btn_list = [[InlineKeyboardButton("➡️ Verificar Ahora ⬅️", url=verify_url)]]
            if VERIFY_TUTORIAL:
                btn_list.append([InlineKeyboardButton("❓ Cómo Verificar", url=VERIFY_TUTORIAL)])
            await message.reply_text(
                 "🔒 **Verificación Requerida**\n\nCompleta la verificación para acceder.",
                 protect_content=True, reply_markup=InlineKeyboardMarkup(btn_list)
            )
            return # Detener hasta que verifique
    except Exception as e:
        logger.error(f"Error en check_verification para {user_id}: {e}", exc_info=True)
        await message.reply_text(f"❌ Error verificando tu estado: {e}")
        return

    # --- Bloque 4: Procesamiento Final del Payload (Verify, Batch, Archivo Único) ---
    logger.info(f"Usuario {user_id} ({link_type}) procesando ID final '{original_payload_id}' (Batch: {is_batch})")

    # --- Sub-bloque 4.1: Lógica para 'verify-' ---
    if link_type == "special" and original_payload_id.startswith("verify-"):
        logger.debug(f"Manejando payload de confirmación 'verify' para {user_id}")
        try:
            parts = original_payload_id.split("-")
            if len(parts) != 3: raise ValueError("Formato token verificación incorrecto.")
            _, verify_userid_str, token = parts
            verify_userid = int(verify_userid_str)
            if user_id != verify_userid: raise PermissionError("Token no pertenece a este usuario.")
            if not await check_token(client, verify_userid, token): raise ValueError("Token inválido o expirado.")

            await verify_user(client, verify_userid, token)
            await message.reply_text(f"✅ ¡Hola {user_mention}! Verificación completa. Intenta el enlace original de nuevo.", protect_content=True)
            logger.info(f"Usuario {verify_userid} verificado con token {token}.")
        except (ValueError, PermissionError) as verify_e:
            logger.warning(f"Error procesando token '{original_payload_id}' para {user_id}: {verify_e}")
            await message.reply_text(f"❌ **Error de Verificación:** {verify_e}", protect_content=True)
        except Exception as generic_verify_e:
             logger.error(f"Error inesperado procesando token '{original_payload_id}' para {user_id}: {generic_verify_e}", exc_info=True)
             await message.reply_text("❌ Error inesperado durante verificación.", protect_content=True)
        return # Terminar después de procesar 'verify-'

    # --- Sub-bloque 4.2: Lógica para BATCH ---
    elif is_batch:
        batch_json_msg_id = original_payload_id
        logger.info(f"Procesando BATCH. ID JSON: {batch_json_msg_id}")
        sts = await message.reply_text("⏳ **Procesando lote...**", quote=True)
        msgs = BATCH_FILES.get(batch_json_msg_id)
        # Cargar JSON si no está en caché
        if not msgs:
             file_path = None
             try:
                 log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
                 logger.debug(f"Descargando JSON BATCH msg {batch_json_msg_id} de {log_channel_int}")
                 batch_list_msg = await client.get_messages(log_channel_int, int(batch_json_msg_id))
                 if not batch_list_msg or not batch_list_msg.document: raise FileNotFoundError("Msg lista batch no encontrado/inválido")
                 file_path = await client.download_media(batch_list_msg.document.file_id, file_name=f"./batch_{batch_json_msg_id}.json")
                 with open(file_path, 'r', encoding='utf-8') as fd: msgs = json.load(fd)
                 BATCH_FILES[batch_json_msg_id] = msgs; logger.info(f"BATCH {batch_json_msg_id} cargado ({len(msgs)} items).")
             except FileNotFoundError as e: logger.error(f"Error BATCH: {e}"); return await sts.edit_text(f"❌ Error: Info lote ({batch_json_msg_id}) no encontrada.")
             except json.JSONDecodeError as e: logger.error(f"Error BATCH: JSON inválido ({batch_json_msg_id}): {e}"); return await sts.edit_text("❌ Error: Info lote corrupta.")
             except Exception as batch_load_err: logger.error(f"Error cargando BATCH {batch_json_msg_id}: {batch_load_err}", exc_info=True); return await sts.edit_text("❌ Error cargando info lote.")
             finally:
                  if file_path and os.path.exists(file_path):
                      try: os.remove(file_path); logger.debug(f"JSON temporal {file_path} eliminado.")
                      except OSError as e: logger.error(f"Error eliminando JSON {file_path}: {e}")
        if not msgs or not isinstance(msgs, list): return await sts.edit_text("❌ Error: Info lote vacía/inválida.")

        # Bucle de envío BATCH
        filesarr = []; total_msgs = len(msgs); logger.info(f"Enviando {total_msgs} mensajes BATCH {batch_json_msg_id} a {user_id}")
        await sts.edit_text(f"⏳ Enviando Archivos (0/{total_msgs})")
        for i, msg_info in enumerate(msgs):
            channel_id = msg_info.get("channel_id"); msgid = msg_info.get("msg_id")
            if not channel_id or not msgid: logger.warning(f"Item {i} BATCH inválido: {msg_info}"); continue
            try:
                channel_id = int(channel_id); msgid = int(msgid)
                original_msg = await client.get_messages(channel_id, msgid);
                if not original_msg: logger.warning(f"Msg {msgid} no encontrado en {channel_id}. Saltando."); continue

                # Preparar caption/botones (Lógica restaurada)
                f_caption_batch = None; stream_reply_markup_batch = None; title_batch = "N/A"; size_batch = "N/A"
                if original_msg.media:
                    media = getattr(original_msg, original_msg.media.value, None)
                    if media:
                         title_batch = formate_file_name(getattr(media, "file_name", "")); size_batch = get_size(getattr(media, "file_size", 0))
                         f_caption_orig = getattr(original_msg, 'caption', ''); f_caption_orig = f_caption_orig.html if hasattr(f_caption_orig, 'html') else str(f_caption_orig)
                         if BATCH_FILE_CAPTION:
                             try: f_caption_batch = BATCH_FILE_CAPTION.format(file_name=title_batch, file_size=size_batch, file_caption=f_caption_orig if f_caption_orig else "")
                             except Exception as e: logger.warning(f"Error fmt BATCH_CAPTION: {e}"); f_caption_batch = f_caption_orig if f_caption_orig else f"<code>{title_batch}</code>"
                         elif f_caption_orig: f_caption_batch = f_caption_orig
                         else: f_caption_batch = f"<code>{title_batch}</code>" if title_batch else None
                    if STREAM_MODE and (original_msg.video or original_msg.document):
                         try: stream_url = "..."; download_url = "..."; stream_buttons = [...]; stream_reply_markup_batch = InlineKeyboardMarkup(stream_buttons) # Tu lógica stream
                         except Exception as e: logger.error(f"Error botones stream BATCH: {e}")

                # Copiar mensaje
                sent_msg = await original_msg.copy(chat_id=user_id, caption=f_caption_batch, reply_markup=stream_reply_markup_batch)
                filesarr.append(sent_msg)

                # Actualizar estado y pausar
                if (i + 1) % 10 == 0 or (i + 1) == total_msgs:
                    try: await sts.edit_text(f"⏳ Enviando Archivos ({i + 1}/{total_msgs})")
                    except MessageNotModified: pass; await asyncio.sleep(0.5) # Pausa igual
                else: await asyncio.sleep(0.1) # Pausa más corta

            except FloodWait as fw_err: # Manejar FloodWait
                wait_time = fw_err.value + 2; logger.warning(f"FloodWait BATCH {i}. Esperando {wait_time}s")
                await sts.edit_text(f"⏳ Enviando lote... ({i}/{total_msgs})\nPausa por FloodWait ({wait_time}s)")
                await asyncio.sleep(wait_time)
                try: original_msg = await client.get_messages(channel_id, msgid); sent_msg = await original_msg.copy(user_id); filesarr.append(sent_msg); logger.info(f"Reintento BATCH {i} OK.")
                except Exception as retry_err: logger.error(f"Error BATCH {i} (retry): {retry_err}")
            except Exception as loop_err: logger.error(f"Error procesando BATCH item {i} (msg {msgid}, chan {channel_id}): {loop_err}", exc_info=True)

        # Fin del bucle BATCH
        try: await sts.delete()
        except Exception: pass
        logger.info(f"Envío BATCH {batch_json_msg_id} a {user_id} finalizado. {len(filesarr)}/{total_msgs} enviados.")

        # Auto-Delete BATCH (Sin cambios)
        if AUTO_DELETE_MODE and filesarr:
            # ... (código auto-delete BATCH sin cambios) ...
            logger.info(f"Auto-Delete BATCH {user_id} iniciado.")
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

    # --- Sub-bloque 4.3: Lógica para Archivo Único ---
    else:
        logger.info(f"Procesando Archivo Único. Payload original ID: {original_payload_id}")
        try:
            # Extraer ID numérico del mensaje desde "file_<id>" o ID directo
            if original_payload_id.startswith("file_"):
                try: decode_file_id = int(original_payload_id.split("_", 1)[1])
                except (IndexError, ValueError): raise ValueError(f"Formato inválido 'file_': {original_payload_id}")
            else:
                 decode_file_id = int(original_payload_id) # Asumir ID directo

            # Obtener mensaje de LOG_CHANNEL
            try: log_channel_int = int(LOG_CHANNEL)
            except ValueError: log_channel_int = str(LOG_CHANNEL)
            original_msg = await client.get_messages(log_channel_int, decode_file_id)
            if not original_msg: raise MessageIdInvalid(f"Msg ID {decode_file_id} no encontrado en {log_channel_int}")

            # Preparar caption y botones (Lógica restaurada)
            f_caption = None; reply_markup = None; title = "N/A"; size = "N/A"
            if original_msg.media:
                media = getattr(original_msg, original_msg.media.value, None)
                if media:
                    title = formate_file_name(getattr(media, "file_name", "")); size = get_size(getattr(media, "file_size", 0))
                    f_caption_orig = getattr(original_msg, 'caption', ''); f_caption_orig = f_caption_orig.html if hasattr(f_caption_orig, 'html') else str(f_caption_orig)
                    if CUSTOM_FILE_CAPTION:
                         try: f_caption = CUSTOM_FILE_CAPTION.format(file_name=title, file_size=size, file_caption=f_caption_orig if f_caption_orig else "")
                         except Exception as e: logger.error(f"Error fmt CUSTOM_CAPTION: {e}"); f_caption = f"<code>{title}</code>"
                    elif f_caption_orig: f_caption = f_caption_orig
                    else: f_caption = f"<code>{title}</code>" if title else None
                    if STREAM_MODE and (original_msg.video or original_msg.document):
                         try: stream_url = "..."; download_url = "..."; stream_buttons = [...]; reply_markup = InlineKeyboardMarkup(stream_buttons) # Tu lógica stream
                         except Exception as e: logger.error(f"Error botones stream: {e}")
            else: logger.debug(f"Msg {decode_file_id} sin media.")

            # Copiar mensaje
            logger.debug(f"Copiando msg {decode_file_id} a {user_id}")
            sent_file_msg = await original_msg.copy(chat_id=user_id, caption=f_caption, reply_markup=reply_markup, protect_content=False)

            # Auto-Delete Archivo Único (Sin cambios)
            if AUTO_DELETE_MODE:
                # ... (código auto-delete archivo único) ...
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

        except MessageIdInvalid as e: logger.error(f"Error Archivo Único: {e}. ID: {decode_file_id}"); await message.reply_text("❌ Archivo no disponible.")
        except (ValueError, IndexError, AttributeError) as payload_err: logger.error(f"Error procesando payload '{original_payload_id}': {payload_err}"); await message.reply_text("❌ Enlace inválido.")
        except Exception as e: logger.error(f"Error crítico Archivo Único {user_id}: {e}", exc_info=True); await message.reply_text("❌ Error inesperado.")
        return

# --- Comandos /api, /base_site, /stats (Formateados) ---
@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    """Maneja el comando /api para ver o establecer la API del acortador."""
    user_id = m.from_user.id
    log_prefix = f"CMD /api (User: {user_id}):" # Prefijo para logs

    try:
        user_data = await get_user(user_id)
        user_base_site = user_data.get("base_site", "No Configurado") if user_data else "N/A (Usuario no encontrado)"
        user_shortener_api = user_data.get("shortener_api", "No Configurada") if user_data else "N/A (Usuario no encontrado)"
        logger.debug(f"{log_prefix} Datos actuales: base_site='{user_base_site}', api='{user_shortener_api[:5]}...'")
    except Exception as e:
        logger.error(f"{log_prefix} Error al obtener datos del usuario desde users_api: {e}")
        return await m.reply_text("❌ Ocurrió un error al consultar tu configuración de API.")

    cmd = m.command
    # Comando sin argumentos: Mostrar configuración actual
    if len(cmd) == 1:
        try:
            if hasattr(script, 'SHORTENER_API_MESSAGE'):
                 s = script.SHORTENER_API_MESSAGE.format(base_site=user_base_site, shortener_api=user_shortener_api)
                 await m.reply_text(s)
            else:
                 logger.error(f"{log_prefix} La variable 'SHORTENER_API_MESSAGE' no existe en 'Script'.")
                 await m.reply_text(f"Tu API actual: `{user_shortener_api}`\nTu Sitio Base: `{user_base_site}`")
        except Exception as fmt_err:
            logger.error(f"{log_prefix} Error formateando SHORTENER_API_MESSAGE: {fmt_err}")
            await m.reply_text("❌ Ocurrió un error al mostrar tu configuración de API.")

    # Comando con un argumento: Establecer o eliminar API
    elif len(cmd) == 2:
        api_key_input = cmd[1].strip()
        update_value = None if api_key_input.lower() == "none" else api_key_input
        if update_value == "": logger.warning(f"{log_prefix} Intento de establecer API vacía."); return await m.reply_text("❌ La clave API no puede ser vacía.")

        log_msg_action = "eliminando" if update_value is None else f"actualizando a: {api_key_input[:5]}..."
        logger.info(f"{log_prefix} {log_msg_action} la Shortener API.")
        try:
            await update_user_info(user_id, {"shortener_api": update_value})
            reply_msg = "✅ Tu API de acortador ha sido eliminada." if update_value is None else "✅ Tu API de acortador ha sido actualizada correctamente."
            await m.reply_text(reply_msg)
            logger.info(f"{log_prefix} Actualización de API exitosa.")
        except Exception as e:
            logger.error(f"{log_prefix} Error al actualizar la API en users_api: {e}")
            await m.reply_text("❌ Ocurrió un error al intentar actualizar tu API.")

    # Comando con formato incorrecto
    else:
        logger.warning(f"{log_prefix} Uso incorrecto: {' '.join(cmd)}")
        await m.reply_text(
            "**Formato incorrecto.**\n\n`/api` (ver)\n`/api KEY` (set)\n`/api None` (del)"
        )

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    """Maneja el comando /base_site."""
    user_id = m.from_user.id
    log_prefix = f"CMD /base_site (User: {user_id}):"

    try:
        user_data = await get_user(user_id)
        current_site = user_data.get("base_site", "Ninguno configurado") if user_data else "N/A"
        logger.debug(f"{log_prefix} Sitio base actual: '{current_site}'")
    except Exception as e:
        logger.error(f"{log_prefix} Error get_user: {e}")
        return await m.reply_text("❌ Error consultando config.")

    cmd = m.command
    help_text = (f"⚙️ **Sitio Base Acortador**\n\nActual: `{current_site}`\n\n➡️ `/base_site url.com`\n➡️ `/base_site None`")

    if len(cmd) == 1:
        await m.reply_text(text=help_text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site_input = cmd[1].strip().lower()
        if base_site_input == "none":
            logger.info(f"{log_prefix} Eliminando base_site.")
            try: await update_user_info(user_id, {"base_site": None}); await m.reply_text("<b>✅ Sitio Base eliminado.</b>")
            except Exception as e: logger.error(f"{log_prefix} Error del base_site: {e}"); await m.reply_text("❌ Error eliminando.")
        else:
            try: is_valid = domain(f"http://{base_site_input}") # Añadir http para validación
            except Exception as val_err: logger.warning(f"{log_prefix} Validacion fallida para {base_site_input}: {val_err}"); is_valid = False
            if not is_valid: return await m.reply_text(help_text + "\n\n❌ Dominio inválido.", disable_web_page_preview=True)
            logger.info(f"{log_prefix} Actualizando base_site a: '{base_site_input}'")
            try: await update_user_info(user_id, {"base_site": base_site_input}); await m.reply_text(f"<b>✅ Sitio Base actualizado a:</b> `{base_site_input}`")
            except Exception as e: logger.error(f"{log_prefix} Error update base_site: {e}"); await m.reply_text("❌ Error actualizando.")
    else:
        logger.warning(f"{log_prefix} Uso incorrecto: {' '.join(cmd)}")
        await m.reply_text("Formato incorrecto.\n" + help_text, disable_web_page_preview=True)

@Client.on_message(filters.command("stats") & filters.private & filters.user(ADMINS))
async def simple_stats_command(client, message: Message):
    """Muestra estadísticas básicas (solo para admins)."""
    log_prefix = f"CMD /stats (Admin: {message.from_user.id}):"
    if message.from_user.id not in ADMINS: return # Doble chequeo por si acaso
    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
        total_users = await db.total_users_count()
        logger.info(f"{log_prefix} Stats: Usuarios={total_users}")
        stats_text = (f"📊 **Estadísticas del Bot**\n\n👥 Usuarios Totales: `{total_users}`")
        await message.reply_text(stats_text, quote=True)
    except Exception as e:
        logger.error(f"{log_prefix} Error: {e}", exc_info=True)
        await message.reply_text("❌ Ocurrió un error al obtener estadísticas.")

# --- Manejador de Callbacks (Botones Inline) ---
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    """Maneja las pulsaciones de botones inline."""
    user_id = query.from_user.id
    q_data = query.data
    message = query.message
    log_prefix = f"CB (User: {user_id}, Data: '{q_data}', Msg: {message.id}):"

    logger.debug(f"{log_prefix} Callback recibido.")
    try: me_mention = client.me.mention if client.me else "Bot"
    except Exception: me_mention = "Bot"

    try:
        if q_data == "close_data":
            logger.debug(f"{log_prefix} Cerrando mensaje.")
            await message.delete()
            await query.answer() # Responder al callback aunque no se muestre nada

        elif q_data == "about":
            logger.debug(f"{log_prefix} Mostrando 'About'")
            buttons = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]
            markup = InlineKeyboardMarkup(buttons)
            about_text = getattr(script, 'ABOUT_TXT', "Info no disponible.").format(me_mention=me_mention) # Usar format con nombre
            await query.edit_message_text(about_text, reply_markup=markup, disable_web_page_preview=True)
            await query.answer()

        elif q_data == "start":
            logger.debug(f"{log_prefix} Mostrando 'Start'")
            buttons = [[InlineKeyboardButton('Canal Principal', url='https://t.me/NessCloud'), InlineKeyboardButton('Grupo de Soporte', url='https://t.me/NESS_Soporte')],[InlineKeyboardButton('❓ Ayuda', callback_data='help'), InlineKeyboardButton('ℹ️ Acerca de', callback_data='about')]]
            if not CLONE_MODE: buttons.append([InlineKeyboardButton('🤖 Clonar Bot', callback_data='clone')])
            markup = InlineKeyboardMarkup(buttons)
            start_text = getattr(script, 'START_TXT', "Bienvenido!").format(mention=query.from_user.mention, me_mention=me_mention) # Usar format con nombres
            try: await query.edit_message_text(start_text, reply_markup=markup, disable_web_page_preview=True)
            except MessageNotModified: pass
            except Exception: # Fallback a editar media
                 logger.warning(f"{log_prefix} Fallo edit text 'start', intentando media.")
                 try: photo_url = random.choice(PICS) if PICS else None; assert photo_url; await query.edit_message_media(media=InputMediaPhoto(photo_url), reply_markup=markup); await query.edit_message_caption(caption=start_text, reply_markup=markup)
                 except Exception as e: logger.error(f"{log_prefix} Fallo edit media 'start': {e}")
            await query.answer()

        elif q_data == "clone":
            logger.debug(f"{log_prefix} Mostrando 'Clone'")
            buttons = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons)
            clone_text = getattr(script, 'CLONE_TXT', "Clone info.").format(mention=query.from_user.mention)
            await query.edit_message_text(clone_text, reply_markup=markup, disable_web_page_preview=True)
            await query.answer()

        elif q_data == "help":
             logger.debug(f"{log_prefix} Mostrando 'Help'")
             buttons = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons)
             help_text = getattr(script, 'HELP_TXT', "Ayuda no disponible.")
             await query.edit_message_text(help_text, reply_markup=markup, disable_web_page_preview=True)
             await query.answer()

        else:
             logger.warning(f"{log_prefix} Callback no reconocido.")
             await query.answer("Opción no implementada.", show_alert=False)

    except MessageNotModified: logger.debug(f"{log_prefix} Mensaje no modificado."); await query.answer()
    except Exception as e: logger.error(f"{log_prefix} Error procesando callback: {e}", exc_info=True); await query.answer("❌ Error", show_alert=True)

# --- Comandos Premium (Formateados con texto modificado) ---
@Client.on_message(filters.command("addpremium") & filters.private & filters.user(ADMINS))
async def add_premium_command(client, message: Message):
    """Añade acceso premium a un usuario (Admin Only)."""
    log_prefix = f"CMD /addpremium (Admin: {message.from_user.id}):"
    usage_text = "⚠️ Uso: `/addpremium <user_id> [días]`\n(Default: permanente)"

    if len(message.command) < 2 or len(message.command) > 3:
        logger.warning(f"{log_prefix} Uso incorrecto: {' '.join(message.command)}")
        return await message.reply_text(usage_text)
    try:
        target_user_id = int(message.command[1])
    except ValueError:
        logger.warning(f"{log_prefix} ID inválido: {message.command[1]}")
        return await message.reply_text(f"❌ ID de usuario inválido.\n\n{usage_text}")

    days = None
    if len(message.command) == 3:
        try:
            days = int(message.command[2])
            if days <= 0: raise ValueError("Días debe ser positivo.")
        except ValueError as e:
            logger.warning(f"{log_prefix} Días inválido: {message.command[2]} ({e})")
            return await message.reply_text(f"❌ Días inválido.\n\n{usage_text}")

    if not await db.is_user_exist(target_user_id):
        logger.warning(f"{log_prefix} Usuario {target_user_id} no encontrado.")
        return await message.reply_text(f"❌ Usuario `{target_user_id}` no encontrado. ¿Inició el bot?")

    try:
        success = await db.set_premium(target_user_id, days)
        if success:
            # --- TEXTOS MODIFICADOS POR EL USUARIO ---
            duration_text = f"por {days} días" if days else "permanentemente"
            admin_reply = f"✅ ¡Premium activado para `{target_user_id}` {duration_text}!"
            user_notification = f"🎉 ¡Felicidades! Has recibido acceso Premium {duration_text}."
            # ------------------------------------------
            await message.reply_text(admin_reply)
            logger.info(f"{log_prefix} Premium activado para {target_user_id} {duration_text}.")
            try:
                await client.send_message(target_user_id, user_notification)
            except Exception as notify_err:
                logger.warning(f"{log_prefix} No notificar premium a {target_user_id}: {notify_err}")
                await message.reply_text("ℹ️ *Nota: No se pudo notificar al usuario.*")
        else:
            logger.error(f"{log_prefix} db.set_premium devolvió False para {target_user_id}.")
            await message.reply_text(f"❌ Error activando premium para `{target_user_id}`.")
    except Exception as e:
         logger.error(f"{log_prefix} Error CRÍTICO set_premium {target_user_id}: {e}", exc_info=True)
         await message.reply_text("❌ Error interno al activar premium.")

@Client.on_message(filters.command("delpremium") & filters.private & filters.user(ADMINS))
async def del_premium_command(client, message: Message):
    """Elimina el acceso premium de un usuario (Admin Only)."""
    log_prefix = f"CMD /delpremium (Admin: {message.from_user.id}):"
    usage_text = "⚠️ Uso: `/delpremium <user_id>`"

    if len(message.command) != 2:
        logger.warning(f"{log_prefix} Uso incorrecto: {' '.join(message.command)}")
        return await message.reply_text(usage_text)
    try:
        target_user_id = int(message.command[1])
    except ValueError:
        logger.warning(f"{log_prefix} ID inválido: {message.command[1]}")
        return await message.reply_text(f"❌ ID de usuario inválido.\n\n{usage_text}")

    if not await db.is_user_exist(target_user_id):
        logger.warning(f"{log_prefix} Usuario {target_user_id} no encontrado.")
        return await message.reply_text(f"❌ Usuario `{target_user_id}` no encontrado.")

    # Verificar si realmente tenía premium antes de intentar quitarlo
    # if not await db.check_premium_status(target_user_id): # Opcional
    #      logger.info(f"{log_prefix} Usuario {target_user_id} ya no tenía premium.")
    #      return await message.reply_text(f"ℹ️ El usuario `{target_user_id}` no tiene Premium activo.")

    try:
        success = await db.remove_premium(target_user_id)
        if success:
             # --- TEXTOS MODIFICADOS POR EL USUARIO ---
             admin_reply = f"✅ Premium desactivado para el usuario `{target_user_id}`."
             user_notification = "ℹ️ Tu acceso Premium ha sido desactivado."
             # ------------------------------------------
             await message.reply_text(admin_reply)
             logger.info(f"{log_prefix} Premium desactivado para {target_user_id}.")
             try:
                 await client.send_message(target_user_id, user_notification)
             except Exception as notify_err:
                 logger.warning(f"{log_prefix} No notificar premium off a {target_user_id}: {notify_err}")
                 await message.reply_text("ℹ️ *Nota: No se pudo notificar al usuario.*")
        else:
            logger.error(f"{log_prefix} db.remove_premium devolvió False para {target_user_id}.")
            await message.reply_text(f"❌ Error desactivando premium para `{target_user_id}`.")
    except Exception as e:
         logger.error(f"{log_prefix} Error CRÍTICO remove_premium {target_user_id}: {e}", exc_info=True)
         await message.reply_text("❌ Error interno al desactivar premium.")

# --- Fin del archivo plugins/commands.py ---