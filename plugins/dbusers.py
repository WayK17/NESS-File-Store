# plugins/dbusers.py

import motor.motor_asyncio
from config import DB_NAME, DB_URI
import logging # <--- Añadido: Importar logging

# <--- Añadido: Configurar logger ---
logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO) # Puedes ajustar el nivel si quieres más o menos logs

class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        logger.info("Conexión a base de datos de usuarios establecida.") # <--- Añadido: Log

    # --- Modificado mínimamente para incluir el nuevo campo ---
    def new_user(self, id, name):
        logger.debug(f"Creando nuevo dict de usuario para ID: {id}")
        return dict(
            id = id,
            name = name,
            pending_join_msg_id = None # <--- Añadido: Campo para el ID del mensaje pendiente
        )

    # --- Modificado para ser más robusto y añadir/actualizar el nuevo campo ---
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        try:
            # Usar update_one con $set y upsert=True es más seguro:
            # - No da error si el usuario ya existe.
            # - Asegura que el campo 'pending_join_msg_id' se añada o se ponga a None si ya existía.
            await self.col.update_one({'id': int(id)}, {"$set": user}, upsert=True)
            logger.info(f"Usuario {id} añadido o actualizado en la BD.")
        except Exception as e:
             logger.error(f"Error al añadir/actualizar usuario {id}: {e}")

    # --- Funciones Originales (sin cambios funcionales) ---
    async def is_user_exist(self, id):
        try: # Añadido try/except para robustez
            user = await self.col.find_one({'id':int(id)})
            return bool(user)
        except Exception as e:
            logger.error(f"Error al chequear existencia del usuario {id}: {e}")
            return False # Asumir que no existe si hay error

    async def total_users_count(self):
        try: # Añadido try/except
            count = await self.col.count_documents({})
            return count
        except Exception as e:
            logger.error(f"Error al contar usuarios: {e}")
            return 0

    async def get_all_users(self):
        logger.debug("Obteniendo cursor para todos los usuarios.")
        # Devuelve un cursor asíncrono
        return self.col.find({})

    async def delete_user(self, user_id):
        try: # Añadido try/except
            await self.col.delete_many({'id': int(user_id)})
            logger.info(f"Usuario {user_id} eliminado de la BD.")
        except Exception as e:
             logger.error(f"Error al eliminar usuario {user_id}: {e}")

    # ======================================================
    # =========== INICIO: NUEVAS FUNCIONES AÑADIDAS ========
    # ======================================================

    async def get_user_info(self, user_id):
        """Obtiene el documento completo de un usuario por su ID."""
        logger.debug(f"Intentando obtener info del usuario {user_id}")
        try:
            user_data = await self.col.find_one({'id': int(user_id)})
            return user_data
        except Exception as e:
            logger.error(f"Error al obtener info del usuario {user_id}: {e}")
            return None

    async def update_user_info(self, user_id, update_data):
        """Actualiza campos específicos de un usuario usando $set.
           'update_data' debe ser un diccionario, ej: {'name': 'NuevoNombre', 'pending_join_msg_id': 123}
        """
        logger.debug(f"Intentando actualizar info del usuario {user_id} con: {update_data}")
        try:
            result = await self.col.update_one(
                {'id': int(user_id)},
                {'$set': update_data}
            )
            # Comprobar si algo fue realmente modificado o si el usuario existía
            if result.matched_count == 0:
                 logger.warning(f"Intento de actualizar usuario {user_id} falló (usuario no encontrado).")
                 return False
            logger.debug(f"Info del usuario {user_id} actualizada. Matched: {result.matched_count}, Modified: {result.modified_count}")
            return True
        except Exception as e:
            logger.error(f"Error al actualizar info del usuario {user_id}: {e}")
            return False

    # ======================================================
    # ============= FIN: NUEVAS FUNCIONES AÑADIDAS =========
    # ======================================================


db = Database(DB_URI, DB_NAME)
