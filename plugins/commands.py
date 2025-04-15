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
from pyrogram.errors import (
    ChatAdminRequired, FloodWait, UserNotParticipant,
    ChatWriteForbidden, MessageIdInvalid, MessageNotModified
)
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InputMediaPhoto, WebAppInfo # Importaciones específicas
)

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
    from utils import (
        check_user_membership, verify_user, check_token,
        check_verification, get_token
    )
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
logger.setLevel(logging.INFO) # Asegurarse de que los logs INFO se muestren

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
    if not isinstance(file_name, str):
        return "archivo_desconocido"
    original_name = file_name
    try:
        # Eliminar corchetes y paréntesis
        file_name = re.sub(r'[\[\]\(\)]', '', file_name)
        # Dividir por espacios y filtrar partes no deseadas
        parts = file_name.split()
        filtered_parts = filter(lambda x: x and not x.startswith(('http', '@', 'www.')), parts)
        cleaned_name = ' '.join(filtered_parts)
        # Devolver nombre limpio o el original si el limpio está vacío
        return cleaned_name if cleaned_name else original_name
    except Exception as e:
        logger.error(f"Error formateando nombre '{original_name}': {e}")
        return original_name # Devolver original en caso de error

# --- Manejador del Comando /start ---
@Client.on_message(filters.command("start") & filters.incoming & filters.private)
async def start(client: Client, message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    user_mention = message.from_user.mention
    logger.info(f"/start recibido de {user_id} ({user_mention})")

    # Registro de usuario si es nuevo
    username = client.me.username
    if not await db.is_user_exist(user_id):
        logger.info(f"Usuario {user_id} ({user_mention}) es nuevo. Añadiendo a la base de datos.")
        await db.add_user(user_id, first_name)
        if LOG_CHANNEL:
            try:
                await client.send_message(
                    LOG_CHANNEL,
                    script.LOG_TEXT.format(user_id, user_mention)
                )
            except Exception as log_err:
                logger.error(f"Error enviando mensaje de nuevo usuario a LOG_CHANNEL {LOG_CHANNEL}: {log_err}")
        else:
            logger.warning("LOG_CHANNEL no está definido. No se pudo enviar log de nuevo usuario.")

    # Manejo de /start sin payload (Mensaje de Bienvenida)
    if len(message.command) == 1:
        logger.info(f"Enviando mensaje de bienvenida normal a {user_id}")
        buttons_list = [
            [InlineKeyboardButton('Únete a Nuestro Canal', url='https://t.me/NessCloud')],
            [InlineKeyboardButton('⚠️ Grupo de Soporte', url='https://t.me/NESS_Soporte')]
        ]
        # --- Botón Clonar Eliminado ---
        # if not CLONE_MODE:
        #     buttons_list.append([InlineKeyboardButton('🤖 Clonar Bot', callback_data='clone')])

        reply_markup = InlineKeyboardMarkup(buttons_list)
        me = client.me
        start_text = script.START_TXT.format(user_mention, me.mention)

        try:
            photo_url = random.choice(PICS) if PICS else None
            if photo_url:
                 await message.reply_photo(
                     photo=photo_url,
                     caption=start_text,
                     reply_markup=reply_markup
                 )
            else: # Fallback a texto si no hay PICS
                 await message.reply_text(
                     text=start_text,
                     reply_markup=reply_markup,
                     disable_web_page_preview=True
                 )
        except Exception as start_err:
            logger.error(f"Error enviando mensaje de bienvenida a {user_id}: {start_err}")
            # Intentar enviar solo texto como último recurso
            try:
                await message.reply_text(
                    text=start_text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
            except Exception as final_err:
                 logger.error(f"Fallo CRÍTICO al enviar bienvenida (texto) a {user_id}: {final_err}")
        return

    # --- PROCESAMIENTO CON PAYLOAD (argumento después de /start) ---
    payload_encoded_full = message.command[1]
    logger.info(f"/start con payload '{payload_encoded_full}' recibido de {user_id}")

    # Borrar mensaje pendiente "Únete al canal" si existe
    try:
        user_info = await db.get_user_info(user_id)
        pending_msg_id = user_info.get("pending_join_msg_id") if user_info else None
        if pending_msg_id:
            logger.debug(f"Intentando borrar mensaje pendiente 'Únete' {pending_msg_id} para {user_id}")
            await client.delete_messages(user_id, pending_msg_id)
            await db.update_user_info(user_id, {"pending_join_msg_id": None}) # Limpiar ID de la DB
    except MessageIdInvalid:
        logger.info(f"Mensaje 'Únete' {pending_msg_id} para {user_id} ya no existía o no se pudo borrar.")
        # Limpiar de la DB igualmente si el mensaje no se encontró
        await db.update_user_info(user_id, {"pending_join_msg_id": None})
    except Exception as db_err:
        logger.error(f"Error en DB o borrando mensaje pendiente 'Únete' para {user_id}: {db_err}")

    # Verificación Force Subscribe (Si está activado)
    should_skip_fsub = not FORCE_SUB_ENABLED or (SKIP_FORCE_SUB_FOR_ADMINS and user_id in ADMINS)
    if not should_skip_fsub and FORCE_SUB_CHANNEL and FORCE_SUB_INVITE_LINK:
        try:
            is_member = await check_user_membership(client, user_id, FORCE_SUB_CHANNEL)
            if not is_member:
                logger.info(f"Usuario {user_id} NO es miembro del canal {FORCE_SUB_CHANNEL}. Mostrando mensaje ForceSub.")
                buttons = [
                    [InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)],
                    [InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{username}?start={payload_encoded_full}")]
                ]
                join_message = await message.reply_text(
                    script.FORCE_MSG.format(mention=user_mention),
                    reply_markup=InlineKeyboardMarkup(buttons),
                    quote=True,
                    disable_web_page_preview=True
                )
                # Guardar ID del mensaje para borrarlo después si el usuario se une
                await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id})
                return # Detener procesamiento hasta que se una
        except UserNotParticipant:
             logger.info(f"Usuario {user_id} no es participante (probablemente baneado) de {FORCE_SUB_CHANNEL}")
             # Aquí podrías enviar un mensaje diferente si quieres manejar baneados
        except ChatAdminRequired:
             logger.error(f"Error CRÍTICO: El bot necesita ser admin en el canal ForceSub {FORCE_SUB_CHANNEL}")
             # Considera notificar a los admins del bot
        except Exception as fs_err:
            logger.error(f"Error CRÍTICO durante la comprobación ForceSub para {user_id}: {fs_err}", exc_info=True)
            # Informar al usuario podría ser útil
            await message.reply_text("⚠️ Ocurrió un error al verificar tu membresía. Inténtalo de nuevo más tarde.")
            return

    # Decodificación del Payload y Chequeos de Acceso (Premium/Verify)
    logger.info(f"Usuario {user_id} pasó chequeos iniciales o no aplican. Procesando payload: {payload_encoded_full}")
    is_batch = False
    base64_to_decode = payload_encoded_full
    link_type = "normal" # Tipo por defecto
    original_payload_id = ""

    if payload_encoded_full.startswith("BATCH-"):
        is_batch = True
        base64_to_decode = payload_encoded_full[len("BATCH-"):]

    try:
        # Añadir padding si es necesario para base64
        padding = 4 - (len(base64_to_decode) % 4)
        padding = 0 if padding == 4 else padding # No añadir padding si ya es múltiplo de 4
        payload_decoded = base64.urlsafe_b64decode(base64_to_decode + "=" * padding).decode("ascii")
        original_payload_id = payload_decoded # Guardar el ID decodificado

        # Determinar el tipo de enlace basado en prefijos
        if payload_decoded.startswith("premium:"):
            link_type = "premium"
            original_payload_id = payload_decoded[len("premium:"):]
        elif payload_decoded.startswith("normal:"):
            link_type = "normal"
            original_payload_id = payload_decoded[len("normal:"):]
        elif payload_decoded.startswith("verify-"):
            link_type = "special" # Usado para el proceso de verificación en sí
            # original_payload_id ya es 'verify-userid-token'
        else:
            logger.warning(f"Payload decodificado '{payload_decoded}' para {user_id} no tiene prefijo conocido. Asumiendo 'normal'.")
            # original_payload_id ya tiene el valor decodificado

        logger.debug(f"Payload decodificado: Tipo='{link_type}', ID Original='{original_payload_id}'")

    except (base64.binascii.Error, UnicodeDecodeError) as decode_err:
        logger.error(f"Error decodificando payload '{base64_to_decode}' (viene de '{payload_encoded_full}') para {user_id}: {decode_err}")
        return await message.reply_text("❌ Enlace inválido o corrupto. No se pudo decodificar.")
    except Exception as generic_decode_err:
         logger.error(f"Error inesperado durante decodificación de payload para {user_id}: {generic_decode_err}")
         return await message.reply_text("❌ Ocurrió un error inesperado al procesar el enlace.")

    # Chequeo de Acceso Premium
    is_premium_user = await db.check_premium_status(user_id)
    is_admin_user = user_id in ADMINS
    logger.debug(f"Chequeo de acceso para {user_id}: premium={is_premium_user}, admin={is_admin_user}")

    if link_type == "premium" and not is_premium_user and not is_admin_user:
        logger.info(f"Acceso denegado: Usuario normal {user_id} intentando acceder a enlace premium '{original_payload_id}'.")
        try:
            await message.reply_text(script.PREMIUM_REQUIRED_MSG.format(mention=user_mention), quote=True)
        except AttributeError: # Si el script no tiene esa variable
            await message.reply_text("❌ Acceso denegado. Este es un enlace solo para usuarios Premium.", quote=True)
        return
    elif link_type == "premium" and is_admin_user and not is_premium_user:
        logger.info(f"Acceso permitido: Admin {user_id} accediendo a enlace premium '{original_payload_id}' (sin ser usuario premium).")
    elif link_type == "premium" and is_premium_user:
         logger.info(f"Acceso permitido: Usuario premium {user_id} accediendo a enlace premium '{original_payload_id}'.")

    # Chequeo de Verificación (si está activado y no es un enlace de verificación)
    try:
        # Solo aplicar si VERIFY_MODE está ON y el payload NO es del tipo 'verify-'
        apply_verify_check = VERIFY_MODE and link_type != "special" # "special" es 'verify-...'
        if apply_verify_check and not await check_verification(client, user_id):
            logger.info(f"Usuario {user_id} necesita verificación para acceder al enlace ({link_type}) '{original_payload_id}'.")
            verify_url = await get_token(client, user_id, f"https://t.me/{username}?start=") # Obtener token/URL de verificación

            if "ERROR" in verify_url: # Si get_token falló
                 logger.error(f"No se pudo obtener el token de verificación para {user_id}. Fallback a mensaje simple.")
                 await message.reply_text(
                     "🔒 **Verificación Requerida**\n\n"
                     "Necesitas verificar tu cuenta para acceder a este contenido. "
                     "Ocurrió un error al generar tu enlace de verificación. Por favor, inténtalo de nuevo más tarde o contacta al soporte.",
                     protect_content=True
                 )
                 return

            btn_list = [[InlineKeyboardButton("➡️ Verificar Ahora ⬅️", url=verify_url)]]
            if VERIFY_TUTORIAL:
                btn_list.append([InlineKeyboardButton("❓ Cómo Verificar (Tutorial)", url=VERIFY_TUTORIAL)])

            await message.reply_text(
                 "🔒 **Verificación Requerida**\n\n"
                 "Por favor, completa la verificación para acceder al enlace. Haz clic en el botón de abajo.",
                 protect_content=True, # Evitar reenvío del mensaje de verificación
                 reply_markup=InlineKeyboardMarkup(btn_list)
            )
            return # Detener hasta que verifique
    except Exception as e:
        logger.error(f"Error durante check_verification para {user_id}: {e}", exc_info=True)
        await message.reply_text(f"❌ Ocurrió un error durante el proceso de verificación: {e}")
        return

    # --- SI PASÓ TODOS LOS CHEQUEOS: Procesar el contenido según el original_payload_id ---
    logger.info(f"Usuario {user_id} ({link_type}, premium={is_premium_user}, admin={is_admin_user}) procesando ID '{original_payload_id}' (Batch: {is_batch})")

    # Lógica para 'verify-' (Confirmación de Verificación)
    if link_type == "special" and original_payload_id.startswith("verify-"):
        logger.debug(f"Manejando payload de confirmación 'verify' para {user_id}")
        try:
            parts = original_payload_id.split("-")
            # Asegurarse de que hay 3 partes: 'verify', userid, token
            if len(parts) != 3: raise ValueError("Formato de token de verificación incorrecto.")
            _, verify_userid_str, token = parts
            verify_userid = int(verify_userid_str)

            # Comprobar que el usuario que hace clic es el dueño del token
            if user_id != verify_userid:
                 logger.warning(f"Usuario {user_id} intentó usar token de verificación de {verify_userid}.")
                 raise PermissionError("Este enlace de verificación no es para ti.")

            # Validar el token con el sistema (check_token)
            if not await check_token(client, verify_userid, token):
                 logger.warning(f"Token de verificación inválido o expirado para {verify_userid}: {token}")
                 raise ValueError("Token inválido o expirado.")

            # Si todo es válido, marcar como verificado y notificar
            await verify_user(client, verify_userid, token) # Marcar usuario como verificado
            await message.reply_text(
                f"✅ ¡Hola {user_mention}! Has sido verificado correctamente. Ahora puedes intentar acceder al enlace original de nuevo.",
                protect_content=True # Para que no reenvíen el mensaje de éxito
            )
            logger.info(f"Usuario {verify_userid} verificado exitosamente con token {token}.")

        except (ValueError, PermissionError) as verify_e:
            logger.error(f"Error procesando token de verificación '{original_payload_id}' para {user_id}: {verify_e}")
            await message.reply_text(f"❌ **Error de Verificación:** {verify_e}", protect_content=True)
        except Exception as generic_verify_e:
             logger.error(f"Error inesperado procesando token de verificación '{original_payload_id}' para {user_id}: {generic_verify_e}", exc_info=True)
             await message.reply_text("❌ Ocurrió un error inesperado durante la verificación.", protect_content=True)
        return # Terminar aquí después de procesar la verificación

    # Lógica para BATCH (Lotes de archivos)
    elif is_batch:
        batch_json_msg_id = original_payload_id # El ID decodificado es el ID del mensaje JSON
        logger.info(f"Procesando solicitud de BATCH. ID del mensaje JSON en LOG_CHANNEL: {batch_json_msg_id}")
        sts = await message.reply_text("⏳ **Procesando lote de archivos...** Por favor, espera.", quote=True)

        msgs = BATCH_FILES.get(batch_json_msg_id) # Intentar obtener de caché primero
        if not msgs:
            logger.debug(f"Info de BATCH {batch_json_msg_id} no encontrada en caché. Intentando descargar desde LOG_CHANNEL.")
            file_path = None # Inicializar fuera del try para el finally
            try:
                # Determinar si LOG_CHANNEL es numérico (ID) o string (username)
                try:
                    log_channel_int = int(LOG_CHANNEL)
                except ValueError:
                     log_channel_int = str(LOG_CHANNEL) # Mantener como string si no es número

                # Obtener el mensaje que contiene el archivo JSON
                batch_list_msg = await client.get_messages(log_channel_int, int(batch_json_msg_id))

                if not batch_list_msg or not batch_list_msg.document:
                    raise FileNotFoundError(f"Mensaje {batch_json_msg_id} en {log_channel_int} no encontrado o no es un documento.")

                if not batch_list_msg.document.file_name.endswith('.json'):
                     logger.warning(f"El documento en msg {batch_json_msg_id} no parece ser JSON: {batch_list_msg.document.file_name}")
                     # Podrías decidir parar aquí o intentar cargarlo de todos modos

                # Descargar el archivo JSON
                logger.debug(f"Descargando archivo JSON del mensaje {batch_json_msg_id}...")
                file_path = await client.download_media(batch_list_msg.document.file_id, file_name=f"./{batch_json_msg_id}.json") # Guardar en disco temporalmente

                # Cargar el JSON desde el archivo
                with open(file_path, 'r', encoding='utf-8') as fd: # Especificar encoding
                    msgs = json.load(fd)

                # Guardar en caché si se cargó correctamente
                BATCH_FILES[batch_json_msg_id] = msgs
                logger.info(f"Info de BATCH {batch_json_msg_id} cargada desde archivo y guardada en caché ({len(msgs)} elementos).")

            except FileNotFoundError as fnf_err:
                 logger.error(f"Error BATCH: {fnf_err}")
                 return await sts.edit_text(f"❌ Error crítico: No se encontró la información del lote ({batch_json_msg_id}).")
            except json.JSONDecodeError as json_err:
                 logger.error(f"Error BATCH: El archivo descargado para {batch_json_msg_id} no es un JSON válido. {json_err}")
                 return await sts.edit_text("❌ Error crítico: El formato de la información del lote es incorrecto.")
            except Exception as batch_load_err:
                logger.error(f"Error cargando BATCH {batch_json_msg_id} desde LOG_CHANNEL: {batch_load_err}", exc_info=True)
                return await sts.edit_text("❌ Ocurrió un error inesperado al cargar la información del lote.")
            finally:
                 # Asegurarse de borrar el archivo JSON descargado
                 if file_path and os.path.exists(file_path):
                     try:
                         os.remove(file_path)
                         logger.debug(f"Archivo temporal JSON {file_path} eliminado.")
                     except OSError as rm_err:
                          logger.error(f"No se pudo eliminar el archivo temporal JSON {file_path}: {rm_err}")

        # Verificar si 'msgs' se cargó correctamente (desde caché o archivo)
        if not msgs or not isinstance(msgs, list):
            logger.error(f"Error BATCH: La información cargada para {batch_json_msg_id} está vacía o no es una lista.")
            return await sts.edit_text("❌ Error: La información del lote está vacía o tiene un formato incorrecto.")

        filesarr = [] # Lista para guardar los mensajes enviados (para auto-delete)
        total_msgs = len(msgs)
        logger.info(f"Enviando {total_msgs} mensajes del BATCH {batch_json_msg_id} al usuario {user_id}")
        await sts.edit_text(f"⏳ Enviando lote... (0/{total_msgs})")

        # --- Bucle de envío BATCH con lógica de caption ---
        for i, msg_info in enumerate(msgs):
            channel_id = msg_info.get("channel_id")
            msgid = msg_info.get("msg_id")

            # Validar que tenemos IDs válidos
            if not channel_id or not msgid:
                logger.warning(f"Elemento {i} del BATCH {batch_json_msg_id} no tiene channel_id o msg_id válidos. Saltando.")
                continue

            try:
                channel_id = int(channel_id)
                msgid = int(msgid)

                # Obtener el mensaje original desde el canal fuente
                original_msg = await client.get_messages(channel_id, msgid)
                if not original_msg:
                    logger.warning(f"No se pudo obtener el mensaje original {msgid} del canal {channel_id}. Saltando.")
                    continue

                # --- Preparar Caption y Botones para el mensaje BATCH ---
                f_caption_batch = None # Usar None por defecto si no hay media o caption
                stream_reply_markup_batch = None
                title_batch = "N/A"
                size_batch = "N/A"

                if original_msg.media:
                    media_batch = getattr(original_msg, original_msg.media.value, None)
                    if media_batch:
                        f_caption_orig_batch = getattr(original_msg, 'caption', '')
                        # Usar .html si existe para preservar formato
                        if f_caption_orig_batch and hasattr(f_caption_orig_batch, 'html'):
                            f_caption_orig_batch = f_caption_orig_batch.html
                        elif f_caption_orig_batch:
                             f_caption_orig_batch = str(f_caption_orig_batch) # Convertir a string si no es html

                        old_title_batch = getattr(media_batch, "file_name", "")
                        title_batch = formate_file_name(old_title_batch) if old_title_batch else "archivo_desconocido"
                        size_batch = get_size(getattr(media_batch, "file_size", 0))

                        # Formatear caption según configuración
                        if BATCH_FILE_CAPTION:
                            try:
                                f_caption_batch = BATCH_FILE_CAPTION.format(
                                    file_name=title_batch,
                                    file_size=size_batch,
                                    file_caption=f_caption_orig_batch if f_caption_orig_batch else ""
                                )
                            except Exception as cap_fmt_err_batch:
                                logger.warning(f"Error formateando BATCH_FILE_CAPTION para msg {msgid}: {cap_fmt_err_batch}. Usando fallback.")
                                # Fallback: Usar caption original o nombre de archivo
                                f_caption_batch = f_caption_orig_batch if f_caption_orig_batch else f"<code>{title_batch}</code>"
                        elif f_caption_orig_batch: # Usar caption original si no hay formato config
                            f_caption_batch = f_caption_orig_batch
                        else: # Usar solo nombre de archivo como último recurso si no hay caption original
                            f_caption_batch = f"<code>{title_batch}</code>"

                    # Generar botones de Stream si aplica
                    if STREAM_MODE and (original_msg.video or original_msg.document):
                        try:
                            # Asegurarse de que get_name y get_hash devuelven algo usable
                            file_name_for_url = get_name(original_msg)
                            file_hash = get_hash(original_msg)
                            if not file_name_for_url or not file_hash:
                                 raise ValueError("No se pudo obtener nombre o hash para URL de stream")

                            stream_url = f"{URL}watch/{str(original_msg.id)}/{quote_plus(file_name_for_url)}?hash={file_hash}"
                            download_url = f"{URL}{str(original_msg.id)}/{quote_plus(file_name_for_url)}?hash={file_hash}"
                            stream_buttons = [
                                [InlineKeyboardButton("📥 Descargar", url=download_url),
                                 InlineKeyboardButton('▶️ Ver Online', url=stream_url)],
                                [InlineKeyboardButton("🌐 Ver en Web App", web_app=WebAppInfo(url=stream_url))]
                            ]
                            stream_reply_markup_batch = InlineKeyboardMarkup(stream_buttons)
                        except Exception as stream_err:
                            logger.error(f"Error generando botones de stream BATCH para msg {msgid}: {stream_err}")
                            stream_reply_markup_batch = None # No poner botones si falló
                else:
                     # Si el mensaje original es solo texto, el caption será None
                     f_caption_batch = None

                # Copiar el mensaje usando el caption y botones preparados
                sent_msg = await original_msg.copy(
                    chat_id=user_id,
                    caption=f_caption_batch, # Pyrogram maneja si es None
                    reply_markup=stream_reply_markup_batch # Pyrogram maneja si es None
                    # protect_content se hereda por defecto al copiar, si quieres cambiarlo: protect_content=False
                )
                filesarr.append(sent_msg) # Añadir a la lista para posible auto-borrado

                # Actualizar estado cada cierto número de mensajes
                if (i + 1) % 10 == 0 or (i + 1) == total_msgs:
                     try: await sts.edit_text(f"⏳ Enviando lote... ({i + 1}/{total_msgs})")
                     except MessageNotModified: pass
                     except FloodWait as fw_sts:
                          logger.warning(f"FloodWait al actualizar estado BATCH ({fw_sts.value}s). Continuando...")
                          await asyncio.sleep(fw_sts.value + 1)

                # Pausa corta para evitar flood
                await asyncio.sleep(0.5) # Ajustar si es necesario

            except FloodWait as fw_err:
                wait_time = fw_err.value
                logger.warning(f"FloodWait en BATCH item {i} (msg {msgid}). Esperando {wait_time} segundos.")
                await sts.edit_text(f"⏳ Enviando lote... ({i}/{total_msgs})\n"
                                    f"Pausa por FloodWait ({wait_time}s)")
                await asyncio.sleep(wait_time + 2) # Esperar tiempo + margen
                # Reintentar enviar el mismo mensaje después de la espera
                try:
                    logger.info(f"Reintentando enviar BATCH item {i} (msg {msgid}) después de FloodWait.")
                    # Re-obtener y re-copiar (simplificado, podrías re-aplicar toda la lógica de caption/botones si fuera necesario)
                    original_msg_retry = await client.get_messages(channel_id, msgid)
                    if original_msg_retry:
                         sent_msg_retry = await original_msg_retry.copy(user_id) # Copia simple en reintento
                         filesarr.append(sent_msg_retry)
                         logger.info(f"Reintento BATCH item {i} exitoso.")
                    else: logger.error(f"Fallo al re-obtener msg {msgid} en reintento.")
                except Exception as retry_err:
                    logger.error(f"Error CRÍTICO al reintentar BATCH item {i} (msg {msgid}): {retry_err}")
            except Exception as loop_err:
                logger.error(f"Error procesando BATCH item {i} (msg {msgid} de canal {channel_id}): {loop_err}", exc_info=True)
                # Podrías notificar al usuario sobre errores específicos si es necesario

        # --- FIN DEL BUCLE for ---

        # Borrar mensaje "Procesando..."
        try:
            await sts.delete()
        except Exception as del_sts_err:
             logger.warning(f"No se pudo borrar el mensaje de estado BATCH: {del_sts_err}")

        logger.info(f"Envío BATCH {batch_json_msg_id} a {user_id} completado. {len(filesarr)}/{total_msgs} mensajes enviados.")

        # Auto-Delete BATCH (si está activado y se enviaron archivos)
        if AUTO_DELETE_MODE and filesarr:
            logger.info(f"Iniciando Auto-Delete para el lote enviado a {user_id} ({len(filesarr)} archivos). Tiempo: {AUTO_DELETE_TIME}s")
            try:
                # --- Mensaje IMPORTANTE Actualizado ---
                warn_msg_text = (
                    f"<blockquote><b><u>❗️❗️❗️IMPORTANTE❗️️❗️❗️</u></b>\n\n"
                    f"Este mensaje será eliminado en <b><u>{AUTO_DELETE} minutos</u></b> 🫥 " # Usando la variable AUTO_DELETE
                    f"<i>(Debido a problemas de derechos de autor)</i>.\n\n"
                    f"<b><i>Por favor, reenvía este mensaje a tus mensajes guardados o a cualquier chat privado.</i></b></blockquote>"
                )
                k = await client.send_message(
                    chat_id=user_id,
                    text=warn_msg_text,
                    parse_mode=enums.ParseMode.HTML
                )

                # Esperar el tiempo configurado
                await asyncio.sleep(AUTO_DELETE_TIME)

                # Borrar los mensajes enviados
                deleted_count = 0
                logger.debug(f"Tiempo de espera {AUTO_DELETE_TIME}s finalizado. Borrando mensajes BATCH para {user_id}...")
                for msg_to_delete in filesarr:
                    try:
                        await msg_to_delete.delete()
                        deleted_count += 1
                    except MessageIdInvalid:
                         logger.warning(f"Mensaje BATCH {msg_to_delete.id} ya no existía al intentar borrar (probablemente borrado por el usuario).")
                    except Exception as del_err:
                        logger.error(f"Error borrando mensaje BATCH {msg_to_delete.id} para {user_id}: {del_err}")

                # Editar mensaje de advertencia para confirmar el borrado
                try:
                    await k.edit_text(f"✅ <b>{deleted_count}/{len(filesarr)} mensajes del lote anterior fueron eliminados automáticamente.</b>")
                except Exception as edit_k_err:
                     logger.warning(f"No se pudo editar el mensaje de confirmación de borrado BATCH: {edit_k_err}")

                logger.info(f"Auto-Delete BATCH para {user_id} completado: {deleted_count}/{len(filesarr)} mensajes borrados.")

            except Exception as auto_del_batch_err:
                logger.error(f"Error durante el proceso Auto-Delete BATCH para {user_id}: {auto_del_batch_err}", exc_info=True)
        elif not filesarr:
             logger.info(f"No se enviaron archivos en el lote {batch_json_msg_id} a {user_id}. Auto-Delete no aplica.")
        else: # AUTO_DELETE_MODE is False
            logger.info(f"Auto-Delete BATCH desactivado. Los archivos enviados a {user_id} permanecerán.")
        return # Fin de la lógica BATCH

    # Lógica para Archivo Único
    else:
        logger.info(f"Procesando solicitud de Archivo Único. Payload original ID: {original_payload_id}")
        try:
            # Determinar el ID numérico del mensaje a enviar
            if original_payload_id.startswith("file_"):
                try:
                    parts = original_payload_id.split("_")
                    if len(parts) > 1 and parts[-1].isdigit():
                         decode_file_id = int(parts[-1])
                         logger.debug(f"Extraído ID {decode_file_id} de payload {original_payload_id}")
                    else:
                         decode_file_id = int(original_payload_id)
                         logger.debug(f"Asumiendo que {original_payload_id} es el ID completo.")
                except ValueError:
                     logger.error(f"No se pudo convertir '{original_payload_id}' o parte de él a un ID numérico.")
                     raise ValueError("Payload de archivo único inválido.")
            else:
                decode_file_id = int(original_payload_id)
                logger.debug(f"Payload no empieza con 'file_', asumiendo ID directo: {decode_file_id}")

            # Obtener el canal de logs
            try:
                log_channel_int = int(LOG_CHANNEL)
            except ValueError:
                log_channel_int = str(LOG_CHANNEL)

            # Obtener el mensaje original desde el canal de logs
            logger.debug(f"Intentando obtener mensaje {decode_file_id} desde {log_channel_int}...")
            original_msg = await client.get_messages(log_channel_int, decode_file_id)

            if not original_msg:
                raise MessageIdInvalid(f"Mensaje con ID {decode_file_id} no encontrado en el canal de logs ({log_channel_int}).")

            logger.info(f"Mensaje {decode_file_id} obtenido. Preparando para enviar a {user_id}.")

            # --- Preparar Caption y Botones para el Archivo Único ---
            f_caption = None # Por defecto
            reply_markup = None # Por defecto
            title = "N/A"
            size = "N/A"

            if original_msg.media:
                media = getattr(original_msg, original_msg.media.value, None)
                if media:
                    title = formate_file_name(getattr(media, "file_name", ""))
                    size = get_size(getattr(media, "file_size", 0))
                    f_caption_orig = getattr(original_msg, 'caption', '')
                    if f_caption_orig and hasattr(f_caption_orig, 'html'):
                        f_caption_orig = f_caption_orig.html
                    elif f_caption_orig:
                         f_caption_orig = str(f_caption_orig)

                    if CUSTOM_FILE_CAPTION:
                        try:
                            f_caption = CUSTOM_FILE_CAPTION.format(
                                file_name=title if title else "archivo_desconocido",
                                file_size=size if size else "N/A",
                                file_caption=f_caption_orig if f_caption_orig else ""
                            )
                            logger.debug(f"Caption formateado con CUSTOM_FILE_CAPTION: '{f_caption[:50]}...'")
                        except Exception as e:
                            logger.error(f"Error al formatear CUSTOM_FILE_CAPTION: {e}. Usando fallback.")
                            f_caption = f_caption_orig if f_caption_orig else (f"<code>{title}</code>" if title else "Archivo")
                    elif f_caption_orig:
                        f_caption = f_caption_orig
                        logger.debug("Usando caption original del mensaje.")
                    else:
                        f_caption = f"<code>{title}</code>" if title else None
                        logger.debug(f"Usando nombre de archivo como caption: '{f_caption}'")

                    if STREAM_MODE and (original_msg.video or original_msg.document):
                        try:
                            file_name_for_url = get_name(original_msg)
                            file_hash = get_hash(original_msg)
                            if not file_name_for_url or not file_hash:
                                 raise ValueError("No se pudo obtener nombre o hash para URL de stream (archivo único)")

                            stream_url = f"{URL}watch/{str(original_msg.id)}/{quote_plus(file_name_for_url)}?hash={file_hash}"
                            download_url = f"{URL}{str(original_msg.id)}/{quote_plus(file_name_for_url)}?hash={file_hash}"
                            stream_buttons = [
                                [InlineKeyboardButton("📥 Descargar", url=download_url),
                                 InlineKeyboardButton('▶️ Ver Online', url=stream_url)],
                                [InlineKeyboardButton("🌐 Ver en Web App", web_app=WebAppInfo(url=stream_url))]
                             ]
                            reply_markup = InlineKeyboardMarkup(stream_buttons)
                            logger.debug("Botones de Stream generados para archivo único.")
                        except Exception as stream_err:
                           logger.error(f"Error generando botones de stream para archivo único {original_msg.id}: {stream_err}")
                           reply_markup = None
                else:
                     logger.warning(f"Mensaje {original_msg.id} tiene atributo 'media' pero no se pudo obtener el objeto media concreto.")
                     f_caption = "⚠️ Error al obtener detalles del archivo."
            else:
                 logger.debug(f"Mensaje {original_msg.id} no tiene media. Se copiará tal cual.")
                 f_caption = None
                 reply_markup = None

            # Copiar el mensaje al usuario usando caption/botones preparados
            logger.debug(f"Copiando mensaje {original_msg.id} a {user_id} con caption: '{str(f_caption)[:50]}...' y markup: {reply_markup is not None}")
            sent_file_msg = await original_msg.copy(
                chat_id=user_id,
                caption=f_caption,
                reply_markup=reply_markup,
                protect_content=False
            )
            logger.info(f"Mensaje {original_msg.id} enviado a {user_id} como mensaje {sent_file_msg.id}")

            # Auto-Delete para Archivo Único (si está activado)
            if AUTO_DELETE_MODE:
                logger.info(f"Iniciando Auto-Delete para archivo único {sent_file_msg.id} enviado a {user_id}. Tiempo: {AUTO_DELETE_TIME}s")
                try:
                    # --- Mensaje IMPORTANTE Actualizado ---
                    warn_msg_text = (
                        f"<blockquote><b><u>❗️❗️❗️IMPORTANTE❗️️❗️❗️</u></b>\n\n"
                        f"Este mensaje será eliminado en <b><u>{AUTO_DELETE} minutos</u></b> 🫥 " # Usando la variable AUTO_DELETE
                        f"<i>(Debido a problemas de derechos de autor)</i>.\n\n"
                        f"<b><i>Por favor, reenvía este mensaje a tus mensajes guardados o a cualquier chat privado.</i></b></blockquote>"
                    )
                    k = await client.send_message(
                        chat_id=user_id,
                        text=warn_msg_text,
                        parse_mode=enums.ParseMode.HTML
                    )

                    # Esperar
                    await asyncio.sleep(AUTO_DELETE_TIME)

                    # Borrar el archivo enviado
                    logger.debug(f"Tiempo de espera {AUTO_DELETE_TIME}s finalizado. Borrando mensaje {sent_file_msg.id} para {user_id}...")
                    try:
                        await sent_file_msg.delete()
                        logger.info(f"Mensaje {sent_file_msg.id} borrado automáticamente.")
                    except MessageIdInvalid:
                         logger.warning(f"Mensaje {sent_file_msg.id} ya no existía al intentar borrarlo.")
                    except Exception as del_err:
                         logger.error(f"Error al borrar mensaje {sent_file_msg.id} en auto-delete: {del_err}")

                    # Editar mensaje de advertencia para confirmar
                    try:
                        await k.edit_text("✅ <b>El mensaje anterior fue eliminado automáticamente.</b>")
                    except Exception as edit_k_err:
                         logger.warning(f"No se pudo editar mensaje de confirmación de borrado: {edit_k_err}")

                    logger.info(f"Auto-Delete de archivo único para {user_id} completado.")

                except Exception as auto_del_err:
                    logger.error(f"Error durante el proceso Auto-Delete de archivo único para {user_id}: {auto_del_err}", exc_info=True)
            else:
                logger.debug(f"Auto-Delete para archivo único desactivado para el usuario {user_id}.")
            return # Fin de la lógica de archivo único

        except MessageIdInvalid as e:
            logger.error(f"Error Archivo Único: {e}. Payload original: {original_payload_id}")
            await message.reply_text("❌ Lo siento, este archivo ya no está disponible o el enlace es incorrecto.")
        except (ValueError, IndexError, AttributeError) as payload_err:
            logger.error(f"Error procesando payload de archivo único '{original_payload_id}' para {user_id}: {payload_err}")
            await message.reply_text("❌ Enlace inválido o mal formado.")
        except Exception as e:
            logger.error(f"Error crítico no esperado al procesar archivo único para {user_id} (payload: {original_payload_id}): {e}", exc_info=True)
            await message.reply_text("❌ Ocurrió un error inesperado al intentar obtener el archivo.")
        return

# --- Comandos /api, /base_site, /stats (Sin cambios aquí) ---
@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    """Maneja el comando /api para ver o establecer la API del acortador."""
    user_id = m.from_user.id
    log_prefix = f"CMD /api (User: {user_id}):" # Prefijo para logs

    try:
        user_data = await get_user(user_id)
        # Usar .get con valor por defecto si el usuario o las claves no existen
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
            # Asegurarse de que el texto del script exista
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
        # Permitir 'None' (case-insensitive) para eliminar la API
        update_value = None if api_key_input.lower() == "none" else api_key_input

        # Validar que la API no sea una cadena vacía si no es None
        if update_value == "":
            logger.warning(f"{log_prefix} Intento de establecer API vacía.")
            return await m.reply_text("❌ La clave API no puede ser una cadena vacía. Usa `/api None` para eliminarla.")

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
        logger.warning(f"{log_prefix} Uso incorrecto del comando: {' '.join(cmd)}")
        await m.reply_text(
            "**Formato incorrecto.**\n\n"
            "Para ver tu API actual:\n`/api`\n\n"
            "Para establecer tu API:\n`/api TU_CLAVE_API`\n\n"
            "Para eliminar tu API:\n`/api None`"
        )

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    """Maneja el comando /base_site para ver o establecer el dominio base del acortador."""
    user_id = m.from_user.id
    log_prefix = f"CMD /base_site (User: {user_id}):"

    try:
        user_data = await get_user(user_id)
        current_site = user_data.get("base_site", "Ninguno configurado") if user_data else "N/A (Usuario no encontrado)"
        logger.debug(f"{log_prefix} Sitio base actual: '{current_site}'")
    except Exception as e:
        logger.error(f"{log_prefix} Error al obtener datos del usuario desde users_api: {e}")
        return await m.reply_text("❌ Ocurrió un error al consultar tu configuración de sitio base.")

    cmd = m.command
    # Texto de ayuda/estado base
    help_text = (
        f"⚙️ **Configuración del Sitio Base del Acortador**\n\n"
        f"Tu sitio base actual es: `{current_site}`\n\n"
        "Usa este comando para establecer el dominio principal de tu servicio de acortador (ej: `google.com`, `ejemplo.net`).\n\n"
        "➡️ Para establecer un sitio base:\n`/base_site tudominio.com`\n\n"
        "➡️ Para eliminar el sitio base configurado:\n`/base_site None`"
    )

    # Comando sin argumentos: Mostrar estado y ayuda
    if len(cmd) == 1:
        await m.reply_text(text=help_text, disable_web_page_preview=True)

    # Comando con un argumento: Establecer o eliminar sitio base
    elif len(cmd) == 2:
        base_site_input = cmd[1].strip()

        # Eliminar sitio base
        if base_site_input.lower() == "none":
            logger.info(f"{log_prefix} Solicitud para eliminar el sitio base.")
            try:
                await update_user_info(user_id, {"base_site": None})
                await m.reply_text("✅ Tu sitio base ha sido eliminado.")
                logger.info(f"{log_prefix} Eliminación de sitio base exitosa.")
            except Exception as e:
                logger.error(f"{log_prefix} Error al eliminar el sitio base en users_api: {e}")
                await m.reply_text("❌ Ocurrió un error al intentar eliminar tu sitio base.")

        # Establecer nuevo sitio base
        else:
            # Validar si es un dominio válido (básico)
            try:
                temp_url_for_validation = f"http://{base_site_input}"
                is_valid = domain(temp_url_for_validation)
                domain_to_save = base_site_input
            except Exception as val_err:
                logger.warning(f"{log_prefix} Validación de dominio fallida para '{base_site_input}': {val_err}")
                is_valid = False

            if not is_valid:
                logger.warning(f"{log_prefix} Intento de establecer sitio base inválido: '{base_site_input}'")
                return await m.reply_text(
                    f"{help_text}\n\n"
                    f"❌ **Error:** '{base_site_input}' no parece ser un nombre de dominio válido. "
                    f"Asegúrate de introducir solo el dominio (ej: `ejemplo.com`) sin `http://` o `/` al final.",
                    disable_web_page_preview=True
                )

            logger.info(f"{log_prefix} Solicitud para actualizar sitio base a: '{domain_to_save}'")
            try:
                await update_user_info(user_id, {"base_site": domain_to_save})
                await m.reply_text(f"✅ Tu sitio base ha sido actualizado a: `{domain_to_save}`")
                logger.info(f"{log_prefix} Actualización de sitio base exitosa.")
            except Exception as e:
                logger.error(f"{log_prefix} Error al actualizar el sitio base en users_api: {e}")
                await m.reply_text("❌ Ocurrió un error al intentar actualizar tu sitio base.")

    # Comando con formato incorrecto
    else:
        logger.warning(f"{log_prefix} Uso incorrecto del comando: {' '.join(cmd)}")
        await m.reply_text(
            "**Formato incorrecto.**\n\n" + help_text,
            disable_web_page_preview=True
        )


@Client.on_message(filters.command("stats") & filters.private & filters.user(ADMINS))
async def simple_stats_command(client, message: Message):
    """Muestra estadísticas básicas (solo para admins)."""
    log_prefix = f"CMD /stats (Admin: {message.from_user.id}):"

    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
        total_users = await db.total_users_count()
        logger.info(f"{log_prefix} Obteniendo estadísticas. Total usuarios: {total_users}")

        stats_text = (
            f"📊 **Estadísticas del Bot**\n\n"
            f"👥 Usuarios Totales Registrados: `{total_users}`\n\n"
        )
        await message.reply_text(stats_text, quote=True)

    except Exception as e:
        logger.error(f"{log_prefix} Error al obtener o enviar estadísticas: {e}", exc_info=True)
        await message.reply_text("❌ Ocurrió un error al intentar obtener las estadísticas.")


# --- Manejador de Callbacks (Botones Inline) (Formateado) ---
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    """Maneja las pulsaciones de botones inline."""
    user_id = query.from_user.id
    q_data = query.data
    message = query.message
    log_prefix = f"CB (User: {user_id}, Data: '{q_data}'):" # Prefijo para logs

    logger.debug(f"{log_prefix} Callback recibido.")

    try:
        try:
            me_mention = client.me.mention if client.me else (await client.get_me()).mention
        except Exception as e:
            logger.error(f"{log_prefix} Error al obtener get_me para mention: {e}")
            me_mention = "este Bot" # Fallback

        # --- Manejar diferentes datos de callback ---

        if q_data == "close_data":
            logger.debug(f"{log_prefix} Solicitud para cerrar mensaje {message.id}")
            await message.delete()
            await query.answer()

        elif q_data == "about":
            logger.debug(f"{log_prefix} Mostrando sección 'About'")
            buttons = [[
                InlineKeyboardButton('🏠 Inicio', callback_data='start'),
                InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')
            ]]
            markup = InlineKeyboardMarkup(buttons)
            about_text = getattr(script, 'ABOUT_TXT', "Información no disponible.")
            if '{me_mention}' in about_text:
                 about_text = about_text.format(me_mention=me_mention)

            await query.edit_message_text(
                about_text,
                reply_markup=markup,
                disable_web_page_preview=True
            )
            await query.answer()

        elif q_data == "start":
            logger.debug(f"{log_prefix} Mostrando sección 'Start'")
            buttons = [
                [InlineKeyboardButton('Canal Principal', url='https://t.me/NessCloud'),
                 InlineKeyboardButton('Grupo de Soporte', url='https://t.me/NESS_Soporte')],
                [InlineKeyboardButton('❓ Ayuda', callback_data='help'),
                 InlineKeyboardButton('ℹ️ Acerca de', callback_data='about')]
            ]
            # --- Botón Clonar Eliminado ---
            # if not CLONE_MODE:
            #     buttons.append([InlineKeyboardButton('🤖 Clonar Bot', callback_data='clone')])
            markup = InlineKeyboardMarkup(buttons)

            start_text = getattr(script, 'START_TXT', "Bienvenido!")
            if '{mention}' in start_text or '{me_mention}' in start_text: # Adaptar según formato exacto en Script.py
                 start_text = start_text.format(mention=query.from_user.mention, me_mention=me_mention)
            elif '{message.from_user.mention}' in start_text or '{me.mention}' in start_text: # Formato alternativo
                  start_text = start_text.format(mention=query.from_user.mention, me_mention=me_mention) # O usar las variables directas si están disponibles


            try:
                await query.edit_message_text(
                    start_text,
                    reply_markup=markup,
                    disable_web_page_preview=True
                )
            except MessageNotModified:
                logger.debug(f"{log_prefix} Mensaje 'Start' no modificado (ya estaba visible).")
                pass
            except Exception as edit_text_err:
                 logger.warning(f"{log_prefix} Fallo al editar texto para 'Start': {edit_text_err}. Intentando editar media.")
                 try:
                     photo_url = random.choice(PICS) if PICS else None
                     if photo_url and query.message.photo:
                          await query.edit_message_media(
                              media=InputMediaPhoto(photo_url),
                              reply_markup=markup
                          )
                          await query.edit_message_caption(
                              caption=start_text,
                              reply_markup=markup
                          )
                     else:
                          logger.warning(f"{log_prefix} No se pudo editar ni texto ni media para 'Start'.")
                 except MessageNotModified:
                      logger.debug(f"{log_prefix} Media/Caption 'Start' no modificado.")
                      pass
                 except Exception as e_media:
                     logger.error(f"{log_prefix} Fallo CRÍTICO al editar media/caption para 'Start': {e_media}")
            await query.answer()

        # --- Bloque 'clone' Eliminado ---
        # elif q_data == "clone":
        #      logger.debug(f"{log_prefix} Mostrando sección 'Clone'")
        #      buttons = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons)
        #      clone_text = getattr(script, 'CLONE_TXT', "Instrucciones de clonación no disponibles.")
        #      if '{query.from_user.mention}' in clone_text:
        #          clone_text = clone_text.format(mention=query.from_user.mention)
        #
        #      await query.edit_message_text(
        #          clone_text,
        #          reply_markup=markup,
        #          disable_web_page_preview=True
        #      )
        #      await query.answer()

        elif q_data == "help":
             logger.debug(f"{log_prefix} Mostrando sección 'Help'")
             buttons = [[
                 InlineKeyboardButton('🏠 Inicio', callback_data='start'),
                 InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')
             ]]
             markup = InlineKeyboardMarkup(buttons)
             help_text = getattr(script, 'HELP_TXT', "Ayuda no disponible.")

             await query.edit_message_text(
                 help_text,
                 reply_markup=markup,
                 disable_web_page_preview=True
             )
             await query.answer()

        else:
            logger.warning(f"{log_prefix} Callback no reconocido.")
            await query.answer("Esta opción no está implementada o es inválida.", show_alert=False)

    except MessageNotModified:
        logger.debug(f"{log_prefix} Mensaje no modificado (contenido idéntico).")
        await query.answer()
    except Exception as e:
        logger.error(f"{log_prefix} Error procesando callback: {e}", exc_info=True)
        try:
            await query.answer("❌ Ocurrió un error al procesar tu solicitud.", show_alert=True)
        except Exception as answer_err:
             logger.error(f"{log_prefix} Error incluso al intentar responder al callback con error: {answer_err}")


# --- Comandos Premium (Sin cambios aquí) ---
@Client.on_message(filters.command("addpremium") & filters.private & filters.user(ADMINS))
async def add_premium_command(client, message: Message):
    """Añade acceso premium a un usuario (Admin Only)."""
    log_prefix = f"CMD /addpremium (Admin: {message.from_user.id}):"
    usage_text = (
        "ℹ️ **Cómo usar /addpremium:**\n\n"
        "Este comando otorga acceso Premium a un usuario.\n\n"
        "**Formatos:**\n"
        "1. Para añadir premium **permanentemente**:\n"
        "   `/addpremium ID_DEL_USUARIO`\n\n"
        "2. Para añadir premium por un **número específico de días**:\n"
        "   `/addpremium ID_DEL_USUARIO NUMERO_DE_DIAS`\n\n"
        "**Ejemplos:**\n"
        "   `/addpremium 123456789` (Otorga premium permanente al usuario con ID 123456789)\n"
        "   `/addpremium 987654321 30` (Otorga premium por 30 días al usuario con ID 987654321)"
    )

    if len(message.command) < 2 or len(message.command) > 3:
        logger.warning(f"{log_prefix} Uso incorrecto: {' '.join(message.command)}")
        return await message.reply_text(usage_text)

    try:
        target_user_id = int(message.command[1])
    except ValueError:
        logger.warning(f"{log_prefix} ID de usuario inválido: {message.command[1]}")
        return await message.reply_text(f"❌ ID de usuario inválido.\n\n{usage_text}")

    days = None
    if len(message.command) == 3:
        try:
            days = int(message.command[2])
            if days <= 0: raise ValueError("Los días deben ser un número positivo.")
        except ValueError as e:
            logger.warning(f"{log_prefix} Número de días inválido: {message.command[2]} ({e})")
            return await message.reply_text(f"❌ Número de días inválido. Debe ser un entero positivo.\n\n{usage_text}")

    if not await db.is_user_exist(target_user_id):
        logger.warning(f"{log_prefix} Usuario {target_user_id} no encontrado en la base de datos.")
        return await message.reply_text(f"❌ Usuario con ID `{target_user_id}` no encontrado. Asegúrate de que haya iniciado el bot al menos una vez.")

    try:
        success = await db.set_premium(target_user_id, days)
        if success:
            d_txt = f"por {days} días" if days else "de forma permanente"
            confirmation_msg = f"✅ ¡Acceso Premium activado para el usuario `{target_user_id}` {d_txt}!"
            await message.reply_text(confirmation_msg)
            logger.info(f"{log_prefix} Premium activado para {target_user_id} {d_txt}.")
            try:
                await client.send_message(
                    target_user_id,
                    f"🎉 ¡Felicidades! Has recibido acceso Premium en {client.me.mention} {d_txt}."
                )
            except Exception as notify_err:
                logger.warning(f"{log_prefix} No se pudo notificar al usuario {target_user_id} sobre su nuevo premium: {notify_err}")
                await message.reply_text("ℹ️ *Nota: No se pudo notificar al usuario directamente (quizás bloqueó al bot).*")
        else:
            logger.error(f"{log_prefix} La función db.set_premium devolvió False para {target_user_id}.")
            await message.reply_text(f"❌ Ocurrió un error inesperado al intentar activar premium para `{target_user_id}`.")
    except Exception as e:
        logger.error(f"{log_prefix} Error CRÍTICO durante set_premium para {target_user_id}: {e}", exc_info=True)
        await message.reply_text("❌ Error interno del servidor al procesar la solicitud.")

@Client.on_message(filters.command("delpremium") & filters.private & filters.user(ADMINS))
async def del_premium_command(client, message: Message):
    """Elimina el acceso premium de un usuario (Admin Only)."""
    log_prefix = f"CMD /delpremium (Admin: {message.from_user.id}):"
    usage_text = (
        "ℹ️ **Cómo usar /delpremium:**\n\n"
        "Este comando elimina el acceso Premium de un usuario.\n\n"
        "**Formato:**\n"
        "   `/delpremium ID_DEL_USUARIO`\n\n"
        "**Ejemplo:**\n"
        "   `/delpremium 123456789` (Elimina el premium del usuario con ID 123456789)"
    )

    if len(message.command) != 2:
        logger.warning(f"{log_prefix} Uso incorrecto: {' '.join(message.command)}")
        return await message.reply_text(usage_text)

    try:
        target_user_id = int(message.command[1])
    except ValueError:
        logger.warning(f"{log_prefix} ID de usuario inválido: {message.command[1]}")
        return await message.reply_text(f"❌ ID de usuario inválido.\n\n{usage_text}")

    if not await db.is_user_exist(target_user_id):
        logger.warning(f"{log_prefix} Usuario {target_user_id} no encontrado.")
        return await message.reply_text(f"❌ Usuario con ID `{target_user_id}` no encontrado en la base de datos.")

    if not await db.check_premium_status(target_user_id):
         logger.info(f"{log_prefix} El usuario {target_user_id} ya no tenía premium.")
         return await message.reply_text(f"ℹ️ El usuario `{target_user_id}` no tiene acceso Premium activo actualmente.")

    try:
        success = await db.remove_premium(target_user_id)
        if success:
            confirmation_msg = f"✅ Acceso Premium desactivado para el usuario `{target_user_id}`."
            await message.reply_text(confirmation_msg)
            logger.info(f"{log_prefix} Premium desactivado para {target_user_id}.")
            try:
                await client.send_message(
                    target_user_id,
                    f"ℹ️ Tu acceso Premium en {client.me.mention} ha sido desactivado."
                )
            except Exception as notify_err:
                logger.warning(f"{log_prefix} No se pudo notificar al usuario {target_user_id} sobre la pérdida de premium: {notify_err}")
                await message.reply_text("ℹ️ *Nota: No se pudo notificar al usuario directamente.*")
        else:
            logger.error(f"{log_prefix} La función db.remove_premium devolvió False para {target_user_id}.")
            await message.reply_text(f"❌ Ocurrió un error inesperado al intentar desactivar premium para `{target_user_id}`.")
    except Exception as e:
        logger.error(f"{log_prefix} Error CRÍTICO durante remove_premium para {target_user_id}: {e}", exc_info=True)
        await message.reply_text("❌ Error interno del servidor al procesar la solicitud.")

# --- Fin del archivo plugins/commands.py ---
