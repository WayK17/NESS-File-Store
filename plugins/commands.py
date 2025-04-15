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
    # Definir funciones dummy para evitar NameError, pero funcionalidad estará rota
    async def check_user_membership(c, u, ch): return True
    async def verify_user(c, u, t): pass
    async def check_token(c, u, t): return False
    async def check_verification(c, u): return True # O False, según prefieras el default
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
# logger.setLevel(logging.DEBUG) # Ajusta si necesitas más detalle

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
        # Eliminar caracteres problemáticos
        file_name = re.sub(r'[\[\]\(\)]', '', file_name)
        # Eliminar URLs, usernames y espacios extra
        parts = file_name.split()
        filtered_parts = filter(lambda x: x and not x.startswith(('http', '@', 'www.')), parts)
        cleaned_name = ' '.join(filtered_parts)
        return cleaned_name if cleaned_name else original_name # Devolver original si queda vacío
    except Exception as e:
        logger.error(f"Error formateando nombre '{original_name}': {e}")
        return original_name # Devolver original en caso de error

# --- Manejador del Comando /start ---
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client: Client, message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    logger.info(f"/start de {user_id} ({message.from_user.mention})")

    # Registro de usuario si es nuevo
    username = client.me.username
    if not await db.is_user_exist(user_id):
        logger.info(f"Usuario {user_id} es nuevo. Añadiendo.")
        await db.add_user(user_id, first_name)
        if LOG_CHANNEL:
            try:
                await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(user_id, message.from_user.mention))
            except Exception as log_err:
                logger.error(f"Error enviando a LOG_CHANNEL {LOG_CHANNEL}: {log_err}")
        else:
            logger.warning("LOG_CHANNEL no definido.")

    # Manejo de /start sin payload (Bienvenida)
    if len(message.command) == 1:
        logger.info(f"Enviando bienvenida normal a {user_id}")
        buttons_list = [
            [InlineKeyboardButton('Únete a Nuestro Canal', url='https://t.me/NessCloud')],
            [InlineKeyboardButton('⚠️ Grupo de Soporte', url='https://t.me/NESS_Soporte')]
        ]
        if not CLONE_MODE: # Simplificado
            buttons_list.append([InlineKeyboardButton('🤖 Clonar Bot', callback_data='clone')]) # Añadido texto
        reply_markup = InlineKeyboardMarkup(buttons_list)
        me = client.me
        try:
            photo_url = random.choice(PICS) if PICS else "https://telegra.ph/file/7d253c933e10c1f47db37.jpg" # Fallback
            await message.reply_photo(
                photo=photo_url,
                caption=script.START_TXT.format(message.from_user.mention, me.mention),
                reply_markup=reply_markup
            )
        except Exception as welcome_err:
             logger.error(f"Error enviando bienvenida a {user_id}: {welcome_err}")
             await message.reply_text(
                 script.START_TXT.format(message.from_user.mention, me.mention),
                 reply_markup=reply_markup
             )
        return

    # --- PROCESAMIENTO CON PAYLOAD ---
    payload_encoded_full = message.command[1]
    logger.info(f"/start con payload '{payload_encoded_full}' de {user_id}")

    # Borrar mensaje "Únete" anterior
    try:
        user_info = await db.get_user_info(user_id)
        pending_msg_id = user_info.get("pending_join_msg_id") if user_info else None
        if pending_msg_id:
            logger.debug(f"Borrando msg {pending_msg_id} para {user_id}")
            await client.delete_messages(user_id, pending_msg_id)
            await db.update_user_info(user_id, {"pending_join_msg_id": None})
    except MessageIdInvalid: # El mensaje ya no existía
        logger.info(f"Mensaje 'Únete' ({pending_msg_id}) para {user_id} ya no existía (probablemente borrado).")
        await db.update_user_info(user_id, {"pending_join_msg_id": None}) # Limpiar DB igual
    except Exception as db_err:
        logger.error(f"Error DB borrando msg pendiente {user_id}: {db_err}")

    # Verificación Force Subscribe
    should_skip_fsub = not FORCE_SUB_ENABLED or (SKIP_FORCE_SUB_FOR_ADMINS and user_id in ADMINS)
    logger.debug(f"ForceSub Check: skip={should_skip_fsub}")
    if not should_skip_fsub and FORCE_SUB_CHANNEL and FORCE_SUB_INVITE_LINK:
        logger.debug(f"Realizando chequeo ForceSub para {user_id}")
        try:
            is_member = await check_user_membership(client, user_id, FORCE_SUB_CHANNEL)
            if not is_member:
                logger.info(f"Usuario {user_id} NO miembro. Mostrando mensaje ForceSub.")
                buttons = [
                    [InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)],
                    [InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{username}?start={payload_encoded_full}")]
                ]
                join_message = await message.reply_text(
                    script.FORCE_MSG.format(mention=message.from_user.mention),
                    reply_markup=InlineKeyboardMarkup(buttons),
                    quote=True,
                    disable_web_page_preview=True
                )
                await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id})
                return
        except Exception as fs_err:
            logger.error(f"Error CRÍTICO en Force Subscribe para {user_id}: {fs_err}", exc_info=True)
            # Permitir continuar como failsafe

    # Decodificación y Chequeos Premium/Verify
    logger.info(f"Usuario {user_id} pasó verificaciones iniciales. Procesando payload: {payload_encoded_full}")
    is_batch = False
    base64_to_decode = payload_encoded_full
    link_type = "normal"
    original_payload_id = ""

    if payload_encoded_full.startswith("BATCH-"):
        is_batch = True
        base64_to_decode = payload_encoded_full[len("BATCH-"):]
        logger.debug(f"Prefijo BATCH- detectado. Base64: {base64_to_decode}")

    try:
        padding = 4 - (len(base64_to_decode) % 4)
        if padding == 4: padding = 0
        payload_decoded = base64.urlsafe_b64decode(base64_to_decode + "=" * padding).decode("ascii")
        logger.debug(f"Payload decodificado: {payload_decoded}")

        original_payload_id = payload_decoded
        if payload_decoded.startswith("premium:"):
            link_type = "premium"
            original_payload_id = payload_decoded[len("premium:"):]
        elif payload_decoded.startswith("normal:"):
            link_type = "normal"
            original_payload_id = payload_decoded[len("normal:"):]
        elif payload_decoded.startswith("verify-"):
             link_type = "special"
             original_payload_id = payload_decoded
        else:
             logger.warning(f"Payload '{payload_decoded}' sin prefijo. Asumiendo normal/especial.")
             original_payload_id = payload_decoded

        logger.debug(f"Tipo enlace: {link_type}. ID original: {original_payload_id}")

    except (base64.binascii.Error, UnicodeDecodeError) as b64_err:
        logger.error(f"Error decodificando Base64 '{base64_to_decode}' para {user_id}: {b64_err}")
        return await message.reply_text("❌ Enlace inválido o corrupto (Error Base64).")
    except Exception as decode_err:
        logger.error(f"Error inesperado decodificando payload para {user_id}: {decode_err}")
        return await message.reply_text("❌ Error al procesar el enlace.")

    # Chequeo Premium
    is_premium_user = await db.check_premium_status(user_id)
    is_admin_user = user_id in ADMINS
    logger.debug(f"Usuario {user_id} es premium: {is_premium_user}, es admin: {is_admin_user}")
    if link_type == "premium" and not is_premium_user and not is_admin_user:
        logger.info(f"Usuario normal {user_id} denegado para enlace premium '{original_payload_id}'.")
        try:
            await message.reply_text(script.PREMIUM_REQUIRED_MSG.format(mention=message.from_user.mention), quote=True)
        except AttributeError:
            await message.reply_text("❌ Acceso denegado. Contenido Premium.", quote=True)
        return
    elif link_type == "premium" and is_admin_user and not is_premium_user:
        logger.info(f"Admin {user_id} accediendo a enlace premium (permitido).")

    # Chequeo Verificación
    try:
        apply_verify_check = VERIFY_MODE and not original_payload_id.startswith("verify-")
        if apply_verify_check and not await check_verification(client, user_id):
            logger.info(f"Usuario {user_id} necesita verificación para enlace tipo {link_type}.")
            verify_url = await get_token(client, user_id, f"https://t.me/{username}?start=")
            btn_list = [[InlineKeyboardButton("Verify", url=verify_url)]]
            if VERIFY_TUTORIAL: btn_list.append([InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)])
            await message.reply_text("<b>You are not verified !\nKindly verify to continue !</b>", protect_content=True, reply_markup=InlineKeyboardMarkup(btn_list))
            return
    except Exception as e:
        logger.error(f"Error en check_verification para {user_id}: {e}")
        return await message.reply_text(f"**Error verificando tu estado: {e}**")

    # --- SI PASÓ TODOS LOS CHEQUEOS: Procesar el original_payload_id ---
    logger.info(f"Usuario {user_id} ({link_type}) procesando ID '{original_payload_id}' (Batch: {is_batch})")

    # Lógica para 'verify-'
    if original_payload_id.startswith("verify-"):
        logger.debug(f"Manejando 'verify' payload para {user_id}")
        try:
            parts = original_payload_id.split("-")
            if len(parts) < 3: raise ValueError("Payload verify incompleto")
            verify_userid_str = parts[1]
            verify_token = parts[2]
            if str(user_id) != verify_userid_str:
                logger.warning(f"Verify fail: ID mismatch ({user_id} != {verify_userid_str})")
                return await message.reply_text("<b>¡Enlace No Válido! (ID)</b>", protect_content=True)

            if await check_token(client, verify_userid_str, verify_token):
                logger.info(f"User {verify_userid_str} verified OK with token {verify_token}")
                await message.reply_text(f"<b>Hey {message.from_user.mention}, ¡Verificado!</b>...", protect_content=True)
                await verify_user(client, verify_userid_str, verify_token)
            else:
                logger.warning(f"Verify fail for {verify_userid_str}: Invalid/used token {verify_token}")
                return await message.reply_text("<b>¡Enlace No Válido! (Token)</b>", protect_content=True)
        except Exception as verify_e:
             logger.error(f"Error en lógica 'verify': {verify_e}")
             await message.reply_text("<b>Error durante verificación.</b>")
        return

    # Lógica para BATCH
    elif is_batch:
        batch_json_msg_id = original_payload_id
        logger.info(f"Manejando 'BATCH'. ID JSON: {batch_json_msg_id}")
        sts = await message.reply_text("**🔺 Procesando lote...**", quote=True)
        msgs = BATCH_FILES.get(batch_json_msg_id)
        if not msgs:
             try:
                 log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
                 batch_list_msg = await client.get_messages(log_channel_int, int(batch_json_msg_id))
                 if not batch_list_msg or not batch_list_msg.document: raise ValueError("Msg lista batch no encontrado/inválido")
                 file_path = await client.download_media(batch_list_msg.document.file_id)
                 try:
                     with open(file_path, 'r') as file_data: msgs = json.loads(file_data.read())
                     BATCH_FILES[batch_json_msg_id] = msgs
                 finally:
                     if os.path.exists(file_path): os.remove(file_path)
             except Exception as batch_load_err:
                 logger.error(f"Error cargando BATCH (JSON ID {batch_json_msg_id}): {batch_load_err}", exc_info=True)
                 return await sts.edit_text("❌ Error cargando información del lote.")
        if not msgs: return await sts.edit_text("❌ Error: Información del lote vacía.")

        filesarr = []
        logger.info(f"Enviando {len(msgs)} mensajes BATCH {batch_json_msg_id} a {user_id}")
        # --- TU BUCLE COMPLETO DE ENVÍO DE BATCH VA AQUÍ ---
        # (Asegúrate que este bucle sea robusto y maneje media groups si es necesario)
        for i, msg_info in enumerate(msgs):
             try:
                 channel_id = int(msg_info.get("channel_id"))
                 msgid = int(msg_info.get("msg_id"))
                 original_msg = await client.get_messages(channel_id, msgid)
                 # Aquí deberías tener tu lógica para preparar caption, botones stream, etc.
                 # y manejar media groups si es necesario antes de copiar/enviar
                 sent_msg = await original_msg.copy(user_id) # Ejemplo simplificado
                 filesarr.append(sent_msg)
                 if i % 5 == 0: await asyncio.sleep(0.1) # Pausa
             except FloodWait as fw_err:
                 logger.warning(f"FloodWait en BATCH item {i}. Esperando {fw_err.value}s")
                 await asyncio.sleep(fw_err.value + 2)
                 try: # Reintentar
                      original_msg = await client.get_messages(channel_id, msgid)
                      sent_msg = await original_msg.copy(user_id); filesarr.append(sent_msg)
                 except Exception as retry_err: logger.error(f"Error BATCH item {i} (retry): {retry_err}")
             except Exception as loop_err: logger.error(f"Error BATCH item {i}: {loop_err}")
        # --- FIN DEL BUCLE ---
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
            # Extraer ID del mensaje del payload "file_<id>"
            if not original_payload_id.startswith("file_"):
                 # Asumir ID directo como fallback para enlaces viejos? O error?
                 logger.warning(f"Payload archivo único '{original_payload_id}' no empieza con 'file_'. Asumiendo ID directo.")
                 decode_file_id = int(original_payload_id)
            else:
                 decode_file_id = int(original_payload_id.split("_", 1)[1])

            log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
            original_msg = await client.get_messages(log_channel_int, decode_file_id)
            if not original_msg: raise MessageIdInvalid("Mensaje original no encontrado")

            # Preparar caption y botones (Tu lógica original)
            f_caption = ""; reply_markup = None
            if original_msg.media:
                 media = getattr(original_msg, original_msg.media.value, None)
                 title = formate_file_name(getattr(media, "file_name", "")) if media else ""
                 size = get_size(getattr(media, "file_size", 0)) if media else ""
                 f_caption_orig = getattr(original_msg, 'caption', '')
                 if CUSTOM_FILE_CAPTION:
                     try: f_caption = CUSTOM_FILE_CAPTION.format(file_name=title, file_size=size, file_caption=f_caption_orig if f_caption_orig else "")
                     except Exception as cap_fmt_err: logger.warning(f"Error formateando CUSTOM_FILE_CAPTION: {cap_fmt_err}"); f_caption = f"<code>{title}</code>"
                 else: f_caption = f"<code>{title}</code>" if title else ""
                 if STREAM_MODE and (original_msg.video or original_msg.document):
                     # ... (Tu lógica de botones Stream) ...
                     pass

            # Copiar el mensaje
            sent_file_msg = await original_msg.copy(
                chat_id=user_id, caption=f_caption if original_msg.media else None,
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

        except MessageIdInvalid as e:
            logger.error(f"Msg ID {decode_file_id} no encontrado {LOG_CHANNEL} (Single File): {e}.")
            await message.reply_text("❌ Error: El archivo solicitado ya no está disponible.")
        except (ValueError, IndexError, AttributeError) as payload_err:
            logger.error(f"Error procesando payload archivo único '{original_payload_id}': {payload_err}")
            await message.reply_text("❌ Error: Enlace de archivo inválido.")
        except Exception as e:
            logger.error(f"Error crítico Archivo Único {user_id}: {e}", exc_info=True)
            await message.reply_text("❌ Ocurrió un error inesperado.")
        return

# --- Comandos /api, /base_site, /stats (Formateados) ---
@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    user_id = m.from_user.id
    try:
        user = await get_user(user_id)
        user_base_site = user.get("base_site", "N/Configurado") if user else "N/A"
        user_shortener_api = user.get("shortener_api", "N/Configurada") if user else "N/A"
    except Exception as e:
        logger.error(f"Error get_user en api_handler {user_id}: {e}")
        return await m.reply_text("❌ Error obteniendo config API.")

    cmd = m.command
    if len(cmd) == 1:
        try:
            s = script.SHORTENER_API_MESSAGE.format(base_site=user_base_site, shortener_api=user_shortener_api)
            await m.reply_text(s)
        except AttributeError: await m.reply_text("Error: Texto no encontrado.")
        except Exception as fmt_err: logger.error(f"Error fmt API_MSG: {fmt_err}"); await m.reply_text("Error info API.")
    elif len(cmd) == 2:
        api_key = cmd[1].strip()
        update_value = None if api_key.lower() == "none" else api_key
        if update_value == "": return await m.reply_text("❌ API no puede ser vacía.")

        log_msg = "eliminando" if update_value is None else f"actualizando a: {api_key[:5]}..."
        logger.info(f"Usuario {user_id} {log_msg} Shortener API.")
        try:
            await update_user_info(user_id, {"shortener_api": update_value})
            reply_msg = "<b>✅ API del Acortador eliminada.</b>" if update_value is None else "<b>✅ API del Acortador actualizada.</b>"
            await m.reply_text(reply_msg)
        except Exception as e: logger.error(f"Error update API {user_id}: {e}"); await m.reply_text("❌ Error actualizando API.")
    else:
        await m.reply_text("Formato:\n`/api` (ver)\n`/api KEY` (establecer)\n`/api None` (eliminar)")

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    user_id = m.from_user.id
    try:
        user = await get_user(user_id)
        current_site = user.get("base_site", "Ninguno") if user else "N/A"
    except Exception as e: logger.error(f"Error get_user base_site {user_id}: {e}"); return await m.reply_text("❌ Error obteniendo config.")

    cmd = m.command
    help_text = (f"⚙️ **Sitio Base Acortador**\n\nActual: `{current_site}`\n\n➡️ `/base_site tudominio.com`\n➡️ `/base_site None`")

    if len(cmd) == 1:
        await m.reply_text(text=help_text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site_input = cmd[1].strip().lower()
        if base_site_input == "none":
            logger.info(f"Usuario {user_id} eliminando base_site.")
            try: await update_user_info(user_id, {"base_site": None}); await m.reply_text("<b>✅ Sitio Base eliminado.</b>")
            except Exception as e: logger.error(f"Error del base_site {user_id}: {e}"); await m.reply_text("❌ Error eliminando.")
        else:
            try: is_valid_domain = domain(base_site_input)
            except Exception as val_err: logger.error(f"Error validando {base_site_input}: {val_err}"); is_valid_domain = False
            if not is_valid_domain: return await m.reply_text(help_text + "\n\n❌ Dominio inválido.", disable_web_page_preview=True)
            logger.info(f"Usuario {user_id} actualizando base_site a: {base_site_input}")
            try: await update_user_info(user_id, {"base_site": base_site_input}); await m.reply_text(f"<b>✅ Sitio Base actualizado a:</b> `{base_site_input}`")
            except Exception as e: logger.error(f"Error update base_site {user_id}: {e}"); await m.reply_text("❌ Error actualizando.")
    else:
        await m.reply_text("Formato incorrecto.\n" + help_text, disable_web_page_preview=True)

@Client.on_message(filters.command("stats") & filters.private)
async def simple_stats_command(client, message):
    # Función formateada
    if message.from_user.id not in ADMINS:
        return await message.reply_text("❌ **Acceso denegado.** Solo admins.")
    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
        total_users = await db.total_users_count()
        stats_text = (f"📊 **Estadísticas de la Base de Datos:**\n\n👥 Usuarios: `{total_users}`")
        await message.reply_text(stats_text, quote=True)
    except Exception as e:
        logger.error(f"Error en /stats (simple): {e}")
        await message.reply_text(" Ocurrió un error.")

# --- Manejador de Callbacks (Formateado) ---
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    q_data = query.data
    logger.debug(f"Callback de {user_id}: {q_data}")

    try: me_mention = client.me.mention if client.me else (await client.get_me()).mention
    except Exception as e: logger.error(f"Error get_me en cb: {e}"); me_mention = "este Bot"

    message = query.message # Mensaje al que está adjunto el botón

    try:
        if q_data == "close_data":
            logger.debug(f"Cerrando mensaje {message.id} para {user_id}")
            await message.delete()

        elif q_data == "about":
            logger.debug(f"Mostrando 'About' para {user_id}")
            buttons = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(
                script.ABOUT_TXT.format(me_mention), reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True
            )

        elif q_data == "start":
            logger.debug(f"Mostrando 'Start' para {user_id}")
            buttons = [[InlineKeyboardButton('Canal Principal', url='https://t.me/NessCloud'), InlineKeyboardButton('Grupo de Soporte', url='https://t.me/NESS_Soporte')],
                       [InlineKeyboardButton('❓ Ayuda', callback_data='help'), InlineKeyboardButton('ℹ️ Acerca de', callback_data='about')]]
            if not CLONE_MODE: buttons.append([InlineKeyboardButton('🤖 Clonar este Bot', callback_data='clone')])
            reply_markup = InlineKeyboardMarkup(buttons)
            # Intentar editar texto, luego media si falla (porque el /start inicial envía foto)
            try:
                 await query.edit_message_text(
                     script.START_TXT.format(query.from_user.mention, me_mention), reply_markup=reply_markup,
                     parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True
                 )
            except MessageNotModified: pass
            except Exception: # Si falla (ej, era una foto), editar media
                 logger.warning("Fallo edit text en cb 'start', intentando edit media.")
                 try:
                     await query.edit_message_media(
                          media=InputMediaPhoto(random.choice(PICS) if PICS else "..."),
                          reply_markup=reply_markup
                     )
                     await query.edit_message_caption( # Editar caption asociado
                          caption=script.START_TXT.format(query.from_user.mention, me_mention),
                          reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML
                     )
                 except Exception as e_media: logger.error(f"Fallo edit media en cb 'start': {e_media}")

        elif q_data == "clone":
             logger.debug(f"Mostrando 'Clone' para {user_id}")
             buttons = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]
             reply_markup = InlineKeyboardMarkup(buttons)
             await query.edit_message_text(
                 script.CLONE_TXT.format(query.from_user.mention), reply_markup=reply_markup,
                 parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True
             )

        elif q_data == "help":
             logger.debug(f"Mostrando 'Help' para {user_id}")
             buttons = [[InlineKeyboardButton('🏠 Inicio', callback_data='start'), InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')]]
             reply_markup = InlineKeyboardMarkup(buttons)
             await query.edit_message_text(
                 script.HELP_TXT, reply_markup=reply_markup,
                 parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True
             )

        else:
             logger.warning(f"Callback no reconocido: {q_data}")
             await query.answer("Opción no implementada.", show_alert=False)

    except MessageNotModified:
        logger.debug(f"Msg no modificado cb '{q_data}' user {user_id}")
        try: await query.answer() # Quitar loading
        except Exception: pass
    except Exception as e:
        logger.error(f"Error procesando cb '{q_data}' user {user_id}: {e}", exc_info=True)
        try: await query.answer("Error procesando tu solicitud.", show_alert=True)
        except Exception: pass


# --- Comandos Premium (Formateados) ---
@Client.on_message(filters.command("addpremium") & filters.private & filters.user(ADMINS))
async def add_premium_command(client, message: Message):
    # Función formateada
    if len(message.command) < 2:
        return await message.reply_text("⚠️ Uso: `/addpremium <user_id> [días]`\n(Si no pones días, será permanente)")
    try:
        target_user_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ ID de usuario inválido.")

    days = None
    if len(message.command) > 2:
        try:
            days = int(message.command[2])
            if days <= 0: return await message.reply_text("❌ Días debe ser positivo.")
        except ValueError: return await message.reply_text("❌ Días debe ser número.")

    if not await db.is_user_exist(target_user_id):
        return await message.reply_text(f"❌ Usuario {target_user_id} no encontrado.")

    try:
        success = await db.set_premium(target_user_id, days)
        if success:
            duration_text = f"por {days} días" if days else "permanentemente"
            await message.reply_text(f"✅ ¡Premium activado para `{target_user_id}` {duration_text}!")
            try:
                await client.send_message(target_user_id, f"🎉 ¡Felicidades! Has recibido acceso Premium {duration_text}.")
            except Exception as send_err: logger.warning(f"No notificar premium a {target_user_id}: {send_err}")
        else:
            await message.reply_text(f"❌ Error activando premium para `{target_user_id}`.")
    except Exception as e:
         logger.error(f"Error ejecutando set_premium para {target_user_id}: {e}")
         await message.reply_text("❌ Error interno al activar premium.")


@Client.on_message(filters.command("delpremium") & filters.private & filters.user(ADMINS))
async def del_premium_command(client, message: Message):
    # Función formateada
    if len(message.command) != 2:
        return await message.reply_text("⚠️ Uso: `/delpremium <user_id>`")
    try:
        target_user_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ ID de usuario inválido.")
    if not await db.is_user_exist(target_user_id):
        return await message.reply_text(f"❌ Usuario {target_user_id} no encontrado.")

    try:
        success = await db.remove_premium(target_user_id)
        if success:
            await message.reply_text(f"✅ Premium desactivado para `{target_user_id}`.")
            try:
                await client.send_message(target_user_id, "ℹ️ Tu acceso Premium ha sido desactivado.")
            except Exception as send_err: logger.warning(f"No notificar premium off a {target_user_id}: {send_err}")
        else:
            await message.reply_text(f"❌ Error desactivando premium para `{target_user_id}`.")
    except Exception as e:
         logger.error(f"Error ejecutando remove_premium para {target_user_id}: {e}")
         await message.reply_text("❌ Error interno al desactivar premium.")

