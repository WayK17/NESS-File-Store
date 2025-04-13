# plugins/broadcast.py

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

# --- Imports existentes y nuevos ---
import asyncio
import datetime
import time
import logging # Añadido para logging en la nueva función

from pyrogram import Client, filters
from pyrogram.errors import (InputUserDeactivated, UserNotParticipant, FloodWait,
                             UserIsBlocked, PeerIdInvalid, MessageIdInvalid, MessageNotModified) # Añadidos MessageIdInvalid, MessageNotModified

from plugins.dbusers import db
# Importar ADMINS y la nueva configuración de config.py
from config import ADMINS, BROADCAST_DELETE_DELAY

# --- Configuración del Logger ---
# (Asegúrate de que esto sea consistente con cómo configuras logging en otros archivos)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO) # O el nivel que prefieras

# ==============================================================
# ============ CÓDIGO ORIGINAL PARA /broadcast =================
# ==============================================================

# --- Tu función auxiliar original (sin cambios) ---
async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        # Considera añadir un logger.warning aquí
        logger.warning(f"FloodWait en broadcast_messages para {user_id}. Esperando {e.value}s.")
        await asyncio.sleep(e.value)
        # Llamada recursiva puede ser peligrosa si hay muchos FloodWait seguidos.
        # Una alternativa sería retornar un estado específico para reintentar en el bucle principal.
        return await broadcast_messages(user_id, message) # Mantenemos la lógica original por ahora
    except InputUserDeactivated:
        logger.info(f"Usuario {user_id} desactivado. Eliminando de la BD.")
        await db.delete_user(int(user_id))
        return False, "Deleted"
    except UserIsBlocked:
        logger.info(f"Usuario {user_id} bloqueó el bot. Eliminando de la BD.")
        await db.delete_user(int(user_id))
        return False, "Blocked"
    except PeerIdInvalid:
        logger.warning(f"PeerIdInvalid para usuario {user_id}. Eliminando de la BD.")
        await db.delete_user(int(user_id))
        return False, "Error" # Podría ser "Invalid Peer" para diferenciar
    except Exception as e:
        logger.error(f"Error desconocido en broadcast_messages para {user_id}: {e}")
        return False, "Error"

# --- Tu manejador original para /broadcast (sin cambios) ---
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def verupikkals(bot, message): # Nombre original mantenido
    users = await db.get_all_users()
    b_msg = message.reply_to_message
    sts = await message.reply_text(text='**Iniciando broadcast estándar...**') # Mensaje ligeramente cambiado
    start_time = time.time()
    total_users = await db.total_users_count()
    done = 0
    blocked = 0
    deleted = 0
    failed = 0
    success = 0
    update_interval = max(10, total_users // 20) # Intervalo para actualizar estado

    async for user in users:
        # Añadido chequeo más robusto para obtener user_id
        user_id = user.get('id')
        if not user_id:
             logger.warning(f"Documento de usuario sin ID encontrado durante broadcast: {user}")
             # ¿Contar como fallo o simplemente saltar? Contaremos como fallo por ahora.
             failed += 1
             done += 1
             continue # Saltar este documento

        # Convertir a int por si acaso viene como string de la BD
        try:
            user_id_int = int(user_id)
        except ValueError:
             logger.warning(f"ID de usuario inválido encontrado durante broadcast: {user_id}")
             failed += 1
             done += 1
             continue

        # Llamar a la función auxiliar original
        pti, sh = await broadcast_messages(user_id_int, b_msg)

        if pti:
            success += 1
        elif not pti: # Equivalente a pti == False
            if sh == "Blocked":
                blocked += 1
            elif sh == "Deleted":
                deleted += 1
            elif sh == "Error": # Incluye PeerIdInvalid y otros errores
                failed += 1
        done += 1

        # Actualizar estado periódicamente
        if done % update_interval == 0:
            try:
                # Usar f-string para formato más limpio
                status_text = (
                    f"**Broadcast estándar en progreso:**\n\n"
                    f"👥 Total Usuarios: {total_users}\n"
                    f"⏳ Completados: {done}/{total_users}\n"
                    f"✅ Éxito: {success}\n"
                    f"🚫 Bloqueados: {blocked}\n"
                    f"🗑️ Eliminados (Desactivados): {deleted}\n"
                    f"❌ Fallos: {failed}"
                )
                await sts.edit(status_text)
            except MessageNotModified:
                pass # No hacer nada si el mensaje no cambió
            except Exception as edit_err:
                logger.warning(f"No se pudo editar el mensaje de estado de /broadcast: {edit_err}")
                pass # Continuar aunque falle la edición

        # Pausa corta
        if done % 5 == 0:
            await asyncio.sleep(0.1)


    # Resumen final
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    final_text = (
        f"**Broadcast estándar Completado:**\n"
        f"⏱️ Tiempo total: {time_taken}\n\n"
        f"👥 Total Usuarios: {total_users}\n"
        f"⏳ Completados: {done}/{total_users}\n"
        f"✅ Éxito: {success}\n"
        f"🚫 Bloqueados: {blocked}\n"
        f"🗑️ Eliminados (Desactivados): {deleted}\n"
        f"❌ Fallos: {failed}"
    )
    try:
        await sts.edit(final_text)
    except Exception as final_edit_err:
         logger.warning(f"No se pudo editar el resumen final de /broadcast: {final_edit_err}")
         await message.reply_text(final_text, quote=True) # Enviar como nuevo mensaje si falla edición


# ==============================================================
# =========== CÓDIGO NUEVO AÑADIDO PARA /dbroadcast ===========
# ==============================================================

# --- Función auxiliar nueva para borrar mensajes después de un retraso ---
async def delete_message_after_delay(client, chat_id, message_id, delay):
    """Espera un 'delay' en segundos y luego intenta borrar el mensaje."""
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
        logger.debug(f"Mensaje de broadcast {message_id} borrado para chat {chat_id} tras {delay}s.")
    except MessageIdInvalid:
        logger.debug(f"Mensaje {message_id} para chat {chat_id} ya no existía al intentar borrar.")
    except Exception as e:
        logger.warning(f"No se pudo borrar mensaje de broadcast {message_id} para chat {chat_id}: {e}")


# --- Manejador nuevo para el comando /dbroadcast ---
@Client.on_message(filters.command("dbroadcast") & filters.private & filters.user(ADMINS))
async def delete_broadcast_handler(client, message):
    # Verificar que el comando responde a un mensaje
    if not message.reply_to_message:
        await message.reply_text("❗️ Por favor, responde al mensaje que quieres transmitir con `/dbroadcast`.")
        return

    replied_message = message.reply_to_message
    total_users = await db.total_users_count()
    users_cursor = db.get_all_users() # Obtiene el cursor de usuarios

    # Mensaje inicial al admin
    broadcast_info_text = (
        f"📢 Iniciando broadcast con auto-borrado...\n"
        f"⏳ Retraso de borrado: {BROADCAST_DELETE_DELAY} segundos.\n"
        f"👥 Total de usuarios estimados: {total_users}"
    )
    broadcast_info_msg = await message.reply_text(broadcast_info_text, quote=True)

    success_count = 0
    failed_count = 0
    processed_count = 0
    start_time_db = time.time() # Tiempo para dbroadcast
    # Actualizar estado cada X usuarios (similar al broadcast normal)
    update_interval_db = max(10, total_users // 20)

    async for user in users_cursor:
        user_id = user.get('id') # Asume que el documento de usuario tiene un campo 'id'
        if not user_id:
            logger.warning(f"Documento de usuario sin ID encontrado durante dbroadcast: {user}")
            failed_count += 1
            processed_count += 1
            continue

        # Convertir a int por si acaso
        try:
            user_id_int = int(user_id)
        except ValueError:
             logger.warning(f"ID de usuario inválido encontrado durante dbroadcast: {user_id}")
             failed_count += 1
             processed_count += 1
             continue

        processed_count += 1

        try:
            # Copiar el mensaje directamente aquí (no usamos broadcast_messages helper)
            sent_msg = await replied_message.copy(chat_id=user_id_int)
            success_count += 1
            # Programar la tarea de borrado sin esperar a que termine
            asyncio.create_task(delete_message_after_delay(client, user_id_int, sent_msg.id, BROADCAST_DELETE_DELAY))

        except FloodWait as e:
            wait_time = e.value + 5 # Añadir un pequeño margen
            logger.warning(f"FloodWait al enviar dbroadcast a {user_id_int}. Esperando {wait_time} segundos...")
            await asyncio.sleep(wait_time)
            # Reintentar después de la espera
            try:
                sent_msg = await replied_message.copy(chat_id=user_id_int)
                success_count += 1
                asyncio.create_task(delete_message_after_delay(client, user_id_int, sent_msg.id, BROADCAST_DELETE_DELAY))
            except Exception as retry_e:
                logger.error(f"Error al reenviar dbroadcast a {user_id_int} después de FloodWait: {retry_e}")
                failed_count += 1

        except (UserIsBlocked, PeerIdInvalid, InputUserDeactivated) as user_err: # Agrupamos errores de usuario
            logger.warning(f"Fallo al enviar dbroadcast a {user_id_int}: {user_err}. Usuario bloqueó, ID inválido o desactivado.")
            failed_count += 1
            # Considera si quieres borrar al usuario aquí también como en broadcast_messages
            # await db.delete_user(user_id_int)
        except Exception as e:
            logger.error(f"Error desconocido al enviar dbroadcast a {user_id_int}: {e}")
            failed_count += 1

        # Actualizar el mensaje de estado para el admin periódicamente
        if processed_count % update_interval_db == 0:
            try:
                update_text = (
                    f"📢 Transmitiendo con auto-borrado...\n"
                    f"⏳ Retraso: {BROADCAST_DELETE_DELAY}s\n"
                    f"👥 Procesados: {processed_count}/{total_users}\n"
                    f"✅ Éxito: {success_count}\n"
                    f"❌ Fallo: {failed_count}"
                )
                # Evitar editar si el mensaje fue eliminado mientras tanto
                if broadcast_info_msg:
                    await broadcast_info_msg.edit_text(update_text)
            except MessageNotModified: # Ignorar si el texto no cambió
                pass
            except Exception as edit_err: # Evitar que un fallo al editar detenga el broadcast
                logger.warning(f"No se pudo editar el mensaje de estado del dbroadcast: {edit_err}")

        # Pequeña pausa para evitar sobrecargar la API
        if processed_count % 5 == 0:
             await asyncio.sleep(0.1) # Pausa corta cada 5 usuarios


    # Mensaje final al admin
    time_taken_db = datetime.timedelta(seconds=int(time.time()-start_time_db))
    final_summary_text_db = (
        f"✅ Broadcast con Auto-Borrado completado.\n"
        f"⏱️ Tiempo total: {time_taken_db}\n\n"
        f"▶️ Mensajes enviados con éxito: {success_count}\n"
        f"▶️ Fallos al enviar: {failed_count}\n"
        f"👤 Total de usuarios procesados: {processed_count}"
    )
    try:
        # Evitar editar si el mensaje fue eliminado mientras tanto
        if broadcast_info_msg:
             await broadcast_info_msg.edit_text(final_summary_text_db)
    except Exception as final_edit_err:
        logger.warning(f"No se pudo editar el resumen final del dbroadcast: {final_edit_err}")
        # Enviar como mensaje nuevo si la edición falla
        await message.reply_text(final_summary_text_db, quote=True)


# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
