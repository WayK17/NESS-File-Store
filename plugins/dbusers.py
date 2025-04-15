# plugins/dbusers.py

import motor.motor_asyncio
from config import DB_NAME, DB_URI
import logging
# --- Añadido: Importar datetime para manejar fechas de expiración ---
import datetime

logger = logging.getLogger(__name__)

class Database:

    def __init__(self, uri, database_name):
        # ... (sin cambios) ...
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        logger.info("Conexión a base de datos de usuarios establecida.")

    # --- Modificado para incluir campos premium ---
    def new_user(self, id, name):
        logger.debug(f"Creando nuevo dict de usuario para ID: {id}")
        return dict(
            id = id,
            name = name,
            pending_join_msg_id = None,
            # --- Campos nuevos ---
            is_premium = False,
            premium_expiry = None # Guardaremos fecha/hora UTC
            # -------------------
        )

    # --- Modificado para asegurar campos premium ---
    async def add_user(self, id, name):
        user_dict = self.new_user(id, name)
        try:
            # Usamos $setOnInsert para añadir campos premium solo si el usuario es nuevo
            # y $set para actualizar nombre (y asegurar id/name existen)
            await self.col.update_one(
                {'id': int(id)},
                {
                    '$set': {'name': name}, # Asegurar/Actualizar nombre
                    '$setOnInsert': {
                        'is_premium': False,
                        'premium_expiry': None,
                        'pending_join_msg_id': None
                        # Añadir otros campos iniciales aquí si los hubiera
                    }
                },
                upsert=True # Crea el usuario si no existe
            )
            logger.info(f"Usuario {id} añadido o actualizado en la BD.")
        except Exception as e:
             logger.error(f"Error al añadir/actualizar usuario {id}: {e}")

    # --- Funciones Originales (sin cambios funcionales) ---
    async def is_user_exist(self, id):
        # ... (sin cambios) ...
        try: user = await self.col.find_one({'id':int(id)}); return bool(user)
        except Exception as e: logger.error(f"Error check exist {id}: {e}"); return False

    async def total_users_count(self):
        # ... (sin cambios) ...
        try: count = await self.col.count_documents({}); return count
        except Exception as e: logger.error(f"Error count users: {e}"); return 0

    async def get_all_users(self):
        # ... (sin cambios) ...
        logger.debug("Obteniendo cursor para todos los usuarios.")
        return self.col.find({}) # Devuelve cursor

    async def delete_user(self, user_id):
        # ... (sin cambios) ...
        try: await self.col.delete_many({'id': int(user_id)}); logger.info(f"Usuario {user_id} eliminado.")
        except Exception as e: logger.error(f"Error delete user {user_id}: {e}")

    async def get_user_info(self, user_id):
        # ... (sin cambios) ...
        logger.debug(f"Intentando obtener info del usuario {user_id}")
        try: user_data = await self.col.find_one({'id': int(user_id)}); return user_data
        except Exception as e: logger.error(f"Error get user info {user_id}: {e}"); return None

    async def update_user_info(self, user_id, update_data):
        # ... (sin cambios) ...
        logger.debug(f"Intentando actualizar info del usuario {user_id} con: {update_data}")
        try:
            result = await self.col.update_one({'id': int(user_id)}, {'$set': update_data})
            if result.matched_count == 0: logger.warning(f"Update fail {user_id}: not found."); return False
            logger.debug(f"Update user {user_id}. Matched: {result.matched_count}, Mod: {result.modified_count}")
            return True
        except Exception as e: logger.error(f"Error update user info {user_id}: {e}"); return False

    # ======================================================
    # =========== INICIO: NUEVAS FUNCIONES PREMIUM =========
    # ======================================================

    async def set_premium(self, user_id, days=None):
        """Activa premium para un usuario. Si days es None, es permanente."""
        expiry_date = None
        if days is not None and days > 0:
            # Calcula la fecha de expiración desde AHORA en UTC
            expiry_date = datetime.datetime.utcnow() + datetime.timedelta(days=days)

        update_data = {
            'is_premium': True,
            'premium_expiry': expiry_date # Puede ser None para permanente
        }
        logger.info(f"Activando premium para {user_id}. Expiración: {expiry_date}")
        return await self.update_user_info(user_id, update_data)

    async def remove_premium(self, user_id):
        """Desactiva premium para un usuario."""
        update_data = {
            'is_premium': False,
            'premium_expiry': None
        }
        logger.info(f"Desactivando premium para {user_id}.")
        return await self.update_user_info(user_id, update_data)

    async def check_premium_status(self, user_id):
        """Verifica si un usuario es premium activo."""
        logger.debug(f"Verificando estado premium para {user_id}")
        user_data = await self.get_user_info(user_id)
        if not user_data:
            logger.warning(f"Usuario {user_id} no encontrado para check_premium_status.")
            return False # No encontrado, no es premium

        is_premium = user_data.get('is_premium', False)
        expiry_date = user_data.get('premium_expiry') # Puede ser None o datetime

        if not is_premium:
            logger.debug(f"Usuario {user_id} no está marcado como premium.")
            return False # No está marcado como premium

        # Si está marcado como premium, verificar expiración
        if expiry_date is None:
            logger.debug(f"Usuario {user_id} tiene premium permanente.")
            return True # Es premium permanente

        # Si tiene fecha de expiración, compararla con la fecha/hora actual UTC
        if isinstance(expiry_date, datetime.datetime):
            if datetime.datetime.utcnow() < expiry_date:
                logger.debug(f"Usuario {user_id} tiene premium activo hasta {expiry_date}.")
                return True # Aún no ha expirado
            else:
                # Premium expirado, desactivarlo en la BD
                logger.info(f"Premium para {user_id} expiró en {expiry_date}. Desactivando...")
                await self.remove_premium(user_id) # Lo desactivamos automáticamente
                return False # Expiró
        else:
             logger.warning(f"Campo premium_expiry para {user_id} no es datetime o None: {expiry_date}. Asumiendo no premium.")
             # Podrías querer arreglar este dato en la BD
             await self.remove_premium(user_id)
             return False

    # ======================================================
    # ============= FIN: NUEVAS FUNCIONES PREMIUM ==========
    # ======================================================

db = Database(DB_URI, DB_NAME)
