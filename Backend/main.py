# Componente: Persistencia de datos
import asyncio
from datetime import date, datetime
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    APSCHEDULER_AVAILABLE = True
except Exception:
    AsyncIOScheduler = None
    APSCHEDULER_AVAILABLE = False
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import create_engine, between, or_, func, desc
from sqlalchemy.orm import Session, sessionmaker, selectinload
from schemas import (
    PacienteBase, PacienteCreate, PacienteResponse,
    RazaBase, RazaCreate, RazaResponse,
    EspecieBase, EspecieCreate, EspecieResponse,
    TutorBase, TutorCreate, TutorPacienteResponse, TutorResponse,
    TutorPacienteBase,
    TratamientoBase, TratamientoCreate, TratamientoResponse,
    consultaTratamientoBase, consultaTratamientoCreate, consultaTratamientoResponse,
    ConsultaBase, ConsultaCreate, ConsultaResponse, EmailSchema,
    EventCreate, consultaTratamientoConDetallesResponse
)
from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel
from database import Base, engine
import models # Donde están las tablas de la base de datos
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Annotated, Optional
from database import engine, SessionLocal
from dotenv import load_dotenv
import os
import json
from prefix_middleware import StripAPIPrefixMiddleware
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType 
from starlette.responses import JSONResponse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google_auth_oauthlib.flow import InstalledAppFlow
from google_auth_oauthlib.flow import Flow

# Para generar pdf
from services.pdf_service import generar_pdf_consulta
from fastapi.responses import Response

# Para comunicar con microservicio whatsapp 
from routers.whatsapp import router as whatsapp_router

# Para Oauth
from auth import get_current_user
from session_auth import router as session_auth_router, get_current_session_user

# Cargar variables de entorno desde el archivo .env
load_dotenv()

app = FastAPI()
#SCOPES = ["https://www.googleapis.com/auth/calendar"]
#CLIENT_SECRETS_FILE = "credentials.json"

# Configuración de Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

app.add_middleware(StripAPIPrefixMiddleware)


# CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

# Incluir routers
from routers import whatsapp
app.include_router(whatsapp.router)

models.Base.metadata.create_all(bind=engine) # Crear tablas en la base de datos

# Crear una sesión para cada solicitud
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

# Función helper para normalizar texto de búsqueda
def normalize_search_text(text: str) -> str:
    """
    Normaliza el texto de búsqueda eliminando puntos, guiones y espacios extras.
    Útil para búsquedas de RUT, nombres completos, etc.
    """
    if not text:
        return ""
    # Eliminar puntos y guiones
    normalized = text.replace(".", "").replace("-", "")
    # Reemplazar múltiples espacios por uno solo
    normalized = " ".join(normalized.split())
    return normalized.strip()

# Función helper para convertir paciente ORM a PacienteResponse
def paciente_to_response(db_paciente: models.Paciente, db: Session) -> PacienteResponse:
    """
    Convierte un objeto Paciente ORM a PacienteResponse.
    Carga explícitamente los nombres de raza y especie como strings.
    Incluye información del tutor si existe.
    """
    # Cargar los nombres de la raza y especie
    raza_obj = db.query(models.Raza).filter(models.Raza.id_raza == db_paciente.id_raza).first()
    especie_obj = None
    if raza_obj:
        especie_obj = db.query(models.Especie).filter(models.Especie.id_especie == raza_obj.id_especie).first()
    
    # Obtener el tutor del paciente
    tutor_data = None
    tutor_paciente = db.query(models.TutorPaciente).filter(
        models.TutorPaciente.id_paciente == db_paciente.id_paciente
    ).first()
    
    if tutor_paciente:
        tutor_obj = db.query(models.Tutor).filter(
            models.Tutor.rut == tutor_paciente.rut
        ).first()
        
        if tutor_obj:
            tutor_data = TutorResponse(
                rut=tutor_obj.rut,
                nombre=tutor_obj.nombre,
                apellido_paterno=tutor_obj.apellido_paterno,
                apellido_materno=tutor_obj.apellido_materno,
                celular=tutor_obj.celular,
                celular2=tutor_obj.celular2,
                comuna=tutor_obj.comuna,
                region=tutor_obj.region,
                observacion=tutor_obj.observacion,
                telefono=tutor_obj.telefono,
                telefono2=tutor_obj.telefono2,
                direccion=tutor_obj.direccion,
                email=tutor_obj.email
            )
    
    # Construir la respuesta con los nombres como strings explícitos
    return PacienteResponse(
        id_paciente=db_paciente.id_paciente,
        nombre=db_paciente.nombre,
        color=db_paciente.color,
        sexo=db_paciente.sexo,
        esterilizado=db_paciente.esterilizado,
        fecha_nacimiento=db_paciente.fecha_nacimiento,
        id_raza=db_paciente.id_raza,
        codigo_chip=db_paciente.codigo_chip,
        raza=str(raza_obj.nombre) if raza_obj else None,
        especie=str(especie_obj.nombre_comun) if especie_obj else None,
        tutor=tutor_data
    )


# HU1: Como Veterinaria quiero ver el calendario con los horarios de atención disponibles, para organizarme con la agenda de horas

def get_calendar_service():
    """
    Crea y retorna el servicio de Google Calendar usando Service Account.
    No requiere interacción del usuario.
    """
    try:
        # Obtener credenciales desde variable de entorno
        service_account_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY"))
        
        # Crear credenciales
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=SCOPES
        )
        
        # Crear servicio
        service = build('calendar', 'v3', credentials=credentials)
        return service
    
    except Exception as e:
        print(f"Error al crear servicio de calendario: {e}")
        raise HTTPException(status_code=500, detail="Error de configuración del calendario")
    
@app.get("/events")
def list_events(max_results: int = 10, current_user: dict = Depends(get_current_session_user)):
    """Obtiene los próximos N eventos."""
    try:
        service = get_calendar_service()
        now = datetime.now(timezone.utc).isoformat()
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return {"events": events_result.get('items', [])}
    
    except HttpError as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/events/day")
def get_events_day(date: str, current_user: dict = Depends(get_current_session_user)):
    """
    Obtiene eventos de un día específico.
    
    Args:
        date: Fecha en formato YYYY-MM-DD (ej: 2025-11-10)
    """
    try:
        service = get_calendar_service()
        
        # Parsear fecha
        target_date = datetime.fromisoformat(date)
        
        # Inicio del día (00:00:00)
        start_of_day = target_date.replace(
            hour=0, minute=0, second=0, microsecond=0,
            tzinfo=timezone.utc
        )
        
        # Fin del día (23:59:59)
        end_of_day = start_of_day + timedelta(days=1) - timedelta(seconds=1)
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return {"events": events_result.get('items', [])}
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
    except HttpError as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/events/week")
def get_events_week(start_date: str, end_date: str, current_user: dict = Depends(get_current_session_user)):
    """
    Obtiene eventos de una semana (7 días) desde la fecha indicada.
    
    Args:
        start_date: Fecha de inicio en formato YYYY-MM-DD
        end_date: Fecha de fin en formato YYYY-MM-DD
    """
    try:
        service = get_calendar_service()
        
        # Parsear fecha
        target_date = datetime.fromisoformat(start_date)
        
        # Inicio de la semana
        start_of_week = target_date.replace(
            hour=0, minute=0, second=0, microsecond=0,
            tzinfo=timezone.utc
        )
        # Fin de la semana
        end_of_week = datetime.fromisoformat(end_date).replace(
            hour=23, minute=59, second=59, microsecond=999999,
            tzinfo=timezone.utc
        )
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_of_week.isoformat(),
            timeMax=end_of_week.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return {"events": events_result.get('items', [])}
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido")
    except HttpError as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/events/month")
def get_events_month(year: int, month: int, current_user: dict = Depends(get_current_session_user)):
    """
    Obtiene eventos de un mes específico.
    
    Args:
        year: Año (ej: 2025)
        month: Mes (1-12)
    """
    try:
        service = get_calendar_service()
        
        # Primer día del mes
        start_of_month = datetime(year, month, 1, tzinfo=timezone.utc)
        
        # Primer día del siguiente mes
        if month == 12:
            end_of_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_of_month = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_of_month.isoformat(),
            timeMax=end_of_month.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return {"events": events_result.get('items', [])}
    
    except HttpError as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/events")
def create_event(event: EventCreate, current_user: dict = Depends(get_current_session_user)):
    """Crea un nuevo evento en el calendario."""
    try:
        service = get_calendar_service()
        
        event_body = {
            'summary': event.summary,
            'description': event.description,
            'location': event.location,
            'start': {
                'dateTime': event.start,
                'timeZone': 'America/Santiago',
            },
            'end': {
                'dateTime': event.end,
                'timeZone': 'America/Santiago',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 60},
                ],
            },
            'attendees': event.attendees if event.attendees else [],
        }
        
        created_event = service.events().insert(
            calendarId=CALENDAR_ID,
            body=event_body
        ).execute()
        
        return {
            "message": "Evento creado exitosamente",
            "event": created_event
        }
    
    except HttpError as error:
        raise HTTPException(status_code=500, detail=str(error))
    
@app.delete("/events/{event_id}")
def delete_event(event_id: str, current_user: dict = Depends(get_current_session_user)):
    """
    Elimina un evento del calendario de Google.
    
    Args:
        event_id: ID del evento de Google Calendar
    """
    try:
        service = get_calendar_service()
        
        # Eliminar el evento
        service.events().delete(
            calendarId=CALENDAR_ID,
            eventId=event_id
        ).execute()
        
        return {
            "message": "Evento eliminado exitosamente",
            "event_id": event_id
        }
    
    except HttpError as error:
        # Si el evento no existe, Google retorna 404
        if error.resp.status == 410 or error.resp.status == 404:
            raise HTTPException(
                status_code=404,
                detail="Evento no encontrado o ya fue eliminado"
            )
        
        print(f"Error al eliminar evento: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar evento: {str(error)}"
        )
    
    except Exception as e:
        print(f"Error inesperado: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# HU 4: Como Veterinaria, quiero poder almacenar al tutor con su RUT y nombre, para poder tener su información para consultas futuras
""" RUTAS PARA TUTORES (dueños de mascotas) """

# Endpoint para obtener regiones - Datos locales SUBDERE
@app.get("/regiones/")
async def obtener_regiones():
    """
    Retorna regiones chilenas desde datos estáticos locales.
    Los datos provienen de SUBDERE (Subsecretaría de Desarrollo Regional y Administrativo).
    """
    from regiones_data import REGIONES_CHILE
    
    print(f"✅ Retornando {len(REGIONES_CHILE)} regiones desde datos locales")
    return REGIONES_CHILE

def obtener_numero_romano(codigo_region: str) -> str:
    """Convierte el código de región a número romano chileno"""
    numeros_romanos = {
        "15": "XV", "01": "I", "02": "II", "03": "III", "04": "IV",
        "05": "V", "06": "VI", "07": "VII", "08": "VIII", "09": "IX",
        "10": "X", "11": "XI", "12": "XII", "13": "RM", "14": "XIV", "16": "XVI"
    }
    return numeros_romanos.get(codigo_region, codigo_region)

# Ruta POST para añadir un dueño
@app.post("/tutores/", response_model=TutorResponse)
def crear_tutor(tutor: TutorCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_tutor = models.Tutor(**tutor.dict())
    db.add(db_tutor)
    db.commit()
    db.refresh(db_tutor)
    return db_tutor

# Ruta GET para obtener un dueño por su RUT
@app.get("/tutores/{rut}", response_model=TutorResponse)
def obtener_tutor(rut: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_tutor = db.query(models.Tutor).filter(
        models.Tutor.rut == rut,
        models.Tutor.activo == True
    ).first()
    if db_tutor is None:
        raise HTTPException(status_code=404, detail="Tutor no encontrado")
    return db_tutor

# Ruta GET para obtener todos los dueños
@app.get("/tutores/", response_model=List[TutorResponse])
def obtener_todos_los_tutores(db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_tutores = db.query(models.Tutor).filter(models.Tutor.activo == True).all()
    if not db_tutores:
        raise HTTPException(status_code=404, detail="No se encontraron tutores")
    return db_tutores

# HU16:
@app.get("/consultas/{id_consulta}/pdf", response_model=ConsultaResponse)
def descargar_pdf_consulta(id_consulta: int, db: Session = Depends(get_db)):
    pdf = generar_pdf_consulta(db, id_consulta)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ficha_consulta_{id_consulta}.pdf"'
        }
    )

# Ruta GET para obtener tutores con paginación
# Opción alternativa más corta
@app.get("/tutores/paginated/")
def obtener_tutores_paginados(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_session_user)
):
    offset = (page - 1) * limit
    query = db.query(models.Tutor).filter(models.Tutor.activo == True)
    
    if search:
        # Normalizar texto de búsqueda
        search_normalized = normalize_search_text(search)
        
        # Búsqueda flexible: permite buscar por nombre completo, RUT sin formato, etc.
        search_pattern = f"%{search_normalized}%"
        
        # Para RUT: buscar sin puntos ni guiones
        # Para nombres: concatenar nombre + apellidos y buscar en el texto completo
        query = query.filter(
            or_(
                # Búsqueda en nombre individual
                models.Tutor.nombre.ilike(f"%{search}%"),
                models.Tutor.apellido_paterno.ilike(f"%{search}%"),
                models.Tutor.apellido_materno.ilike(f"%{search}%"),
                models.Tutor.email.ilike(f"%{search}%"),
                # Búsqueda en nombre completo (permite "nicolas ortiz")
                func.concat(
                    models.Tutor.nombre, ' ',
                    models.Tutor.apellido_paterno, ' ',
                    models.Tutor.apellido_materno
                ).ilike(f"%{search}%"),
                # Búsqueda en RUT sin formato (permite buscar con o sin puntos/guiones)
                func.replace(
                    func.replace(models.Tutor.rut, '.', ''), '-', ''
                ).ilike(search_pattern)
            )
        )
    
    total_count = query.count()
    tutores_db = query.order_by(models.Tutor.rut).offset(offset).limit(limit).all()
    
    total_pages = (total_count + limit - 1) // limit
    has_next = page < total_pages
    has_previous = page > 1
    
    # Usar el esquema Pydantic para convertir cada objeto
    tutores_serializados = [TutorResponse.model_validate(tutor).model_dump() for tutor in tutores_db]
    
    return {
        "tutores": tutores_serializados,
        "pagination": {
            "current_page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "limit": limit,
            "has_next": has_next,
            "has_previous": has_previous,
            "next_page": page + 1 if has_next else None,
            "previous_page": page - 1 if has_previous else None
        }
    }

# Ruta para ver todas las mascotas de un tutor
@app.get("/tutores/{rut}/pacientes/", response_model=List[PacienteResponse])
def obtener_mascotas_de_tutor(rut: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_tutor = db.query(models.Tutor).filter(
        models.Tutor.rut == rut,
        models.Tutor.activo == True
    ).first()
    if not db_tutor:
        raise HTTPException(status_code=404, detail="Tutor no encontrado")
    db_pacientes = db.query(models.Paciente).join(models.TutorPaciente).filter(
        models.TutorPaciente.rut == rut,
        models.Paciente.activo == True
    ).all()
    return [paciente_to_response(p, db) for p in db_pacientes]

# HU 3: Como Veterinaria, quiero poder almacenar el paciente por su nombre y raza para indentificarlos y buscarlos facilmente
""" RUTAS PARA PACIENTES (mascotas) """
# Ruta POST para añadir un paciente
@app.post("/pacientes/", response_model=PacienteResponse)
def crear_paciente(paciente: PacienteCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_paciente = models.Paciente(**paciente.dict())
    db.add(db_paciente)
    db.commit()
    db.refresh(db_paciente)
    
    # Usar helper function para construir la respuesta
    return paciente_to_response(db_paciente, db)

# Ruta GET para obtener un paciente por su ID
@app.get("/pacientes/{id_paciente}", response_model=PacienteResponse)
def obtener_paciente(id_paciente: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_paciente = db.query(models.Paciente).filter(
        models.Paciente.id_paciente == id_paciente,
        models.Paciente.activo == True
    ).first()
    if db_paciente is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return paciente_to_response(db_paciente, db)

# Ruta GET para obtener pacientes por su nombre
@app.get("/pacientes/nombre/{nombre}", response_model=List[PacienteResponse])
def obtener_pacientes_por_nombre(nombre: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_pacientes = db.query(models.Paciente).filter(
        models.Paciente.nombre.ilike(f"%{nombre}%"),
        models.Paciente.activo == True
    ).all() # el ilike no diferencia mayusculas o minusculas asi facilitamos la busqueda al no ser tan estricta
    if not db_pacientes:
        raise HTTPException(status_code=404, detail="No se encontraron pacientes con ese nombre")
    return [paciente_to_response(p, db) for p in db_pacientes]

# Ruta GET para obtener pacientes por su raza (nombre de la raza)
@app.get("/pacientes/raza/{nombre_raza}", response_model=List[PacienteResponse])
def obtener_pacientes_por_raza(nombre_raza: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_pacientes = db.query(models.Paciente).join(models.Raza).filter(
        models.Raza.nombre.ilike(f"%{nombre_raza}%"),
        models.Paciente.activo == True
    ).all()
    if not db_pacientes:
        raise HTTPException(status_code=404, detail="No se encontraron pacientes con esa raza")
    return [paciente_to_response(p, db) for p in db_pacientes]

# Ruta GET para obtener todos los pacientes
@app.get("/pacientes/", response_model=List[PacienteResponse])
def obtener_todos_los_pacientes(db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_pacientes = db.query(models.Paciente).filter(models.Paciente.activo == True).all()
    if not db_pacientes:
        raise HTTPException(status_code=404, detail="No se encontraron pacientes")
    return [paciente_to_response(p, db) for p in db_pacientes]

# Rut GET para obtener todos los pacientes por rut de su tutor
@app.get("/pacientes/tutor/{rut}", response_model=List[PacienteResponse])
def obtener_pacientes_por_rut_tutor(rut: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    # Hacer JOIN con Raza y Especie para obtener esa información
    pacientes_query = db.query(
        models.Paciente,
        models.Raza.nombre.label('raza_nombre'),
        models.Especie.nombre_comun.label('especie_nombre')
    ).join(
        models.TutorPaciente, 
        models.Paciente.id_paciente == models.TutorPaciente.id_paciente
    ).join(
        models.Raza,
        models.Paciente.id_raza == models.Raza.id_raza,
        isouter=True
    ).join(
        models.Especie,
        models.Raza.id_especie == models.Especie.id_especie,
        isouter=True
    ).filter(
        models.TutorPaciente.rut == rut,
        models.Paciente.activo == True
    ).all()
    
    if not pacientes_query:
        raise HTTPException(status_code=404, detail="No se encontraron pacientes para ese tutor")
    
    # Convertir resultados a la estructura esperada
    resultado = []
    for paciente, raza_nombre, especie_nombre in pacientes_query:
        paciente_dict = {
            "id_paciente": paciente.id_paciente,
            "nombre": paciente.nombre,
            "color": paciente.color,
            "sexo": paciente.sexo,
            "esterilizado": paciente.esterilizado,
            "fecha_nacimiento": paciente.fecha_nacimiento,
            "id_raza": paciente.id_raza,
            "codigo_chip": paciente.codigo_chip,
            "raza": raza_nombre,
            "especie": especie_nombre
        }
        resultado.append(paciente_dict)
    
    return resultado

# Ruta GET para obtener pacientes con paginación y búsqueda avanzada
@app.get("/pacientes/paginated/")
def obtener_pacientes_paginados(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_session_user)
):
    offset = (page - 1) * limit
    
    # Query con joins para obtener información relacionada
    query = db.query(
        models.Paciente,
        models.Raza.nombre.label('raza_nombre'),
        models.Especie.nombre_comun.label('especie_nombre'),
        models.Tutor.nombre.label('tutor_nombre'),
        models.Tutor.apellido_paterno.label('tutor_apellido_paterno'),
        models.Tutor.apellido_materno.label('tutor_apellido_materno'),
        models.Tutor.rut.label('tutor_rut'),
        models.Tutor.telefono.label('tutor_telefono'),
        models.Tutor.email.label('tutor_email')
    ).join(
        models.Raza, models.Paciente.id_raza == models.Raza.id_raza, isouter=True
    ).join(
        models.Especie, models.Raza.id_especie == models.Especie.id_especie, isouter=True
    ).join(
        models.TutorPaciente, models.Paciente.id_paciente == models.TutorPaciente.id_paciente, isouter=True
    ).join(
        models.Tutor, models.TutorPaciente.rut == models.Tutor.rut, isouter=True
    ).filter(
        models.Paciente.activo == True
    )
    
    if search:
        # Normalizar texto de búsqueda
        search_normalized = normalize_search_text(search)
        search_pattern = f"%{search_normalized}%"
        
        query = query.filter(
            or_(
                # Búsqueda en nombre del paciente
                models.Paciente.nombre.ilike(f"%{search}%"),
                # Búsqueda en raza y especie
                models.Raza.nombre.ilike(f"%{search}%"),
                models.Especie.nombre_comun.ilike(f"%{search}%"),
                # Búsqueda en nombre del tutor (individual)
                models.Tutor.nombre.ilike(f"%{search}%"),
                models.Tutor.apellido_paterno.ilike(f"%{search}%"),
                # Búsqueda en nombre completo del tutor
                func.concat(
                    models.Tutor.nombre, ' ',
                    models.Tutor.apellido_paterno, ' ',
                    models.Tutor.apellido_materno
                ).ilike(f"%{search}%"),
                # Búsqueda en RUT del tutor sin formato
                func.replace(
                    func.replace(models.Tutor.rut, '.', ''), '-', ''
                ).ilike(search_pattern)
            )
        )
    
    # Contar total sin aplicar offset/limit
    total_count = query.count()
    
    # Aplicar paginación y obtener resultados
    results = query.order_by(models.Paciente.id_paciente).offset(offset).limit(limit).all()
    
    total_pages = (total_count + limit - 1) // limit
    has_next = page < total_pages
    has_previous = page > 1
    
    # Construir respuesta personalizada con información completa
    pacientes_serializados = []
    for result in results:
        paciente = result[0]  # El objeto Paciente
        
        # Construir el diccionario con información completa
        paciente_dict = {
            "id_paciente": paciente.id_paciente,
            "nombre": paciente.nombre,
            "fecha_nacimiento": paciente.fecha_nacimiento.isoformat() if paciente.fecha_nacimiento else None,
            "color": paciente.color,
            "sexo": paciente.sexo,
            "esterilizado": paciente.esterilizado,
            "id_raza": paciente.id_raza,
            # Información de la raza
            "raza": result.raza_nombre if result.raza_nombre else None,
            # Información de la especie
            "especie": result.especie_nombre if result.especie_nombre else None,
            # Información del tutor
            "tutor": {
                "nombre": result.tutor_nombre if result.tutor_nombre else None,
                "apellido_paterno": result.tutor_apellido_paterno if result.tutor_apellido_paterno else None,
                "apellido_materno": result.tutor_apellido_materno if result.tutor_apellido_materno else None,
                "rut": result.tutor_rut if result.tutor_rut else None,
                "telefono": result.tutor_telefono if result.tutor_telefono else None,
                "email": result.tutor_email if result.tutor_email else None
            } if result.tutor_nombre else None
        }
        
        pacientes_serializados.append(paciente_dict)

    return {
        "pacientes": pacientes_serializados,
        "pagination": {
            "current_page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "limit": limit,
            "has_next": has_next,
            "has_previous": has_previous,
            "next_page": page + 1 if has_next else None,
            "previous_page": page - 1 if has_previous else None
        }
    }

# HU 5: Como veterinaria quiero poder modificar la información de una mascota registrada, para tratar con casos donde se necesite corregir alguna información hasta cambiar de dueño.

# Ruta PUT para actualizar la información de un paciente
@app.put("/pacientes/{id_paciente}", response_model=PacienteResponse)
def actualizar_paciente(id_paciente: int, paciente: PacienteCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_paciente = db.query(models.Paciente).filter(models.Paciente.id_paciente == id_paciente).first()
    if not db_paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    for key, value in paciente.dict().items():
        setattr(db_paciente, key, value)
    db.commit()
    db.refresh(db_paciente)

    return {
        "id_paciente": db_paciente.id_paciente,
        "nombre": db_paciente.nombre,
        "color": db_paciente.color,
        "sexo": db_paciente.sexo,
        "esterilizado": db_paciente.esterilizado,
        "fecha_nacimiento": db_paciente.fecha_nacimiento,
        "raza": db_paciente.raza.nombre,
        "id_raza": db_paciente.raza.id_raza,
        "codigo_chip": db_paciente.codigo_chip,
    }

# Ruta PUT para actualizar el tutor de un paciente
@app.put("/pacientes/{id_paciente}/tutor/{rut_tutor}", response_model=PacienteResponse)
def actualizar_tutor_paciente(id_paciente: int, rut_tutor: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_paciente = db.query(models.Paciente).filter(models.Paciente.id_paciente == id_paciente).first()
    db_tutor = db.query(models.Tutor).filter(
        models.Tutor.rut == rut_tutor,
        models.Tutor.activo == True
    ).first()
    if not db_paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    if not db_tutor:
        raise HTTPException(status_code=404, detail="Tutor no encontrado")
    # Actualizar la asociación en la tabla TutorPaciente
    db_tutor_paciente = db.query(models.TutorPaciente).filter(models.TutorPaciente.id_paciente == id_paciente).first()
    if db_tutor_paciente:
        db_tutor_paciente.rut = rut_tutor
    else:
        db_tutor_paciente = models.TutorPaciente(rut=rut_tutor, id_paciente=id_paciente, fecha=date.today())
        db.add(db_tutor_paciente)
    db.commit()
    return {
        "id_paciente": db_paciente.id_paciente,
        "nombre": db_paciente.nombre,
        "color": db_paciente.color,
        "sexo": db_paciente.sexo,
        "esterilizado": db_paciente.esterilizado,
        "fecha_nacimiento": db_paciente.fecha_nacimiento,
        "raza": db_paciente.raza.nombre,
        "id_raza": db_paciente.raza.id_raza,
        "codigo_chip": db_paciente.codigo_chip,
    }

# Ruta DELETE para eliminar tutor SOLO sin pacientes
@app.delete("/tutores/{rut}")
def eliminar_tutor(rut: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_tutor = db.query(models.Tutor).filter(models.Tutor.rut == rut).first()
    if db_tutor:
        db.delete(db_tutor)
        db.commit()
    return {"message": "Tutor eliminado"}

""" RUTAS PARA ASOCIAR TUTORES Y PACIENTES """
# Ruta PUT para editar la asociación tutor_paciente
@app.put("/tutores/{rut_tutor}/pacientes/{id_paciente}", response_model=TutorPacienteResponse)
def editar_asociacion_tutor_paciente(rut_tutor: str, id_paciente: int, fecha: date, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_tutor_paciente = db.query(models.TutorPaciente).filter(
        models.TutorPaciente.rut == rut_tutor,
        models.TutorPaciente.id_paciente == id_paciente
    ).first()
    if not db_tutor_paciente:
        raise HTTPException(status_code=404, detail="Asociación tutor-paciente no encontrada")
    db_tutor_paciente.fecha = fecha
    db.commit()
    db.refresh(db_tutor_paciente)
    

# ruta put para editar la informacion de un tutor
@app.put("/tutores/{rut}", response_model=TutorResponse)
def editar_tutor(rut: str, tutor: TutorCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_tutor = db.query(models.Tutor).filter(
        models.Tutor.rut == rut,
        models.Tutor.activo == True
    ).first()
    if not db_tutor:
        raise HTTPException(status_code=404, detail="Tutor no encontrado")
    for key, value in tutor.dict().items():
        setattr(db_tutor, key, value)
    db.commit()
    db.refresh(db_tutor)
    return db_tutor

# Ruta POST para asociar un tutor a un paciente (tutor_paciente)
@app.post("/tutores/{rut_tutor}/pacientes/{id_paciente}", response_model=TutorPacienteResponse)
def asociar_tutor_a_paciente(rut_tutor: str, id_paciente: int, fecha: date, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_tutor = db.query(models.Tutor).filter(
        models.Tutor.rut == rut_tutor,
        models.Tutor.activo == True
    ).first()
    db_paciente = db.query(models.Paciente).filter(models.Paciente.id_paciente == id_paciente).first()
    if not db_tutor:
        raise HTTPException(status_code=404, detail="Tutor no encontrado")
    if not db_paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    db_tutor_paciente = models.TutorPaciente(rut=rut_tutor, id_paciente=id_paciente, fecha=fecha)
    db.add(db_tutor_paciente)
    db.commit()
    db.refresh(db_tutor_paciente)
    return db_tutor_paciente

# Ruta para ver mascotas asociadas a un tutor
@app.get("/tutores/{rut}/pacientes/", response_model=List[PacienteResponse])
def obtener_mascotas_por_tutor(rut: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_tutor = db.query(models.Tutor).filter(
        models.Tutor.rut == rut,
        models.Tutor.activo == True
    ).first()
    if not db_tutor:
        raise HTTPException(status_code=404, detail="Tutor no encontrado")
    db_mascotas = db.query(models.Paciente).join(models.TutorPaciente).filter(
        models.TutorPaciente.rut == rut,
        models.Paciente.activo == True
    ).all()
    if not db_mascotas:
        raise HTTPException(status_code=404, detail="No se encontraron mascotas para ese tutor")
    return db_mascotas

""" RUTAS PARA RAZAS """
# Ruta POST para añadir una raza
@app.post("/razas/", response_model=RazaResponse)
def crear_raza(raza: RazaCreate, db: Session = Depends(get_db)):
    db_raza = models.Raza(**raza.dict())
    db.add(db_raza)
    db.commit()
    db.refresh(db_raza)
    return db_raza

# Ruta GET para obtener una raza por su nombre
@app.get("/razas/nombre/{nombre}", response_model=List[RazaResponse])
def obtener_razas_por_nombre(nombre: str, db: Session = Depends(get_db)):
    db_razas = db.query(models.Raza).filter(models.Raza.nombre.ilike(f"%{nombre}%")).all()
    if not db_razas:
        raise HTTPException(status_code=404, detail="No se encontraron razas con ese nombre")
    return db_razas

# Ruta GET para obtener todas las razas
@app.get("/razas/", response_model=List[RazaResponse])  
def obtener_todas_las_razas(db: Session = Depends(get_db)):
    db_razas = db.query(models.Raza).all()
    if not db_razas:
        raise HTTPException(status_code=404, detail="No se encontraron razas")
    return db_razas

# Ruta GET para obtener todas las razas mediante el nombre común de la especie
@app.get("/razas/especie/{nombre_especie}", response_model=List[RazaResponse])
def obtener_razas_por_especie(nombre_especie: str, db: Session = Depends(get_db)):
    db_razas = db.query(models.Raza).join(models.Especie).filter(models.Especie.nombre_comun.ilike(f"%{nombre_especie}%")).all()
    if not db_razas:
        raise HTTPException(status_code=404, detail="No se encontraron razas para esa especie")
    return db_razas

""" RUTAS PARA ESPECIE """
# Ruta POST para añadir una especie
@app.post("/especies/", response_model=EspecieResponse)
def crear_especie(especie: EspecieCreate, db: Session = Depends(get_db)):
    db_especie = models.Especie(**especie.dict())
    db.add(db_especie)
    db.commit()
    db.refresh(db_especie)
    return db_especie

# Ruta GET para obtener una especie por su nombre común o científico
@app.get("/especies/nombre/{nombre}", response_model=List[EspecieResponse])
def obtener_especies_por_nombre(nombre: str, db: Session = Depends(get_db)):
    db_especies = db.query(models.Especie).filter(
        or_(
            models.Especie.nombre_cientifico.ilike(f"%{nombre}%"),
            models.Especie.nombre_comun.ilike(f"%{nombre}%")
        )
    ).all()
    if not db_especies:
        raise HTTPException(status_code=404, detail="No se encontraron especies con ese nombre")
    return db_especies

# Ruta GET para obtener todas las especies
@app.get("/especies/", response_model=List[EspecieResponse])
def obtener_todas_las_especies(db: Session = Depends(get_db)):
    db_especies = db.query(models.Especie).all()
    if not db_especies:
        raise HTTPException(status_code=404, detail="No se encontraron especies")
    return db_especies

# HU 7: Como veterinaria quiero buscar pacientes, tutores y fichas con su información 
# clave para recuperar información importante de forma flexible y rápida
""" RUTAS PARA FICHAS DE PACIENTES (CONSULTAS) """
# Ruta POST para añadir una consulta
@app.post("/consultas/", response_model=ConsultaResponse)
def crear_consulta(consulta: ConsultaCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_consulta = models.Consulta(**consulta.dict())
    db.add(db_consulta)
    db.commit()
    db.refresh(db_consulta)
    return db_consulta

# Ruta PUT para actualizar una consulta existente
@app.put("/consultas/{id_consulta}", response_model=ConsultaResponse)
def actualizar_consulta(
    id_consulta: int, 
    consulta: ConsultaCreate, 
    db: Session = Depends(get_db), 
    current_user: dict = Depends(get_current_session_user)
):
    # Buscar la consulta existente
    db_consulta = db.query(models.Consulta).filter(
        models.Consulta.id_consulta == id_consulta
    ).first()
    
    if not db_consulta:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    
    # Actualizar los campos de la consulta
    for key, value in consulta.dict(exclude_unset=True).items():
        setattr(db_consulta, key, value)
    
    db.commit()
    db.refresh(db_consulta)
    
    # Cargar relaciones para la respuesta
    db_consulta = db.query(models.Consulta)\
        .options(selectinload(models.Consulta.recetas))\
        .options(selectinload(models.Consulta.tratamientos).selectinload(models.ConsultaTratamiento.tratamiento))\
        .filter(models.Consulta.id_consulta == id_consulta).first()
    
    return ConsultaResponse.from_orm_with_tratamientos(db_consulta)

# Ruta GET para obtener una consulta por su ID
@app.get("/consultas/{id_consulta}", response_model=ConsultaResponse)
def obtener_consulta_por_id(id_consulta: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_consulta = db.query(models.Consulta)\
        .options(selectinload(models.Consulta.recetas))\
        .options(selectinload(models.Consulta.tratamientos).selectinload(models.ConsultaTratamiento.tratamiento))\
        .filter(models.Consulta.id_consulta == id_consulta).first()
    if not db_consulta:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    return ConsultaResponse.from_orm_with_tratamientos(db_consulta)

# Ruta GET para obtener todas las consultas
@app.get("/consultas/", response_model=List[ConsultaResponse])
def obtener_todas_las_consultas(db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    db_consultas = db.query(models.Consulta)\
        .options(selectinload(models.Consulta.recetas))\
        .options(selectinload(models.Consulta.tratamientos).selectinload(models.ConsultaTratamiento.tratamiento))\
        .order_by(desc(models.Consulta.fecha_consulta)).all()
    if not db_consultas:
        raise HTTPException(status_code=404, detail="No se encontraron consultas")
    return [ConsultaResponse.from_orm_with_tratamientos(c) for c in db_consultas]

# Ruta GET para obtener consultas por ID de paciente
@app.get("/consultas/paciente/id/{id_paciente}", response_model=List[ConsultaResponse])
def obtener_consultas_por_id_paciente(id_paciente: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    # Verificar que el paciente existe
    db_paciente = db.query(models.Paciente).filter(models.Paciente.id_paciente == id_paciente).first()
    if not db_paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    
    # Obtener todas las consultas del paciente ordenadas por fecha más reciente
    db_consultas = db.query(models.Consulta)\
        .options(selectinload(models.Consulta.recetas))\
        .options(selectinload(models.Consulta.tratamientos).selectinload(models.ConsultaTratamiento.tratamiento))\
        .filter(models.Consulta.id_paciente == id_paciente)\
        .order_by(desc(models.Consulta.fecha_consulta)).all()
    
    if not db_consultas:
        raise HTTPException(status_code=404, detail="No se encontraron consultas para ese paciente")
    
    return [ConsultaResponse.from_orm_with_tratamientos(c) for c in db_consultas]

# Ruta GET para obtener consultas por nombre de paciente
@app.get("/consultas/paciente/{nombre_paciente}", response_model=List[ConsultaResponse])
def obtener_consultas_por_nombre_paciente(nombre_paciente: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    # Normalizar búsqueda para mayor flexibilidad
    db_consultas = db.query(models.Consulta)\
        .options(selectinload(models.Consulta.recetas))\
        .options(selectinload(models.Consulta.tratamientos).selectinload(models.ConsultaTratamiento.tratamiento))\
        .join(models.Paciente).filter(
        models.Paciente.nombre.ilike(f"%{nombre_paciente}%")
    ).order_by(desc(models.Consulta.fecha_consulta)).all()
    if not db_consultas:
        raise HTTPException(status_code=404, detail="No se encontraron consultas para ese paciente")
    return [ConsultaResponse.from_orm_with_tratamientos(c) for c in db_consultas]

@app.get("/consultas/paginated/")
def obtener_consultas_paginadas(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_session_user)
):
    offset = (page - 1) * limit
    
    # Query con joins para obtener información relacionada
    # IMPORTANTE: Agregar selectinload para recetas y tratamientos
    query = db.query(
        models.Consulta,
        models.Paciente.nombre.label('paciente_nombre'),
        models.Paciente.color.label('paciente_color'),
        models.Paciente.sexo.label('paciente_sexo'),
        models.Paciente.fecha_nacimiento.label('paciente_fecha_nacimiento'),
        models.Paciente.codigo_chip.label('paciente_codigo_chip'),
        models.Raza.nombre.label('raza_nombre'),
        models.Especie.nombre_comun.label('especie_nombre'),
        models.Tutor.nombre.label('tutor_nombre'),
        models.Tutor.apellido_paterno.label('tutor_apellido_paterno'),
        models.Tutor.apellido_materno.label('tutor_apellido_materno'),
        models.Tutor.rut.label('tutor_rut'),
        models.Tutor.telefono.label('tutor_telefono'),
        models.Tutor.email.label('tutor_email')
    ).options(
        selectinload(models.Consulta.recetas),
        selectinload(models.Consulta.tratamientos).selectinload(models.ConsultaTratamiento.tratamiento)
    ).join(
        models.Paciente, models.Consulta.id_paciente == models.Paciente.id_paciente, isouter=True
    ).join(
        models.Raza, models.Paciente.id_raza == models.Raza.id_raza, isouter=True
    ).join(
        models.Especie, models.Raza.id_especie == models.Especie.id_especie, isouter=True
    ).join(
        models.Tutor, models.Consulta.rut == models.Tutor.rut, isouter=True
    )
    
    if search:
        # Normalizar texto de búsqueda
        search_normalized = normalize_search_text(search)
        search_pattern_normalized = f"%{search_normalized}%"
        
        query = query.filter(
            or_(
                # Búsqueda en datos de la consulta
                models.Consulta.diagnostico.ilike(f"%{search}%"),
                models.Consulta.motivo.ilike(f"%{search}%"),
                models.Consulta.observaciones.ilike(f"%{search}%"),
                # Búsqueda en datos del paciente
                models.Paciente.nombre.ilike(f"%{search}%"),
                models.Paciente.codigo_chip.ilike(f"%{search}%"),
                # Búsqueda en raza y especie
                models.Raza.nombre.ilike(f"%{search}%"),
                models.Especie.nombre_comun.ilike(f"%{search}%"),
                # Búsqueda en datos del tutor (individual y completo)
                models.Tutor.nombre.ilike(f"%{search}%"),
                models.Tutor.apellido_paterno.ilike(f"%{search}%"),
                func.concat(
                    models.Tutor.nombre, ' ',
                    models.Tutor.apellido_paterno, ' ',
                    models.Tutor.apellido_materno
                ).ilike(f"%{search}%"),
                # Búsqueda en RUT sin formato
                func.replace(
                    func.replace(models.Tutor.rut, '.', ''), '-', ''
                ).ilike(search_pattern_normalized)
            )
        )
    
    # Contar total sin aplicar offset/limit
    total_count = query.count()
    
    # Aplicar ordenamiento según el parámetro sort_order
    if sort_order == "asc":
        query = query.order_by(models.Consulta.fecha_consulta.asc())
    else:  # desc por defecto
        query = query.order_by(desc(models.Consulta.fecha_consulta))
    
    # Aplicar paginación y obtener resultados
    results = query.offset(offset).limit(limit).all()
    
    total_pages = (total_count + limit - 1) // limit
    has_next = page < total_pages
    has_previous = page > 1
    
    # Construir respuesta personalizada con información completa
    consultas_serializadas = []
    for result in results:
        consulta = result[0]  # El objeto Consulta
        
        # Construir el diccionario con información completa
        consulta_dict = {
            # Información de la consulta
            "id_consulta": consulta.id_consulta,
            "id_paciente": consulta.id_paciente,
            "rut": consulta.rut,
            "fecha_consulta": consulta.fecha_consulta.isoformat() if consulta.fecha_consulta else None,
            "motivo": consulta.motivo,
            "motivo_consulta": consulta.motivo,  # Alias para compatibilidad
            
            # Constantes vitales
            "peso": consulta.peso,
            "temperatura": consulta.temperatura,
            "frecuencia_cardiaca": consulta.frecuencia_cardiaca,
            "frecuencia_respiratoria": consulta.frecuencia_respiratoria,
            "tllc": consulta.tllc,
            "dht": consulta.dht,
            
            # Examen físico
            "mucosas": consulta.mucosas,
            "condicion_corporal": consulta.condicion_corporal,
            "estado_pelaje": consulta.estado_pelaje,
            "estado_piel": consulta.estado_piel,
            "nodulos_linfaticos": consulta.nodulos_linfaticos,
            "auscultacion_cardiaca_toraxica": consulta.auscultacion_cardiaca_toraxica,
            "examen_clinico": consulta.examen_clinico,
            
            # Diagnóstico
            "prediagnostico": consulta.prediagnostico,
            "diagnostico": consulta.diagnostico,
            "pronostico": consulta.pronostico,
            "observaciones": consulta.observaciones,
            
            # Plan
            "indicaciones_generales": consulta.indicaciones_generales,
            
            # Recetas médicas
            "recetas": [
                {
                    "id_receta": r.id_receta,
                    "medicamento": r.medicamento,
                    "dosis": r.dosis,
                    "frecuencia": r.frecuencia,
                    "duracion": r.duracion,
                    "numero_serie": r.numero_serie
                } for r in consulta.recetas
            ] if consulta.recetas else [],
            
            # Tratamientos aplicados (vacunas, antiparasitarios)
            "tratamientos": [
                {
                    "fecha_tratamiento": ct.fecha_tratamiento.isoformat() if ct.fecha_tratamiento else None,
                    "dosis": ct.dosis,
                    "marca": ct.marca,
                    "numero_serial": ct.numero_serial,
                    "proxima_dosis": ct.proxima_dosis.isoformat() if ct.proxima_dosis else None,
                    "nombre_tratamiento": ct.tratamiento.nombre if ct.tratamiento else "Tratamiento",
                    "tipo_tratamiento": ct.tratamiento.tipo_tratamiento if ct.tratamiento else None
                } for ct in consulta.tratamientos
            ] if consulta.tratamientos else [],
            
            # Información del paciente
            "paciente": {
                "id_paciente": consulta.id_paciente,
                "nombre": result.paciente_nombre if result.paciente_nombre else None,
                "color": result.paciente_color if result.paciente_color else None,
                "sexo": result.paciente_sexo if result.paciente_sexo else None,
                "fecha_nacimiento": result.paciente_fecha_nacimiento.isoformat() if result.paciente_fecha_nacimiento else None,
                "codigo_chip": result.paciente_codigo_chip if result.paciente_codigo_chip else None,
                "raza": result.raza_nombre if result.raza_nombre else None,
                "especie": result.especie_nombre if result.especie_nombre else None
            } if result.paciente_nombre else None,
            
            # Información del tutor
            "tutor": {
                "nombre": result.tutor_nombre if result.tutor_nombre else None,
                "apellido_paterno": result.tutor_apellido_paterno if result.tutor_apellido_paterno else None,
                "apellido_materno": result.tutor_apellido_materno if result.tutor_apellido_materno else None,
                "rut": result.tutor_rut if result.tutor_rut else None,
                "telefono": result.tutor_telefono if result.tutor_telefono else None,
                "email": result.tutor_email if result.tutor_email else None
            } if result.tutor_nombre else None
        }
        
        consultas_serializadas.append(consulta_dict)

    return {
        "consultas": consultas_serializadas,  # ← Cambio de "pacientes" a "consultas"
        "pagination": {
            "current_page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "limit": limit,
            "has_next": has_next,
            "has_previous": has_previous,
            "next_page": page + 1 if has_next else None,
            "previous_page": page - 1 if has_previous else None
        }
    }

# HU 8: Como Veterinaria quiero ver el detalle de los pacientes, 
# para saber su estado y cuándo es su proxima vacuna y/o cita
""" RUTAS PARA TRATAMIENTOS """
# Ruta POST para añadir un tratamiento
@app.post("/tratamientos/", response_model=TratamientoResponse)
def crear_tratamiento(tratamiento: TratamientoCreate, db: Session = Depends(get_db)):
    db_tratamiento = models.Tratamiento(**tratamiento.dict())
    db.add(db_tratamiento)
    db.commit()
    db.refresh(db_tratamiento)
    return db_tratamiento

# Ruta GET para obtener todos los tratamientos
@app.get("/tratamientos/", response_model=List[TratamientoResponse])
def obtener_todos_los_tratamientos(db: Session = Depends(get_db)):
    db_tratamientos = db.query(models.Tratamiento).all()
    if not db_tratamientos:
        raise HTTPException(status_code=404, detail="No se encontraron tratamientos")
    return db_tratamientos

# Ruta GET para obtener un tratamiento por su nombre
@app.get("/tratamientos/nombre/{nombre}", response_model=TratamientoResponse)
def obtener_tratamiento_por_nombre(nombre: str, db: Session = Depends(get_db)):
    db_tratamiento = db.query(models.Tratamiento).filter(models.Tratamiento.nombre.ilike(f"%{nombre}%")).first()
    if not db_tratamiento:
        raise HTTPException(status_code=404, detail="Tratamiento no encontrado")
    return db_tratamiento

# Ruta POST para consulta_tratamiento
@app.post("/consultas_tratamientos/", response_model=consultaTratamientoResponse)
def crear_consulta_tratamiento(consulta_tratamiento: consultaTratamientoBase, db: Session = Depends(get_db)):
    db_consulta_tratamiento = models.ConsultaTratamiento(**consulta_tratamiento.dict())
    db.add(db_consulta_tratamiento)
    db.commit()
    db.refresh(db_consulta_tratamiento)
    return db_consulta_tratamiento

# Ruta GET para obtener todos los registros de consulta_tratamiento
@app.get("/consultas_tratamientos/", response_model=List[consultaTratamientoResponse])
def obtener_todas_las_consultas_tratamiento(db: Session = Depends(get_db)):
    db_consultas_tratamiento = db.query(models.ConsultaTratamiento).order_by(desc(models.ConsultaTratamiento.fecha_tratamiento)).all()
    if not db_consultas_tratamiento:
        raise HTTPException(status_code=404, detail="No se encontraron tratamientos asociados a consultas")
    return db_consultas_tratamiento

# Ruta GET para obtener registros de consulta_tratamiento por nombre de paciente
@app.get("/consultas_tratamientos/paciente/{nombre_paciente}", response_model=List[consultaTratamientoResponse])
def obtener_consultas_tratamiento_por_nombre_paciente(nombre_paciente: str, db: Session = Depends(get_db)):
    db_consultas_tratamiento = db.query(models.ConsultaTratamiento).join(models.Paciente).filter(models.Paciente.nombre.ilike(f"%{nombre_paciente}%")).order_by(desc(models.ConsultaTratamiento.fecha_tratamiento)).all()
    if not db_consultas_tratamiento:
        raise HTTPException(status_code=404, detail="No se encontraron tratamientos para ese paciente")
    return db_consultas_tratamiento

# Ruta GET para obtener registros de consulta_tratamiento solo de vacunas con detalles
@app.get("/consultas/tratamientos/vacunas/nombre/", response_model=List[consultaTratamientoConDetallesResponse])
def obtener_vacunas_por_nombre(db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    # Filtrar próximas vacunas en los próximos 30 días (1 mes)
    fecha_actual = datetime.now().date()
    fecha_limite = fecha_actual + timedelta(days=30)
    
    db_vacunas = db.query(
        models.ConsultaTratamiento,
        models.Tratamiento.nombre.label('nombre_tratamiento'),
        models.Tratamiento.descripcion.label('descripcion_tratamiento'),
        models.Paciente.nombre.label('nombre_paciente')
    ).join(
        models.Tratamiento, 
        models.ConsultaTratamiento.id_tratamiento == models.Tratamiento.id_tratamiento
    ).join(
        models.Paciente,
        models.ConsultaTratamiento.id_paciente == models.Paciente.id_paciente,
        isouter=True
    ).filter(
        models.Tratamiento.nombre.ilike("%Vacuna%"),
        models.ConsultaTratamiento.proxima_dosis.isnot(None),
        models.ConsultaTratamiento.proxima_dosis >= fecha_actual,
        models.ConsultaTratamiento.proxima_dosis <= fecha_limite
    ).order_by(models.ConsultaTratamiento.proxima_dosis.asc()).limit(20).all()
    
    if not db_vacunas:
        raise HTTPException(status_code=404, detail="No se encontraron vacunas administradas")
    
    # Construir la respuesta usando el nuevo esquema
    return [
        consultaTratamientoConDetallesResponse(
            id_consulta=resultado[0].id_consulta,
            id_tratamiento=resultado[0].id_tratamiento,
            id_paciente=resultado[0].id_paciente,
            dosis=resultado[0].dosis,
            fecha_tratamiento=resultado[0].fecha_tratamiento,
            id_aplicacion=resultado[0].id_aplicacion,
            marca=resultado[0].marca,
            proxima_dosis=resultado[0].proxima_dosis,
            numero_serial=resultado[0].numero_serial,
            nombre_tratamiento=resultado.nombre_tratamiento,
            descripcion_tratamiento=resultado.descripcion_tratamiento,
            nombre_paciente=resultado.nombre_paciente
        ) for resultado in db_vacunas
    ]

# Ruta GET para obtener próximas vacunas por ID de paciente
@app.get("/consultas/tratamientos/vacunas/paciente/{id_paciente}/proximas/", response_model=List[consultaTratamientoConDetallesResponse])
def obtener_proximas_vacunas_por_paciente(id_paciente: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    # Verificar que el paciente existe
    db_paciente = db.query(models.Paciente).filter(models.Paciente.id_paciente == id_paciente).first()
    if not db_paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    
    # Obtener fecha actual para filtrar vacunas futuras
    fecha_actual = datetime.now().date()
    
    # Query para obtener vacunas próximas del paciente específico
    db_vacunas = db.query(
        models.ConsultaTratamiento,
        models.Tratamiento.nombre.label('nombre_tratamiento'),
        models.Tratamiento.descripcion.label('descripcion_tratamiento'),
        models.Paciente.nombre.label('nombre_paciente')
    ).join(
        models.Tratamiento, 
        models.ConsultaTratamiento.id_tratamiento == models.Tratamiento.id_tratamiento
    ).join(
        models.Paciente,
        models.ConsultaTratamiento.id_paciente == models.Paciente.id_paciente
    ).filter(
        models.Tratamiento.nombre.ilike("%Vacuna%"),  # Solo tratamientos que contengan "Vacuna"
        models.ConsultaTratamiento.id_paciente == id_paciente,  # Solo del paciente específico
        models.ConsultaTratamiento.fecha_tratamiento >= fecha_actual  # Solo fechas futuras o hoy
    ).order_by(models.ConsultaTratamiento.fecha_tratamiento.asc()).all()  # Ordenar por fecha más próxima
    
    if not db_vacunas:
        raise HTTPException(status_code=404, detail="No se encontraron próximas vacunas para este paciente")
    
    # Construir la respuesta usando el esquema
    return [
        consultaTratamientoConDetallesResponse(
            id_consulta=resultado[0].id_consulta,
            id_tratamiento=resultado[0].id_tratamiento,
            id_paciente=resultado[0].id_paciente,
            dosis=resultado[0].dosis,
            fecha_tratamiento=resultado[0].fecha_tratamiento,
            id_aplicacion=resultado[0].id_aplicacion,
            marca=resultado[0].marca,
            proxima_dosis=resultado[0].proxima_dosis,
            numero_serial=resultado[0].numero_serial,
            nombre_tratamiento=resultado.nombre_tratamiento,
            descripcion_tratamiento=resultado.descripcion_tratamiento,
            nombre_paciente=resultado.nombre_paciente
        ) for resultado in db_vacunas
    ]

""" RUTA PARA ENVIAR EMAILS A TUTORES """
conf = ConnectionConfig (
    MAIL_USERNAME = os.getenv("USER"),
    MAIL_PASSWORD = os.getenv("PASSWORD"),
    MAIL_FROM = os.getenv("USER_EMAIL"),
    MAIL_PORT = int(os.getenv("PORT")),
    MAIL_SERVER = os.getenv("SERVER"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME"),
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)
# Scheduler (APScheduler) - usar AsyncIOScheduler para integrarlo con FastAPI/uvicorn
if APSCHEDULER_AVAILABLE:
    scheduler = AsyncIOScheduler(timezone="UTC")


    @app.on_event("startup")
    async def start_scheduler():
        # arrancar el scheduler en el arranque de la app
        scheduler.start()


    @app.on_event("shutdown")
    async def shutdown_scheduler():
        # apagar el scheduler en el cierre de la app
        scheduler.shutdown(wait=False)
else:
    scheduler = None
    # Fallback simple: programar tareas usando asyncio.create_task + sleep
    async def _delayed_send(run_date: datetime, email: 'EmailSchema') -> None:
        try:
            now = datetime.utcnow()
            # if run_date is timezone-aware, convert to UTC naive for comparison
            if run_date.tzinfo is not None:
                run_date_utc = run_date.astimezone(tz=None).replace(tzinfo=None)
            else:
                run_date_utc = run_date
            delay = (run_date_utc - now).total_seconds()
            if delay > 0:
                await asyncio.sleep(delay)
            await envia(email)
        except Exception as e:
            # Log exception but don't crash
            import logging
            logging.exception("Error en delayed send: %s", e)

    def schedule_via_asyncio(run_date: datetime, email: 'EmailSchema') -> None:
        # crea una tarea en background que esperará y luego enviará
        asyncio.create_task(_delayed_send(run_date, email))


async def envia(email: EmailSchema) -> None:
    """Envía el email usando FastMail (async)."""
    html = f"<p>{email.cuerpo}</p>"
    message = MessageSchema(
        subject=getattr(email, "asunto", "Notificación"),
        recipients=[email.email],
        body=html,
        subtype=MessageType.html,
    )
    fm = FastMail(conf)
    await fm.send_message(message)

# HU 13: Como veterinaria quiero dejar alertas programadas que se envien al whatsApp de los dueños para hacerles recuerdos sobre citas
app.include_router(whatsapp_router)

# HU 14: Cómo dueño quiero recibir alertas programadas por correo para recordar cada consulta.
@app.post("/email/{fecha_envio}")
async def programar_envio(email: EmailSchema, fecha_envio: datetime, current_user: dict = Depends(get_current_session_user)):
    """Programa el envío de un correo en la fecha indicada.

    Si APScheduler está disponible, se usa `scheduler.add_job`. Si no, se usa
    un fallback que crea una tarea asyncio que duerme hasta la fecha y luego
    llama a `envia`.
    """
    if APSCHEDULER_AVAILABLE and scheduler is not None:
        scheduler.add_job(envia, 'date', run_date=fecha_envio, args=[email])
    else:
        # usar fallback sin dependencia externa
        schedule_via_asyncio(fecha_envio, email)

    return JSONResponse(status_code=200, content={"message": "La notificación fue programada correctamente"})


# HU 16: Cómo veterinaria quiero generar resumenes de citas que pueda enviar a los dueños
@app.get("/consultas/{id_consulta}/pdf")
def descargar_pdf_consulta(id_consulta: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    # Cuerpo del endpoint, se encuentra en Backend/services/pdf_service.py y devuelve los bytes del pdf
    pdf = generar_pdf_consulta(db, id_consulta)
    # Respuesta cruda de fastApi, permite mejor control
    return Response(
        content=pdf, # Contenido: Bytes del pdf
        media_type="application/pdf", # Tipo de media: Le dice a la web que tipo de data es, para no confundir pdf por texto
        headers={ # Que hacer con la respuesta: inline = Muestra en navegador - attachment = Descarga como archivo con el filename
            "Content-Disposition": f'attachment; filename="ficha_consulta_{id_consulta}.pdf"' 
        }
    )

# Generar certificado de transporte
@app.get("/pacientes/{id_paciente}/certificado-transporte")
def descargar_certificado_transporte(id_paciente: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_session_user)):
    from services.pdf_service import generar_certificado_transporte
    pdf = generar_certificado_transporte(db, id_paciente)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="certificado_transporte_{id_paciente}.pdf"'
        }
    )

# Generar consentimiento informado
class ConsentimientoRequest(BaseModel):
    procedimiento: Optional[str] = None
    indicaciones: Optional[str] = None
    objetivos: Optional[str] = None
    peso: Optional[float] = None
    autorizaciones_adicionales: Optional[List[str]] = None
    testigo_requerido: Optional[bool] = False

@app.post("/pacientes/{id_paciente}/consentimiento-informado")
def descargar_consentimiento_informado(
    id_paciente: int,
    request: ConsentimientoRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_session_user)
):
    from services.pdf_service import generar_consentimiento_informado
    pdf = generar_consentimiento_informado(
        db=db,
        id_paciente=id_paciente,
        procedimiento=request.procedimiento,
        indicaciones=request.indicaciones,
        objetivos=request.objetivos,
        peso=request.peso,
        autorizaciones_adicionales=request.autorizaciones_adicionales,
        testigo_requerido=request.testigo_requerido
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="consentimiento_informado_{id_paciente}.pdf"'
        }
    )

# Generar orden de exámenes
class OrdenExamenesRequest(BaseModel):
    id_consulta: Optional[int] = None
    examenes: Optional[List[dict]] = None
    observaciones: Optional[str] = None

@app.post("/pacientes/{id_paciente}/orden-examenes")
def descargar_orden_examenes(
    id_paciente: int,
    request: OrdenExamenesRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_session_user)
):
    from services.pdf_service import generar_orden_examenes
    pdf = generar_orden_examenes(
        db=db,
        id_paciente=id_paciente,
        id_consulta=request.id_consulta,
        examenes=request.examenes,
        observaciones=request.observaciones
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="orden_examenes_{id_paciente}.pdf"'
        }
    )

# Generar receta médica
class RecetaMedicaRequest(BaseModel):
    id_consulta: Optional[int] = None
    recetas: Optional[List[dict]] = None
    observaciones: Optional[str] = None
    fecha_receta: Optional[str] = None

@app.post("/pacientes/{id_paciente}/receta-medica")
def descargar_receta_medica(
    id_paciente: int,
    request: RecetaMedicaRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_session_user)
):
    from services.pdf_service import generar_receta_medica
    pdf = generar_receta_medica(
        db=db,
        id_paciente=id_paciente,
        id_consulta=request.id_consulta,
        recetas=request.recetas,
        observaciones=request.observaciones,
        fecha_receta=request.fecha_receta
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="receta_medica_{id_paciente}.pdf"'
        }
    )

# Inicio de sesion con tiempo personalizado
app.include_router(session_auth_router)

# async def envia(email: EmailSchema) -> JSONResponse:
#     html = f"""<p>{email.cuerpo}</p>"""

#     message = MessageSchema(
#         subject="Notificación",
#         recipients=[email.email],
#         body=html,
#         subtype=MessageType.html
#     )

#     fm = FastMail(conf)
#     await fm.send_message(message)
#     return JSONResponse(status_code=200, content={"message": "La notificación fue enviada correctamente"})
