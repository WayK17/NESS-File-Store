# Archivo: config.py

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import re
import os
from os import environ
# Asegúrate de tener un archivo Script.py con los textos necesarios
from Script import script

id_pattern = re.compile(r'^.\d+$')
def is_enabled(value, default):
    if value is None: # Manejar caso donde la variable de entorno no esté definida
        return default
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# --- Bot Information ---
API_ID = int(environ.get("API_ID", 0)) # Añadir valor por defecto 0 o manejar error si no se provee
API_HASH = environ.get("API_HASH", "")
BOT_TOKEN = environ.get("BOT_TOKEN", "")

# --- Bot Appearance ---
PICS = (environ.get('PICS', 'https://graph.org/file/ce1723991756e48c35aa1.jpg')).split() # Bot Start Picture

# --- Admin and Bot Info ---
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '').split() if admin] # Asegurar que admin no esté vacío
BOT_USERNAME = environ.get("BOT_USERNAME", "") # without @
PORT = environ.get("PORT", "8080")

# --- Clone Info ---
CLONE_MODE = is_enabled(environ.get('CLONE_MODE'), False) # Set True or False
# If Clone Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
CLONE_DB_URI = environ.get("CLONE_DB_URI", "") if CLONE_MODE else ""
CDB_NAME = environ.get("CDB_NAME", "clonetechvj") if CLONE_MODE else ""

# --- Database Information ---
DB_URI = environ.get("DB_URI", "")
DB_NAME = environ.get("DB_NAME", "techvjbotz")

# --- Auto Delete Information ---
AUTO_DELETE_MODE = is_enabled(environ.get('AUTO_DELETE_MODE'), True) # Set True or False
# If Auto Delete Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
# Tiempo en minutos para el mensaje de aviso
AUTO_DELETE = int(environ.get("AUTO_DELETE", "30")) if AUTO_DELETE_MODE else 0
# Tiempo en segundos para la eliminación real (AUTO_DELETE * 60)
AUTO_DELETE_TIME = int(environ.get("AUTO_DELETE_TIME", str(AUTO_DELETE * 60))) if AUTO_DELETE_MODE else 0

# --- Channel Information ---
# Asegúrate que LOG_CHANNEL sea un ID numérico válido o 0/None si no se usa
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", 0)) if environ.get("LOG_CHANNEL") else None

# --- File Caption Information ---
# Usa f-string correctamente o asegúrate que script.CAPTION exista
DEFAULT_CAPTION = getattr(script, 'CAPTION', '{file_name}\n\n💾 Size: {file_size}') # Caption por defecto
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", DEFAULT_CAPTION)
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)

# --- File Store Mode ---
PUBLIC_FILE_STORE = is_enabled(environ.get('PUBLIC_FILE_STORE', "True"), True)

# --- Verify Info ---
VERIFY_MODE = is_enabled(environ.get('VERIFY_MODE'), False) # Set True or False
# If Verify Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
SHORTLINK_URL = environ.get("SHORTLINK_URL", "") if VERIFY_MODE else "" # shortlink domain without https://
SHORTLINK_API = environ.get("SHORTLINK_API", "") if VERIFY_MODE else "" # shortlink api
VERIFY_TUTORIAL = environ.get("VERIFY_TUTORIAL", "") if VERIFY_MODE else "" # how to open link

# --- Website Info ---
WEBSITE_URL_MODE = is_enabled(environ.get('WEBSITE_URL_MODE'), False) # Set True or False
# If Website Url Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
WEBSITE_URL = environ.get("WEBSITE_URL", "") if WEBSITE_URL_MODE else "" # For More Information Check Video On Yt - @Tech_VJ

# --- File Stream Config ---
STREAM_MODE = is_enabled(environ.get('STREAM_MODE'), True) # Set True or False
# If Stream Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
MULTI_CLIENT = False # Parece no usado en el código provisto, mantener o eliminar según necesidad
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '60')) # Para Heroku?
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  # 20 minutes, para Heroku?
if 'DYNO' in environ:
    ON_HEROKU = True
    # Asegurar que URL se defina si está en Heroku y se necesita para stream/ping
    HEROKU_APP_NAME = environ.get('HEROKU_APP_NAME', None)
    if HEROKU_APP_NAME:
         URL = environ.get("URL", f"https://{HEROKU_APP_NAME}.herokuapp.com/")
    else:
         URL = environ.get("URL", "") # Requiere que URL se configure manualmente si no hay app name
else:
    ON_HEROKU = False
    URL = environ.get("URL", "") # Requiere que URL se configure manualmente si no está en Heroku

# --- Validaciones básicas ---
if not BOT_TOKEN:
    print("¡ERROR CRÍTICO: BOT_TOKEN no configurado!")
if not API_ID or not API_HASH:
    print("¡ERROR CRÍTICO: API_ID o API_HASH no configurados!")
if not DB_URI:
    print("¡ERROR CRÍTICO: DB_URI no configurada!")
if STREAM_MODE and not URL:
    print("¡ADVERTENCIA: STREAM_MODE está activo pero URL no está configurada!")
if VERIFY_MODE and (not SHORTLINK_URL or not SHORTLINK_API):
     print("¡ADVERTENCIA: VERIFY_MODE está activo pero falta SHORTLINK_URL o SHORTLINK_API!")

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
