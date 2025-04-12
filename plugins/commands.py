# Archivo: commands.py (ACTUALIZADO)

import re
import os
import logging
import random
import asyncio
import json
import base64
import datetime # Necesario para dbusers si se usa join_date
from urllib.parse import quote_plus
from os import environ

# Asegúrate de que 'validators' esté instalado: pip install validators
try:
    from validators import domain
except ImportError:
    logging.critical("'validators' library not found. Please install: pip install validators")
    # Define una función dummy para evitar errores, pero /base_site no funcionará correctamente
    def domain(value): return False

# Importaciones de Pyrogram
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait, MessageNotModified
from pyrogram.types import *

# Importaciones de tu proyecto (¡ASEGÚRATE DE QUE LAS RUTAS SEAN CORRECTAS!)
try:
    from Script import script # Tus textos
except ImportError:
    logging.critical("¡Archivo Script.py no encontrado! Usando textos por defecto.")
    # Define un objeto script dummy para evitar errores
    class Script:
        START_TXT = "Hola {0}, soy {1}. ¡Usa /help para ver qué puedo hacer!"
        HELP_TXT = "Comandos disponibles:\n/start - Iniciar\n/help - Esta ayuda\n/about - Información"
        ABOUT_TXT = "Bot creado por VJ_Botz. Clonado por {0}."
        LOG_TEXT = "Nuevo usuario: {1} (ID: {0})"
        CLONE_TXT = "Información sobre clonación para {0}."
        SHORTENER_API_MESSAGE = "API actual: {shortener_api}\nSitio base: {base_site}"
        # Añade otros textos que uses
    script = Script()

# --- Importa la instancia 'db' de dbusers.py ---
try:
    from plugins.dbusers import db # << IMPORTANTE: Usa la instancia db
except ImportError:
     logging.critical("¡Archivo plugins/dbusers.py no encontrado o no se pudo importar 'db'!")
     # Salir si la DB es esencial
     exit()

# --- Importaciones opcionales (verifica si estos archivos/funciones existen) ---
try:
    # Estas funciones deben existir para que VERIFY_MODE funcione
    from utils import verify_user, check_token, check_verification, get_token
except ImportError:
    logging.warning("Módulo 'utils' o funciones de verificación no encontradas. VERIFY_MODE no funcionará.")
    # Define funciones dummy si no existen
    async def verify_user(c, u, t): pass
    async def check_token(c, u, t): return False
    async def check_verification(c, u): return not VERIFY_MODE # Asume verificado si VERIFY_MODE está off
    async def get_token(c, u, s): return "https://example.com/verify" # URL dummy

try:
    # Estas funciones deben existir para que /api y /base_site funcionen
    from plugins.users_api import get_user, update_user_info
except ImportError:
    logging.warning("Módulo 'plugins.users_api' no encontrado. Comandos /api y /base_site no funcionarán.")
    # Define funciones dummy si no existen
    async def get_user(uid): return None
    async def update_user_info(uid, data): pass

try:
    # Necesario para generar nombres/hashes en links de stream
    from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size
except ImportError:
    logging.warning("Módulo 'TechVJ.utils.file_properties' no encontrado. Streaming puede fallar.")
    # Define funciones dummy
    def get_name(msg): return getattr(getattr(msg, msg.media.value, None), 'file_name', 'unknown_file')
    def get_hash(msg): return "dummyhash" + str(msg.id) # Hash dummy simple basado en ID
    def get_media_file_size(msg): return getattr(getattr(msg, msg.media.value, None), 'file_size', 0)

# --- Importa la configuración ---
from config import *

# --- Configuración básica de Logging ---
# Ajusta el nivel según necesites (DEBUG, INFO, WARNING, ERROR, CRITICAL)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING) # Silencia logs de Pyrogram si son muy verbosos


# --- Caché para lotes ---
BATCH_FILES = {}

# --- Funciones de Ayuda ---
def get_size(size):
    """Obtiene el tamaño en formato legible"""
    try:
        size = float(size)
        if size < 0: return "N/A" # Tamaño negativo no es válido
    except (ValueError, TypeError):
        return "N/A"
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    i = 0
    while size >= 1024.0 and i < len(units) - 1:
        i += 1
        size /= 1024.0
    # Evitar mostrar .00 para Bytes
    if i == 0:
         return "%d %s" % (size, units[i])
    else:
         return "%.2f %s" % (size, units[i])

def formate_file_name(file_name):
    """Formatea el nombre del archivo"""
    if not isinstance(file_name, str):
        return "unknown_file"
    # Elimina caracteres problemáticos
    file_name = re.sub(r'[\[\](){}<>|#@*~:]', '', file_name)
    # Elimina URLs, menciones, etc. y añade prefijo
    prefix = "@VJ_Botz" # Cambia o elimina si quieres
    # Filtra palabras que empiezan con http, @, www.
    cleaned_name = ' '.join(filter(lambda x: not x.lower().startswith(('http://', 'https://', '@', 'www.')), file_name.split()))
    # Elimina espacios extra y combina con prefijo
    final_name = f"{prefix} {cleaned_name}".strip()
    return final_name if final_name != prefix else cleaned_name # Evita devolver solo el prefijo

# --- Función auxiliar para generar links de stream ---
async def get_stream_links(message: Message):
    """Genera links de stream y descarga para un mensaje."""
    if not STREAM_MODE or not URL:
        raise ValueError("STREAM_MODE desactivado o URL no configurada.")

    msg_id = message.id
    try:
        # Obtiene nombre y hash usando las funciones importadas (o dummy)
        file_name_quoted = quote_plus(get_name(message))
        file_hash = get_hash(message)
        if not file_name_quoted or not file_hash:
             raise ValueError("Nombre o hash de archivo vacío.")
    except Exception as e:
        logger.error(f"Error en get_name o get_hash para msg {msg_id}: {e}")
        raise ValueError("No se pudo obtener nombre o hash del archivo.")

    # Construye las URLs (asegúrate que URL termine en '/')
    base_url = URL if URL.endswith('/') else URL + '/'
    stream_link = f"{base_url}watch/{str(msg_id)}/{file_name_quoted}?hash={file_hash}"
    download_link = f"{base_url}{str(msg_id)}/{file_name_quoted}?hash={file_hash}" # Asume endpoint de descarga en raíz
    return stream_link, download_link

# --- Manejador del Comando /start ---
@Client.on_message(filters.command("start") & filters.private & filters.incoming)
async def start(client: Client, message: Message):
    """Manejador principal para el comando /start y deep links."""
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    mention = message.from_user.mention

    # Registrar nuevo usuario si no existe
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, first_name)
        if LOG_CHANNEL:
            try:
                log_text = script.LOG_TEXT.format(user_id, mention)
                await client.send_message(LOG_CHANNEL, log_text)
            except Exception as e:
                logger.error(f"No se pudo enviar log a LOG_CHANNEL {LOG_CHANNEL}: {e}")

    # Si no es un deep link, muestra el menú principal
    if len(message.command) == 1:
        buttons = [[
            InlineKeyboardButton('💝 YouTube', url='https://youtube.com/@Tech_VJ'), # URL Real
        ],[
            InlineKeyboardButton('🔍 Soporte', url='https://t.me/vj_bot_disscussion'), # URL Real
            InlineKeyboardButton('🤖 Updates', url='https://t.me/vj_botz') # URL Real
        ],[
            InlineKeyboardButton('💁‍♀️ Ayuda', callback_data='help'),
            InlineKeyboardButton('😊 Acerca', callback_data='about')
        ]]
        if CLONE_MODE:
            buttons.append([InlineKeyboardButton('🤖 Clonar Bot', callback_data='clone')])

        reply_markup = InlineKeyboardMarkup(buttons)
        me = client.me

        try:
            photo_url = random.choice(PICS) if PICS else "https://graph.org/file/ce1723991756e48c35aa1.jpg"
            await message.reply_photo(
                photo=photo_url,
                caption=script.START_TXT.format(mention, me.mention),
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.warning(f"No se pudo enviar foto de inicio ({photo_url}): {e}. Enviando solo texto.")
            await message.reply_text(
                script.START_TXT.format(mention, me.mention),
                reply_markup=reply_markup
            )
        return

    # --- Procesamiento de Deep Links ---
    data = message.command[1]
    bot_username = BOT_USERNAME or client.me.username # Usa username configurado o el del bot

    try:
        # 1. Manejar Link de Verificación
        if data.startswith("verify-"):
            parts = data.split("-")
            if len(parts) == 3:
                _, userid_str, token = parts
                if str(user_id) != userid_str:
                    return await message.reply_text("<b>❌ Enlace inválido o no es para ti.</b>", quote=True)

                is_valid = await check_token(client, user_id, token)
                if is_valid:
                    await verify_user(client, user_id, token)
                    await message.reply_text(f"✅ ¡Hola {mention}! Has sido verificado correctamente.", quote=True)
                else:
                    await message.reply_text("<b>❌ Enlace de verificación inválido o expirado.</b>", quote=True)
            else:
                 await message.reply_text("<b>⚠️ Enlace de verificación mal formado.</b>", quote=True)
            return

        # 2. Comprobar si el usuario necesita verificación
        # Usa 'check_verification' que importamos (real o dummy)
        needs_verification = VERIFY_MODE and not await check_verification(client, user_id)
        if needs_verification:
            try:
                # Usa 'get_token' que importamos (real o dummy)
                token_url = await get_token(client, user_id, f"https://telegram.me/{bot_username}?start=")
                btn = [[InlineKeyboardButton("🔐 Verificar Ahora", url=token_url)]]
                if VERIFY_TUTORIAL:
                    btn.append([InlineKeyboardButton("❓ Cómo Verificar", url=VERIFY_TUTORIAL)])
                await message.reply_text(
                    text="**🔒 Debes verificarte para acceder a los archivos.**",
                    protect_content=True,
                    reply_markup=InlineKeyboardMarkup(btn),
                    quote=True
                )
            except Exception as e:
                logger.error(f"Error generando link de verificación para {user_id}: {e}")
                await message.reply_text("❌ Ocurrió un error al intentar iniciar la verificación.", quote=True)
            return

        # --- Si pasa la verificación (o no es necesaria), procesa el link ---

        # 3. Manejar Link de Lote (Batch)
        if data.startswith("BATCH-"):
            # --- Incrementa contador de solicitudes ---
            await db.increment_start_request_count()
            # ---------------------------------------
            sts = await message.reply_text("⏳ Procesando lote, por favor espera...", quote=True)
            file_id_encoded = data.split("-", 1)[1]
            msgs = BATCH_FILES.get(file_id_encoded)

            if not msgs:
                try:
                    decoded_msg_id = base64.urlsafe_b64decode(file_id_encoded + "=" * (-len(file_id_encoded) % 4)).decode("ascii")
                    if not LOG_CHANNEL: raise ValueError("LOG_CHANNEL no configurado")
                    msg_with_json = await client.get_messages(LOG_CHANNEL, int(decoded_msg_id))
                    if not msg_with_json or not msg_with_json.document or msg_with_json.document.mime_type != "application/json":
                        raise ValueError("El mensaje del lote no es un documento JSON válido.")
                    json_path = await client.download_media(msg_with_json.document.file_id, file_name=f"batch_{file_id_encoded}.json")
                    with open(json_path, 'r') as f:
                        msgs = json.load(f)
                    os.remove(json_path)
                    BATCH_FILES[file_id_encoded] = msgs
                except Exception as e:
                    logger.error(f"Error al cargar/procesar JSON del lote {file_id_encoded}: {e}")
                    await sts.edit_text("❌ Error: No se pudo obtener la definición del lote.")
                    return

            files_sent_list = []
            total_files_in_batch = len(msgs) if isinstance(msgs, list) else 0
            if total_files_in_batch == 0:
                 await sts.edit_text("❌ Error: El lote está vacío o tiene formato incorrecto.")
                 return

            await sts.edit_text(f"📦 Enviando {total_files_in_batch} archivo(s) del lote...")

            for i, msg_data in enumerate(msgs):
                # Validar formato de cada item en el lote
                if not isinstance(msg_data, dict) or "channel_id" not in msg_data or "msg_id" not in msg_data:
                    logger.warning(f"Item inválido en lote {file_id_encoded}: {msg_data}")
                    continue
                channel_id = int(msg_data["channel_id"])
                msg_id = int(msg_data["msg_id"])

                try:
                    original_msg = await client.get_messages(channel_id, msg_id)
                    if not original_msg: continue # Saltar si el mensaje original no existe

                    # Preparar caption y botones
                    caption = getattr(original_msg, 'caption', '')
                    caption_html = caption.html if caption else ''
                    reply_markup = None
                    file_title = "N/A"
                    file_size = "N/A"
                    parse_mode = enums.ParseMode.HTML # Usar HTML por defecto para captions

                    if original_msg.media:
                        media = getattr(original_msg, original_msg.media.value)
                        file_title = formate_file_name(getattr(media, 'file_name', None))
                        file_size = get_size(getattr(media, 'file_size', 0))

                        # Aplicar formato de caption para lotes
                        if BATCH_FILE_CAPTION:
                            try:
                                final_caption = BATCH_FILE_CAPTION.format(
                                    file_name=file_title or '',
                                    file_size=file_size or '',
                                    file_caption=caption_html or '' # Pasar caption original
                                ).strip()
                            except Exception as cap_err:
                                logger.warning(f"Error formateando BATCH_FILE_CAPTION: {cap_err}")
                                final_caption = caption_html or f"<b>{file_title}</b>" # Fallback
                        else:
                            final_caption = caption_html or f"<b>{file_title}</b>" # Fallback

                        # Generar botones de stream/descarga si aplica
                        if STREAM_MODE and (original_msg.video or original_msg.document):
                            try:
                                stream_url, download_url = await get_stream_links(original_msg)
                                button = [[InlineKeyboardButton("📥 Descargar", url=download_url),
                                           InlineKeyboardButton('▶️ Ver Online', url=stream_url)]]
                                # Botón Web App (Opcional)
                                # button.append([InlineKeyboardButton("📱 Ver en App", web_app=WebAppInfo(url=stream_url))])
                                reply_markup = InlineKeyboardMarkup(button)
                            except Exception as e_stream:
                                logger.warning(f"No se pudieron generar links de stream para msg {msg_id} del lote: {e_stream}")
                    else: # Mensaje sin media
                        final_caption = original_msg.text.html if original_msg.text else ''
                        parse_mode = enums.ParseMode.HTML # Usar HTML si hay formato

                    # Enviar la copia al usuario
                    sent_msg = await original_msg.copy(
                        chat_id=user_id,
                        caption=final_caption if final_caption else None, # Enviar None si está vacío
                        parse_mode=parse_mode,
                        reply_markup=reply_markup,
                        protect_content=False # Opcional
                    )
                    files_sent_list.append(sent_msg)

                except FloodWait as fw:
                    logger.warning(f"FloodWait en lote: Esperando {fw.value} segundos...")
                    await asyncio.sleep(fw.value + 1) # Añadir 1 segundo extra
                    # Considera reintentar el envío aquí si es importante
                except Exception as e:
                    logger.error(f"Error enviando archivo msg_id {msg_id} del lote {file_id_encoded}: {e}")
                await asyncio.sleep(1.5) # Pausa un poco más larga entre envíos

            try: await sts.delete()
            except Exception: pass

            # Auto-Eliminación para el lote
            if AUTO_DELETE_MODE and files_sent_list:
                delete_notice = await client.send_message(
                    chat_id=user_id,
                    text=f"❗️ **IMPORTANTE:** {len(files_sent_list)} archivo(s) enviados se eliminarán en **{AUTO_DELETE} minutos**."
                )
                await asyncio.sleep(AUTO_DELETE_TIME)
                deleted_count = 0
                for msg_to_delete in files_sent_list:
                    try:
                        await msg_to_delete.delete()
                        deleted_count += 1
                    except Exception: pass # Ignorar errores al borrar
                try:
                     await delete_notice.edit_text(f"✅ {deleted_count} archivo(s) del lote eliminados.")
                except MessageNotModified: pass # Ignorar si el texto no cambia
                except Exception: pass
            elif not files_sent_list:
                await message.reply_text("🤷‍♂️ No se pudo enviar ningún archivo de este lote.", quote=True)

            return

        # 4. Manejar Link de Archivo Individual (después de descartar BATCH y verify)
        try:
            # Intenta decodificar el formato esperado (pre_id)
            decoded_data = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii")
            if "_" not in decoded_data: raise ValueError("Formato inválido 1")
            pre, msg_id_str = decoded_data.split("_", 1)
            if not msg_id_str.isdigit(): raise ValueError("Formato inválido 2")
            msg_id = int(msg_id_str)

            # --- Incrementa contador de solicitudes ---
            await db.increment_start_request_count()
            # ---------------------------------------

            sts_single = await message.reply_text("⏳ Obteniendo archivo...", quote=True)

            if not LOG_CHANNEL: raise ValueError("LOG_CHANNEL no configurado")
            original_msg = await client.get_messages(LOG_CHANNEL, msg_id)

            if not original_msg or original_msg.empty:
                await sts_single.edit_text("❌ Error: El archivo solicitado no existe o fue eliminado.")
                return

            caption = getattr(original_msg, 'caption', '')
            caption_html = caption.html if caption else ''
            reply_markup = None
            file_title = "N/A"
            file_size = "N/A"
            parse_mode = enums.ParseMode.HTML

            if original_msg.media:
                media = getattr(original_msg, original_msg.media.value)
                file_title = formate_file_name(getattr(media, 'file_name', None))
                file_size = get_size(getattr(media, 'file_size', 0))

                # Aplicar formato de caption personalizado
                if CUSTOM_FILE_CAPTION:
                    try:
                        final_caption = CUSTOM_FILE_CAPTION.format(
                            file_name=file_title or '',
                            file_size=file_size or '',
                            file_caption=caption_html or '' # Pasar caption original
                        ).strip()
                    except Exception as cap_err:
                        logger.warning(f"Error formateando CUSTOM_FILE_CAPTION: {cap_err}")
                        final_caption = f"<code>{file_title}</code>" # Fallback simple
                else:
                    final_caption = f"<code>{file_title}</code>" # Fallback simple

                # Generar botones de stream/descarga
                if STREAM_MODE and (original_msg.video or original_msg.document):
                    try:
                        stream_url, download_url = await get_stream_links(original_msg)
                        button = [[InlineKeyboardButton("📥 Descargar", url=download_url),
                                   InlineKeyboardButton('▶️ Ver Online', url=stream_url)]]
                        # Botón Web App (Opcional)
                        # button.append([InlineKeyboardButton("📱 Ver en App", web_app=WebAppInfo(url=stream_url))])
                        reply_markup = InlineKeyboardMarkup(button)
                    except Exception as e_stream:
                        logger.warning(f"No se pudieron generar links de stream para msg {msg_id}: {e_stream}")

                # Enviar la copia al usuario
                sent_msg = await original_msg.copy(
                    chat_id=user_id,
                    caption=final_caption if final_caption else None,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    protect_content=False # Opcional
                )
                try: await sts_single.delete()
                except Exception: pass

                # Auto-Eliminación
                if AUTO_DELETE_MODE:
                    delete_notice = await client.send_message(
                        chat_id=user_id,
                        text=f"❗️ **IMPORTANTE:** Este archivo se eliminará en **{AUTO_DELETE} minutos**."
                    )
                    await asyncio.sleep(AUTO_DELETE_TIME)
                    try:
                        await sent_msg.delete()
                        await delete_notice.edit_text(f"✅ Archivo eliminado correctamente.")
                    except MessageNotModified: pass
                    except Exception: # Ignora si ya fue borrado, etc.
                         try: await delete_notice.edit_text("⚠️ No se pudo eliminar (quizás ya fue borrado).")
                         except Exception: pass

            else: # Mensaje original sin media
                await sts_single.edit_text("ℹ️ El enlace corresponde a un mensaje de texto, no a un archivo.")
                # Opcional: copiar el mensaje de texto si quieres
                # await original_msg.copy(chat_id=user_id)

        except (ValueError, TypeError, base64.binascii.Error) as e_decode:
             # Este error ocurre si 'data' no es BATCH, ni verify, ni el formato esperado de archivo individual
             logger.warning(f"Formato de deep link no reconocido: {data} | Error: {e_decode}")
             await message.reply_text("❓ Link desconocido o inválido.", quote=True)
        except FloodWait as fw:
            logger.warning(f"FloodWait procesando link {data}: Esperando {fw.value} segundos...")
            await asyncio.sleep(fw.value + 1)
            # Podrías intentar reenviar el mensaje aquí si falló por FloodWait
            await message.reply_text("⏳ Hubo una espera por límite de Telegram, por favor intenta de nuevo.", quote=True)
        except Exception as e:
            logger.exception(f"Error procesando deep link '{data}' para user {user_id}: {e}")
            try: await sts_single.edit_text("❌ Error: No se pudo obtener el archivo solicitado.") # Si sts_single existe
            except NameError: await message.reply_text("❌ Error: No se pudo procesar tu solicitud.", quote=True) # Si falla antes


    except Exception as e: # Captura errores generales en /start
        logger.exception(f"Error fatal procesando /start con data '{data}' para user {user_id}: {e}")
        await message.reply_text("🤖 ¡Ups! Ocurrió un error inesperado.", quote=True)


# --- Manejador del Comando /stats (ACTUALIZADO) ---
@Client.on_message(filters.command("stats") & filters.private & filters.user(ADMINS))
async def stats_command(client: Client, message: Message):
    """Muestra estadísticas del bot (solo para admins)."""
    if not ADMINS: # No hacer nada si ADMINS está vacío
         return
    sts = await message.reply_text("🔄 Obteniendo estadísticas...", quote=True)
    try:
        users_count = await db.total_users_count()
        start_requests_count = await db.get_start_request_count()

        stats_text = f"""📊 **Estadísticas del Bot:**

👥 Usuarios Registrados: `{users_count}`
🚀 Solicitudes de Archivos (/start): `{start_requests_count}`"""

        await sts.edit_text(stats_text) # No necesita parse_mode si no hay Markdown/HTML

    except Exception as e:
        logger.error(f"Error en el comando /stats: {e}")
        await sts.edit_text("❌ Ocurrió un error al obtener las estadísticas.")


# --- Manejador para Comandos /api y /base_site ---
# Asegúrate que las funciones get_user y update_user_info existan en plugins.users_api

@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    user_id = m.from_user.id
    try:
        user = await get_user(user_id) # Necesita implementación real
        if user is None: # Si get_user devuelve None en error o si no existe
             return await m.reply("Error: No se encontró tu información de usuario.", quote=True)
    except Exception as e:
         logger.error(f"Error getting user {user_id} for /api: {e}")
         return await m.reply("Error al obtener tu configuración.", quote=True)

    cmd = m.command
    if len(cmd) == 1:
        # Obtener valores con .get() para evitar KeyErrors si no existen
        s = script.SHORTENER_API_MESSAGE.format(
            base_site=user.get("base_site", "No configurado"),
            shortener_api=user.get("shortener_api", "No configurada")
        )
        return await m.reply(s, quote=True)
    elif len(cmd) == 2:
        api = cmd[1].strip()
        if not api: # Evitar guardar API vacía
             return await m.reply("⚠️ Por favor, proporciona una clave API válida.", quote=True)
        try:
            # Asegúrate que update_user_info funcione correctamente
            await update_user_info(user_id, {"shortener_api": api})
            await m.reply(f"✅ API del acortador actualizada.", quote=True)
        except Exception as e:
             logger.error(f"Error updating shortener_api for {user_id}: {e}")
             await m.reply("❌ Error al actualizar la API.", quote=True)


@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    user_id = m.from_user.id
    try:
        user = await get_user(user_id) # Necesita implementación real
        if user is None:
             return await m.reply("Error: No se encontró tu información de usuario.", quote=True)
    except Exception as e:
         logger.error(f"Error getting user {user_id} for /base_site: {e}")
         return await m.reply("Error al obtener tu configuración.", quote=True)

    cmd = m.command
    current_site = user.get('base_site', 'No configurado')
    text = (f"Usa: `/base_site tudominio.com`\n"
            f"Sitio base actual: **{current_site}**\n\n"
            f"Ejemplo: `/base_site midominio.com`\n\n"
            f"Para eliminarlo: `/base_site none`")

    if len(cmd) == 1:
        return await m.reply(text=text, disable_web_page_preview=True, quote=True)
    elif len(cmd) == 2:
        base_site_input = cmd[1].strip()
        new_value = None # Valor por defecto para eliminar

        if base_site_input.lower() != 'none':
            # Validar el dominio usando la librería 'validators'
            if not domain(base_site_input):
                return await m.reply(text=f"⚠️ Formato de dominio inválido: `{base_site_input}`\n\n{text}", disable_web_page_preview=True, quote=True)
            new_value = base_site_input # Establecer el nuevo dominio

        try:
            # Asegúrate que update_user_info funcione correctamente
            await update_user_info(user_id, {"base_site": new_value})
            if new_value:
                 await m.reply(f"✅ Sitio base actualizado a: `{new_value}`", quote=True)
            else:
                 await m.reply("✅ Sitio base eliminado correctamente.", quote=True)
        except Exception as e:
             logger.error(f"Error updating base_site for {user_id}: {e}")
             await m.reply("❌ Error al actualizar el sitio base.", quote=True)


# --- Manejador de Callback Queries ---
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    """Manejador para botones inline."""
    user_id = query.from_user.id
    mention = query.from_user.mention
    query_data = query.data
    message = query.message # Mensaje original del callback

    try:
        if query_data == "close_data":
            await message.delete()

        elif query_data == "start":
            buttons = [[
                InlineKeyboardButton('💝 YouTube', url='https://youtube.com/@Tech_VJ'), # URL Real
            ],[
                InlineKeyboardButton('🔍 Soporte', url='https://t.me/vj_bot_disscussion'), # URL Real
                InlineKeyboardButton('🤖 Updates', url='https://t.me/vj_botz') # URL Real
            ],[
                InlineKeyboardButton('💁‍♀️ Ayuda', callback_data='help'),
                InlineKeyboardButton('😊 Acerca', callback_data='about')
            ]]
            if CLONE_MODE:
                buttons.append([InlineKeyboardButton('🤖 Clonar Bot', callback_data='clone')])
            reply_markup = InlineKeyboardMarkup(buttons)
            me = client.me
            photo_url = random.choice(PICS) if PICS else "https://graph.org/file/ce1723991756e48c35aa1.jpg"
            # Editar mensaje existente para volver al menú start
            # Si el mensaje original era solo texto, editamos el texto
            if message.photo:
                 await query.edit_message_media(
                     media=InputMediaPhoto(photo_url),
                     reply_markup=reply_markup
                 )
                 # Necesario editar caption después de media si había foto
                 await query.edit_message_caption(
                     caption=script.START_TXT.format(mention, me.mention),
                     reply_markup=reply_markup
                 )
            else:
                 await query.edit_message_text(
                      text=script.START_TXT.format(mention, me.mention),
                      reply_markup=reply_markup,
                      disable_web_page_preview = True # Opcional
                 )

        elif query_data in ["about", "help", "clone"]:
             buttons = [[
                 InlineKeyboardButton('🏠 Volver', callback_data='start'),
                 InlineKeyboardButton('✖️ Cerrar', callback_data='close_data')
             ]]
             reply_markup = InlineKeyboardMarkup(buttons)
             photo_url = random.choice(PICS) if PICS else "https://graph.org/file/ce1723991756e48c35aa1.jpg"

             # Determinar texto según el callback_data
             if query_data == "about":
                 text = script.ABOUT_TXT.format(client.me.mention)
             elif query_data == "help":
                 text = script.HELP_TXT
             elif query_data == "clone":
                 text = script.CLONE_TXT.format(mention)
             else: # No debería ocurrir si validamos arriba
                  return await query.answer("Acción desconocida.", show_alert=True)

             # Editar el mensaje
             if message.photo:
                 await query.edit_message_media(
                     media=InputMediaPhoto(photo_url), # Opcional: Cambiar foto
                     reply_markup=reply_markup
                 )
                 await query.edit_message_caption(
                     caption=text,
                     reply_markup=reply_markup,
                     parse_mode=enums.ParseMode.HTML # Asumiendo que los textos usan HTML
                 )
             else:
                  await query.edit_message_text(
                       text=text,
                       reply_markup=reply_markup,
                       parse_mode=enums.ParseMode.HTML, # Asumiendo que los textos usan HTML
                       disable_web_page_preview=True
                  )

        # Responde al callback (silencioso) para que el cliente sepa que fue procesado
        await query.answer()

    except MessageNotModified:
        # Ignorar si el mensaje no cambió (el usuario hizo clic rápido o el contenido era igual)
        await query.answer()
    except FloodWait as fw:
        logger.warning(f"FloodWait en callback_query ({query_data}): Esperando {fw.value} segundos...")
        await asyncio.sleep(fw.value)
    except Exception as e:
        logger.exception(f"Error procesando callback_query ({query_data}) para user {user_id}: {e}")
        try:
            # Intenta notificar al usuario del error
            await query.answer("❌ Ocurrió un error.", show_alert=True)
        except Exception: pass


# --- Fin de commands.py ---
