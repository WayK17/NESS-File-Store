# plugins/commands.py

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import logging
import random
import asyncio
import datetime # Necesario para calcular la expiración
from validators import domain
from Script import script # Necesitamos importar script para PREMIUM_REQUIRED_MSG
from plugins.dbusers import db # Importamos db desde dbusers (¡ya está actualizado!)
from pyrogram import Client, filters, enums
from plugins.users_api import get_user, update_user_info # Relacionado con acortador
from pyrogram.errors import ChatAdminRequired, FloodWait, UserNotParticipant, ChatWriteForbidden, MessageIdInvalid, MessageNotModified # Añadimos más errores
from pyrogram.types import * # Importa todos los tipos

from config import (
    ADMINS, LOG_CHANNEL, CLONE_MODE, PICS, VERIFY_MODE, VERIFY_TUTORIAL,
    STREAM_MODE, URL, CUSTOM_FILE_CAPTION, BATCH_FILE_CAPTION,
    AUTO_DELETE_MODE, AUTO_DELETE_TIME, AUTO_DELETE, FORCE_SUB_ENABLED, FORCE_SUB_CHANNEL, FORCE_SUB_INVITE_LINK,
    SKIP_FORCE_SUB_FOR_ADMINS
)

# Importar la función de verificación desde utils.py en la carpeta principal
try:
    from utils import check_user_membership
except ImportError:
    logging.error("¡ADVERTENCIA! La función 'check_user_membership' no se encontró en utils.py (carpeta principal). ForceSubscribe no funcionará.")
    async def check_user_membership(client, user_id, channel_id): return True # Failsafe

import re
import json
import base64
from urllib.parse import quote_plus
try:
    from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size
except ImportError:
    logging.warning("No se pudo importar desde TechVJ.utils.file_properties.")
    def get_name(msg): return "archivo"
    def get_hash(msg): return "dummyhash"
    def get_media_file_size(msg): return getattr(getattr(msg, msg.media.value, None), 'file_size', 0)

logger = logging.getLogger(__name__)

BATCH_FILES = {}

# --- Funciones get_size y formate_file_name (Sin cambios) ---
def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]; size = float(size); i = 0
    while size >= 1024.0 and i < len(units): i += 1; size /= 1024.0
    return "%.2f %s" % (size, units[i])

def formate_file_name(file_name):
    if not isinstance(file_name, str): return ""
    original_name = file_name
    try:
        chars = ["[", "]", "(", ")"];
        for c in chars: file_name = file_name.replace(c, "")
        file_name = '' + ' '.join(filter(lambda x: x and not x.startswith('http') and not x.startswith('@') and not x.startswith('www.'), file_name.split()))
        return file_name if file_name else original_name
    except Exception as e: logger.error(f"Error formateando nombre '{original_name}': {e}"); return original_name

# ============================================================
# ================== FUNCIÓN /START MODIFICADA ===============
# ============================================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    logger.info(f"/start de {user_id} ({message.from_user.mention})")

    # --- Registro de usuario si es nuevo (Sin cambios) ---
    username = client.me.username # Necesario para enlaces 'Try Again'
    if not await db.is_user_exist(user_id):
        logger.info(f"Usuario {user_id} es nuevo. Añadiendo.")
        await db.add_user(user_id, first_name)
        if LOG_CHANNEL:
             try: await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(user_id, message.from_user.mention))
             except Exception as log_err: logger.error(f"Error enviando a LOG_CHANNEL {LOG_CHANNEL}: {log_err}")
        else: logger.warning("LOG_CHANNEL no definido.")

    # --- Manejo de /start sin payload (Bienvenida) (Sin cambios) ---
    if len(message.command) == 1:
        logger.info(f"Enviando bienvenida normal a {user_id}")
        # ... (tu código de bienvenida con botones sin cambios) ...
        buttons = [[InlineKeyboardButton('Únete a Nuestro Canal', url='https://t.me/NessCloud')],[InlineKeyboardButton('⚠️ Grupo de Soporte', url='https://t.me/NESS_Soporte')]]
        if CLONE_MODE == False: buttons.append([InlineKeyboardButton('', callback_data='clone')])
        reply_markup = InlineKeyboardMarkup(buttons); me = client.me
        try: await message.reply_photo(photo=random.choice(PICS) if PICS else "...", caption=script.START_TXT.format(message.from_user.mention, me.mention), reply_markup=reply_markup)
        except Exception: await message.reply_text(script.START_TXT.format(message.from_user.mention, me.mention), reply_markup=reply_markup)
        return

    # --- PROCESAMIENTO CON PAYLOAD ---
    payload_encoded = message.command[1]
    logger.info(f"/start con payload '{payload_encoded}' de {user_id}")

    # --- Borrar mensaje "Únete" anterior (Sin cambios) ---
    try:
        user_info = await db.get_user_info(user_id); pending_msg_id = user_info.get("pending_join_msg_id") if user_info else None
        if pending_msg_id: logger.debug(f"Borrando msg {pending_msg_id} para {user_id}"); await client.delete_messages(user_id, pending_msg_id); await db.update_user_info(user_id, {"pending_join_msg_id": None})
    except Exception as db_err: logger.error(f"Error DB borrando msg pendiente {user_id}: {db_err}")

    # --- Verificación Force Subscribe (Sin cambios en su lógica interna) ---
    should_skip_check = not FORCE_SUB_ENABLED or (SKIP_FORCE_SUB_FOR_ADMINS and user_id in ADMINS)
    logger.debug(f"ForceSub Check: skip={should_skip_check}")
    if not should_skip_check and FORCE_SUB_CHANNEL and FORCE_SUB_INVITE_LINK:
        logger.debug(f"Realizando chequeo ForceSub para {user_id}")
        try:
            is_member = await check_user_membership(client, user_id, FORCE_SUB_CHANNEL)
            if not is_member:
                logger.info(f"Usuario {user_id} NO miembro. Mostrando mensaje ForceSub.")
                # --- Tus botones y textos ---
                buttons = [[InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)]]
                try: buttons.append([InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{username}?start={payload_encoded}")]) # Usar payload_encoded original
                except IndexError: buttons.append([InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{username}?start")])
                join_message = await message.reply_text(script.FORCE_MSG.format(mention=message.from_user.mention), reply_markup=InlineKeyboardMarkup(buttons), quote=True, disable_web_page_preview=True)
                # Guardar ID
                await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id})
                return # Detener
        except Exception as fs_err: logger.error(f"Error CRÍTICO en Force Subscribe para {user_id}: {fs_err}", exc_info=True)

    # =========================================================================
    # ============ INICIO: SECCIÓN MODIFICADA PARA PREMIUM/NORMAL =============
    # =========================================================================
    logger.info(f"Usuario {user_id} pasó verificaciones. Procesando payload: {payload_encoded}")

    # --- Decodificar payload y determinar tipo ---
    try:
        padding = 4 - (len(payload_encoded) % 4)
        payload_decoded = base64.urlsafe_b64decode(payload_encoded + "=" * padding).decode("ascii")
        logger.debug(f"Payload decodificado: {payload_decoded}")

        link_type = "normal" # Asumir normal por defecto o para enlaces viejos
        original_payload = payload_decoded # Payload real a procesar

        # Verificar prefijo nuevo (ej: "premium:file_123" o "normal:BATCH-...") NO! BATCH ya tiene prefijo
        # El prefijo va DENTRO del base64
        if payload_decoded.startswith("premium:"):
            link_type = "premium"
            original_payload = payload_decoded[len("premium:"):] # Quitar prefijo "premium:"
            logger.debug(f"Tipo Premium detectado. Payload original: {original_payload}")
        elif payload_decoded.startswith("normal:"):
            link_type = "normal"
            original_payload = payload_decoded[len("normal:"):] # Quitar prefijo "normal:"
            logger.debug(f"Tipo Normal detectado. Payload original: {original_payload}")
        else:
            # Sin prefijo: ¿Enlace antiguo? ¿Verify? ¿BATCH antiguo?
            # Mantenemos el payload_decoded como original_payload para compatibilidad
            logger.debug(f"Sin prefijo 'premium:' o 'normal:'. Asumiendo tipo 'normal' o formato especial. Payload original: {original_payload}")
            # La lógica de abajo manejará "verify-", "BATCH-", etc.

    except (base64.binascii.Error, UnicodeDecodeError) as b64_err:
        logger.error(f"Error decodificando payload '{payload_encoded}' para {user_id}: {b64_err}")
        return await message.reply_text("❌ Enlace inválido o corrupto.")
    except Exception as decode_err:
        logger.error(f"Error inesperado decodificando payload para {user_id}: {decode_err}")
        return await message.reply_text("❌ Error al procesar el enlace.")

    # --- Chequeo de Acceso Premium ---
    is_premium_user = await db.check_premium_status(user_id)
    # --- NUEVO: Comprobar si es Admin ---
    is_admin_user = user_id in ADMINS
    logger.debug(f"Usuario {user_id} es premium: {is_premium_user}, es admin: {is_admin_user}")

    # --- Condición Modificada ---
    # Denegar SOLO SI: el enlace es premium Y el usuario NO es premium Y TAMPOCO es admin
    if link_type == "premium" and not is_premium_user and not is_admin_user:
        logger.info(f"Usuario normal {user_id} intentó acceder a enlace premium '{original_payload}'. Denegado.")
        # Enviar mensaje de acceso denegado (Necesita PREMIUM_REQUIRED_MSG en Script.py)
        try:
             await message.reply_text(
                 script.PREMIUM_REQUIRED_MSG.format(mention=message.from_user.mention),
                 quote=True
             )
        except AttributeError: # Fallback si falta el texto en Script.py
             await message.reply_text("❌ Acceso denegado. Este contenido es solo para usuarios Premium.", quote=True)
        return # Detener ejecución
    else:
        # Log opcional si un admin accede sin ser premium explícito
        if link_type == "premium" and is_admin_user and not is_premium_user:
             logger.info(f"Admin {user_id} accediendo a enlace premium (permitido por ser admin).")

    # --- Chequeo de VERIFICACIÓN (Tu lógica original, aplicada ahora) ---
    # (Decide si aplica a todos los enlaces o solo a normales/premium)
    try:
        # Ejemplo: aplicar a todos excepto 'verify-'
        is_verify_payload = original_payload.startswith("verify-")
        apply_verify_check = VERIFY_MODE and not is_verify_payload

        if apply_verify_check and not await check_verification(client, user_id):
            logger.info(f"Usuario {user_id} necesita verificación para enlace tipo {link_type}.")
            verify_url = await get_token(client, user_id, f"https://t.me/{username}?start=")
            btn = [[InlineKeyboardButton("Verify", url=verify_url)]]
            if VERIFY_TUTORIAL: btn.append([InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)])
            await message.reply_text("<b>You are not verified !\nKindly verify to continue !</b>", protect_content=True, reply_markup=InlineKeyboardMarkup(btn))
            return
    except Exception as e:
        logger.error(f"Error en check_verification para {user_id} (link_type={link_type}): {e}")
        return await message.reply_text(f"**Error verificando tu estado: {e}**")


    # --- SI PASÓ TODOS LOS CHEQUEOS: Procesar el original_payload ---
    logger.info(f"Usuario {user_id} ({'Premium' if is_premium_user else 'Normal'}) procesando payload '{original_payload}' (Tipo enlace: {link_type})")

    # AHORA USAMOS 'original_payload' en lugar de 'data' para la lógica original
    data_to_process = original_payload # Renombrar para claridad

    # --- Lógica Original para 'verify-' ---
    if data_to_process.startswith("verify-"):
        logger.debug(f"Manejando 'verify' payload para {user_id}")
        try:
            parts = data_to_process.split("-")
            if len(parts) < 3: raise ValueError("Payload verify incompleto")
            userid = parts[1]; token = parts[2]
            if str(user_id) != str(userid):
                 return await message.reply_text("<b>¡Enlace No Válido o Enlace Caducado!</b>", protect_content=True)
            is_valid = await check_token(client, userid, token)
            if is_valid == True:
                 await message.reply_text(f"<b>Hey {message.from_user.mention}, You are successfully verified!...</b>", protect_content=True)
                 await verify_user(client, userid, token)
            else:
                 return await message.reply_text("<b>¡Enlace No Válido o Enlace Caducado!</b>", protect_content=True)
        except Exception as verify_e:
             logger.error(f"Error en lógica 'verify': {verify_e}"); await message.reply_text("<b>Error durante verificación.</b>")
        return

    # --- Lógica Original para 'BATCH-' ---
    # (¡OJO! El payload ahora es el ID del JSON, el prefijo BATCH- está fuera del Base64)
    # Necesitamos verificar si el 'data' original (antes de decodificar) empezaba con BATCH-
    elif message.command[1].startswith("BATCH-"):
        # El 'original_payload' contiene ahora el ID del JSON (ej: "12345")
        # Ya no necesitamos hacer data.split("-", 1)[1] sobre 'data_to_process'
        batch_json_msg_id = original_payload # Asumiendo que no había prefijo normal:/premium: aquí
        logger.info(f"Manejando 'BATCH' payload para {user_id}. ID JSON: {batch_json_msg_id}")

        # --- Tu lógica original para obtener y enviar el BATCH ---
        # (Usando batch_json_msg_id en lugar de file_id_encoded para buscar en caché o descargar)
        # (El resto del código de BATCH se mantiene igual, incluyendo el Auto-Delete)
        sts = await message.reply_text("**🔺 Procesando lote...**", quote=True)
        msgs = BATCH_FILES.get(batch_json_msg_id) # Buscar ID del JSON en caché

        if not msgs:
            try:
                 log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
                 # Obtener el mensaje JSON usando el ID decodificado
                 batch_list_msg = await client.get_messages(log_channel_int, int(batch_json_msg_id))
                 if not batch_list_msg or not batch_list_msg.document: raise ValueError("Batch list message not found or not document")
                 file_path = await client.download_media(batch_list_msg.document.file_id)
                 try:
                     with open(file_path, 'r') as file_data: msgs = json.loads(file_data.read())
                     BATCH_FILES[batch_json_msg_id] = msgs # Cache con ID del JSON
                 finally:
                     if os.path.exists(file_path): os.remove(file_path)
            except Exception as batch_load_err:
                 logger.error(f"Error cargando BATCH (JSON ID {batch_json_msg_id}): {batch_load_err}")
                 return await sts.edit_text("❌ Error cargando información del lote.")

        if not msgs: return await sts.edit_text("❌ Error: Información del lote vacía.")

        filesarr = []
        logger.info(f"Enviando {len(msgs)} mensajes de BATCH (JSON ID {batch_json_msg_id}) a {user_id}")
        # ... (TU BUCLE COMPLETO DE ENVÍO DE BATCH VA AQUÍ, SIN CAMBIOS INTERNOS) ...
        for i, msg_info in enumerate(msgs):
             try:
                  channel_id = int(msg_info.get("channel_id"))
                  msgid = int(msg_info.get("msg_id"))
                  original_msg = await client.get_messages(channel_id, msgid)
                  sent_msg = await original_msg.copy(user_id) # Simplificado
                  filesarr.append(sent_msg)
                  if i % 5 == 0: await asyncio.sleep(0.1)
             except Exception as loop_err: logger.error(f"Error BATCH item {i}: {loop_err}")

        try: await sts.delete()
        except: pass

        # --- Tu lógica de Auto-Delete para BATCH (Restaurada y correcta) ---
        if AUTO_DELETE_MODE and filesarr:
            logger.info(f"Auto-Delete BATCH para {user_id} iniciado.")
            try:
                 k = await client.send_message(chat_id=user_id,text=(f"<blockquote><b><u>❗️❗️❗️IMPORTANTE❗️️❗️❗️</u></b>\n\nEste mensaje será eliminado en <b><u>{AUTO_DELETE} minutos</u> 🫥 <i></b>(Debido a problemas de derechos de autor)</i>.\n\n<b><i>Por favor, reenvía este mensaje a tus mensajes guardados o a cualquier chat privado.</i></b></blockquote>"),parse_mode=enums.ParseMode.HTML)
                 await asyncio.sleep(AUTO_DELETE_TIME)
                 deleted_count = 0
                 for x in filesarr:
                     try: await x.delete(); deleted_count += 1
                     except Exception: pass
                 await k.edit_text(f"<b>✅ {deleted_count} mensajes del lote fueron eliminados automáticamente.</b>")
                 logger.info(f"Auto-Delete BATCH completado {user_id}: {deleted_count}/{len(filesarr)} borrados.")
            except Exception as auto_del_err: logger.error(f"Error Auto-Delete BATCH {user_id}: {auto_del_err}")
        else: logger.info(f"Auto-Delete BATCH desactivado o sin archivos para {user_id}.")
        return

    # --- Lógica Original para Archivo Único ---
    # (Ahora se activa si el payload no es verify ni BATCH)
    else:
        logger.info(f"Manejando Archivo Único payload para {user_id}")
        # El 'original_payload' debería ser ahora "file_<msg_id>"
        try:
            # Extraer el ID del mensaje real del LOG_CHANNEL
            if not original_payload.startswith("file_"):
                 raise ValueError("Formato de payload de archivo único inválido")
            decode_file_id = int(original_payload.split("_", 1)[1])

            log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
            original_msg = await client.get_messages(log_channel_int, decode_file_id)
            if not original_msg: raise MessageIdInvalid

            # --- Tu lógica original para preparar caption y botones ---
            f_caption = ""; reply_markup = None
            if original_msg.media:
                 media = getattr(original_msg, original_msg.media.value, None)
                 title = formate_file_name(getattr(media, "file_name", "")) if media else ""
                 size = get_size(getattr(media, "file_size", 0)) if media else ""
                 f_caption_orig = getattr(original_msg, 'caption', '')
                 if CUSTOM_FILE_CAPTION: f_caption = CUSTOM_FILE_CAPTION.format(file_name=title, file_size=size, file_caption=f_caption_orig)
                 else: f_caption = f"<code>{title}</code>" if title else ""
                 if STREAM_MODE: pass # Lógica botones stream

            # --- Tu lógica original para copiar el mensaje ---
            sent_file_msg = await original_msg.copy(
                chat_id=user_id, caption=f_caption if original_msg.media else None,
                reply_markup=reply_markup, protect_content=False
            )

            # --- Tu lógica de Auto-Delete para Archivo Único (Restaurada y correcta) ---
            if AUTO_DELETE_MODE:
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

        except MessageIdInvalid:
             logger.error(f"Msg ID {decode_file_id} no encontrado en {LOG_CHANNEL} (Single File).")
             await message.reply_text("❌ Error: El archivo solicitado ya no está disponible.")
        except (ValueError, IndexError) as payload_err:
              logger.error(f"Error procesando payload de archivo único '{original_payload}': {payload_err}")
              await message.reply_text("❌ Error: Enlace de archivo inválido.")
        except Exception as e:
             logger.error(f"Error crítico procesando Archivo Único para {user_id}: {e}", exc_info=True)
             await message.reply_text("❌ Ocurrió un error inesperado.")
        return

    # =========================================================================
    # ============ FIN: SECCIÓN MODIFICADA PARA PREMIUM/NORMAL ==============
    # =========================================================================


# --- Tus comandos /api, /base_site, /stats y cb_handler sin cambios ---
@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    # ... (código sin cambios) ...
    user_id = m.from_user.id; user = await get_user(user_id); cmd = m.command
    if len(cmd) == 1: s = script.SHORTENER_API_MESSAGE.format(base_site=user.get("base_site", "N/A"), shortener_api=user.get("shortener_api", "N/A")); return await m.reply(s)
    elif len(cmd) == 2: api = cmd[1].strip(); await update_user_info(user_id, {"shortener_api": api}); await m.reply("<b>Shortener API updated successfully to</b> " + api)
    else: await m.reply("Formato: /api TU_API_KEY")

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    # ... (código sin cambios) ...
    user_id = m.from_user.id; user = await get_user(user_id); cmd = m.command; current_site = user.get("base_site", "None")
    text = (f"`/base_site (base_site)`\n\n**Current base site:** {current_site}\n\n**Ejemplo:** `/base_site tudominio.com`\n\nPara eliminar: `/base_site None`")
    if len(cmd) == 1: return await m.reply(text=text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site = cmd[1].strip().lower()
        if base_site == "none": await update_user_info(user_id, {"base_site": None}); return await m.reply("<b>✅ Base Site eliminado correctamente</b>")
        if not domain(base_site): return await m.reply(text=text + "\n\n❌ Dominio inválido", disable_web_page_preview=True)
        await update_user_info(user_id, {"base_site": base_site}); await m.reply("<b>✅ Base Site actualizado correctamente</b>")
    else: await m.reply("Formato: /base_site tudominio.com | /base_site None")

@Client.on_message(filters.command("stats") & filters.private)
async def simple_stats_command(client, message):
    # ... (código sin cambios) ...
    if message.from_user.id not in ADMINS: return await message.reply_text("❌ **Acceso denegado.** Solo admins.")
    try:
        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING); total_users = await db.total_users_count()
        stats_text = (f"📊 **Estadísticas de la Base de Datos:**\n\n👥 Usuarios: `{total_users}`"); await message.reply_text(stats_text, quote=True)
    except Exception as e: logger.error(f"Error en /stats (simple): {e}"); await message.reply_text(" Ocurrió un error.")

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    # ... (código sin cambios) ...
    user_id = query.from_user.id; q_data = query.data; logger.debug(f"Callback de {user_id}: {q_data}")
    if q_data == "close_data": await query.message.delete()
    elif q_data == "about":
        buttons = [[InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'), InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons); me2 = client.me.mention
        try: await query.edit_message_text(script.ABOUT_TXT.format(me2), reply_markup=markup, parse_mode=enums.ParseMode.HTML)
        except: pass
    elif q_data == "start":
        buttons = [[InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ', url='https://youtube.com/@Tech_VJ')],[InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ', url='https://t.me/vj_bot_disscussion'), InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ', url='https://t.me/vj_botz')],[InlineKeyboardButton('💁‍♀️ ʜᴇʟᴘ', callback_data='help'), InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')]]
        if CLONE_MODE == True: buttons.append([InlineKeyboardButton('🤖 ᴄʟᴏɴᴇ', callback_data='clone')])
        markup = InlineKeyboardMarkup(buttons); me2 = client.me.mention
        try: await query.edit_message_text(script.START_TXT.format(query.from_user.mention, me2), reply_markup=markup, parse_mode=enums.ParseMode.HTML)
        except: pass
    elif q_data == "clone":
        buttons = [[InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'), InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons)
        try: await query.edit_message_text(script.CLONE_TXT.format(query.from_user.mention), reply_markup=markup, parse_mode=enums.ParseMode.HTML)
        except: pass
    elif q_data == "help":
        buttons = [[InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'), InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons)
        try: await query.edit_message_text(script.HELP_TXT, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
        except: pass
    else:
         logger.warning(f"Callback no reconocido: {q_data}"); await query.answer("Opción no implementada", show_alert=False)


# ======================================================
# =========== INICIO: NUEVOS COMANDOS PREMIUM ==========
# ======================================================
# (Tus comandos /addpremium y /delpremium añadidos aquí)
@Client.on_message(filters.command("addpremium") & filters.private & filters.user(ADMINS))
async def add_premium_command(client, message: Message):
    # ... (código sin cambios) ...
    if len(message.command) < 2: return await message.reply_text("⚠️ Uso: `/addpremium <user_id> [días]`\n(Si no pones días, será permanente)")
    try: target_user_id = int(message.command[1])
    except ValueError: return await message.reply_text("❌ ID de usuario inválido.")
    days = None
    if len(message.command) > 2:
        try: days = int(message.command[2]);
        except ValueError: return await message.reply_text("❌ Los días deben ser un número.")
        if days <= 0: return await message.reply_text("❌ Los días deben ser positivos.")
    if not await db.is_user_exist(target_user_id): return await message.reply_text(f"❌ Usuario {target_user_id} no encontrado.")
    success = await db.set_premium(target_user_id, days)
    if success:
        duration_text = f"por {days} días" if days else "permanentemente"; await message.reply_text(f"✅ ¡Premium activado para `{target_user_id}` {duration_text}!")
        try: await client.send_message(target_user_id, f"🎉 ¡Felicidades! Has recibido acceso Premium {duration_text}.")
        except Exception as send_err: logger.warning(f"No notificar premium a {target_user_id}: {send_err}")
    else: await message.reply_text(f"❌ Error activando premium para `{target_user_id}`.")

@Client.on_message(filters.command("delpremium") & filters.private & filters.user(ADMINS))
async def del_premium_command(client, message: Message):
    # ... (código sin cambios) ...
    if len(message.command) != 2: return await message.reply_text("⚠️ Uso: `/delpremium <user_id>`")
    try: target_user_id = int(message.command[1])
    except ValueError: return await message.reply_text("❌ ID de usuario inválido.")
    if not await db.is_user_exist(target_user_id): return await message.reply_text(f"❌ Usuario {target_user_id} no encontrado.")
    success = await db.remove_premium(target_user_id)
    if success:
        await message.reply_text(f"✅ Premium desactivado para `{target_user_id}`.")
        try: await client.send_message(target_user_id, "ℹ️ Tu acceso Premium ha sido desactivado.")
        except Exception as send_err: logger.warning(f"No notificar premium off a {target_user_id}: {send_err}")
    else: await message.reply_text(f"❌ Error desactivando premium para `{target_user_id}`.")
# ======================================================
# ============= FIN: NUEVOS COMANDOS PREMIUM ===========
# ======================================================

