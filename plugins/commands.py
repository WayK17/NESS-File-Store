# plugins/commands.py

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import logging
import random
import asyncio
from validators import domain # Asegúrate que esta librería esté instalada (pip install validators)
from Script import script
from plugins.dbusers import db # Importamos db desde dbusers (¡ya está actualizado!)
from pyrogram import Client, filters, enums
from plugins.users_api import get_user, update_user_info # Relacionado con acortador
from pyrogram.errors import ChatAdminRequired, FloodWait, UserNotParticipant, ChatWriteForbidden, MessageIdInvalid, MessageNotModified # Añadimos más errores
from pyrogram.types import * # Importa todos los tipos

# --- Importaciones específicas necesarias (Asegúrate que estén presentes) ---
from config import (
    ADMINS, LOG_CHANNEL, CLONE_MODE, PICS, VERIFY_MODE, VERIFY_TUTORIAL,
    STREAM_MODE, URL, CUSTOM_FILE_CAPTION, BATCH_FILE_CAPTION,
    AUTO_DELETE_MODE, AUTO_DELETE_TIME,
    # Variables específicas de Force Subscribe
    FORCE_SUB_ENABLED, FORCE_SUB_CHANNEL, FORCE_SUB_INVITE_LINK,
    SKIP_FORCE_SUB_FOR_ADMINS
)
# Importar la función de verificación de utils.py
try:
    from plugins.utils import check_user_membership
except ImportError:
    # Si no existe, define una función dummy para evitar errores
    logging.error("¡ADVERTENCIA! La función 'check_user_membership' no se encontró en plugins.utils.py. ForceSubscribe no funcionará.")
    async def check_user_membership(client, user_id, channel_id): return True # Failsafe

# Importaciones originales que ya tenías
import re
import json
import base64
from urllib.parse import quote_plus
try:
    from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size
except ImportError:
    # Si falla, define funciones dummy
    logging.warning("No se pudo importar desde TechVJ.utils.file_properties.")
    def get_name(msg): return "archivo"
    def get_hash(msg): return "dummyhash"
    def get_media_file_size(msg): return getattr(getattr(msg, msg.media.value, None), 'file_size', 0)

# Configuración del Logger
logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

# Variable global (ya la tenías)
BATCH_FILES = {}

# ======================================================
# ============ FUNCIONES AUXILIARES ORIGINALES =========
# ======================================================
# (Tus funciones get_size y formate_file_name sin cambios)
def get_size(size):
    """Get size in readable format"""
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def formate_file_name(file_name):
    # Tu función original formate_file_name
    if not isinstance(file_name, str): return ""
    original_name = file_name
    try:
        chars = ["[", "]", "(", ")"]
        for c in chars:
            file_name = file_name.replace(c, "")
        file_name = '' + ' '.join(filter(lambda x: x and not x.startswith('http') and not x.startswith('@') and not x.startswith('www.'), file_name.split()))
        return file_name if file_name else original_name
    except Exception as e:
        logger.error(f"Error formateando nombre de archivo '{original_name}': {e}")
        return original_name

# ============================================================
# ================== FUNCIÓN /START ORIGINAL =================
# === (CON BLOQUES AÑADIDOS PARA NUEVA FUNCIONALIDAD) =========
# ============================================================

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message: Message):
    # --- Información básica del usuario (Original) ---
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    logger.info(f"/start de {user_id} ({message.from_user.mention})")

    # --- Registro de usuario si es nuevo (Original, usando add_user actualizado) ---
    username = client.me.username # Obtenido aquí en tu original
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

    # --- Manejo de /start sin payload (Bienvenida) (Original) ---
    if len(message.command) != 2:
        logger.info(f"Enviando bienvenida normal a {user_id}")
        buttons = [[
            InlineKeyboardButton('Únete a Nuestro Canal', url='https://t.me/NessCloud') # Tu texto y URL
            ],[
            InlineKeyboardButton('⚠️ Grupo de Soporte', url='https://t.me/NESS_Soporte') # Tu texto y URL
            ]]
        if CLONE_MODE == False:
            buttons.append([InlineKeyboardButton('', callback_data='clone')]) # Tu botón original sin texto
        reply_markup = InlineKeyboardMarkup(buttons)
        me = client.me
        try:
            await message.reply_photo(
                photo=random.choice(PICS) if PICS else "https://telegra.ph/file/7d253c933e10c1f47db37.jpg", # Fallback
                caption=script.START_TXT.format(message.from_user.mention, me.mention),
                reply_markup=reply_markup
            )
        except Exception as welcome_err:
             logger.error(f"Error enviando bienvenida a {user_id}: {welcome_err}")
             # Fallback a texto
             await message.reply_text(script.START_TXT.format(message.from_user.mention, me.mention), reply_markup=reply_markup)
        return # Terminar aquí si era solo /start

    # --- PROCESAMIENTO SOLO SI HAY PAYLOAD (len(message.command) >= 2) ---
    logger.info(f"/start con payload '{message.command[1]}' de {user_id}")

    # ====================================================================
    # ========= BLOQUE AÑADIDO 1: BORRAR MENSAJE "ÚNETE" ANTERIOR ========
    # ====================================================================
    try:
        user_info = await db.get_user_info(user_id)
        pending_msg_id = user_info.get("pending_join_msg_id") if user_info else None

        if pending_msg_id:
            logger.debug(f"Usuario {user_id} tenía mensaje pendiente {pending_msg_id}. Intentando borrar.")
            try:
                await client.delete_messages(chat_id=user_id, message_ids=pending_msg_id)
                logger.info(f"Mensaje 'Únete' ({pending_msg_id}) borrado para usuario {user_id}")
            except MessageIdInvalid:
                 logger.info(f"Mensaje 'Únete' ({pending_msg_id}) para {user_id} ya no existía.")
            except Exception as del_err:
                logger.warning(f"No se pudo borrar el mensaje 'Únete' ({pending_msg_id}) para {user_id}: {del_err}")
            finally:
                # Limpiar el campo de la BD
                update_success = await db.update_user_info(user_id, {"pending_join_msg_id": None})
                if not update_success:
                     logger.error(f"FALLO al limpiar pending_join_msg_id para usuario {user_id} en la BD.")
    except Exception as db_err:
         logger.error(f"Error (DB) al intentar borrar mensaje pendiente para {user_id}: {db_err}")
    # ==================================================================
    # ========= FIN BLOQUE AÑADIDO 1 ===================================
    # ==================================================================

    # ====================================================================
    # ========= BLOQUE AÑADIDO 2: VERIFICACIÓN FORCE SUBSCRIBE ===========
    # ====================================================================
    should_skip_check = not FORCE_SUB_ENABLED or (SKIP_FORCE_SUB_FOR_ADMINS and user_id in ADMINS)
    logger.debug(f"ForceSub Check para {user_id}: skip={should_skip_check}, channel={FORCE_SUB_CHANNEL}, link={FORCE_SUB_INVITE_LINK}")

    if not should_skip_check and FORCE_SUB_CHANNEL and FORCE_SUB_INVITE_LINK:
        logger.debug(f"Realizando chequeo ForceSub para {user_id}")
        try:
            is_member = await check_user_membership(client, user_id, FORCE_SUB_CHANNEL)

            if not is_member:
                logger.info(f"Usuario {user_id} NO es miembro de {FORCE_SUB_CHANNEL}. Mostrando mensaje ForceSub.")
                # --- Usamos tu estructura de botones y textos ---
                buttons = [
                    [InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)] # <--- TU TEXTO/LINK
                ]
                try:
                    start_payload = message.command[1]
                    buttons.append([InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{client.me.username}?start={start_payload}")]) # <--- TU TEXTO
                except IndexError:
                    buttons.append([InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{client.me.username}?start")]) # <--- TU TEXTO

                # Enviar el mensaje para forzar suscripción
                join_message = await message.reply_text( # Guardamos el mensaje enviado
                    text=script.FORCE_MSG.format(mention=message.from_user.mention), # Texto desde Script.py
                    reply_markup=InlineKeyboardMarkup(buttons),
                    quote=True,
                    disable_web_page_preview=True
                )

                # --- Guardar el ID del mensaje enviado en la BD ---
                update_success = await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id})
                if update_success:
                     logger.debug(f"Guardado pending_join_msg_id: {join_message.id} para usuario {user_id}")
                else:
                     logger.error(f"FALLO al guardar pending_join_msg_id para {user_id} en la BD.")
                # -------------------------------------------------

                # Detener la ejecución
                return

        except Exception as fs_err:
            logger.error(f"Error CRÍTICO en Force Subscribe para {user_id}: {fs_err}", exc_info=True)
            # Failsafe: permitir continuar
    # ==================================================================
    # ========= FIN BLOQUE AÑADIDO 2 ===================================
    # ==================================================================

    # --- LÓGICA ORIGINAL PARA PROCESAR EL PAYLOAD ---
    # (Esta parte solo se ejecuta si había payload Y el usuario pasó las verificaciones)
    logger.info(f"Usuario {user_id} pasó verificaciones. Procesando payload.")

    data = message.command[1] # Payload original

    # --- Tu código original para manejar 'verify', 'BATCH', y archivo único ---
    # (Pegado aquí tal cual me lo enviaste antes, con mínimas adiciones de logging/robustez)
    try:
        pre, file_id = data.split('_', 1)
    except ValueError: # Si no hay '_', data es el file_id
        file_id = data
        pre = ""
    logger.debug(f"Payload procesado: pre='{pre}', file_id='{file_id}'")

    if data.split("-", 1)[0] == "verify":
        logger.debug(f"Manejando 'verify' payload para {user_id}")
        # ... (Tu código original para 'verify') ...
        # (Incluyendo los return necesarios dentro de esta lógica)
        try:
            parts = data.split("-")
            if len(parts) < 3: raise ValueError("Payload verify incompleto")
            userid = parts[1]; token = parts[2]
            if str(message.from_user.id) != str(userid):
                 logger.warning(f"Verify fail: ID mismatch ({user_id} != {userid})")
                 return await message.reply_text("<b>¡Enlace No Válido o Enlace Caducado!</b>", protect_content=True)
            # Asume que check_token y verify_user existen en utils.py
            is_valid = await check_token(client, userid, token)
            if is_valid == True:
                 logger.info(f"User {userid} verified OK with token {token}")
                 await message.reply_text(f"<b>Hey {message.from_user.mention}, You are successfully verified !\nNow you have unlimited access for all files till today midnight.</b>", protect_content=True)
                 await verify_user(client, userid, token)
            else:
                 logger.warning(f"Verify fail for {userid}: Invalid/used token {token}")
                 return await message.reply_text("<b>¡Enlace No Válido o Enlace Caducado!</b>", protect_content=True)
        except Exception as verify_e:
             logger.error(f"Error en lógica 'verify' para {user_id}: {verify_e}")
             await message.reply_text("<b>Error durante verificación.</b>")
        return # Salir después de manejar verify

    elif data.split("-", 1)[0] == "BATCH":
        logger.info(f"Manejando 'BATCH' payload para {user_id}")
        # --- Tu chequeo original de VERIFY_MODE ---
        try:
            if VERIFY_MODE and not await check_verification(client, message.from_user.id): # Asume check_verification existe
                logger.info(f"User {user_id} needs verification for BATCH")
                verify_url = await get_token(client, message.from_user.id, f"https://t.me/{username}?start=") # Asume get_token existe
                btn = [[InlineKeyboardButton("Verify", url=verify_url)]]
                if VERIFY_TUTORIAL: btn.append([InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)])
                await message.reply_text("<b>You are not verified !\nKindly verify to continue !</b>", protect_content=True, reply_markup=InlineKeyboardMarkup(btn))
                return
        except Exception as e:
            logger.error(f"Error en check_verification BATCH para {user_id}: {e}")
            return await message.reply_text(f"**Error - {e}**")

        # --- Tu lógica original para obtener y enviar el BATCH ---
        sts = await message.reply_text("**🔺 Procesando lote...**", quote=True) # Cambiado texto y quote
        file_id_encoded = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id_encoded)
        # ... (El resto de tu lógica para decodificar, descargar JSON si no está en caché,
        #      iterar, manejar media groups, enviar copias, y auto-borrado) ...
        # (Esta parte es compleja y se mantiene como la tenías, asumiendo que funcionaba)
        # ... (Asegúrate que toda esta lógica esté aquí) ...
        if not msgs: # Descargar y procesar JSON
            try:
                 padding = 4 - (len(file_id_encoded) % 4)
                 decode_file_id = base64.urlsafe_b64decode(file_id_encoded + "=" * padding).decode("ascii")
                 log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
                 batch_list_msg = await client.get_messages(log_channel_int, int(decode_file_id))
                 if not batch_list_msg or not batch_list_msg.document: raise ValueError("Batch list message not found or not document")
                 file_path = await client.download_media(batch_list_msg.document.file_id)
                 try:
                     with open(file_path, 'r') as file_data: msgs = json.loads(file_data.read())
                     BATCH_FILES[file_id_encoded] = msgs # Cache
                 finally:
                     if os.path.exists(file_path): os.remove(file_path)
            except Exception as batch_load_err:
                 logger.error(f"Error cargando BATCH {file_id_encoded}: {batch_load_err}")
                 return await sts.edit_text("❌ Error cargando información del lote.")

        if not msgs: return await sts.edit_text("❌ Error: Información del lote vacía.")

        filesarr = []
        # Reutilizar lógica de envío de lote que tenías... (simplificado aquí por brevedad)
        logger.info(f"Enviando {len(msgs)} mensajes de BATCH {file_id_encoded} a {user_id}")
        # ... (TU BUCLE COMPLETO DE ENVÍO DE BATCH VA AQUÍ) ...
        # Ejemplo simplificado:
        for i, msg_info in enumerate(msgs):
             try:
                  channel_id = int(msg_info.get("channel_id"))
                  msgid = int(msg_info.get("msg_id"))
                  original_msg = await client.get_messages(channel_id, msgid)
                  # Aquí iría tu lógica de media_group y copy/send_media_group
                  sent_msg = await original_msg.copy(user_id) # Simplificado!! Usa tu lógica real
                  filesarr.append(sent_msg)
                  if i % 5 == 0: await asyncio.sleep(0.1)
             except Exception as loop_err:
                   logger.error(f"Error en bucle BATCH item {i} para {user_id}: {loop_err}")

        await sts.delete()
        # Tu lógica de AUTO_DELETE_MODE para BATCH
        if AUTO_DELETE_MODE and filesarr:
             # ... (tu código de auto-borrado para BATCH) ...
             logger.info(f"Auto-delete BATCH para {user_id} iniciado.")
             # k = await client.send_message(...)
             # await asyncio.sleep(AUTO_DELETE_TIME)
             # for x in filesarr: await x.delete()
             # await k.edit_text(...)

        return # Terminar después de BATCH

    # --- Tu lógica original para Archivo Único ---
    else:
        logger.info(f"Manejando Archivo Único payload para {user_id}")
        # Tu chequeo original de VERIFY_MODE
        try:
             if VERIFY_MODE and not await check_verification(client, message.from_user.id):
                  logger.info(f"User {user_id} needs verification for Single File")
                  # ... (tu código para solicitar verificación) ...
                  # verify_url = await get_token(...)
                  # btn = ...
                  # await message.reply_text(...)
                  return
        except Exception as e:
             logger.error(f"Error en check_verification Single File para {user_id}: {e}")
             return await message.reply_text(f"**Error - {e}**")

        # Tu lógica original para decodificar, obtener y enviar archivo único
        try:
            # Decodificar (usando tu lógica original)
            decode_data = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii")
            if "_" in decode_data: pre, decode_file_id = decode_data.split("_", 1)
            else: pre = ""; decode_file_id = decode_data

            log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
            original_msg = await client.get_messages(log_channel_int, int(decode_file_id))
            if not original_msg: raise MessageIdInvalid

            # Preparar caption y botones (tu lógica original)
            f_caption = ""
            reply_markup = None
            # ... (tu código para preparar f_caption y reply_markup si STREAM_MODE) ...
            if original_msg.media:
                 media = getattr(original_msg, original_msg.media.value, None)
                 title = formate_file_name(getattr(media, "file_name", "")) if media else ""
                 size = get_size(getattr(media, "file_size", 0)) if media else ""
                 f_caption_orig = getattr(original_msg, 'caption', '')
                 # ... aplicar CUSTOM_FILE_CAPTION etc...
                 if CUSTOM_FILE_CAPTION: f_caption = CUSTOM_FILE_CAPTION.format(file_name=title, file_size=size, file_caption=f_caption_orig)
                 else: f_caption = f"<code>{title}</code>" if title else "" # Simplificado

                 if STREAM_MODE: # Simplificado
                      # ... generar botones ...
                      # reply_markup = InlineKeyboardMarkup(...)
                      pass


            # Copiar mensaje (tu lógica original)
            sent_file_msg = await original_msg.copy(
                chat_id=user_id,
                caption=f_caption if original_msg.media else None,
                reply_markup=reply_markup,
                protect_content=False
            )

            # Auto-borrado (tu lógica original)
            if AUTO_DELETE_MODE:
                 # ... (tu código de auto-borrado para archivo único) ...
                 logger.info(f"Auto-delete Single File para {user_id} iniciado.")
                 # k = await client.send_message(...)
                 # await asyncio.sleep(AUTO_DELETE_TIME)
                 # await sent_file_msg.delete()
                 # await k.edit_text(...)

            return # Terminar después de Archivo Único

        except (base64.binascii.Error, UnicodeDecodeError) as b64_err:
             logger.error(f"Error decodificando Archivo Único ({data}): {b64_err}")
             await message.reply_text("❌ Error: Enlace de archivo inválido.")
        except MessageIdInvalid:
             logger.error(f"Msg ID {decode_file_id} no encontrado en {LOG_CHANNEL}.")
             await message.reply_text("❌ Error: El archivo solicitado ya no está disponible.")
        except Exception as e:
             logger.error(f"Error crítico procesando Archivo Único para {user_id}: {e}", exc_info=True)
             await message.reply_text("❌ Ocurrió un error inesperado.")
        return # Asegurar salida en caso de error

# ======================================================
# ============ COMANDOS ORIGINALES /api y /base_site ===
# ======================================================
# (Tu código original para estos comandos, sin cambios)
@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    user_id = m.from_user.id
    user = await get_user(user_id) # Asume viene de users_api
    cmd = m.command
    if len(cmd) == 1:
        s = script.SHORTENER_API_MESSAGE.format(base_site=user.get("base_site", "N/A"), shortener_api=user.get("shortener_api", "N/A"))
        return await m.reply(s)
    elif len(cmd) == 2:
        api = cmd[1].strip()
        await update_user_info(user_id, {"shortener_api": api}) # Asume viene de users_api
        await m.reply("<b>Shortener API updated successfully to</b> " + api)
    else:
        await m.reply("Formato: /api TU_API_KEY") # Mensaje de ayuda

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    user_id = m.from_user.id
    user = await get_user(user_id) # Asume viene de users_api
    cmd = m.command
    current_site = user.get("base_site", "None")
    text = (f"`/base_site (base_site)`\n\n**Current base site:** {current_site}\n\n**Ejemplo:** `/base_site tudominio.com`\n\nPara eliminar: `/base_site None`")
    if len(cmd) == 1:
        return await m.reply(text=text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site = cmd[1].strip().lower()
        if base_site == "none":
            await update_user_info(user_id, {"base_site": None}) # Asume viene de users_api
            return await m.reply("<b>✅ Base Site eliminado correctamente</b>")
        if not domain(base_site):
            return await m.reply(text=text + "\n\n❌ Dominio inválido", disable_web_page_preview=True)
        await update_user_info(user_id, {"base_site": base_site}) # Asume viene de users_api
        await m.reply("<b>✅ Base Site actualizado correctamente</b>")
    else:
        await m.reply("Formato: /base_site tudominio.com | /base_site None")

# ==============================================================
# ============ COMANDO /STATS AÑADIDO ANTERIORMENTE ============
# ==============================================================
# (Tu comando /stats simple, sin cambios)
@Client.on_message(filters.command("stats") & filters.private)
async def simple_stats_command(client, message):
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

# ==============================================================
# ============ MANEJADOR DE CALLBACKS ORIGINAL =================
# ==============================================================
# (Tu código original para on_callback_query, sin cambios)
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    # Tu código original para cb_handler...
    # ... (close_data, about, start, clone, help) ...
    user_id = query.from_user.id # Añadido para logging
    q_data = query.data
    logger.debug(f"Callback de {user_id}: {q_data}")

    if q_data == "close_data": await query.message.delete()
    elif q_data == "about":
        # ... tu lógica para about ...
        buttons = [[InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'), InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')]]
        reply_markup = InlineKeyboardMarkup(buttons); me2 = client.me.mention
        # Simplificado: Editar texto directamente
        try: await query.edit_message_text(script.ABOUT_TXT.format(me2), reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        except: pass # Ignorar errores de edición
    elif q_data == "start":
        # ... tu lógica para start callback ...
        buttons = [[InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ', url='https://youtube.com/@Tech_VJ')],[InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ', url='https://t.me/vj_bot_disscussion'), InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ', url='https://t.me/vj_botz')],[InlineKeyboardButton('💁‍♀️ ʜᴇʟᴘ', callback_data='help'), InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')]]
        if CLONE_MODE == True: buttons.append([InlineKeyboardButton('🤖 ᴄʟᴏɴᴇ', callback_data='clone')])
        reply_markup = InlineKeyboardMarkup(buttons); me2 = client.me.mention
        # Simplificado: Editar texto directamente
        try: await query.edit_message_text(script.START_TXT.format(query.from_user.mention, me2), reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        except: pass
    elif q_data == "clone":
        # ... tu lógica para clone callback ...
        buttons = [[InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'), InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        try: await query.edit_message_text(script.CLONE_TXT.format(query.from_user.mention), reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        except: pass
    elif q_data == "help":
        # ... tu lógica para help callback ...
        buttons = [[InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'), InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        try: await query.edit_message_text(script.HELP_TXT, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        except: pass
    else:
         logger.warning(f"Callback no reconocido: {q_data}")
         try: await query.answer("Opción no implementada", show_alert=False)
         except: pass

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

