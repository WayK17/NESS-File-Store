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
    # Se cambió 'plugins.utils' a solo 'utils'
    from utils import check_user_membership
except ImportError:
    # Mensaje de error también corregido
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
# ================== FUNCIÓN /START CORREGIDA ===============
# ============================================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    logger.info(f"/start de {user_id} ({message.from_user.mention})")

    # --- Registro de usuario si es nuevo (Sin cambios) ---
    username = client.me.username
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
        buttons = [[InlineKeyboardButton('Únete a Nuestro Canal', url='https://t.me/NessCloud')],[InlineKeyboardButton('⚠️ Grupo de Soporte', url='https://t.me/NESS_Soporte')]]
        if CLONE_MODE == False: buttons.append([InlineKeyboardButton('', callback_data='clone')])
        reply_markup = InlineKeyboardMarkup(buttons); me = client.me
        try: await message.reply_photo(photo=random.choice(PICS) if PICS else "...", caption=script.START_TXT.format(message.from_user.mention, me.mention), reply_markup=reply_markup)
        except Exception: await message.reply_text(script.START_TXT.format(message.from_user.mention, me.mention), reply_markup=reply_markup)
        return

    # --- PROCESAMIENTO CON PAYLOAD ---
    payload_encoded_full = message.command[1]
    logger.info(f"/start con payload '{payload_encoded_full}' de {user_id}")

    # --- Borrar mensaje "Únete" anterior (Sin cambios) ---
    try:
        user_info = await db.get_user_info(user_id); pending_msg_id = user_info.get("pending_join_msg_id") if user_info else None
        if pending_msg_id: logger.debug(f"Borrando msg {pending_msg_id} para {user_id}"); await client.delete_messages(user_id, pending_msg_id); await db.update_user_info(user_id, {"pending_join_msg_id": None})
    except Exception as db_err: logger.error(f"Error DB borrando msg pendiente {user_id}: {db_err}")

    # --- Verificación Force Subscribe (Sin cambios en su lógica interna) ---
    should_skip_fsub = not FORCE_SUB_ENABLED or (SKIP_FORCE_SUB_FOR_ADMINS and user_id in ADMINS)
    logger.debug(f"ForceSub Check: skip={should_skip_fsub}")
    if not should_skip_fsub and FORCE_SUB_CHANNEL and FORCE_SUB_INVITE_LINK:
        logger.debug(f"Realizando chequeo ForceSub para {user_id}")
        try:
            is_member = await check_user_membership(client, user_id, FORCE_SUB_CHANNEL)
            if not is_member:
                logger.info(f"Usuario {user_id} NO miembro. Mostrando mensaje ForceSub.")
                buttons = [[InlineKeyboardButton("Unirme al Canal 📣", url=FORCE_SUB_INVITE_LINK)], [InlineKeyboardButton("Intentar de Nuevo ↻", url=f"https://t.me/{username}?start={payload_encoded_full}")]]
                join_message = await message.reply_text(script.FORCE_MSG.format(mention=message.from_user.mention), reply_markup=InlineKeyboardMarkup(buttons), quote=True, disable_web_page_preview=True)
                await db.update_user_info(user_id, {"pending_join_msg_id": join_message.id})
                return
        except Exception as fs_err: logger.error(f"Error CRÍTICO en Force Subscribe para {user_id}: {fs_err}", exc_info=True)

    # --- INICIO: Decodificación y Chequeos Premium/Verify (LÓGICA CORREGIDA) ---
    logger.info(f"Usuario {user_id} pasó verificaciones iniciales. Procesando payload: {payload_encoded_full}")

    is_batch = False
    base64_to_decode = payload_encoded_full
    link_type = "normal" # Default
    original_payload_id = "" # Inicializar

    # --- NUEVO: Separar prefijo BATCH- ANTES de decodificar ---
    if payload_encoded_full.startswith("BATCH-"):
        is_batch = True
        base64_to_decode = payload_encoded_full[len("BATCH-"):] # Obtener solo la parte Base64
        logger.debug(f"Prefijo BATCH- detectado. Base64 a decodificar: {base64_to_decode}")
    # ---------------------------------------------------------

    try:
        # Calcular padding CORRECTAMENTE sobre la parte Base64
        padding = 4 - (len(base64_to_decode) % 4)
        if padding == 4: padding = 0 # Evitar añadir '====' si ya es múltiplo de 4

        # Decodificar usando la parte correcta y el padding correcto
        payload_decoded = base64.urlsafe_b64decode(base64_to_decode + "=" * padding).decode("ascii")
        logger.debug(f"Payload decodificado: {payload_decoded}")

        original_payload_id = payload_decoded # ID real (ej: "file_158" o "161")

        # Verificar prefijo interno (normal:/premium:)
        if payload_decoded.startswith("premium:"):
            link_type = "premium"
            original_payload_id = payload_decoded[len("premium:"):]
        elif payload_decoded.startswith("normal:"):
            link_type = "normal"
            original_payload_id = payload_decoded[len("normal:"):]
        # Considerar si 'verify-' puede venir aquí (probablemente no si no se codificó con prefijo)
        elif payload_decoded.startswith("verify-"):
             link_type = "special" # Marcar como especial para saltar chequeo premium
             original_payload_id = payload_decoded # Mantener completo para la lógica verify
        else:
             # Si no tiene prefijo normal/premium, podría ser un enlace antiguo
             # Mantenemos el payload decodificado como ID y tipo normal por defecto
             logger.warning(f"Payload decodificado '{payload_decoded}' sin prefijo 'normal:' o 'premium:'. Asumiendo normal o formato especial.")
             original_payload_id = payload_decoded # Usar directamente

        logger.debug(f"Tipo enlace: {link_type}. ID original: {original_payload_id}")

    except (base64.binascii.Error, UnicodeDecodeError) as b64_err:
        logger.error(f"Error decodificando Base64 '{base64_to_decode}' para {user_id}: {b64_err}")
        return await message.reply_text("❌ Enlace inválido o corrupto (Error Base64).")
    except Exception as decode_err:
        logger.error(f"Error inesperado decodificando payload para {user_id}: {decode_err}")
        return await message.reply_text("❌ Error al procesar el enlace.")

    # --- Chequeo de Acceso Premium (Sin cambios) ---
    is_premium_user = await db.check_premium_status(user_id)
    is_admin_user = user_id in ADMINS
    logger.debug(f"Usuario {user_id} es premium: {is_premium_user}, es admin: {is_admin_user}")
    if link_type == "premium" and not is_premium_user and not is_admin_user:
        logger.info(f"Usuario normal {user_id} denegado para enlace premium '{original_payload_id}'.")
        try: await message.reply_text(script.PREMIUM_REQUIRED_MSG.format(mention=message.from_user.mention), quote=True)
        except AttributeError: await message.reply_text("❌ Acceso denegado. Contenido Premium.", quote=True)
        return
    elif link_type == "premium" and is_admin_user and not is_premium_user: logger.info(f"Admin {user_id} accediendo a enlace premium (permitido).")

    # --- Chequeo de VERIFICACIÓN (Sin cambios)---
    try:
        apply_verify_check = VERIFY_MODE and not original_payload_id.startswith("verify-")
        if apply_verify_check and not await check_verification(client, user_id):
            logger.info(f"Usuario {user_id} necesita verificación para enlace tipo {link_type}.")
            verify_url = await get_token(client, user_id, f"https://t.me/{username}?start=")
            btn = [[InlineKeyboardButton("Verify", url=verify_url)]];
            if VERIFY_TUTORIAL: btn.append([InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)])
            await message.reply_text("<b>You are not verified !\nKindly verify to continue !</b>", protect_content=True, reply_markup=InlineKeyboardMarkup(btn)); return
    except Exception as e: logger.error(f"Error en check_verification para {user_id}: {e}"); return await message.reply_text(f"**Error verificando tu estado: {e}**")

    # --- FIN: Decodificación y Chequeos ---

    # --- SI PASÓ TODOS LOS CHEQUEOS: Procesar el original_payload_id ---
    logger.info(f"Usuario {user_id} ({link_type}) procesando ID '{original_payload_id}' (Batch: {is_batch})")

    # --- Lógica para 'verify-' (Sin cambios funcionales) ---
    if original_payload_id.startswith("verify-"):
        # ... (Tu código verify sin cambios, usa original_payload_id) ...
        logger.debug(f"Manejando 'verify' payload para {user_id}")
        try:
            parts = original_payload_id.split("-"); userid = parts[1]; token = parts[2]
            if str(user_id) != str(userid): return await message.reply_text("<b>¡Enlace Inválido!</b>", protect_content=True)
            if await check_token(client, userid, token): await message.reply_text(f"<b>Hey {message.from_user.mention}, Verificado!...", protect_content=True); await verify_user(client, userid, token)
            else: return await message.reply_text("<b>¡Enlace Inválido!</b>", protect_content=True)
        except Exception as verify_e: logger.error(f"Error verify: {verify_e}"); await message.reply_text("<b>Error verificación.</b>")
        return

    # --- Lógica para BATCH (Sin cambios funcionales, usa ID correcto) ---
    elif is_batch:
        batch_json_msg_id = original_payload_id # Este es el ID del JSON (ej: "161")
        logger.info(f"Manejando 'BATCH'. ID JSON: {batch_json_msg_id}")
        # ... (Tu código original BATCH completo va aquí) ...
        # (Asegúrate de usar batch_json_msg_id para obtener el JSON)
        # (La parte de Auto-Delete ya está correcta y restaurada abajo)
        sts = await message.reply_text("**🔺 Procesando lote...**", quote=True)
        msgs = BATCH_FILES.get(batch_json_msg_id)
        if not msgs:
             try:
                 log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
                 batch_list_msg = await client.get_messages(log_channel_int, int(batch_json_msg_id)) # <-- Usar ID correcto
                 if not batch_list_msg or not batch_list_msg.document: raise ValueError("Batch list message not found or not document")
                 file_path = await client.download_media(batch_list_msg.document.file_id)
                 try:
                     with open(file_path, 'r') as file_data: msgs = json.loads(file_data.read())
                     BATCH_FILES[batch_json_msg_id] = msgs # Cache
                 finally:
                     if os.path.exists(file_path): os.remove(file_path)
             except Exception as batch_load_err: logger.error(f"Error cargando BATCH (JSON ID {batch_json_msg_id}): {batch_load_err}"); return await sts.edit_text("❌ Error cargando info.")
        if not msgs: return await sts.edit_text("❌ Error: Info lote vacía.")
        filesarr = []; logger.info(f"Enviando {len(msgs)} mensajes BATCH {batch_json_msg_id} a {user_id}")
        for i, msg_info in enumerate(msgs): # Tu bucle BATCH
             try:
                 channel_id = int(msg_info.get("channel_id")); msgid = int(msg_info.get("msg_id"))
                 original_msg = await client.get_messages(channel_id, msgid)
                 sent_msg = await original_msg.copy(user_id); filesarr.append(sent_msg) # Simplificado
                 if i % 5 == 0: await asyncio.sleep(0.1)
             except Exception as loop_err: logger.error(f"Error BATCH item {i}: {loop_err}")
        try: await sts.delete()
        except: pass
        if AUTO_DELETE_MODE and filesarr: # Auto-Delete BATCH (Restaurado)
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

    # --- Lógica para Archivo Único (Sin cambios funcionales, usa ID correcto)---
    else:
        logger.info(f"Manejando Archivo Único. Payload original ID: {original_payload_id}")
        try:
            if not original_payload_id.startswith("file_"): decode_file_id = int(original_payload_id) # Asumir ID directo si no hay 'file_'
            else: decode_file_id = int(original_payload_id.split("_", 1)[1])

            log_channel_int = int(LOG_CHANNEL) if str(LOG_CHANNEL).lstrip('-').isdigit() else LOG_CHANNEL
            original_msg = await client.get_messages(log_channel_int, decode_file_id)
            if not original_msg: raise MessageIdInvalid

            # ... (Tu código original para preparar caption y botones) ...
            f_caption = ""; reply_markup = None
            if original_msg.media:
                 media = getattr(original_msg, original_msg.media.value, None)
                 title = formate_file_name(getattr(media, "file_name", "")) if media else ""
                 size = get_size(getattr(media, "file_size", 0)) if media else ""
                 f_caption_orig = getattr(original_msg, 'caption', '')
                 if CUSTOM_FILE_CAPTION: f_caption = CUSTOM_FILE_CAPTION.format(file_name=title, file_size=size, file_caption=f_caption_orig)
                 else: f_caption = f"<code>{title}</code>" if title else ""
                 if STREAM_MODE: pass

            # ... (Tu código original para copiar el mensaje) ...
            sent_file_msg = await original_msg.copy(chat_id=user_id, caption=f_caption if original_msg.media else None, reply_markup=reply_markup, protect_content=False)

            # ... (Tu código de Auto-Delete para Archivo Único, restaurado) ...
            if AUTO_DELETE_MODE: # Auto-Delete Single File (Restaurado)
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

        except MessageIdInvalid: logger.error(f"Msg ID {decode_file_id} no encontrado {LOG_CHANNEL} (Single File)."); await message.reply_text("❌ Error: Archivo no disponible.")
        except (ValueError, IndexError, AttributeError) as payload_err: logger.error(f"Error procesando payload archivo único '{original_payload_id}': {payload_err}"); await message.reply_text("❌ Error: Enlace inválido.")
        except Exception as e: logger.error(f"Error crítico Archivo Único {user_id}: {e}", exc_info=True); await message.reply_text("❌ Error inesperado.")
        return

# --- Tus comandos /api, /base_site, /stats y cb_handler (SIN CAMBIOS) ---

@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    user_id = m.from_user.id
    try:
        # Obtener info del usuario (manejando si no existe o falta data)
        user = await get_user(user_id) # Asume que get_user es de plugins.users_api
        if not user:
            logger.warning(f"Datos de usuario no encontrados para {user_id} en shortener_api_handler")
            user_base_site = "N/Configurado"
            user_shortener_api = "N/Configurada"
        else:
            user_base_site = user.get("base_site", "N/Configurado")
            user_shortener_api = user.get("shortener_api", "N/Configurada")

    except Exception as e:
        logger.error(f"Error obteniendo datos de usuario {user_id} en shortener_api_handler: {e}")
        await m.reply_text("❌ Ocurrió un error al obtener tu configuración de API.")
        return

    cmd = m.command

    if len(cmd) == 1:
        # Mostrar información actual
        # Asume que SHORTENER_API_MESSAGE existe en Script.py
        try:
            s = script.SHORTENER_API_MESSAGE.format(
                base_site=user_base_site,
                shortener_api=user_shortener_api
            )
            await m.reply_text(s) # Usar reply_text
        except AttributeError:
             logger.error("Falta 'script.SHORTENER_API_MESSAGE'")
             await m.reply_text("Error: Texto de mensaje no encontrado.")
        except Exception as fmt_err:
             logger.error(f"Error formateando SHORTENER_API_MESSAGE: {fmt_err}")
             await m.reply_text("Error mostrando la información de la API.")


    elif len(cmd) == 2:
        # Actualizar API
        api_key = cmd[1].strip()

        # --- Manejo para eliminar la API ---
        if api_key.lower() == "none":
            logger.info(f"Usuario {user_id} eliminando Shortener API.")
            try:
                # Asume que update_user_info es de plugins.users_api
                await update_user_info(user_id, {"shortener_api": None})
                await m.reply_text("<b>✅ API del Acortador eliminada correctamente.</b>")
            except Exception as e:
                 logger.error(f"Error eliminando shortener_api para {user_id}: {e}")
                 await m.reply_text("❌ Ocurrió un error al eliminar tu API.")
            return # Terminar después de eliminar

        # --- Establecer nueva API (si no es 'none') ---
        if not api_key: # Chequear si envió /api ""
             await m.reply_text("❌ No puedes establecer una API vacía. Usa `/api None` para eliminarla.")
             return

        logger.info(f"Usuario {user_id} actualizando Shortener API a: {api_key[:5]}...") # Loguear solo parte de la API
        try:
            # Asume que update_user_info es de plugins.users_api
            await update_user_info(user_id, {"shortener_api": api_key})
            await m.reply_text(f"<b>✅ API del Acortador actualizada correctamente.</b>") # Mensaje genérico por seguridad
        except Exception as e:
             logger.error(f"Error actualizando shortener_api para {user_id}: {e}")
             await m.reply_text("❌ Ocurrió un error al actualizar tu API.")
    else:
        # Comando inválido (más de 2 partes)
        await m.reply_text(
            "Formato incorrecto. Uso:\n"
            "`/api` (para ver tu API actual)\n"
            "`/api TU_NUEVA_API_KEY` (para establecerla)\n"
            "`/api None` (para eliminarla)"
        )


@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    user_id = m.from_user.id
    try:
        # Obtener info del usuario
        user = await get_user(user_id) # Asume de plugins.users_api
        if not user:
             logger.warning(f"Datos de usuario no encontrados para {user_id} en base_site_handler")
             current_site = "N/A (Usuario no encontrado)"
        else:
             current_site = user.get("base_site", "Ninguno") # Default a "Ninguno"

    except Exception as e:
        logger.error(f"Error obteniendo datos de usuario {user_id} en base_site_handler: {e}")
        await m.reply_text("❌ Ocurrió un error al obtener tu configuración de Sitio Base.")
        return

    cmd = m.command

    # Mensaje de ayuda/estado
    help_text = (
         f"⚙️ **Configuración del Sitio Base del Acortador**\n\n"
         f"Usa este comando para establecer el dominio principal (sin https://).\n\n"
         f"Sitio Base Actual: `{current_site}`\n\n"
         f"➡️ Para cambiarlo: `/base_site tudominio.com`\n"
         f"➡️ Para eliminarlo: `/base_site None`"
    )

    if len(cmd) == 1:
        # Mostrar estado actual y ayuda
        await m.reply_text(text=help_text, disable_web_page_preview=True)

    elif len(cmd) == 2:
        # Actualizar o eliminar Sitio Base
        base_site_input = cmd[1].strip().lower()

        if base_site_input == "none":
            # Eliminar
            logger.info(f"Usuario {user_id} eliminando base_site.")
            try:
                await update_user_info(user_id, {"base_site": None}) # Asume de plugins.users_api
                await m.reply_text("<b>✅ Sitio Base eliminado correctamente.</b>")
            except Exception as e:
                logger.error(f"Error eliminando base_site para {user_id}: {e}")
                await m.reply_text("❌ Ocurrió un error al eliminar el Sitio Base.")
        else:
            # Establecer nuevo Sitio Base
            # Validar dominio usando librería 'validators'
            try:
                is_valid_domain = domain(base_site_input)
            except Exception as val_err:
                 # La librería validators puede lanzar errores si la entrada es muy rara
                 logger.error(f"Error validando dominio '{base_site_input}': {val_err}")
                 is_valid_domain = False # Asumir inválido si la validación falla

            if not is_valid_domain:
                logger.warning(f"Intento de configurar base_site inválido por {user_id}: {base_site_input}")
                await m.reply_text(text=help_text + "\n\n❌ **El dominio ingresado no parece válido.**", disable_web_page_preview=True)
                return

            # Actualizar en DB
            logger.info(f"Usuario {user_id} actualizando base_site a: {base_site_input}")
            try:
                await update_user_info(user_id, {"base_site": base_site_input}) # Asume de plugins.users_api
                await m.reply_text(f"<b>✅ Sitio Base actualizado correctamente a:</b> `{base_site_input}`")
            except Exception as e:
                 logger.error(f"Error actualizando base_site para {user_id}: {e}")
                 await m.reply_text("❌ Ocurrió un error al actualizar el Sitio Base.")
    else:
        # Comando inválido (más de 2 partes)
         await m.reply_text("Formato incorrecto.\n" + help_text, disable_web_page_preview=True)




@Client.on_message(filters.command("stats") & filters.private)
# ... (código stats sin cambios) ...
async def simple_stats_command(client, message):
    if message.from_user.id not in ADMINS: return await message.reply_text("❌ **Acceso denegado.** Solo admins.")
    try: await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING); total_users = await db.total_users_count(); stats_text = (f"📊 **Estadísticas de la Base de Datos:**\n\n👥 Usuarios: `{total_users}`"); await message.reply_text(stats_text, quote=True)
    except Exception as e: logger.error(f"Error en /stats (simple): {e}"); await message.reply_text(" Ocurrió un error.")

@Client.on_callback_query()
# ... (código cb_handler sin cambios) ...
async def cb_handler(client: Client, query: CallbackQuery): user_id = query.from_user.id; q_data = query.data; logger.debug(f"Callback de {user_id}: {q_data}"); if q_data == "close_data": await query.message.delete(); elif q_data == "about": buttons = [[InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'), InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons); me2 = client.me.mention; try: await query.edit_message_text(script.ABOUT_TXT.format(me2), reply_markup=markup, parse_mode=enums.ParseMode.HTML); except: pass; elif q_data == "start": buttons = [[InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ', url='https://youtube.com/@Tech_VJ')],[InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ', url='https://t.me/vj_bot_disscussion'), InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ', url='https://t.me/vj_botz')],[InlineKeyboardButton('💁‍♀️ ʜᴇʟᴘ', callback_data='help'), InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')]]; if CLONE_MODE == True: buttons.append([InlineKeyboardButton('🤖 ᴄʟᴏɴᴇ', callback_data='clone')]); markup = InlineKeyboardMarkup(buttons); me2 = client.me.mention; try: await query.edit_message_text(script.START_TXT.format(query.from_user.mention, me2), reply_markup=markup, parse_mode=enums.ParseMode.HTML); except: pass; elif q_data == "clone": buttons = [[InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'), InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons); try: await query.edit_message_text(script.CLONE_TXT.format(query.from_user.mention), reply_markup=markup, parse_mode=enums.ParseMode.HTML); except: pass; elif q_data == "help": buttons = [[InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'), InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')]]; markup = InlineKeyboardMarkup(buttons); try: await query.edit_message_text(script.HELP_TXT, reply_markup=markup, parse_mode=enums.ParseMode.HTML); except: pass; else: logger.warning(f"Callback no reconocido: {q_data}"); await query.answer("Opción no implementada", show_alert=False)


# --- Tus comandos /addpremium y /delpremium (SIN CAMBIOS) ---
@Client.on_message(filters.command("addpremium") & filters.private & filters.user(ADMINS))
# ... (código addpremium sin cambios) ...
async def add_premium_command(client, message: Message):
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
    if success: duration_text = f"por {days} días" if days else "permanentemente"; await message.reply_text(f"✅ ¡Premium activado para `{target_user_id}` {duration_text}!"); try: await client.send_message(target_user_id, f"🎉 ¡Felicidades! Has recibido acceso Premium {duration_text}.")
    except Exception as send_err: logger.warning(f"No notificar premium a {target_user_id}: {send_err}")
    else: await message.reply_text(f"❌ Error activando premium para `{target_user_id}`.")

@Client.on_message(filters.command("delpremium") & filters.private & filters.user(ADMINS))
# ... (código delpremium sin cambios) ...
async def del_premium_command(client, message: Message):
    if len(message.command) != 2: return await message.reply_text("⚠️ Uso: `/delpremium <user_id>`")
    try: target_user_id = int(message.command[1])
    except ValueError: return await message.reply_text("❌ ID de usuario inválido.")
    if not await db.is_user_exist(target_user_id): return await message.reply_text(f"❌ Usuario {target_user_id} no encontrado.")
    success = await db.remove_premium(target_user_id)
    if success: await message.reply_text(f"✅ Premium desactivado para `{target_user_id}`."); try: await client.send_message(target_user_id, "ℹ️ Tu acceso Premium ha sido desactivado.")
    except Exception as send_err: logger.warning(f"No notificar premium off a {target_user_id}: {send_err}")
    else: await message.reply_text(f"❌ Error desactivando premium para `{target_user_id}`.")

