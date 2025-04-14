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

# ... (el resto de tu código existente en utils.py: get_verify_shorted_link, check_token, etc.) ...

# --- PEGA ESTA NUEVA FUNCIÓN AQUÍ ABAJO ---

# logger debe estar definido (ya lo tienes al principio del archivo)
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

async def check_user_membership(client, user_id, channel_id):
    """Verifica si un usuario es miembro de un canal específico."""
    if not channel_id:
        logger.warning("FORCE_SUB_CHANNEL no está configurado. Saltando verificación.")
        return True # Si no hay canal configurado, se asume que pasa

    # Convertir a int si es ID numérico, mantener como string si es @username
    try:
        chat_id_or_username = int(channel_id) if channel_id.lstrip('-').isdigit() else channel_id
    except ValueError:
         logger.error(f"Valor inválido para FORCE_SUB_CHANNEL: {channel_id}")
         return True # Failsafe en caso de configuración inválida

    try:
        member = await client.get_chat_member(chat_id=chat_id_or_username, user_id=user_id)
        # Comprobar si el estado es válido (miembro activo, admin, creador)
        if member.status in [enums.ChatMemberStatus.MEMBER,
                             enums.ChatMemberStatus.ADMINISTRATOR,
                             enums.ChatMemberStatus.CREATOR]:
            logger.debug(f"Usuario {user_id} ES miembro de {channel_id}.")
            return True
        else:
            # Estados como RESTRICTED, LEFT, KICKED cuentan como no miembro para este propósito
            logger.debug(f"Usuario {user_id} NO es miembro activo de {channel_id} (status: {member.status}).")
            return False
    except UserNotParticipant:
        # El usuario no está en el canal o nunca ha estado.
        logger.debug(f"Usuario {user_id} NO es participante de {channel_id} (UserNotParticipant).")
        return False
    except (ChatAdminRequired, ChatWriteForbidden):
        # ¡Error crítico de configuración! El bot necesita ser admin.
        logger.error(f"¡ERROR DE PERMISOS! El bot NO es administrador en el canal ForceSub ({channel_id}). No se puede verificar membresía.")
        # Failsafe: Dejar pasar si hay error de permisos del bot.
        return True
    except Exception as e:
        # Otros errores inesperados (ej. channel_id inválido, error de red)
        logger.error(f"Error inesperado al verificar membresía de {user_id} en {channel_id}: {e}")
        # Failsafe: Dejar pasar en caso de error desconocido.
        return True

# --- FIN DE LA NUEVA FUNCIÓN ---

