import os
import bcrypt
import multiprocessing
from typing import Optional , List
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from sqlmodel import SQLModel, Field, create_engine, Session, select
from jose import jwt, JWTError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from pyngrok import ngrok
import uvicorn
import socket
import requests
import time
from fastapi.middleware.cors import CORSMiddleware
from google.colab import userdata

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
def check_server_ready(port, timeout=10):
    """Yeh function check karega ke server zinda hua ya nahi"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"http://127.0.0.1:{port}/docs")
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(3)
    return False

def find_free_port(start_port=8000):
  port = start_port
  while True:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
      try:
        s.bind(('localhost', port))
        return port
      except OSError:
        port += 1
        if port > 65535:
          raise RuntimeError("No free ports available.")

SECRET_KEY = "SUPER_SECRET_AI_AGENT_KEY_DONT_SHARE"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/enterprise_db")
engine = create_engine(DATABASE_URL, echo = True)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl= "/api/v1/auth/login")
app = FastAPI(title = "Enterprise AI Agent SaaS System")
class Employee(SQLModel, table = True, table_args={'extend_existing': True}):
  id : Optional[int] = Field(default = None, primary_key = True)
  name : str
  email : str = Field(unique= True, index = True)
  password : str
  role : str = "Employee"

class Client(SQLModel, table=True, table_args={'extend_existing': True}):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    password: str
    company_name: Optional[str] = None
    role: str = "Client"

def get_db():
  with Session(engine) as session:
    yield session

@app.on_event("startup")
def on_startup():

  SQLModel.metadata.create_all(engine)

training_texts = [
    "hi", "hello", "hey", "good morning", "aslam o alaikum", "anyone there",
    "what are your office timings?", "when do you open?", "are you open on weekends?", "office timing",
    "where is your office located?", "what is your address?", "location of company", "where are you guys based?",
    "what services do you offer?", "what do you do?", "tell me about your company products",
    "I want a custom software for my bakery business", "can you build an e-commerce website?",
    "I need a quote for an AI chatbot", "integrate AI agent into my platform", "hire developer for app"
]
training_labels = [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2]

COMPANY_KNOWLEDGE_BASE = {
    0: "Hello! Welcome to Alpha Tech Solutions. How can we assist you today?",
    1: "Alpha Tech Solutions is open Mon-Fri from 9 AM to 5 PM. We are located in Lahore, Pakistan, and we provide premium Web, Mobile App, and AI Automation services."
}

sklearn_pipeline = Pipeline([
    ("Vectorizer" , TfidfVectorizer()),
    ("Classifier" , LogisticRegression())
])

sklearn_pipeline.fit(training_texts, training_labels)

class UserSignup(BaseModel):
    name: str
    email: EmailStr
    password: str
    user_type: str  
    company_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class QueryModel(BaseModel):
    text: str


def create_access_token(data : dict):
  to_encode = data.copy()
  expire = datetime.utcnow()  + timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
  to_encode.update({"exp" : expire})
  return jwt.encode(to_encode, SECRET_KEY , algorithm = ALGORITHM)

def get_current_user(token : str = Depends(oauth2_scheme) , db : Session = Depends(get_db)):
  credentials_exception = HTTPException(
      status_code = status.HTTP_401_UNAUTHORIZED,
      detail = "Could not Validate Credentials!",
      headers = {"WWW-Authenticate" : "Bearer"}
  )
  try:
    payload = jwt.decode(token , SECRET_KEY , algorithms = [ALGORITHM])
    email : str = payload.get("sub")
    role : str = payload.get("role")
    if email is None:
      raise credentials_exception
  except JWTError:
    raise credentials_exception

  if role.lower() == "Employee":
    user = db.exec(select(Employee).where(Employee.email == email)).first()

  else:
        user = db.exec(select(Client).where(Client.email == email)).first()

  if user is None:
        raise credentials_exception
  return user

# This is the signup endpoint of backend

@app.post("/api/v1/auth/signup", status_code= 201)
def signup(user_data: UserSignup, db: Session = Depends(get_db)):
  try:

    password_bytes = user_data.password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)

    final_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    if user_data.user_type.lower() == "employee":
        existing = db.exec(select(Employee).where(Employee.email == user_data.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
        new_user = Employee(
            name=user_data.name,
            email=user_data.email,
            password= final_hash
        )

    elif user_data.user_type.lower() == "client":
        existing = db.exec(select(Client).where(Client.email == user_data.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        new_user = Client(
            name=user_data.name,
            email=user_data.email,
            password=final_hash,
            company_name=user_data.company_name
        )

  except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))


  db.add(new_user)
  db.commit()
  db.refresh(new_user)
  return {"status":"Success", "Message": "Signup successful!"}

@app.post("/api/v1/auth/login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
  try:

    user = db.exec(select(Employee).where(Employee.email == login_data.email)).first()
    role = "Employee"
    if not user:
        user = db.exec(select(Client).where(Client.email == login_data.email)).first()
        role = "Client"


    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")


    try:
        user_password_bytes = login_data.password.encode('utf-8')
        db_password_bytes = user.password.encode('utf-8')


        is_password_correct = bcrypt.checkpw(user_password_bytes, db_password_bytes)
    except Exception as e:

        raise HTTPException(status_code=500, detail=f"Bcrypt verification failed: {str(e)}")

    if not is_password_correct:
        raise HTTPException(status_code=400, detail="Incorrect email or password")


    access_token = create_access_token(data={"sub": user.email, "role": role})
    return {"access_token": access_token, "token_type": "bearer"}
  except Exception as e:
    raise HTTPException(status_code=400, detail=f"Asal Masla Yeh Hai: {type(e).__name__} -> {str(e)}")
@app.post("/api/v1/agent/query")
def route_query(query_data: QueryModel, current_user: SQLModel = Depends(get_current_user)):
  user_query = query_data.text
  prediction = int(sklearn_pipeline.predict([user_query])[0])
  if prediction in [0, 1]:

        return {
            "intent": "static_info",
            "class": prediction,
            "response": COMPANY_KNOWLEDGE_BASE[prediction],
            "tokens_saved": True
        }
  else:

        return {
            "intent": "complex_agent_action",
            "class": prediction,
            "response": f"Query '{user_query}' classified as Complex/Lead. Triggering LangChain Agent & ChromaDB vector search...",
            "tokens_saved": False
        }

@app.get("/api/v1/company/info")
def get_company_static_info(query: str):
    """
    Yeh endpoint GET hai aur iske liye login zaroori nahi hai (Public FAQ).
    Streamlit ka chatbot bina login ke isko hit kar sakta hai cost bachane ke liye.
    """
    prediction = int(sklearn_pipeline.predict([query])[0])
    if prediction in [0, 1]:
        return {"status": "success", "response": COMPANY_KNOWLEDGE_BASE[prediction]}
    else:
        return {"status": "redirect", "response": "This seems like a custom requirement."}
def run_server(port):
  uvicorn.run(app, host="127.0.0.1", port=port , log_level="info")


if __name__ == "__main__":
  port = find_free_port()
  ngrok.set_auth_token(userdata.get("Ngrok"))

  process = multiprocessing.Process(target=run_server, args=(port,))
  process.start()

  public_url = None # Initialize public_url

  if check_server_ready(port):
    print("FastAPI is up! Now connecting Ngrok...")
    public_url = ngrok.connect(port)
    print(f" URL: {public_url}")
  else:
    print(" Error: FastAPI background process failed to start or crashed!")
    process.terminate()

  if public_url:
    print("\n" + "="*60)
    print(f" NGROK PUBLIC URL: {public_url.public_url}")
    print(f" API DOCUMENTATION (Swagger UI): {public_url.public_url}/docs")
    print("="*60 + "\n")
  else:
    print("\n" + "="*60)
    print("Ngrok public URL could not be established because the FastAPI server did not start.")
    print("Please check the database connection and PostgreSQL server status.")
    print("="*60 + "\n")
    # Run FastAPI Server

  print({"status" : True} , "Server is Starting!...........")
