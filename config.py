# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01


import re
import os
from os import environ
from Script import script

id_pattern = re.compile(r'^.\d+$')
def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# Bot Information
API_ID = int(environ.get("API_ID", "15353803"))
API_HASH = environ.get("API_HASH", "0dc88c619c52613806822fd600eec006")
BOT_TOKEN = environ.get("BOT_TOKEN", "7095517891:AAGXGWs6hW7IU2XnOTMtZrjSEBmsWJG2rUI")

PICS = (environ.get('PICS', 'https://envs.sh/GwI.jpg/IMG11042025.jpg')).split() # Bot Start Picture
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '6279723048').split()]
BOT_USERNAME = environ.get("BOT_USERNAME", "") # without @
PORT = environ.get("PORT", "8080")

# Clone Info :-
CLONE_MODE = bool(environ.get('CLONE_MODE', False)) # Set True or False

# If Clone Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
CLONE_DB_URI = environ.get("CLONE_DB_URI", "")
CDB_NAME = environ.get("CDB_NAME", "clonetechvj")

# Database Information
DB_URI = environ.get("DB_URI", "mongodb+srv://XinZ:m3olvidexD@xinz.iulcp9d.mongodb.net")
DB_NAME = environ.get("DB_NAME", "XinZ")

# Auto Delete Information
AUTO_DELETE_MODE = bool(environ.get('AUTO_DELETE_MODE', True)) # Set True or False

# If Auto Delete Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
AUTO_DELETE = int(environ.get("AUTO_DELETE", "10")) # Time in Minutes
AUTO_DELETE_TIME = int(environ.get("AUTO_DELETE_TIME", "600")) # Time in Seconds

# Channel Information
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1002514857367"))

# File Caption Information
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)

# Enable - True or Disable - False
PUBLIC_FILE_STORE = is_enabled((environ.get('PUBLIC_FILE_STORE', "False")), False)

# Verify Info :-
VERIFY_MODE = bool(environ.get('VERIFY_MODE', False)) # Set True or False

# If Verify Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
SHORTLINK_URL = environ.get("SHORTLINK_URL", "") # shortlink domain without https://
SHORTLINK_API = environ.get("SHORTLINK_API", "") # shortlink api
VERIFY_TUTORIAL = environ.get("VERIFY_TUTORIAL", "") # how to open link 

# Website Info:
WEBSITE_URL_MODE = bool(environ.get('WEBSITE_URL_MODE', False)) # Set True or False

# If Website Url Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
WEBSITE_URL = environ.get("WEBSITE_URL", "") # For More Information Check Video On Yt - @Tech_VJ

# File Stream Config
STREAM_MODE = bool(environ.get('STREAM_MODE', False)) # Set True or False

# If Stream Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
MULTI_CLIENT = False
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '60'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  # 20 minutes
if 'DYNO' in environ:
    ON_HEROKU = True
else:
    ON_HEROKU = False
URL = environ.get("URL", "https://testofvjfilter-1fa60b1b8498.herokuapp.com/")


# CONFIGURACIÓN BROADCAST CON AUTO-BORRADO
# ==========================================
# Tiempo en segundos que el mensaje permanecerá visible antes de ser borrado.
# Default: 3600 segundos = 1 hora
BROADCAST_DELETE_DELAY = int(environ.get("BROADCAST_DELETE_DELAY", "300"))


# ==========================================
#      CONFIGURACIÓN FORCE SUBSCRIBE
# ==========================================
# Activar/Desactivar la función (True o False)
FORCE_SUB_ENABLED = is_enabled(environ.get('FORCE_SUB_ENABLED', "True"), True)

# ID numérico o @username del canal al que deben unirse. ¡El bot DEBE ser admin aquí!
# Ejemplo: FORCE_SUB_CHANNEL = -10012345678**  o  FORCE_SUB_CHANNEL = "MiCanal"
FORCE_SUB_CHANNEL = environ.get('FORCE_SUB_CHANNEL', "-1002173951862")

# Enlace de invitación del canal (si es privado o quieres usar uno específico)
# Ejemplo: FORCE_SUB_INVITE_LINK = "https://t.me/joinchat/ABCDEFGHIJKL12345"
# Si el canal es público, puedes poner el enlace normal (e.g., "https://t.me/MiCanal")
FORCE_SUB_INVITE_LINK = environ.get('FORCE_SUB_INVITE_LINK', "https://t.me/NessCloud")

# Opcional: Permitir que los admins del bot salten la verificación (True o False)
SKIP_FORCE_SUB_FOR_ADMINS = is_enabled(environ.get('SKIP_FORCE_SUB_FOR_ADMINS', "True"), True)



# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
