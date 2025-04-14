# plugins/commands.py

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import logging
import random
import asyncio
from validators import domain
from Script import script
from plugins.dbusers import db
from pyrogram import Client, filters, enums
from plugins.users_api import get_user, update_user_info
from pyrogram.errors import ChatAdminRequired, FloodWait, UserNotParticipant, ChatWriteForbidden, MessageIdInvalid, MessageNotModified
from pyrogram.types import *

from config import (
    ADMINS, LOG_CHANNEL, CLONE_MODE, PICS, VERIFY_MODE, VERIFY_TUTORIAL,
    STREAM_MODE, URL, CUSTOM_FILE_CAPTION, BATCH_FILE_CAPTION,
    AUTO_DELETE_MODE, AUTO_DELETE_TIME, AUTO_DELETE, FORCE_SUB_ENABLED, FORCE_SUB_CHANNEL, FORCE_SUB_INVITE_LINK,
    SKIP_FORCE_SUB_FOR_ADMINS
)

# ====================================================================
# ===================== CAMBIO 1: IMPORTACIÓN CORREGIDA =============
# ====================================================================
# Importar la función de verificación desde utils.py en la carpeta principal
try:
    # Se cambió 'plugins.utils' a solo 'utils'
    from utils import check_user_membership
except ImportError:
    # Mensaje de error también corregido
    logging.error("¡ADVERTENCIA! La función 'check_user_membership' no se encontró en utils.py (carpeta principal). ForceSubscribe no funcionará.")
    async def check_user_membership(client, user_id, channel_id): return True # Failsafe
# ====================================================================
# ===================== FIN CAMBIO 1 ===============================
# ====================================================================

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

def get_size(size):
    # ... (función sin cambios) ...
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def formate_file_name(file_name):
    # ... (función sin cambios) ...
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

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    logger.info(f"/start de {user_id} ({message.from_user.mention})")

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

    if len(message.command) == 1:
        logger.info(f"Enviando bienvenida normal a {user_id}")
        buttons = [[
            InlineKeyboardButton('Únete a Nuestro Canal', url='https://t.me/NessCloud')
            ],[
            InlineKeyboardButton('⚠️ Grupo de Soporte', url='https://t.me/NESS_Soporte')
            ]]
        if CLONE_MODE == False:
            buttons.append([InlineKeyboardButton('', callback_data='clone')])
        reply_markup = InlineKeyboardMarkup(buttons)
        me = client.me
        try:
            await message.reply_photo(
                photo=random.choice(PICS) if PICS else "https://telegra.ph/file/7d253c933e10c1f47db37.jpg",
                caption=script.START_TXT.format(message.from_user.mention, me.mention),
                reply_markup=reply_markup
            )
        except Exception as welcome_err:
             logger.error(f"Error enviando bienvenida a {user_id}: {welcome_err}")
             await message.reply_text(script.START_TXT.format(message.from_user.mention, me.mention), reply_markup=reply_markup)
        return

    logger.info(f"/start con payload '{message.command[1]}' de {user_id}")

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
                update_success = await db.update_user_info(user_id, {"pending_join_msg_id": None})
                if not update_success:
                     logger.error(f"FALLO al limpiar pending_join_msg_id para usuario {user_id} en la BD.")
    except Exception as db_err:
         logger.error(f"Error (DB) al intentar borrar mensaje pendiente para {user_id}: {db_err}")

    should_skip_check = not FORCE_SUB_ENABLED or (SKIP_FORCE_SUB_FOR_ADMINS and user_id in ADMINS)
    logger.debug(f"ForceSub Check para {user_id}: skip={should_skip_check}, channel={FORCE_SUB_CHANNEL}, link={FORCE_SUB_INVITE_LINK}")

    if not should_skip_check and FORCE_SUB_CHANNEL and FORCE_SUB_INVITE_LINK:
        logger.debug(f"Realizando chequeo ForceSub para {user_id}")
        try:
            is_member = await check_user_membership(client, user_id, FORCE_SUB_CHANNEL)
            if not is_member:
                logger.info(f"Usuario {user_id} NO es miembro de {FORCE_SUB_CHANNEL}. Mostrando mensaje ForceSub.")
                buttons = [
                    [InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)]
                ]
                try:
                    start_payload = message.command[1]
                    buttons.append([InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{client.me.username}?start={start_payload}")])
                except IndexError:
                    buttons.append([InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{client.me.username}?start")])

                join_message = await message.reply_text(
                    text=script.FORCE_MSG.format(mention=message.from_user.mention),
                    reply_markup=InlineKeyboardMarkup(buttons),
                    quote=True,
                    disable_web_page_preview=True
                )
                update_success = await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id})
                if update_success:
                     logger.debug(f"Guardado pending_join_msg_id: {join_message.id} para usuario {user_id}")
                else:
                     logger.error(f"FALLO al guardar pending_join_msg_id para {user_id} en la BD.")
                return
        except Exception as fs_err:
            logger.error(f"Error CRÍTICO en Force Subscribe para {user_id}: {fs_err}", exc_info=True)

    logger.info(f"Usuario {user_id} pasó verificaciones. Procesando payload.")
    data = message.command[1]

    try:
        pre, file_id = data.split('_', 1)
    except ValueError:
        file_id = data
        pre = ""
    logger.debug(f"Payload procesado: pre='{pre}', file_id='{file_id}'")

    if data.split("-", 1)[0] == "verify":
        logger.debug(f"Manejando 'verify' payload para {user_id}")
        try:
            parts = data.split("-")
            if len(parts) < 3: raise ValueError("Payload verify incompleto")
            userid = parts[1]; token = parts[2]
            if str(message.from_user.id) != str(userid):
                 logger.warning(f"Verify fail: ID mismatch ({user_id} != {userid})")
                 return await message.reply_text("<b>¡Enlace No Válido o Enlace Caducado!</b>", protect_content=True)
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
        return

    elif data.split("-", 1)[0] == "BATCH":
        logger.info(f"Manejando 'BATCH' payload para {user_id}")
        try:
            if VERIFY_MODE and not await check_verification(client, message.from_user.id):
                logger.info(f"User {user_id} needs verification for BATCH")
                verify_url = await get_token(client, message.from_user.id, f"https://t.me/{username}?start=")
                btn = [[InlineKeyboardButton("Verify", url=verify_url)]]
                if VERIFY_TUTORIAL: btn.append([InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)])
                await message.reply_text("<b>You are not verified !\nKindly verify to continue !</b>", protect_content=True, reply_markup=InlineKeyboardMarkup(btn))
                return
        except Exception as e:
            logger.error(f"Error en check_verification BATCH para {user_id}: {e}")
            return await message.reply_text(f"**Error - {e}**")

        sts = await message.reply_text("**🔺 Procesando lote...**", quote=True)
        file_id_encoded = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id_encoded)

        if not msgs:
            try:
                 padding = 4 - (len(file_id_encoded) % 4)
                 decode_file_id = base64.urlsafe_b64decode(file_id_encoded + "=" * padding).decode("ascii")
                 log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
                 batch_list_msg = await client.get_messages(log_channel_int, int(decode_file_id))
                 if not batch_list_msg or not batch_list_msg.document: raise ValueError("Batch list message not found or not document")
                 file_path = await client.download_media(batch_list_msg.document.file_id)
                 try:
                     with open(file_path, 'r') as file_data: msgs = json.loads(file_data.read())
                     BATCH_FILES[file_id_encoded] = msgs
                 finally:
                     if os.path.exists(file_path): os.remove(file_path)
            except Exception as batch_load_err:
                 logger.error(f"Error cargando BATCH {file_id_encoded}: {batch_load_err}")
                 return await sts.edit_text("❌ Error cargando información del lote.")

        if not msgs: return await sts.edit_text("❌ Error: Información del lote vacía.")

        filesarr = []
        logger.info(f"Enviando {len(msgs)} mensajes de BATCH {file_id_encoded} a {user_id}")
        # --- TU BUCLE COMPLETO DE ENVÍO DE BATCH VA AQUÍ ---
        # (Asegúrate que este bucle esté completo y funcional como lo tenías)
        for i, msg_info in enumerate(msgs):
             try:
                  channel_id = int(msg_info.get("channel_id"))
                  msgid = int(msg_info.get("msg_id"))
                  original_msg = await client.get_messages(channel_id, msgid)
                  # Lógica de media_group y copy/send_media_group...
                  # Ejemplo simplificado:
                  sent_msg = await original_msg.copy(user_id) # Usa tu lógica real
                  filesarr.append(sent_msg)
                  if i % 5 == 0: await asyncio.sleep(0.1)
             except Exception as loop_err:
                   logger.error(f"Error en bucle BATCH item {i} para {user_id}: {loop_err}")
        # --- FIN DEL BUCLE DE ENVÍO ---

        try: await sts.delete()
        except: pass

        # ====================================================================
        # ========= CAMBIO 2.1: RESTAURAR AUTO-DELETE PARA BATCH ===========
        # ====================================================================
        if AUTO_DELETE_MODE and filesarr:
            logger.info(f"Auto-Delete activado. Programando borrado BATCH para {user_id} en {AUTO_DELETE_TIME}s.")
            try:
                 # --- Línea restaurada ---
                 k = await client.send_message(
                     chat_id = user_id,
                     text=(
                          f"<blockquote><b><u>❗️❗️❗️IMPORTANTE❗️️❗️❗️</u></b>\n\n"
                          f"Este mensaje será eliminado en <b><u>{AUTO_DELETE} minutos</u> 🫥 <i></b>(Debido a problemas de derechos de autor)</i>.\n\n"
                          f"<b><i>Por favor, reenvía este mensaje a tus mensajes guardados o a cualquier chat privado.</i></b></blockquote>"
                     ),
                     parse_mode=enums.ParseMode.HTML
                 )
                 # -----------------------
                 await asyncio.sleep(AUTO_DELETE_TIME)
                 deleted_count = 0
                 for x in filesarr:
                     try:
                         await x.delete()
                         deleted_count += 1
                     except Exception: pass
                 # --- Línea restaurada ---
                 await k.edit_text(f"<b>✅ {deleted_count} mensajes del lote fueron eliminados automáticamente.</b>")
                 # -----------------------
                 logger.info(f"Auto-Delete BATCH completado para {user_id}. {deleted_count}/{len(filesarr)} borrados.")
            except Exception as auto_del_err:
                 logger.error(f"Error durante Auto-Delete BATCH para {user_id}: {auto_del_err}")
        else:
             logger.info(f"Auto-Delete BATCH desactivado o sin archivos para {user_id}.")
        # ====================================================================
        # ========= FIN CAMBIO 2.1 =========================================
        # ====================================================================
        return # Terminar después de BATCH

    else:
        logger.info(f"Manejando Archivo Único payload para {user_id}")
        try:
             if VERIFY_MODE and not await check_verification(client, message.from_user.id):
                  logger.info(f"User {user_id} needs verification for Single File")
                  verify_url = await get_token(client, message.from_user.id, f"https://t.me/{username}?start=")
                  btn = [[InlineKeyboardButton("Verify", url=verify_url)]]
                  if VERIFY_TUTORIAL: btn.append([InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)])
                  await message.reply_text("<b>You are not verified !\nKindly verify to continue !</b>", protect_content=True, reply_markup=InlineKeyboardMarkup(btn))
                  return
        except Exception as e:
             logger.error(f"Error en check_verification Single File para {user_id}: {e}")
             return await message.reply_text(f"**Error - {e}**")

        try:
            decode_data = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii")
            if "_" in decode_data: pre, decode_file_id = decode_data.split("_", 1)
            else: pre = ""; decode_file_id = decode_data

            log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
            original_msg = await client.get_messages(log_channel_int, int(decode_file_id))
            if not original_msg: raise MessageIdInvalid

            f_caption = ""
            reply_markup = None
            # ... (Tu lógica para preparar f_caption y reply_markup) ...
            if original_msg.media:
                 media = getattr(original_msg, original_msg.media.value, None)
                 title = formate_file_name(getattr(media, "file_name", "")) if media else ""
                 size = get_size(getattr(media, "file_size", 0)) if media else ""
                 f_caption_orig = getattr(original_msg, 'caption', '')
                 if CUSTOM_FILE_CAPTION: f_caption = CUSTOM_FILE_CAPTION.format(file_name=title, file_size=size, file_caption=f_caption_orig)
                 else: f_caption = f"<code>{title}</code>" if title else ""
                 if STREAM_MODE: pass # Añadir lógica de botones aquí si es necesario

            sent_file_msg = await original_msg.copy(
                chat_id=user_id,
                caption=f_caption if original_msg.media else None,
                reply_markup=reply_markup,
                protect_content=False
            )

            # ====================================================================
            # ===== CAMBIO 2.2: RESTAURAR AUTO-DELETE PARA ARCHIVO ÚNICO =======
            # ====================================================================
            if AUTO_DELETE_MODE:
                 logger.info(f"Auto-Delete activado para archivo único. Programando borrado para {user_id} en {AUTO_DELETE_TIME}s.")
                 try:
                     # --- Línea restaurada ---
                     k = await client.send_message(
                         chat_id = user_id,
                         text=(
                              f"<blockquote><b><u>❗️❗️❗️IMPORTANTE❗️️❗️❗️</u></b>\n\n"
                              f"Este mensaje será eliminado en <b><u>{AUTO_DELETE} minutos</u> 🫥 <i></b>(Debido a problemas de derechos de autor)</i>.\n\n"
                              f"<b><i>Por favor, reenvía este mensaje a tus mensajes guardados o a cualquier chat privado.</i></b></blockquote>"
                         ),
                         parse_mode=enums.ParseMode.HTML
                      )
                     # -----------------------
                     await asyncio.sleep(AUTO_DELETE_TIME)
                     try: await sent_file_msg.delete()
                     except Exception: pass
                     # --- Línea restaurada ---
                     try: await k.edit_text("<b>✅ El mensaje anterior fue eliminado automáticamente.</b>")
                     except Exception: pass
                     # -----------------------
                     logger.info(f"Auto-Delete completado para archivo único para {user_id}.")
                 except Exception as auto_del_err:
                      logger.error(f"Error durante Auto-Delete (archivo único) para {user_id}: {auto_del_err}")
            else:
                 logger.debug(f"Auto-Delete desactivado para archivo único para {user_id}.")
            # ====================================================================
            # ========= FIN CAMBIO 2.2 =========================================
            # ====================================================================
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
        return

# --- Tus comandos /api, /base_site, /stats y cb_handler sin cambios ---
@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    # ... (código sin cambios) ...
    user_id = m.from_user.id; user = await get_user(user_id); cmd = m.command
    if len(cmd) == 1:
        s = script.SHORTENER_API_MESSAGE.format(base_site=user.get("base_site", "N/A"), shortener_api=user.get("shortener_api", "N/A"))
        return await m.reply(s)
    elif len(cmd) == 2:
        api = cmd[1].strip(); await update_user_info(user_id, {"shortener_api": api}); await m.reply("<b>Shortener API updated successfully to</b> " + api)
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
