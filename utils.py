import logging, asyncio, os, re, random, pytz, aiohttp, requests, string, json, http.client
from datetime import date, datetime
from config import SHORTLINK_API, SHORTLINK_URL
from shortzy import Shortzy
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, ChatWriteForbidden
from pyrogram import enums

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
TOKENS = {}
VERIFIED = {}

async def get_verify_shorted_link(link):
    if SHORTLINK_URL == "api.shareus.io":
        url = f'https://{SHORTLINK_URL}/easy_api'
        params = {
            "key": SHORTLINK_API,
            "link": link,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, raise_for_status=True, ssl=False) as response:
                    data = await response.text()
                    return data
        except Exception as e:
            logger.error(e)
            return link
    else:
  #      response = requests.get(f"https://{SHORTLINK_URL}/api?api={SHORTLINK_API}&url={link}")
 #       data = response.json()
  #      if data["status"] == "success" or rget.status_code == 200:
   #         return data["shortenedUrl"]
        shortzy = Shortzy(api_key=SHORTLINK_API, base_site=SHORTLINK_URL)
        link = await shortzy.convert(link)
        return link

async def check_token(bot, userid, token):
    user = await bot.get_users(userid)
    if user.id in TOKENS.keys():
        TKN = TOKENS[user.id]
        if token in TKN.keys():
            is_used = TKN[token]
            if is_used == True:
                return False
            else:
                return True
    else:
        return False

async def get_token(bot, userid, link):
    user = await bot.get_users(userid)
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    TOKENS[user.id] = {token: False}
    link = f"{link}verify-{user.id}-{token}"
    shortened_verify_url = await get_verify_shorted_link(link)
    return str(shortened_verify_url)

async def verify_user(bot, userid, token):
    user = await bot.get_users(userid)
    TOKENS[user.id] = {token: True}
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    VERIFIED[user.id] = str(today)

async def check_verification(bot, userid):
    user = await bot.get_users(userid)
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    if user.id in VERIFIED.keys():
        EXP = VERIFIED[user.id]
        years, month, day = EXP.split('-')
        comp = date(int(years), int(month), int(day))
        if comp<today:
            return False
        else:
            return True
    else:
        return False
 #--------------------------------------------------------------------------

# --- PEGA ESTA NUEVA FUNCIÓN AQUÍ ABAJO ---

async def check_user_membership(client, user_id, channel_id):
    """Verifica si un usuario es miembro de un canal específico (con logging mejorado)."""
    if not channel_id:
        logger.warning("FORCE_SUB_CHANNEL no está configurado. Saltando verificación.")
        return True

    try:
        chat_id_or_username = int(channel_id) if channel_id.lstrip('-').isdigit() else channel_id
    except ValueError:
        logger.error(f"Valor inválido para FORCE_SUB_CHANNEL: {channel_id}")
        return True # Failsafe

    try:
        logger.debug(f"Llamando a get_chat_member para {user_id} en {chat_id_or_username}")
        member = await client.get_chat_member(chat_id=chat_id_or_username, user_id=user_id)

        # --- Logging Adicional ---
        status_value = getattr(member, 'status', 'STATUS_NOT_FOUND') # Obtener status de forma segura
        status_type = type(status_value).__name__ # Obtener el tipo del status
        logger.debug(f"Resultado get_chat_member para {user_id}: status={status_value}, type={status_type}")
        # -------------------------

        # Comprobar si el estado es válido
        valid_statuses = [enums.ChatMemberStatus.MEMBER,
                          enums.ChatMemberStatus.ADMINISTRATOR,
                          enums.ChatMemberStatus.OWNER]
        is_valid_status = status_value in valid_statuses
        logger.debug(f"Comprobando si status '{status_value}' está en {valid_statuses}. Resultado: {is_valid_status}") # Log del resultado

        if is_valid_status:
            logger.debug(f"Usuario {user_id} ES miembro de {channel_id}. Devolviendo True.") # Log antes de retornar
            return True
        else:
            logger.debug(f"Usuario {user_id} NO es miembro activo de {channel_id} (status: {status_value}). Devolviendo False.")
            return False
    except UserNotParticipant:
        logger.debug(f"Usuario {user_id} NO es participante de {channel_id} (UserNotParticipant). Devolviendo False.")
        return False
    except (ChatAdminRequired, ChatWriteForbidden) as perm_err:
        logger.error(f"¡ERROR DE PERMISOS! Bot no admin en {channel_id}. Error: {perm_err}. Devolviendo True (Failsafe).")
        return True # Failsafe MANTENIDO
    except Exception as e:
        # Loguear tipo y representación del error, y el traceback completo
        logger.error(f"Error inesperado al verificar membresía de {user_id} en {channel_id}. Tipo: {type(e)}, Repr: {repr(e)}, Str: {e}", exc_info=True)
        return True # Failsafe MANTENIDO


# --- FIN DE LA NUEVA FUNCIÓN ---

