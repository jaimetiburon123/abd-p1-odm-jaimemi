__author__ = 'Pablo Ramos Criado'
__students__ = 'Nombres_y_Apellidos'


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
from typing import Generator, Any, Self
from geojson import Point
import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import yaml

def getLocationPoint(address: str) -> Point:
    """ 
    Obtiene las coordenadas de una dirección en formato geojson.Point
    Utilizar la API de geopy para obtener las coordenadas de la direccion
    Cuidado, la API es publica tiene limite de peticiones, utilizar sleeps.

    Parameters
    ----------
        address : str
            direccion completa de la que obtener las coordenadas
    Returns
    -------
        geojson.Point
            coordenadas del punto de la direccion
    """
    location = None
    intentos = 0
    maxIntentos = 5
    while location is None and intentos < maxIntentos:
        intentos += 1
        try:
            time.sleep(1)
            #TODO
            # Es necesario proporcionar un user_agent para utilizar la API
            # Utilizar un nombre aleatorio para el user_agent
            location = Nominatim(user_agent="EnVivoODM_JE").geocode(address)
        except GeocoderTimedOut:
            # Puede lanzar una excepcion si se supera el tiempo de espera
            # Volver a intentarlo
            continue
    #TODO
    # Devolver un GeoJSON de tipo punto con la latitud y longitud almacenadas.
    # Si no se consiguieron coordenadas, lanzar ValueError: la funcion no puede
    # devolver un punto inventado ni None silenciosamente. Es lo que espera la
    # prueba test_get_location_point_timeout_failure.

    if location is None:
        raise ValueError("No se pudieron obtener coordenadas")

    return Point([location.longitude, location.latitude])

class Model:
    """ 
    Clase de modelo abstracta
    Crear tantas clases que hereden de esta clase como  
    colecciones/modelos se deseen tener en la base de datos.

    Attributes
    ----------
        required_vars : set[str]
            conjunto de atributos requeridos por el modelo
        admissible_vars : set[str]
            conjunto de atributos admitidos por el modelo
        db : pymongo.collection.Collection
            conexion a la coleccion de la base de datos
    
    Methods
    -------
        __setattr__(name: str, value: str | dict) -> None
            Sobreescribe el metodo de asignacion de valores a los 
            atributos del objeto con el fin de controlar qué atributos 
            son modificados y cuando son modificados.
        __getattr__(name: str) -> Any
            Sobreescribe el metodo de acceso a atributos del objeto 
        save()  -> None
            Guarda el modelo en la base de datos
        delete() -> None
            Elimina el modelo de la base de datos
        find(filter: dict[str, str | dict]) -> ModelCursor
            Realiza una consulta de lectura en la BBDD.
            Devuelve un cursor de modelos ModelCursor
        aggregate(pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor
            Devuelve el resultado de una consulta aggregate.
        find_by_id(id: str) -> dict | None
            Busca un documento por su id utilizando la cache y lo devuelve.
            Si no se encuentra el documento, devuelve None.
        init_class(db_collection: pymongo.collection.Collection, required_vars: set[str], admissible_vars: set[str]) -> None
            Inicializa las variables de clase en la inicializacion del sistema.

    """
    _required_vars: set[str]
    _admissible_vars: set[str]
    _location_var: str | None = None
    _db: pymongo.collection.Collection
    _internal_vars: set[str] = frozenset(('_modified_vars', '_required_vars', '_admissible_vars', '_db', '_data', '_location_var'))

    def __init__(self, **kwargs: dict[str, str | dict | list]) -> None:
        """
        Inicializa el modelo con los valores proporcionados en kwargs
        Comprueba que los valores proporcionados en kwargs son admitidos
        por el modelo y que las atributos requeridos son proporcionadas.

        Parameters
        ----------
            kwargs : dict[str, str | dict]
                diccionario con los valores de las atributos del modelo
        """
        self._data: dict[str, str | dict | list] = {}
        self._modified_vars: set[str] = set()
        #TODO
        # Realizar las comprabociones y gestiones necesarias
        # antes de la asignacion.

        # Asigna todos los valores en kwargs a las atributos con 
        # nombre las claves en kwargs
        # Utilizamos el atributo data para guardar los variables 
        # almacenadas en la base de datos en una solo atributo
        # Encapsular los datos en una sola variable facilita la 
        # gestion en metodos como save.

        for var in self._required_vars:
            if var not in kwargs:
                raise ValueError(f"Missing required variable: {var}")

        for var in kwargs:
            if (var not in self._required_vars and var not in self._admissible_vars and var != "_id"):
                raise ValueError(f"Variable {var} is not admissible for this model")

        self._data.update(kwargs)

    def __setattr__(self, name: str, value: str | dict) -> None:
        """ Sobreescribe el metodo de asignacion de valores a los 
        atributos del objeto con el fin de controlar que atributos 
        son modificados y cuando son modificados.
        """
        if name in self._internal_vars:
            super().__setattr__(name, value)
            return
        #TODO
        # Realizar las comprabociones y gestiones necesarias
        # antes de la asignacion.

        if name not in self._required_vars and name not in self._admissible_vars:
            raise ValueError(f"Variable {name} is not admissible for this model")

        if name not in self._data or self._data[name] != value:
            self._modified_vars.add(name)

        # Asigna el valor value a la variable name
        self._data[name] = value

    def __getattr__(self, name: str) -> Any:
        """ Sobreescribe el metodo de acceso a atributos del objeto
        __getattr__ solo es llamado cuando no encuentra el atributo
        en el objeto 
        """
        if name in self._internal_vars:
            return super().__getattribute__(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError
        
    def save(self) -> None:
        """
        Guarda el modelo en la base de datos
        Si el modelo no existe en la base de datos, se crea un nuevo
        documento con los valores del modelo. En caso contrario, se
        actualiza el documento existente con los nuevos valores del
        modelo.
        """
        #TODO

        is_new = "_id" not in self._data

        address_field = self._location_var

        if(
            address_field is not None
            and address_field in self._data
            and self._data[address_field] is not None
            and (is_new or address_field in self._modified_vars)
        ):
            location_field = f"{address_field}_loc"
            self._data[location_field] = getLocationPoint(self._data[address_field])
            self._modified_vars.add(location_field)


        if is_new:
            result = self._db.insert_one(self._data.copy())
            self._data["_id"] = result.inserted_id
        elif self._modified_vars: 
            updates = {}
            for field in self._modified_vars:
                updates[field] = self._data[field]

            self._db.update_one(
                {"_id": self._data["_id"]},
                {"$set": updates},
            )

        self._modified_vars.clear()

    def delete(self) -> None:
        """
        Elimina el modelo de la base de datos
        """
        #TODO
        if "_id" not in self._data:
            raise ValueError("Cannot delete unsaved documents")

        self._db.delete_one({"_id": self._data["_id"]})

        del self._data["_id"]
        self._modified_vars.clear()
    
    @classmethod
    def find(cls, filter: dict[str, str | dict]) -> Any:
        """ 
        Utiliza el metodo find de pymongo para realizar una consulta
        de lectura en la BBDD.
        find debe devolver un cursor de modelos ModelCursor

        Parameters
        ----------
            filter : dict[str, str | dict]
                diccionario con el criterio de busqueda de la consulta
        Returns
        -------
            ModelCursor
                cursor de modelos
        """ 
        #TODO
        # cls es el puntero a la clase
        
        if filter is None:
            filter = {}

        mongo_cursor = cls._db.find(filter)
        return ModelCursor(cls, mongo_cursor)
        

    @classmethod
    def aggregate(cls, pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor:
        """ 
        Devuelve el resultado de una consulta aggregate. 
        No hay nada que hacer en esta funcion.
        Se utilizara para las consultas solicitadas
        en el segundo proyecto de la practica.

        Parameters
        ----------
            pipeline : list[dict]
                lista de etapas de la consulta aggregate 
        Returns
        -------
            pymongo.command_cursor.CommandCursor
                cursor de pymongo con el resultado de la consulta
        """ 
        return cls._db.aggregate(pipeline)
    
    @classmethod
    def find_by_id(cls, id: str) -> Self | None:
        """ 
        NO IMPLEMENTAR HASTA EL TERCER PROYECTO
        Busca un documento por su id utilizando la cache y lo devuelve.
        Si no se encuentra el documento, devuelve None.

        Parameters
        ----------
            id : str
                id del documento a buscar
        Returns
        -------
            Self | None
                Modelo del documento encontrado o None si no se encuentra
        """ 
        #TODO
        pass

    @classmethod
    def init_class(cls, db_collection: pymongo.collection.Collection, indexes:dict[str,str], required_vars: set[str], admissible_vars: set[str]) -> None:
        """ 
        Inicializa los atributos de clase en la inicializacion del sistema.
        Aqui se deben inicializar o asegurar los indices. Tambien se puede
        alguna otra inicialización/comprobaciones o cambios adicionales
        que estime el alumno.

        Parameters
        ----------
            db_collection : pymongo.collection.Collection
                Conexion a la collecion de la base de datos.
            indexes: Dict[str,str]
                Set de indices y tipo de indices para la coleccion
            required_vars : set[str]
                Set de atributos requeridos por el modelo
            admissible_vars : set[str] 
                Set de atributos admitidos por el modelo
        """
        cls._db = db_collection
        cls._required_vars = required_vars
        cls._admissible_vars = admissible_vars
        # TODO
        # Recorrer indexes y crear cada índice segun su tipo: 'unique', 'asc'
        # y 'geosphere'. Comparar el tipo por igualdad, no con el operador 'in'.
        # Ojo con el índice geoespacial: save() guarda el GeoJSON Point en
        # <campo>_loc, luego el índice 2dsphere va sobre <campo>_loc, mientras
        # que _location_var debe guardar el nombre del campo base.

        for field, index_type in indexes.items():
            if index_type == "unique":
                cls._db.create_index(field, unique=True)
            elif index_type == "asc":
                cls._db.create_index(field)
            elif index_type == "geosphere":
                cls._db.create_index([(f"{field}_loc", pymongo.GEOSPHERE)])
                cls._location_var = field


class ModelCursor:
    """ 
    Cursor para iterar sobre los documentos del resultado de una
    consulta. Los documentos deben ser devueltos en forma de objetos
    modelo.

    Attributes
    ----------
        model_class : Model
            Clase para crear los modelos de los documentos que se iteran.
        cursor : pymongo.cursor.Cursor
            Cursor de pymongo a iterar

    Methods
    -------
        __iter__() -> Generator
            Devuelve un iterador que recorre los elementos del cursor
            y devuelve los documentos en forma de objetos modelo.
    """

    def __init__(self, model_class: Model, cursor: pymongo.cursor.Cursor):
        """
        Inicializa el cursor con la clase de modelo y el cursor de pymongo

        Parameters
        ----------
            model_class : Model
                Clase para crear los modelos de los documentos que se iteran.
            cursor: pymongo.cursor.Cursor
                Cursor de pymongo a iterar
        """
        self.model = model_class
        self.cursor = cursor
    
    def __iter__(self) -> Generator:
        """
        Devuelve un iterador que recorre los elementos del cursor
        y devuelve los documentos en forma de objetos modelo.
        Utilizar yield para generar el iterador
        Utilizar la funcion next para obtener el siguiente documento del cursor
        Utilizar alive para comprobar si existen mas documentos.
        """
        #TODO

        while self.cursor.alive:
            try:
                document = next(self.cursor)
            except StopIteration:
                break

            yield self.model(**document)


def initApp(definitions_path: str = "./models.yml", mongodb_uri="mongodb://localhost:27017/", db_name="abd", scope=globals()) -> None:
    """ 
    Declara las clases que heredan de Model para cada uno de los 
    modelos de las colecciones definidas en definitions_path.
    Inicializa las clases de los modelos proporcionando los indices y 
    atributos admitidos y requeridos para cada una de ellas y la conexión a la
    collecion de la base de datos.
    
    Parameters
    ----------
        definitions_path : str
            ruta al fichero de definiciones de modelos
        mongodb_uri : str
            uri de conexion a la base de datos
        db_name : str
            nombre de la base de datos
    """
    #TODO
    # Inicializar base de datos
    client = MongoClient(mongodb_uri)
    db = client[db_name]

    #TODO
    # Declarar tantas clases modelo colecciones existan en la base de datos
    # Leer el fichero de definiciones de modelos para obtener las colecciones,
    # indices y los atributos admitidos y requeridos para cada una de ellas.

    with open(definitions_path, "r", encoding="utf-8") as file:
        definitions = yaml.safe_load(file)

    for model_name, config in definitions.items():
        collection = db[model_name]

        scope[model_name] = type(model_name, (Model,),{})

        indexes = {}

        for field in config.get("unique_indexes", []):
            indexes[field] = "unique"

        for field in config.get("regular_indexes", []):
            indexes[field] = "asc"

        if "location_index" in config:
            location_index = config["location_index"]
            indexes[location_index] = "geosphere"

        scope[model_name].init_class(db_collection=collection, indexes=indexes, required_vars=set(config.get("required_vars")), admissible_vars=set(config.get("admissible_vars", [])))

if __name__ == "__main__":

    initApp()

    Artista._db.delete_many({})
    Recinto._db.delete_many({})
    Evento._db.delete_many({})
    Asistente._db.delete_many({})

    artista1 = Artista(nombre="Bad Bunny", generos=["Reggaeton", "Trap"],
                      pais_de_origen="Puerto Rico", año_de_inicio=2016)

    artista2 = Artista(nombre="Taylor Swift", generos=["Pop", "Country"],
                      pais_de_origen="Estados Unidos", año_de_inicio=2006)

    artista3 = Artista(nombre="Rosalia", generos=["Pop", "Flamenco"],
                      pais_de_origen="España", año_de_inicio=2013)

    artista4 = Artista(nombre="Drake", generos=["Rap", "Hip-Hop"],
                      pais_de_origen="Canada", año_de_inicio=2006)

    artista5 = Artista(nombre="Coldplay", generos=["Pop", "Rock"],
                      pais_de_origen="Reino Unido", año_de_inicio=1997)

    artista1.save()
    artista2.save()
    artista3.save()
    artista4.save()
    artista5.save()

    print("5 artists saved")


    recinto1 = Recinto(nombre="Movistar Arena", direccion="Madrid, España",
                       aforo=17000, zonas={"Pista": 5000, "Grada": 12000})

    recinto2 = Recinto(nombre="Palau Sant Jordi", direccion="Barcelona, España",
                       aforo=18000, zonas={"Pista": 6000, "Grada": 12000})

    recinto3 = Recinto(nombre="Estadio Metropolitano", direccion="Madrid, España",
                       aforo=68000, zonas={"Pista": 15000, "Grada": 53000})

    recinto4 = Recinto(nombre="WiZink Hall", direccion="Valencia, España",
                       aforo=3000, zonas={"Pista": 1000, "Grada": 2000})

    recinto5 = Recinto(nombre="Coliseum A Coruna", direccion="A Coruña, España",
                       aforo=11000, zonas={"Pista": 4000, "Grada": 7000})

    recinto1.save()
    recinto2.save()
    recinto3.save()
    recinto4.save()
    recinto5.save()

    print("5 venues saved")


    evento1 = Evento(titulo="Bad Bunny Madrid 2026",
                     artistas=["Bad Bunny"], recinto="Movistar Arena",
                     fecha_y_hora="2026-12-15 21:00",
                     precio_por_zona={"Pista": 120, "Grada": 80})

    evento2 = Evento(titulo="Taylor Swift Barcelona 2025",
                     artistas=["Taylor Swift"], recinto="Palau Sant Jordi",
                     fecha_y_hora="2025-06-20 20:00",
                     precio_por_zona={"Pista": 150, "Grada": 100})

    evento3 = Evento(titulo="Rosalia Madrid 2027",
                     artistas=["Rosalia"], recinto="Estadio Metropolitano",
                     fecha_y_hora="2027-05-10 22:00",
                     precio_por_zona={"Pista": 100, "Grada": 70})

    evento4 = Evento(titulo="Drake Valencia 2024",
                     artistas=["Drake"], recinto="WiZink Hall",
                     fecha_y_hora="2024-09-12 21:30",
                     precio_por_zona={"Pista": 110, "Grada": 75})

    evento5 = Evento(titulo="Coldplay A Coruna 2026",
                     artistas=["Coldplay"], recinto="Coliseum A Coruna",
                     fecha_y_hora="2026-08-25 20:30",
                     precio_por_zona={"Pista": 130, "Grada": 90})

    evento1.save()
    evento2.save()
    evento3.save()
    evento4.save()
    evento5.save()

    print("5 events saved")


    asistente1 = Asistente(nombre="Carlos Garcia",
                          correo_electronico="carlos@example.com",
                          direccion="Madrid, España")

    asistente2 = Asistente(nombre="Lucia Fernandez",
                          correo_electronico="lucia@example.com",
                          direccion="Barcelona, España")

    asistente3 = Asistente(nombre="Pablo Martinez",
                          correo_electronico="pablo@example.com",
                          direccion="Valencia, España")

    asistente4 = Asistente(nombre="Ana Lopez",
                          correo_electronico="ana@example.com",
                          direccion="Sevilla, España")

    asistente5 = Asistente(nombre="David Rodriguez",
                          correo_electronico="david@example.com",
                          direccion="A Coruña, España")

    asistente1.save()
    asistente2.save()
    asistente3.save()
    asistente4.save()
    asistente5.save()

    print("5 attendees saved")



    print("\nTESTING ODM")

    print("\nTEST 1: Find")

    artists = list(Artista.find({"nombre": "Bad Bunny"}))

    assert len(artists) == 1
    print("Find Passed")

    print("\nTEST 2: Update")

    print("Before:", artista1.pais_de_origen)

    artista1.pais_de_origen = "España"
    artista1.save()

    updated = list(Artista.find({"nombre": "Bad Bunny"}))[0]

    assert updated.pais_de_origen == "España"

    print("After:", updated.pais_de_origen)
    print("Update Passed")

    artista1.pais_de_origen = "Puerto Rico"
    artista1.save()

    print("\nTEST 3: Delete")

    temporary = Artista(nombre="Temporary Artist", generos=["Pop"])
    temporary.save()

    print("Before delete:",
          len(list(Artista.find({"nombre": "Temporary Artist"}))))

    temporary.delete()

    print("After delete:",
          len(list(Artista.find({"nombre": "Temporary Artist"}))))

    assert len(list(Artista.find({"nombre": "Temporary Artist"}))) == 0

    print("Delete Passed")


    print("\nTEST 4: Geolocation")

    venue = list(Recinto.find({"nombre": "Movistar Arena"}))[0]

    assert "direccion_loc" in venue._data

    print("Geolocation Passed")


    print("\nFINAL RESULTS")

    print("Artists:", len(list(Artista.find({}))))
    print("Venues:", len(list(Recinto.find({}))))
    print("Events:", len(list(Evento.find({}))))
    print("Attendees:", len(list(Asistente.find({}))))

    print("\nAll tests passed")