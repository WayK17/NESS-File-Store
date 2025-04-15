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
    CallbackQuery, InputMediaPhoto, WebAppInfo # Importaciones específicas
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
    logging.error("¡ADVERTENCIA! Funciones no encontradas en utils.py. Algunas características pueden fallar.")
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
logger = logging.getLogger(__name__) # <--- Corregido 'name' por '__name__' (práctica estándar)
logger.setLevel(logging.INFO)

# Variable global
BATCH_FILES = {}

# --- Funciones Auxiliares ---

def get_size(size):
    """Convierte bytes a formato legible (KB, MB, GB...)."""
    try:
        units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
        size = float(size)
        i = 0
        while size >= 1024.0 and i < len(units) - 1: i += 1; size /= 1024.0
        return "%.2f %s" % (size, units[i])
    except Exception as e: logger.error(f"Error en get_size: {e}"); return "N/A"

def formate_file_name(file_name):
    """Limpia un nombre de archivo."""
    if not isinstance(file_name, str): return "archivo_desconocido"
    original_name = file_name
    try:
        # Eliminación de caracteres potencialmente problemáticos (ajusta según necesidad)
        file_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', file_name) # Eliminación más robusta
        file_name = re.sub(r'[‘’“”]', "'", file_name) # Normalizar comillas
        file_name = re.sub(r'\s+', ' ', file_name).strip() # Normalizar espacios

        # Filtrar partes no deseadas (ej. URLs, menciones)
        parts = file_name.split()
        filtered_parts = filter(lambda x: x and not x.startswith(('http', '@', 'www.')), parts)
        cleaned_name = ' '.join(filtered_parts).strip()

        return cleaned_name if cleaned_name else original_name # Devolver original si queda vacío
    except Exception as e: logger.error(f"Error formateando nombre '{original_name}': {e}"); return original_name

# --- Manejador del Comando /start ---

@Client.on_message(filters.command("start") & filters.incoming & filters.private)
async def start(client: Client, message: Message):
    """Maneja el comando /start."""
    user_id = message.from_user.id; first_name = message.from_user.first_name; user_mention = message.from_user.mention
    try:
        bot_username = client.me.username
    except AttributeError: # Manejo por si client.me no está disponible inmediatamente
        bot_info = await client.get_me()
        bot_username = bot_info.username
        client.me = bot_info # Cachear para futuras referencias si es necesario

    logger.info(f"/start de {user_id} ({user_mention})")

    # Registro de Usuario Nuevo
    if not await db.is_user_exist(user_id):
        logger.info(f"Usuario {user_id} nuevo. Añadiendo.")
        await db.add_user(user_id, first_name)
        if LOG_CHANNEL:
            try: await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(user_id=user_id, mention=user_mention)) # Usar nombres de clave explícitos
            except Exception as log_err: logger.error(f"Error enviando log a LOG_CHANNEL {LOG_CHANNEL}: {log_err}")
        else: logger.warning("LOG_CHANNEL no definido.")

    # /start sin Payload (Bienvenida)
    if len(message.command) == 1:
        logger.info(f"Enviando bienvenida normal a {user_id}")
        buttons_list = [
            [InlineKeyboardButton('Únete a Nuestro Canal', url='https://t.me/NessCloud')],
            [InlineKeyboardButton('⚠️ Grupo de Soporte', url='https://t.me/NESS_Soporte')]
            # --- Botón Clonar ELIMINADO ---
        ]
        reply_markup = InlineKeyboardMarkup(buttons_list); me = client.me
        start_text = script.START_TXT.format(mention=user_mention, me_mention=me.mention)
        try:
            photo_url = random.choice(PICS) if PICS else None
            if photo_url: await message.reply_photo(photo=photo_url, caption=start_text, reply_markup=reply_markup)
            else: await message.reply_text(text=start_text, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as start_err: logger.error(f"Error enviando bienvenida {user_id}: {start_err}"); await message.reply_text(text=start_text, reply_markup=reply_markup, disable_web_page_preview=True)
        return

    # --- PROCESAMIENTO CON PAYLOAD ---
    payload_encoded_full = message.command[1]
    logger.info(f"/start con payload '{payload_encoded_full}' de {user_id}")

    # Borrar mensaje "Únete" anterior
    try:
        user_info = await db.get_user_info(user_id); pending_msg_id = user_info.get("pending_join_msg_id") if user_info else None
        if pending_msg_id: logger.debug(f"Borrando msg {pending_msg_id} para {user_id}"); await client.delete_messages(user_id, pending_msg_id); await db.update_user_info(user_id, {"pending_join_msg_id": None})
    except MessageIdInvalid: logger.info(f"Msg 'Únete' {pending_msg_id} ya no existía."); await db.update_user_info(user_id, {"pending_join_msg_id": None})
    except Exception as db_err: logger.error(f"Error DB borrando msg pendiente {user_id}: {db_err}")

    # Verificación Force Subscribe
    should_skip_fsub = not FORCE_SUB_ENABLED or (SKIP_FORCE_SUB_FOR_ADMINS and user_id in ADMINS)
    if not should_skip_fsub and FORCE_SUB_CHANNEL and FORCE_SUB_INVITE_LINK:
        try:
            # Asegurarse que FORCE_SUB_CHANNEL es un ID/username válido
            if not isinstance(FORCE_SUB_CHANNEL, (int, str)):
                 raise TypeError(f"FORCE_SUB_CHANNEL debe ser int o str, no {type(FORCE_SUB_CHANNEL)}")

            if not await check_user_membership(client, user_id, FORCE_SUB_CHANNEL):
                logger.info(f"User {user_id} NO miembro {FORCE_SUB_CHANNEL}. Mostrando msg ForceSub.")
                buttons = [[InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)], [InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{bot_username}?start={payload_encoded_full}")]]
                join_message = await message.reply_text(script.FORCE_MSG.format(mention=user_mention), reply_markup=InlineKeyboardMarkup(buttons), quote=True, disable_web_page_preview=True)
                await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id}); return
        except ChatAdminRequired: logger.error(f"Error: Bot NO admin en ForceSub channel {FORCE_SUB_CHANNEL}")
        except UserNotParticipant: # Añadido manejo explícito
            logger.info(f"User {user_id} NO miembro {FORCE_SUB_CHANNEL} (UserNotParticipant capturado). Mostrando msg ForceSub.")
            buttons = [[InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)], [InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{bot_username}?start={payload_encoded_full}")]]
            join_message = await message.reply_text(script.FORCE_MSG.format(mention=user_mention), reply_markup=InlineKeyboardMarkup(buttons), quote=True, disable_web_page_preview=True)
            await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id}); return
        except TypeError as te: logger.error(f"Error de tipo en ForceSubscribe (¿Configuración incorrecta?): {te}")
        except Exception as fs_err: logger.error(f"Error CRÍTICO ForceSubscribe {user_id}: {fs_err}", exc_info=True)

    # Decodificación y Chequeos Premium/Verify
    logger.info(f"User {user_id} pasó chequeos iniciales. Procesando payload: {payload_encoded_full}")
    is_batch = False; base64_to_decode = payload_encoded_full; link_type = "normal"; original_payload_id = ""
    if payload_encoded_full.startswith("BATCH-"): is_batch = True; base64_to_decode = payload_encoded_full[len("BATCH-"):]
    try:
        # Añadir padding si es necesario
        padding = 4 - (len(base64_to_decode) % 4)
        if padding == 4: padding = 0 # Si ya es múltiplo de 4, no añadir padding
        base64_to_decode += "=" * padding

        payload_decoded = base64.urlsafe_b64decode(base64_to_decode).decode("ascii")
        original_payload_id = payload_decoded # Guardar ID decodificado original

        # Determinar tipo de enlace
        if payload_decoded.startswith("premium:"): link_type = "premium"; original_payload_id = payload_decoded[len("premium:"):]
        elif payload_decoded.startswith("normal:"): link_type = "normal"; original_payload_id = payload_decoded[len("normal:"):]
        elif payload_decoded.startswith("verify-"): link_type = "special"; original_payload_id = payload_decoded # Mantener payload completo para verify
        else: logger.warning(f"Payload '{payload_decoded}' sin prefijo reconocido. Tratando como normal."); link_type = "normal" # Asumir normal si no hay prefijo

        logger.debug(f"Tipo: {link_type}. ID procesado: {original_payload_id}") # Log del ID que se usará
    except (base64.binascii.Error, UnicodeDecodeError) as decode_err: # Capturar errores específicos
        logger.error(f"Error decodificando base64 '{base64_to_decode}' (Payload original: '{payload_encoded_full}'): {decode_err}")
        return await message.reply_text("❌ Enlace inválido o corrupto.")
    except Exception as e: # Capturar cualquier otro error inesperado
        logger.error(f"Error inesperado procesando payload '{payload_encoded_full}': {e}", exc_info=True)
        return await message.reply_text("❌ Error procesando el enlace.")

    # Chequeo Premium
    is_premium_user = await db.check_premium_status(user_id); is_admin_user = user_id in ADMINS
    logger.debug(f"User {user_id}: premium={is_premium_user}, admin={is_admin_user}")
    if link_type == "premium" and not is_premium_user and not is_admin_user:
        logger.info(f"User normal {user_id} denegado para link premium '{original_payload_id}'.")
        try: await message.reply_text(script.PREMIUM_REQUIRED_MSG.format(mention=user_mention), quote=True)
        except AttributeError: await message.reply_text("❌ Acceso denegado. Este contenido requiere una cuenta Premium.", quote=True) # Mensaje más claro
        return
    elif link_type == "premium" and is_admin_user and not is_premium_user: logger.info(f"Admin {user_id} accediendo a link premium como admin.")

    # Chequeo Verificación
    try:
        apply_verify_check = VERIFY_MODE and link_type != "special" # No verificar links 'verify-'
        if apply_verify_check and not await check_verification(client, user_id):
            logger.info(f"User {user_id} necesita verificación para link tipo {link_type}.")
            # Construir URL de retorno correcta (con el payload original)
            verify_url = await get_token(client, user_id, f"https://t.me/{bot_username}?start={payload_encoded_full}") # Usar payload ENCODED
            if "ERROR" in verify_url: logger.error(f"Fallo get_token para {user_id}"); return await message.reply_text("🔒 Verificación Requerida\n\n(Hubo un error generando tu enlace de verificación. Por favor, inténtalo de nuevo o contacta soporte.)", protect_content=True)

            btn_list = [[InlineKeyboardButton("➡️ Verificar Ahora ⬅️", url=verify_url)]];
            if VERIFY_TUTORIAL: btn_list.append([InlineKeyboardButton("❓ Cómo Verificar", url=VERIFY_TUTORIAL)])
            await message.reply_text("🔒 **Verificación Requerida**\n\nPara acceder a este contenido, por favor completa una rápida verificación usando el botón de abajo.", protect_content=True, reply_markup=InlineKeyboardMarkup(btn_list)); return
    except Exception as e: logger.error(f"Error durante check_verification para {user_id}: {e}", exc_info=True); return await message.reply_text(f"❌ Error interno durante la verificación: {e}")

    # --- Procesamiento Final del Payload ---
    logger.info(f"User {user_id} ({link_type}) procesando ID '{original_payload_id}' (Batch: {is_batch})")

    # Lógica para 'verify-'
    if link_type == "special" and original_payload_id.startswith("verify-"):
        logger.debug(f"Manejando 'verify' payload para {user_id}")
        try:
            parts = original_payload_id.split("-")
            if len(parts) != 3: raise ValueError("Formato de token inválido")
            _, verify_userid_str, token = parts
            verify_userid = int(verify_userid_str)
            if user_id != verify_userid: raise PermissionError("Token no pertenece a este usuario") # Más específico
            if not await check_token(client, verify_userid, token): raise ValueError("Token inválido o expirado") # Más específico

            await verify_user(client, verify_userid, token)
            await message.reply_text(f"✅ ¡Hola {user_mention}! Tu verificación ha sido completada exitosamente.", protect_content=True)
            logger.info(f"User {verify_userid} verificado OK con token.")
        except (ValueError, IndexError, PermissionError) as verify_e: # Capturar errores esperados
            logger.warning(f"Error procesando token '{original_payload_id}' para {user_id}: {verify_e}")
            await message.reply_text(f"❌ **Error de Verificación:** {verify_e}. Por favor, intenta generar un nuevo enlace de verificación.", protect_content=True)
        except Exception as generic_verify_e: # Capturar errores inesperados
            logger.error(f"Error inesperado procesando verify '{original_payload_id}' para {user_id}: {generic_verify_e}", exc_info=True)
            await message.reply_text("❌ Ocurrió un error inesperado durante la verificación. Contacta soporte.", protect_content=True)
        return

    # Lógica para BATCH
    elif is_batch:
        batch_json_msg_id = original_payload_id # ID del mensaje que contiene el JSON
        logger.info(f"Procesando BATCH. ID JSON: {batch_json_msg_id}")
        sts = await message.reply_text("⏳ **Procesando lote...** Por favor espera.", quote=True)
        msgs = BATCH_FILES.get(batch_json_msg_id)

        # Cargar JSON si no está en caché
        if not msgs:
             file_path = None
             # --- SECCIÓN CORREGIDA ---
             try:
                 # Intenta convertir LOG_CHANNEL a entero si es numérico (incluyendo negativos)
                 log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL

                 logger.debug(f"Descargando JSON BATCH msg {batch_json_msg_id} de {log_channel_int}")

                 # Obtiene el mensaje que contiene el archivo JSON
                 batch_list_msg = await client.get_messages(log_channel_int, int(batch_json_msg_id))

                 # Asegura que el mensaje existe y tiene un documento
                 if not (batch_list_msg and batch_list_msg.document): # Comprobación más explícita
                     raise FileNotFoundError(f"Mensaje {batch_json_msg_id} en {log_channel_int} no encontrado o no es un documento.")

                 # Descarga el archivo JSON
                 logger.debug(f"Descargando documento {batch_list_msg.document.file_id}...")
                 file_path = await client.download_media(
                     batch_list_msg.document.file_id,
                     file_name=f"./batch_{batch_json_msg_id}.json" # Usar un prefijo de directorio temporal si es posible
                 )
                 logger.debug(f"Archivo JSON descargado en: {file_path}")

                 # Abre y lee el archivo JSON
                 with open(file_path, 'r', encoding='utf-8') as fd:
                     msgs = json.load(fd)

                 # Almacena los mensajes cargados en caché
                 BATCH_FILES[batch_json_msg_id] = msgs
                 logger.info(f"BATCH {batch_json_msg_id} cargado desde archivo ({len(msgs)} items) y cacheado.")

             # --- FIN SECCIÓN CORREGIDA ---
             except FileNotFoundError as e:
                 logger.error(f"Error BATCH: {e}. No se encontró el archivo JSON o el mensaje asociado ({batch_json_msg_id}).")
                 return await sts.edit_text(f"❌ Error: La información del lote ({batch_json_msg_id}) no se pudo encontrar o no es válida.")
             except (json.JSONDecodeError, TypeError) as e: # TypeError puede ocurrir si el contenido no es JSON válido
                 logger.error(f"Error BATCH: JSON inválido o corrupto ({batch_json_msg_id}): {e}")
                 return await sts.edit_text("❌ Error: La información del lote está corrupta o tiene un formato incorrecto.")
             except ValueError: # Capturar error si batch_json_msg_id no es un entero válido
                  logger.error(f"Error BATCH: ID de mensaje inválido: {batch_json_msg_id}")
                  return await sts.edit_text("❌ Error: Identificador de lote inválido.")
             except MessageIdInvalid: # Capturar si el mensaje no existe en Telegram
                  logger.error(f"Error BATCH: Mensaje {batch_json_msg_id} no encontrado en el canal de logs {log_channel_int}.")
                  return await sts.edit_text("❌ Error: La información del lote ha expirado o no se encontró.")
             except Exception as batch_load_err: # Capturar cualquier otro error
                 logger.error(f"Error inesperado cargando BATCH {batch_json_msg_id} desde {log_channel_int}: {batch_load_err}", exc_info=True)
                 return await sts.edit_text("❌ Error inesperado al cargar la información del lote.")
             finally:
                  # Limpieza del archivo temporal si existe
                  if file_path and os.path.exists(file_path):
                      try:
                          os.remove(file_path)
                          logger.debug(f"Archivo JSON temporal {file_path} eliminado.")
                      except OSError as e:
                          logger.error(f"Error eliminando archivo JSON temporal {file_path}: {e}")

        # Validar que `msgs` es una lista no vacía después de intentar cargarla
        if not msgs or not isinstance(msgs, list):
            logger.error(f"Error BATCH: La información cargada para {batch_json_msg_id} está vacía o no es una lista.")
            # Limpiar caché si está corrupta
            if batch_json_msg_id in BATCH_FILES: del BATCH_FILES[batch_json_msg_id]
            return await sts.edit_text("❌ Error: La información del lote está vacía o tiene un formato inválido.")

        # Bucle de envío BATCH con caption restaurado
        filesarr = []; total_msgs = len(msgs); logger.info(f"Enviando {total_msgs} mensajes del BATCH {batch_json_msg_id} a {user_id}")
        await sts.edit_text(f"⏳ Enviando Archivos (0/{total_msgs})")
        for i, msg_info in enumerate(msgs):
            channel_id = msg_info.get("channel_id"); msgid = msg_info.get("msg_id")
            if not channel_id or not msgid:
                logger.warning(f"Item {i} del BATCH {batch_json_msg_id} inválido (falta channel_id o msg_id): {msg_info}"); continue
            try:
                # Convertir a enteros y obtener mensaje original
                channel_id = int(channel_id); msgid = int(msgid)
                original_msg = await client.get_messages(channel_id, msgid);
                if not original_msg:
                    logger.warning(f"Msg {msgid} no encontrado en canal {channel_id} (BATCH {batch_json_msg_id}, item {i}). Saltando."); continue

                # Preparar caption/botones BATCH (Lógica restaurada y mejorada)
                f_caption_batch = None; stream_reply_markup_batch = None; title_batch = "N/A"; size_batch = "N/A"
                if original_msg.media:
                    media = getattr(original_msg, original_msg.media.value, None)
                    if media:
                         title_batch = formate_file_name(getattr(media, "file_name", "")) or f"Archivo_{i+1}" # Nombre fallback
                         size_batch = get_size(getattr(media, "file_size", 0))
                         f_caption_orig = getattr(original_msg, 'caption', ''); f_caption_orig_html = f_caption_orig.html if hasattr(f_caption_orig, 'html') else str(f_caption_orig)

                         # Usar plantilla de caption si está definida
                         if BATCH_FILE_CAPTION:
                             try: f_caption_batch = BATCH_FILE_CAPTION.format(file_name=title_batch, file_size=size_batch, file_caption=f_caption_orig_html if f_caption_orig_html else "")
                             except Exception as e: logger.warning(f"Error formateando BATCH_FILE_CAPTION: {e}"); f_caption_batch = f_caption_orig_html if f_caption_orig_html else f"<code>{title_batch}</code>"
                         # Si no hay plantilla, usar caption original o el nombre del archivo como fallback
                         elif f_caption_orig_html: f_caption_batch = f_caption_orig_html
                         else: f_caption_batch = f"<code>{title_batch}</code>"

                    # Añadir botones de Stream si está activado y el medio es compatible
                    if STREAM_MODE and original_msg.media in (enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT): # Comprobación más segura
                         try:
                             # Asegurarse que URL tiene / al final si no lo tiene
                             base_url = URL.rstrip('/') + '/'
                             # Generar hash y nombre seguro para URL
                             msg_hash = get_hash(original_msg)
                             safe_name = quote_plus(get_name(original_msg) or title_batch) # Usar nombre limpio o título

                             stream_url = f"{base_url}watch/{str(original_msg.id)}/{safe_name}?hash={msg_hash}"
                             download_url = f"{base_url}{str(original_msg.id)}/{safe_name}?hash={msg_hash}"

                             stream_buttons = [
                                 [InlineKeyboardButton("📥 Descargar", url=download_url), InlineKeyboardButton('▶️ Ver Online', url=stream_url)],
                                 [InlineKeyboardButton("🌐 Ver en Web App", web_app=WebAppInfo(url=stream_url))]
                             ]
                             stream_reply_markup_batch = InlineKeyboardMarkup(stream_buttons)
                         except Exception as e: logger.error(f"Error generando botones stream para BATCH item {i} (msg {msgid}): {e}")

                # Copiar mensaje al usuario
                sent_msg = await original_msg.copy(
                    chat_id=user_id,
                    caption=f_caption_batch,
                    reply_markup=stream_reply_markup_batch,
                    parse_mode=enums.ParseMode.HTML # Asegurar parse mode si usamos HTML en caption
                )
                filesarr.append(sent_msg)

                # Actualizar estado y pausar para evitar flood
                if (i + 1) % 10 == 0 or (i + 1) == total_msgs: # Actualizar cada 10 o al final
                    try: await sts.edit_text(f"⏳ Enviando Archivos ({i + 1}/{total_msgs})")
                    except MessageNotModified: pass
                    await asyncio.sleep(1.5) # Pausa más larga cada 10
                else:
                    await asyncio.sleep(0.5) # Pausa corta entre mensajes

            except FloodWait as fw_err: # Manejar FloodWait
                wait_time = fw_err.value + 5 # Añadir margen extra
                logger.warning(f"FloodWait en BATCH item {i}. Esperando {wait_time} segundos.")
                try: await sts.edit_text(f"⏳ Pausando por FloodWait... ({i}/{total_msgs})\nEspera {wait_time}s")
                except MessageNotModified: pass
                await asyncio.sleep(wait_time)
                # Reintentar copiar el mismo mensaje después de la espera
                try:
                    original_msg = await client.get_messages(channel_id, msgid) # Volver a obtener por si acaso
                    sent_msg = await original_msg.copy(
                        chat_id=user_id,
                        caption=f_caption_batch, # Reusar caption/markup ya preparados
                        reply_markup=stream_reply_markup_batch,
                        parse_mode=enums.ParseMode.HTML
                    )
                    filesarr.append(sent_msg)
                    logger.info(f"Reintento BATCH item {i} después de FloodWait OK.")
                except Exception as retry_err: logger.error(f"Error en reintento BATCH item {i} después de FloodWait: {retry_err}")

            except ChatWriteForbidden: # Si el bot no puede escribir al usuario
                 logger.error(f"Error BATCH: ChatWriteForbidden para user {user_id}. Abortando lote.")
                 await sts.edit_text("❌ Error: No puedo enviarte mensajes. ¿Me has bloqueado?")
                 break # Salir del bucle si no se puede escribir

            except Exception as loop_err: # Capturar otros errores en el bucle
                logger.error(f"Error procesando BATCH item {i} (Msg {msgid} en {channel_id}): {loop_err}", exc_info=True)
                try: # Intentar notificar al usuario del error en ese item
                     await client.send_message(user_id, f"⚠️ Hubo un error al procesar uno de los archivos del lote (item {i+1}). Continuando con los demás...")
                except Exception: pass # Ignorar si no se puede notificar


        # Fin del bucle BATCH
        try: await sts.delete() # Borrar mensaje de estado "Procesando..."
        except Exception: pass
        logger.info(f"Envío BATCH {batch_json_msg_id} a {user_id} finalizado. {len(filesarr)}/{total_msgs} mensajes enviados.")

        # Auto-Delete BATCH
        if AUTO_DELETE_MODE and filesarr:
            logger.info(f"Auto-Delete BATCH para {user_id} iniciado ({AUTO_DELETE} minutos).")
            try:
                 # Enviar mensaje de advertencia sobre auto-delete
                 k = await client.send_message(
                     chat_id=user_id,
                     text=(f"<blockquote><b><u>❗️❗️❗️ IMPORTANTE ❗️️❗️❗️</u></b>\n\n"
                           f"Estos archivos serán eliminados automáticamente en <b><u>{AUTO_DELETE} minutos</u> 🫥</b> "
                           f"<i>(Debido a políticas internas o de derechos de autor)</i>.\n\n"
                           f"<b><i>Por favor, guarda o reenvía los archivos importantes antes de que desaparezcan.</i></b></blockquote>"),
                     parse_mode=enums.ParseMode.HTML
                 )
                 await asyncio.sleep(AUTO_DELETE_TIME) # Esperar el tiempo configurado

                 deleted_count = 0
                 # Borrar los mensajes enviados en el lote
                 for x in filesarr:
                     try:
                         await x.delete()
                         deleted_count += 1
                     except Exception: pass # Ignorar errores al borrar mensajes individuales
                 # Editar el mensaje de advertencia para confirmar la eliminación
                 await k.edit_text(f"<b>✅ {deleted_count}/{len(filesarr)} archivos del lote anterior han sido eliminados automáticamente.</b>")
                 logger.info(f"Auto-Delete BATCH para {user_id}: {deleted_count}/{len(filesarr)} mensajes eliminados.")
            except Exception as auto_del_err: logger.error(f"Error durante Auto-Delete BATCH para {user_id}: {auto_del_err}")
        else: logger.info(f"Auto-Delete BATCH desactivado o no hubo archivos enviados para {user_id}.")
        return

    # Lógica para Archivo Único
    else:
        logger.info(f"Procesando Archivo Único. Payload original ID: {original_payload_id}")
        try:
            # Extraer ID numérico del mensaje (validando)
            decode_file_id = None
            if original_payload_id.startswith("file_"):
                try: decode_file_id = int(original_payload_id.split("_", 1)[1])
                except (IndexError, ValueError): raise ValueError(f"Formato de payload 'file_' inválido: {original_payload_id}")
            else:
                try: decode_file_id = int(original_payload_id)
                except ValueError: raise ValueError(f"Payload no es un ID numérico válido: {original_payload_id}")

            # Obtener mensaje de LOG_CHANNEL (validando canal)
            try: log_channel_int = int(LOG_CHANNEL)
            except ValueError: log_channel_int = str(LOG_CHANNEL) # Asumir que es username/link si no es int
            except TypeError: raise ValueError("LOG_CHANNEL no está configurado correctamente.") # Si LOG_CHANNEL es None o inválido

            original_msg = await client.get_messages(log_channel_int, decode_file_id)
            if not original_msg: raise MessageIdInvalid(f"Mensaje ID {decode_file_id} no encontrado en LOG_CHANNEL {log_channel_int}")

            # Preparar caption y botones (Lógica similar a BATCH pero para archivo único)
            f_caption = None; reply_markup = None; title = "N/A"; size = "N/A"
            if original_msg.media:
                media = getattr(original_msg, original_msg.media.value, None)
                if media:
                    title = formate_file_name(getattr(media, "file_name", "")) or "Archivo" # Fallback
                    size = get_size(getattr(media, "file_size", 0))
                    f_caption_orig = getattr(original_msg, 'caption', ''); f_caption_orig_html = f_caption_orig.html if hasattr(f_caption_orig, 'html') else str(f_caption_orig)

                    # Usar plantilla de caption si existe
                    if CUSTOM_FILE_CAPTION:
                         try: f_caption = CUSTOM_FILE_CAPTION.format(file_name=title, file_size=size, file_caption=f_caption_orig_html if f_caption_orig_html else "")
                         except Exception as e: logger.error(f"Error formateando CUSTOM_FILE_CAPTION: {e}"); f_caption = f"<code>{title}</code>" # Fallback
                    # Usar caption original o nombre de archivo
                    elif f_caption_orig_html: f_caption = f_caption_orig_html
                    else: f_caption = f"<code>{title}</code>"

                    # Añadir botones de Stream
                    if STREAM_MODE and original_msg.media in (enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT):
                         try:
                             base_url = URL.rstrip('/') + '/'
                             msg_hash = get_hash(original_msg)
                             safe_name = quote_plus(get_name(original_msg) or title)
                             stream_url = f"{base_url}watch/{str(original_msg.id)}/{safe_name}?hash={msg_hash}"
                             download_url = f"{base_url}{str(original_msg.id)}/{safe_name}?hash={msg_hash}"
                             stream_buttons = [
                                 [InlineKeyboardButton("📥 Descargar", url=download_url), InlineKeyboardButton('▶️ Ver Online', url=stream_url)],
                                 [InlineKeyboardButton("🌐 Ver en Web App", web_app=WebAppInfo(url=stream_url))]
                             ]
                             reply_markup = InlineKeyboardMarkup(stream_buttons)
                         except Exception as e: logger.error(f"Error generando botones stream para archivo único (msg {decode_file_id}): {e}")
            else: logger.debug(f"Mensaje {decode_file_id} en {log_channel_int} no tiene media adjunta.")

            # Copiar mensaje al usuario
            logger.debug(f"Copiando mensaje {decode_file_id} desde {log_channel_int} a {user_id}")
            sent_file_msg = await original_msg.copy(
                chat_id=user_id,
                caption=f_caption,
                reply_markup=reply_markup,
                protect_content=False, # Permitir reenvío por defecto
                parse_mode=enums.ParseMode.HTML # Asegurar parse mode si usamos HTML
            )

            # Auto-Delete Archivo Único
            if AUTO_DELETE_MODE:
                 logger.info(f"Auto-Delete para archivo único para {user_id} iniciado ({AUTO_DELETE} minutos).")
                 try:
                     # Enviar mensaje de advertencia
                     k = await client.send_message(
                         chat_id=user_id,
                         text=(f"<blockquote><b><u>❗️❗️❗️ IMPORTANTE ❗️️❗️❗️</u></b>\n\n"
                               f"Este archivo será eliminado automáticamente en <b><u>{AUTO_DELETE} minutos</u> 🫥</b> "
                               f"<i>(Debido a políticas internas o de derechos de autor)</i>.\n\n"
                               f"<b><i>Por favor, guarda o reenvía el archivo si lo necesitas.</i></b></blockquote>"),
                         parse_mode=enums.ParseMode.HTML
                     )
                     await asyncio.sleep(AUTO_DELETE_TIME) # Esperar

                     # Borrar el archivo enviado
                     try: await sent_file_msg.delete()
                     except Exception: pass # Ignorar si ya no existe
                     # Editar el mensaje de advertencia
                     try: await k.edit_text("<b>✅ El archivo anterior fue eliminado automáticamente.</b>")
                     except Exception: pass # Ignorar si no se puede editar
                     logger.info(f"Auto-Delete para archivo único completado para {user_id}.")
                 except Exception as auto_del_err: logger.error(f"Error durante Auto-Delete de archivo único para {user_id}: {auto_del_err}")
            else: logger.debug(f"Auto-Delete para archivo único desactivado para {user_id}.")
            return

        except MessageIdInvalid as e: logger.error(f"Error Archivo Único: {e}. ID: {original_payload_id} (procesado: {decode_file_id}). Canal: {log_channel_int}"); await message.reply_text("❌ Lo sentimos, este archivo ya no está disponible o el enlace ha expirado.")
        except ValueError as payload_err: logger.error(f"Error procesando payload '{original_payload_id}': {payload_err}"); await message.reply_text("❌ El enlace que has usado es inválido o tiene un formato incorrecto.")
        except ChatWriteForbidden: logger.error(f"Error Archivo Único: ChatWriteForbidden para user {user_id}."); await message.reply_text("❌ No puedo enviarte el archivo. ¿Me has bloqueado?")
        except Exception as e: logger.error(f"Error crítico procesando archivo único para {user_id} (Payload: '{original_payload_id}'): {e}", exc_info=True); await message.reply_text("❌ Ocurrió un error inesperado al procesar tu solicitud.")
        return

# --- Comandos /api, /base_site, /stats (Formateados) ---

@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    """Maneja el comando /api para ver o establecer la API del acortador."""
    user_id = m.from_user.id
    log_prefix = f"CMD /api (User: {user_id}):"
    try:
        user_data = await get_user(user_id)
        # Usar valores por defecto más claros si no existen los datos
        user_base_site = user_data.get("base_site", "No Configurado") if user_data else "Error al obtener datos"
        user_shortener_api = user_data.get("shortener_api", "No Configurada") if user_data else "Error al obtener datos"
        logger.debug(f"{log_prefix} Datos actuales: base='{user_base_site}', api='{user_shortener_api[:5]}...'")
    except Exception as e:
        logger.error(f"{log_prefix} Error obteniendo datos del usuario: {e}")
        return await m.reply_text("❌ Hubo un error al obtener tu configuración de API. Inténtalo de nuevo más tarde.")

    cmd = m.command
    # Ver configuración actual
    if len(cmd) == 1:
        try:
            # Usar un texto fallback si script.SHORTENER_API_MESSAGE no existe
            if hasattr(script, 'SHORTENER_API_MESSAGE'):
                s = script.SHORTENER_API_MESSAGE.format(base_site=user_base_site, shortener_api=user_shortener_api)
            else:
                logger.warning(f"{log_prefix} Falta script.SHORTENER_API_MESSAGE. Usando texto por defecto.")
                s = f"🔑 **Configuración del Acortador**\n\n🔗 Sitio Base: `{user_base_site}`\n\n⚙️ API Key: `{user_shortener_api}`\n\nPara cambiarla, usa `/api TU_NUEVA_API_KEY`.\nPara eliminarla, usa `/api None`."
            await m.reply_text(s)
        except Exception as fmt_err:
            logger.error(f"{log_prefix} Error formateando mensaje de API: {fmt_err}")
            await m.reply_text(f"❌ Error al mostrar la configuración.\nAPI: `{user_shortener_api}`\nSitio: `{user_base_site}`")

    # Establecer o eliminar API
    elif len(cmd) == 2:
        api_key_input = cmd[1].strip()
        # Manejar "None" para eliminar la API
        update_value = None if api_key_input.lower() == "none" else api_key_input

        # Validar que la API no sea vacía si se está estableciendo
        if update_value == "":
            logger.warning(f"{log_prefix} Intento de establecer API vacía.")
            return await m.reply_text("❌ La clave API no puede estar vacía. Si quieres eliminarla, usa `/api None`.")

        # Actualizar en la base de datos
        action = "eliminando" if update_value is None else f"actualizando a: {api_key_input[:5]}..."
        logger.info(f"{log_prefix} {action} Shortener API.")
        try:
            await update_user_info(user_id, {"shortener_api": update_value})
            reply_msg = "✅ Tu clave API del acortador ha sido eliminada." if update_value is None else "✅ Tu clave API del acortador ha sido actualizada correctamente."
            await m.reply_text(reply_msg)
            logger.info(f"{log_prefix} Actualización de API OK.")
        except Exception as e:
            logger.error(f"{log_prefix} Error actualizando API en DB: {e}")
            await m.reply_text("❌ Hubo un error al guardar tu nueva clave API. Por favor, inténtalo de nuevo.")
    # Argumentos incorrectos
    else:
        logger.warning(f"{log_prefix} Uso incorrecto del comando: {' '.join(cmd)}")
        await m.reply_text("❓ **Uso del comando /api:**\n\n`/api` - Muestra tu clave API actual.\n`/api TU_API_KEY` - Establece una nueva clave API.\n`/api None` - Elimina tu clave API actual.")

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    """Maneja el comando /base_site para configurar el dominio del acortador."""
    user_id = m.from_user.id
    log_prefix = f"CMD /base_site (User: {user_id}):"
    try:
        user_data = await get_user(user_id)
        current_site = user_data.get("base_site", "Ninguno Configurado") if user_data else "Error al obtener datos"
    except Exception as e:
        logger.error(f"{log_prefix} Error obteniendo datos del usuario: {e}")
        return await m.reply_text("❌ Hubo un error al obtener tu configuración de Sitio Base.")

    cmd = m.command
    help_text = (f"⚙️ **Configuración del Sitio Base del Acortador**\n\n"
                 f"Este es el dominio principal que se usará para tus enlaces acortados (ej: `ejemplo.com`).\n\n"
                 f"🔗 Sitio Base Actual: `{current_site}`\n\n"
                 f"➡️ Para cambiarlo: `/base_site tudominio.com`\n"
                 f"➡️ Para eliminarlo: `/base_site None`")

    # Ver configuración actual
    if len(cmd) == 1:
        await m.reply_text(text=help_text, disable_web_page_preview=True)

    # Establecer o eliminar sitio base
    elif len(cmd) == 2:
        base_site_input = cmd[1].strip().lower()

        # Eliminar sitio base
        if base_site_input == "none":
            logger.info(f"{log_prefix} Eliminando base_site.")
            try:
                await update_user_info(user_id, {"base_site": None})
                await m.reply_text("<b>✅ Sitio Base eliminado correctamente.</b>")
            except Exception as e:
                logger.error(f"{log_prefix} Error eliminando base_site en DB: {e}")
                await m.reply_text("❌ Error al eliminar el Sitio Base.")
        # Establecer nuevo sitio base
        else:
            # Validar el dominio (básico)
            try:
                # Añadir http:// para que validators lo acepte, pero guardar sin él
                if not base_site_input.startswith(('http://', 'https://')):
                     validation_url = f"http://{base_site_input}"
                else:
                     validation_url = base_site_input # Ya tiene protocolo
                     base_site_input = re.sub(r'^https?://', '', base_site_input) # Quitar protocolo para guardar

                # Quitar / al final si existe
                base_site_input = base_site_input.rstrip('/')

                is_valid = domain(validation_url) or domain(base_site_input) # Intentar con y sin http
                if not is_valid: raise ValueError("Formato de dominio inválido")

            except Exception as val_err:
                logger.warning(f"{log_prefix} Validación de dominio fallida para '{base_site_input}': {val_err}")
                return await m.reply_text(help_text + "\n\n❌ **Error:** El dominio proporcionado no parece ser válido. Asegúrate de que sea como `ejemplo.com`.", disable_web_page_preview=True)

            # Actualizar en la base de datos
            logger.info(f"{log_prefix} Actualizando base_site a: '{base_site_input}'")
            try:
                await update_user_info(user_id, {"base_site": base_site_input})
                await m.reply_text(f"<b>✅ Sitio Base actualizado correctamente a:</b> `{base_site_input}`")
            except Exception as e:
                logger.error(f"{log_prefix} Error actualizando base_site en DB: {e}")
                await m.reply_text("❌ Error al guardar el nuevo Sitio Base.")
    # Argumentos incorrectos
    else:
        logger.warning(f"{log_prefix} Uso incorrecto del comando: {' '.join(cmd)}")
        await m.reply_text("❓ **Uso incorrecto.**\n\n" + help_text, disable_web_page_preview=True)


@Client.on_message(filters.command("stats") & filters.private & filters.user(ADMINS))
async def simple_stats_command(client, message: Message):
    """Muestra estadísticas básicas (solo para admins)."""
    log_prefix = f"CMD /stats (Admin: {message.from_user.id}):"
    if message.from_user.id not in ADMINS: # Doble chequeo por si el filtro falla
         logger.warning(f"{log_prefix} Intento de acceso no autorizado denegado.")
         return

    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
        total_users = await db.total_users_count()
        # Podrías añadir más estadísticas aquí si db las proporciona
        # total_premium = await db.total_premium_users_count()
        # total_files = await db.total_files_count() # Ejemplo
        logger.info(f"{log_prefix} Obteniendo estadísticas: Usuarios={total_users}")

        stats_text = (f"📊 **Estadísticas del Bot**\n\n"
                      f"👥 Usuarios Totales Registrados: `{total_users}`\n"
                      # f"⭐ Usuarios Premium Activos: `{total_premium}`\n" # Descomentar si se implementa
                      # f"📁 Archivos Gestionados: `{total_files}`" # Descomentar si se implementa
                     )
        await message.reply_text(stats_text, quote=True)
    except Exception as e:
        logger.error(f"{log_prefix} Error obteniendo estadísticas: {e}", exc_info=True)
        await message.reply_text("❌ Hubo un error al obtener las estadísticas.")


# --- Manejador de Callbacks (Botones Inline) ---

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    """Maneja las pulsaciones de botones inline."""
    user_id = query.from_user.id; q_data = query.data; message = query.message
    log_prefix = f"CB (User: {user_id}, Data: '{q_data}', Msg ID: {message.id if message else 'N/A'}):"

    # Comprobar si el mensaje original existe
    if not message:
        logger.warning(f"{log_prefix} Callback recibido pero el mensaje original no existe (probablemente muy antiguo).")
        await query.answer("Este botón ya no está activo.", show_alert=True)
        return

    logger.debug(f"{log_prefix} Callback recibido.")
    try:
        me_info = client.me or await client.get_me() # Obtener info del bot si no está cacheada
        me_mention = me_info.mention
    except Exception as e:
        logger.error(f"{log_prefix} No se pudo obtener la mención del bot: {e}")
        me_mention = "este Bot" # Fallback genérico

    try:
        # --- Botón Cerrar ---
        if q_data == "close_data":
            logger.debug(f"{log_prefix} Cerrando mensaje.")
            await message.delete()
            # No necesita query.answer() aquí porque el mensaje desaparece.
            # Sin embargo, si la eliminación falla, sería bueno saberlo.
            try:
                await query.answer() # Responde silenciosamente para quitar el "loading" del botón
            except Exception: pass # Ignorar si responder falla después de borrar

        # --- Botón Acerca de ---
        elif q_data == "about":
            logger.debug(f"{log_prefix} Mostrando 'About'")
            buttons = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]
            markup = InlineKeyboardMarkup(buttons)
            about_text = getattr(script, 'ABOUT_TXT', "Información sobre el bot no disponible.").format(me_mention=me_mention)
            # Intentar editar texto, si falla (porque era foto), intentar editar caption
            try:
                await query.edit_message_text(about_text, reply_markup=markup, disable_web_page_preview=True)
            except MessageNotModified: pass # Ignorar si el texto es el mismo
            except Exception as e_text:
                 logger.warning(f"{log_prefix} Falló edit_message_text para 'about', intentando edit_message_caption: {e_text}")
                 try:
                     await query.edit_message_caption(caption=about_text, reply_markup=markup)
                 except Exception as e_caption:
                      logger.error(f"{log_prefix} Falló también edit_message_caption para 'about': {e_caption}")
            await query.answer() # Confirmar recepción del callback

        # --- Botón Inicio ---
        elif q_data == "start":
            logger.debug(f"{log_prefix} Volviendo a 'Start'")
            buttons = [
                [InlineKeyboardButton('Canal Principal', url='https://t.me/NessCloud'), InlineKeyboardButton('Grupo de Soporte', url='https://t.me/NESS_Soporte')],
                [InlineKeyboardButton('❓ Ayuda', callback_data='help'), InlineKeyboardButton('ℹ️ Acerca de', callback_data='about')]
            ]
            markup = InlineKeyboardMarkup(buttons)
            start_text = getattr(script, 'START_TXT', "¡Bienvenido de nuevo!").format(mention=query.from_user.mention, me_mention=me_mention)

            # Intentar editar el mensaje. Si es una foto, editar caption, si es texto, editar texto.
            try:
                if message.photo: # Si el mensaje actual tiene foto
                    await query.edit_message_caption(caption=start_text, reply_markup=markup)
                else: # Si el mensaje actual es de texto
                    await query.edit_message_text(start_text, reply_markup=markup, disable_web_page_preview=True)
            except MessageNotModified: pass # Ignorar si no hay cambios
            except Exception as e: # Fallback: Si falla la edición, intentar enviar la foto de inicio
                logger.warning(f"{log_prefix} Falló edición para 'start', intentando enviar foto: {e}")
                try:
                    photo_url = random.choice(PICS) if PICS else None
                    if photo_url:
                        await query.edit_message_media(media=InputMediaPhoto(photo_url), reply_markup=markup)
                        await query.edit_message_caption(caption=start_text, reply_markup=markup) # Asegurarse de poner el caption de nuevo
                    else: # Si no hay PICS, al menos intentar editar el texto
                         await query.edit_message_text(start_text, reply_markup=markup, disable_web_page_preview=True)
                except Exception as e_fallback:
                     logger.error(f"{log_prefix} Falló también el fallback de enviar foto para 'start': {e_fallback}")

            await query.answer()

        # --- Bloque 'clone' ELIMINADO --- (Asegurarse que no hay lógica residual)

        # --- Botón Ayuda ---
        elif q_data == "help":
             logger.debug(f"{log_prefix} Mostrando 'Help'")
             buttons = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons)
             help_text = getattr(script, 'HELP_TXT', "Instrucciones de ayuda no disponibles.")
             # Intentar editar texto o caption como en 'about'
             try:
                await query.edit_message_text(help_text, reply_markup=markup, disable_web_page_preview=True)
             except MessageNotModified: pass
             except Exception as e_text:
                 logger.warning(f"{log_prefix} Falló edit_message_text para 'help', intentando edit_message_caption: {e_text}")
                 try:
                     await query.edit_message_caption(caption=help_text, reply_markup=markup)
                 except Exception as e_caption:
                      logger.error(f"{log_prefix} Falló también edit_message_caption para 'help': {e_caption}")
             await query.answer()

        # --- Callback Desconocido ---
        else:
             logger.warning(f"{log_prefix} Callback data '{q_data}' no reconocido.")
             await query.answer("Esta opción no está implementada o ya no es válida.", show_alert=False) # Mensaje discreto

    except MessageNotModified:
        logger.debug(f"{log_prefix} Mensaje no modificado (contenido idéntico).")
        await query.answer() # Responder silenciosamente
    except Exception as e:
        logger.error(f"{log_prefix} Error procesando callback: {e}", exc_info=True)
        try:
             await query.answer("❌ Ocurrió un error al procesar tu acción.", show_alert=True) # Notificar al usuario del error
        except Exception as e_ans:
             logger.error(f"{log_prefix} Error incluso al responder al callback con error: {e_ans}")

# --- Comandos Premium (Formateados con texto modificado y ayuda) ---

@Client.on_message(filters.command("addpremium") & filters.private & filters.user(ADMINS))
async def add_premium_command(client, message: Message):
    """Añade acceso premium a un usuario (Admin Only)."""
    log_prefix = f"CMD /addpremium (Admin: {message.from_user.id}):"
    # --- Texto de Ayuda Mejorado ---
    usage_text = """ℹ️ **Cómo usar /addpremium:**

Este comando otorga acceso Premium a un usuario específico.

**Formatos Válidos:**

1.  **Premium Permanente:**
    `/addpremium ID_DEL_USUARIO`
    *(Ej: `/addpremium 123456789`)*

2.  **Premium Temporal (por días):**
    `/addpremium ID_DEL_USUARIO NUMERO_DE_DIAS`
    *(Ej: `/addpremium 987654321 30` para 30 días)*

**Nota:** Asegúrate de que el ID del usuario sea correcto y que el usuario haya iniciado el bot al menos una vez."""

    # Validar número de argumentos
    if not (2 <= len(message.command) <= 3):
        logger.warning(f"{log_prefix} Uso incorrecto: {message.text}")
        return await message.reply_text(usage_text, quote=True, disable_web_page_preview=True)

    # Validar User ID
    try:
        target_user_id = int(message.command[1])
    except ValueError:
        logger.warning(f"{log_prefix} ID de usuario inválido: {message.command[1]}")
        return await message.reply_text(f"❌ El ID de usuario `{message.command[1]}` no es válido. Debe ser un número.\n\n{usage_text}", quote=True, disable_web_page_preview=True)

    # Validar Días (si se proporcionan)
    days = None
    expiration_date = None # Para logging y mensajes
    if len(message.command) == 3:
        try:
            days = int(message.command[2])
            if days <= 0: raise ValueError("El número de días debe ser mayor que cero.")
            expiration_date = datetime.datetime.now() + datetime.timedelta(days=days)
        except ValueError as e:
            logger.warning(f"{log_prefix} Número de días inválido: {message.command[2]} ({e})")
            return await message.reply_text(f"❌ El número de días `{message.command[2]}` no es válido. Debe ser un número entero positivo.\n\n{usage_text}", quote=True, disable_web_page_preview=True)

    # Validar si el usuario existe en la base de datos
    if not await db.is_user_exist(target_user_id):
        logger.warning(f"{log_prefix} El usuario {target_user_id} no existe en la BD.")
        return await message.reply_text(f"❌ El usuario con ID `{target_user_id}` no ha iniciado el bot aún. Pídele que envíe /start primero.")

    # Intentar activar premium
    try:
        success = await db.set_premium(target_user_id, days)
        if success:
            # --- Textos de Éxito Mejorados ---
            duration_text = f"por **{days} días**" if days else "**permanentemente**"
            expiration_info = f"(Expira: {expiration_date.strftime('%Y-%m-%d %H:%M')})" if expiration_date else ""
            admin_reply = f"✅ ¡Acceso Premium activado para el usuario `{target_user_id}` {duration_text}! {expiration_info}"
            user_notification = f"🎉 ¡Felicidades! Has recibido acceso **Premium** en {client.me.mention} {duration_text}. {expiration_info}"
            # ------------------------------------
            await message.reply_text(admin_reply, quote=True)
            logger.info(f"{log_prefix} Premium activado para {target_user_id} {duration_text}. {expiration_info}")

            # Notificar al usuario (con manejo de errores)
            try:
                await client.send_message(target_user_id, user_notification)
            except Exception as notify_err:
                logger.warning(f"{log_prefix} No se pudo notificar la activación premium al usuario {target_user_id}: {notify_err}")
                # Informar al admin que no se pudo notificar
                await message.reply_text("*(ℹ️ Nota: No se pudo enviar la notificación al usuario. Asegúrate de que no haya bloqueado al bot.)*", quote=True)
        else:
            # Si db.set_premium devuelve False (podría ser un error interno de la función db)
            logger.error(f"{log_prefix} La función db.set_premium devolvió False para {target_user_id}.")
            await message.reply_text(f"❌ Hubo un error al intentar activar el premium para `{target_user_id}` en la base de datos.", quote=True)
    except Exception as e:
        logger.error(f"{log_prefix} Error CRÍTICO durante set_premium para {target_user_id}: {e}", exc_info=True)
        await message.reply_text("❌ Ocurrió un error interno inesperado al activar el premium. Revisa los logs.", quote=True)


@Client.on_message(filters.command("delpremium") & filters.private & filters.user(ADMINS))
async def del_premium_command(client, message: Message):
    """Elimina el acceso premium de un usuario (Admin Only)."""
    log_prefix = f"CMD /delpremium (Admin: {message.from_user.id}):"
    # --- Texto de Ayuda Mejorado ---
    usage_text = """ℹ️ **Cómo usar /delpremium:**

Este comando elimina el acceso Premium de un usuario específico.

**Formato:**
`/delpremium ID_DEL_USUARIO`

**Ejemplo:**
`/delpremium 123456789`

**Nota:** Esto eliminará el estado premium del usuario, ya sea temporal o permanente."""

    # Validar número de argumentos
    if len(message.command) != 2:
        logger.warning(f"{log_prefix} Uso incorrecto: {message.text}")
        return await message.reply_text(usage_text, quote=True, disable_web_page_preview=True)

    # Validar User ID
    try:
        target_user_id = int(message.command[1])
    except ValueError:
        logger.warning(f"{log_prefix} ID de usuario inválido: {message.command[1]}")
        return await message.reply_text(f"❌ El ID de usuario `{message.command[1]}` no es válido. Debe ser un número.\n\n{usage_text}", quote=True, disable_web_page_preview=True)

    # Validar si el usuario existe en la base de datos
    if not await db.is_user_exist(target_user_id):
        logger.warning(f"{log_prefix} El usuario {target_user_id} no existe en la BD.")
        # No es necesario devolver error aquí, podemos intentar quitar premium igualmente por si acaso quedó registro
        # return await message.reply_text(f"❌ El usuario con ID `{target_user_id}` no ha iniciado el bot.")

    # Intentar quitar premium
    try:
        # Primero, verificar si el usuario realmente *es* premium para dar feedback más preciso
        is_currently_premium = await db.check_premium_status(target_user_id)

        success = await db.remove_premium(target_user_id)

        if success:
            # --- Textos de Éxito Mejorados ---
            admin_reply = f"✅ Acceso Premium desactivado correctamente para el usuario `{target_user_id}`."
            user_notification = f"ℹ️ Tu acceso **Premium** en {client.me.mention} ha sido desactivado."
            # ------------------------------------
            await message.reply_text(admin_reply, quote=True)
            logger.info(f"{log_prefix} Premium desactivado para {target_user_id}.")

            # Notificar al usuario (solo si *era* premium antes, para evitar spam)
            if is_currently_premium:
                try:
                    await client.send_message(target_user_id, user_notification)
                except Exception as notify_err:
                    logger.warning(f"{log_prefix} No se pudo notificar la desactivación premium al usuario {target_user_id}: {notify_err}")
                    await message.reply_text("*(ℹ️ Nota: No se pudo enviar la notificación al usuario.)*", quote=True)
            else:
                 logger.info(f"{log_prefix} Usuario {target_user_id} ya no era premium, pero se ejecutó remove_premium por si acaso.")
                 await message.reply_text("*(ℹ️ Nota: El usuario ya no tenía premium activo, pero se limpió cualquier posible registro.)*", quote=True)

        else:
            # Si db.remove_premium devuelve False
            logger.error(f"{log_prefix} La función db.remove_premium devolvió False para {target_user_id}.")
            # Podría ser que no era premium, o un error interno.
            if not is_currently_premium:
                await message.reply_text(f"ℹ️ El usuario `{target_user_id}` ya no tenía Premium activo.", quote=True)
            else:
                await message.reply_text(f"❌ Hubo un error al intentar desactivar el premium para `{target_user_id}` en la base de datos.", quote=True)

    except Exception as e:
        logger.error(f"{log_prefix} Error CRÍTICO durante remove_premium para {target_user_id}: {e}", exc_info=True)
        await message.reply_text("❌ Ocurrió un error interno inesperado al desactivar el premium. Revisa los logs.", quote=True)

# --- Fin del archivo plugins/commands.py ---
