import os
import logging
import bcrypt
import httpx
import asyncio
from fastapi import FastAPI, Request, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jose import jwt
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, TIMESTAMP
from pydantic import BaseModel
from dotenv import load_dotenv

#  Ngarko variablat nga .env
load_dotenv()

#  Konfigurimi i logut
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#  Inicimi i aplikacionit FastAPI
app = FastAPI()

#  Drejtoria për template dhe skedarët statikë
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Lidhja me PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:florent123@localhost:5433/kosovai_db")
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

#  Sekreti për JWT
SECRET_KEY = os.getenv("SECRET_KEY", "kosovai_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

#  API Key për Mistral
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "tuaVm3CITgLnkeSIEGJVhIYdTj1Squ1K")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-medium"

#  Definimi i modelit për përdoruesit
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

#  Inicializimi i bazës së të dhënave
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        result = await session.execute(select(User).limit(1))
        user_exists = result.scalars().first()

        if not user_exists:
            test_users = [("user1", "pass1"), ("user2", "pass2"), ("user3", "pass3"), ("user4", "pass4")]

            for username, password in test_users:
                hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                new_user = User(username=username, password=hashed_password)
                session.add(new_user)

            await session.commit()

#  Eventi i startup-it
@app.on_event("startup")
async def on_startup():
    try:
        logger.info("🔄 Inicializimi i bazës së të dhënave...")
        await init_db()
        logger.info("✅ Baza e të dhënave u inicializua me sukses!")
    except Exception as e:
        logger.error(f"❌ Gabim gjatë startup-it: {e}")

#  Menaxhimi i sesioneve
async def get_db():
    async with SessionLocal() as session:
        yield session

#  Funksionet ndihmëse për autentifikim
async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

async def authenticate_user(session: AsyncSession, username: str, password: str):
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalars().first()

    if user and await verify_password(password, user.password):
        return user
    return None

def create_access_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

#  Home Route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Login Route
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    session: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(session, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "❌ Kredencialet janë të pasakta!"})

    token = create_access_token(username)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

#  Model për kërkesën e përdoruesit
class ChatRequest(BaseModel):
    message: str

#  Endpoint për chatbot me Mistral
@app.post("/chat")
async def chat_endpoint(chat_request: ChatRequest):
    if not MISTRAL_API_KEY:
        return JSONResponse(content={"error": "API Key për Mistral mungon"}, status_code=500)

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    #  API e re kërkon "messages", jo vetëm "prompt"
    payload = {
        "model": MISTRAL_MODEL,
        "messages": [{"role": "user", "content": chat_request.message}],
        "temperature": 0.7,
        "max_tokens": 100
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(MISTRAL_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return {"response": result.get("choices", [{}])[0].get("message", {}).get("content", "No response.")}
        except httpx.HTTPStatusError as e:
            return JSONResponse(content={"error": f"API Error: {e.response.text}"}, status_code=e.response.status_code)
        except httpx.RequestError:
            return JSONResponse(content={"error": "Kërkesa dështoi. Sigurohu që API e Mistral po funksionon."}, status_code=500)
