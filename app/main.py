from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import logging
from dotenv import load_dotenv, find_dotenv
import openai

from app.routers import pdf_router

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables - try to find .env file explicitly
dotenv_path = find_dotenv()
if dotenv_path:
    logger.info(f"Found .env file at: {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    logger.warning("No .env file found. Using environment variables from the system.")

# Configure OpenAI API key
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    # For newer OpenAI client (v1.0.0+)
    # We don't set it globally here, we'll create client instances as needed
    logger.info(f"OpenAI API key is set (starts with {api_key[:4]}...)")
else:
    logger.warning("OpenAI API key is not set. Translation functionality will not work.")

app = FastAPI(title="PDF Translator")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(pdf_router.router)

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def status():
    """Check the API status and configuration"""
    api_key = os.getenv("OPENAI_API_KEY")
    api_key_status = "Not set"
    
    if api_key:
        api_key_status = "Set (starts with {}...)".format(api_key[:4])
    
    return {
        "status": "operational",
        "api_key_status": api_key_status,
        "translation_available": api_key
    }

@app.get("/api/env-check")
async def env_check():
    """Debug endpoint to check environment variables"""
    env_vars = {}
    for key, value in os.environ.items():
        if key.lower() == "openai_api_key" and value:
            # Mask the API key for security
            env_vars[key] = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
        elif "api" in key.lower() or "key" in key.lower():
            # Mask other potential API keys
            env_vars[key] = "***" if value else "Not set"
        else:
            # Include other environment variables
            env_vars[key] = value
    
    dotenv_path = find_dotenv()
    
    return {
        "dotenv_found": bool(dotenv_path),
        "dotenv_path": dotenv_path if dotenv_path else "Not found",
        "openai_api_key_set": bool(os.getenv("OPENAI_API_KEY")),
        "env_vars_count": len(env_vars)
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
