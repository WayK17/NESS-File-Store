# Archivo: dbusers.py (MODIFICADO)

import motor.motor_asyncio
import logging
import datetime # Importado para join_date
from config import DB_NAME, DB_URI

logger = logging.getLogger(__name__)

# --- Validaciones de Configuración ---
if not DB_URI:
    logger.critical("¡DB_URI no está configurada! El bot no puede funcionar sin base de datos.")
    # Podrías salir del programa aquí si es crítico: exit()
if not DB_NAME:
     logger.warning("DB_NAME no está configurada, usando nombre por defecto 'techvjbotz'")
     DB_NAME = "techvjbotz" # O el nombre que definiste en config.py

class Database:
    """Clase para interactuar con la base de datos MongoDB."""

    def __init__(self, uri, database_name):
        try:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
            self.db = self._client[database_name]
            # Colección de usuarios
            self.col = self.db.users
            # Colección para estadísticas
            self.stats_col = self.db.bot_stats
            logger.info(f"Conectado a la base de datos: {database_name}")
        except Exception as e:
            logger.critical(f"¡ERROR FATAL al conectar a MongoDB! {e}")
            # Considera salir si la conexión falla: exit()
            self._client = None
            self.db = None
            self.col = None
            self.stats_col = None


    def new_user(self, id, name):
        """Crea un diccionario para un nuevo usuario."""
        return dict(
            id=id,
            name=name,
            verified=False,  # Ejemplo: Añadir campo de verificación
            join_date=datetime.datetime.utcnow() # Fecha de registro
        )

    async def add_user(self, id, name):
        """Añade un nuevo usuario si no existe."""
        if not self.col: return # No hacer nada si la conexión falló
        # Verifica si ya existe para evitar duplicados
        if not await self.is_user_exist(id):
            user = self.new_user(id, name)
            try:
                await self.col.insert_one(user)
                logger.info(f"Nuevo usuario añadido: {name} (ID: {id})")
            except Exception as e:
                logger.error(f"Error al añadir usuario {id}: {e}")
        # else: # Opcional: actualizar nombre si ya existe
        #    try:
        #        await self.col.update_one({'id': int(id)}, {'$set': {'name': name}})
        #    except Exception as e:
        #        logger.error(f"Error al actualizar nombre de usuario {id}: {e}")

    async def is_user_exist(self, id):
        """Verifica si un usuario existe por su ID."""
        if not self.col: return False # No hacer nada si la conexión falló
        try:
            user = await self.col.find_one({'id': int(id)})
            return bool(user)
        except Exception as e:
            logger.error(f"Error al verificar si existe usuario {id}: {e}")
            return False # Asume que no existe si hay error

    async def total_users_count(self):
        """Cuenta el número total de usuarios."""
        if not self.col: return 0 # No hacer nada si la conexión falló
        try:
            count = await self.col.count_documents({})
            return count
        except Exception as e:
            logger.error(f"Error al contar usuarios: {e}")
            return 0

    async def get_all_users(self):
        """Obtiene un cursor para todos los usuarios."""
        if not self.col: return None # No hacer nada si la conexión falló
        # Considera añadir proyecciones si no necesitas todos los campos:
        # return self.col.find({}, {'_id': 0, 'id': 1}) # Ejemplo: solo obtener IDs
        return self.col.find({})

    async def delete_user(self, user_id):
        """Elimina un usuario por su ID."""
        if not self.col: return # No hacer nada si la conexión falló
        try:
            await self.col.delete_many({'id': int(user_id)})
            logger.info(f"Usuario eliminado: {user_id}")
        except Exception as e:
            logger.error(f"Error al eliminar usuario {user_id}: {e}")

    # --- MÉTODOS PARA ESTADÍSTICAS ---

    async def get_start_request_count(self):
        """Obtiene el contador total de solicitudes /start para archivos."""
        if not self.stats_col: return 0 # No hacer nada si la conexión falló
        try:
            stats_doc = await self.stats_col.find_one({'_id': 'stats'})
            return stats_doc.get('total_start_requests', 0) if stats_doc else 0
        except Exception as e:
            logger.error(f"Error al obtener contador de solicitudes: {e}")
            return 0

    async def increment_start_request_count(self):
        """Incrementa el contador total de solicitudes /start para archivos en 1."""
        if not self.stats_col: return # No hacer nada si la conexión falló
        try:
            await self.stats_col.update_one(
                {'_id': 'stats'},
                {'$inc': {'total_start_requests': 1}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error al incrementar contador de solicitudes: {e}")

# --- Instancia global de la base de datos ---
# Esta instancia estará disponible para ser importada en otros archivos
db = Database(DB_URI, DB_NAME)

