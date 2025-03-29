from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.encoders import jsonable_encoder
import os
import io
import uuid
import logging
import traceback
import json
import asyncio
import shutil
from dotenv import load_dotenv, find_dotenv
from typing import List, Dict, Any, Optional
import markdown2
import openai
import PyPDF2
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["pdf"])

# Ensure environment variables are loaded
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
    logger.info(f"PDF Router: Loaded .env from {dotenv_path}")

# Initialize OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
logger.info(f"PDF Router: API key status: {'Set' if openai.api_key else 'Not set'}")
if openai.api_key:
    logger.info(f"PDF Router: API key starts with: {openai.api_key[:5]}...")

# Temporary storage for uploaded files and translations
UPLOAD_DIR = "uploads"
EXPORT_DIR = "exports"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# Store translations in memory (in a production app, use a database)
translations_cache = {}
# Store active translation tasks
active_translations = {}
active_connections = {}

async def cleanup_files():
    """Delete all files in uploads and exports directories"""
    try:
        # Clean uploads directory
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        # Clean exports directory
        if os.path.exists(EXPORT_DIR):
            for filename in os.listdir(EXPORT_DIR):
                file_path = os.path.join(EXPORT_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        # Clear the translations cache
        translations_cache.clear()
        
        # Close any active WebSocket connections
        for file_id in list(active_connections.keys()):
            try:
                await active_connections[file_id].close()
                del active_connections[file_id]
            except Exception as e:
                logger.error(f"Error closing WebSocket for {file_id}: {str(e)}")
        
        logger.info("Cleaned up all existing files and connections")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF file and extract text content page by page"""
    try:
        # Check if the file is a PDF
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        # Generate a unique ID for the file
        file_id = str(uuid.uuid4())
        
        # Create upload directory if it doesn't exist
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(EXPORT_DIR, exist_ok=True)
        
        # Clean up existing files
        await cleanup_files()
        
        # Save the file
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Extract text from PDF
        try:
            pages_content = []
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    pages_content.append({
                        "page_number": page_num + 1,
                        "content": text
                    })
            
            # Store in cache
            translations_cache[file_id] = {
                "original": pages_content,
                "translations": {},
                "filename": file.filename
            }
            
            return {
                "file_id": file_id,
                "total_pages": len(pages_content),
                "pages": pages_content,
                "filename": file.filename
            }
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            logger.error(traceback.format_exc())
            # Clean up on error
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
    except Exception as e:
        logger.error(f"Error uploading PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@router.websocket("/ws/translate/{file_id}")
async def websocket_translate(websocket: WebSocket, file_id: str):
    await websocket.accept()
    
    # Store the WebSocket connection in the active connections
    active_connections[file_id] = websocket
    
    # Send a connected message
    await websocket.send_json({
        "status": "connected",
        "message": "WebSocket connection established",
        "file_id": file_id
    })
    
    try:
        # Keep the connection open and listen for messages
        while True:
            data = await websocket.receive_json()
            logger.info(f"Received WebSocket message: {data}")
            
            # Handle any client messages if needed
            if data.get("action") == "start_translation":
                await websocket.send_json({
                    "status": "translating",
                    "message": "Starting translation process",
                    "file_id": file_id,
                    "progress": 0
                })
    except WebSocketDisconnect:
        # Remove the connection when it's closed
        if file_id in active_connections:
            del active_connections[file_id]
        logger.info(f"WebSocket connection closed for file_id: {file_id}")
    except Exception as e:
        logger.error(f"WebSocket error for file_id {file_id}: {str(e)}")
        if file_id in active_connections:
            del active_connections[file_id]

async def translate_page(page, target_language, file_id, page_index, total_pages):
    """Translate a single page and send progress updates via WebSocket"""
    try:
        # Skip empty content
        if not page["content"].strip():
            logger.warning(f"Page {page['page_number']} has no content to translate")
            return {
                "page_number": page["page_number"],
                "content": ""
            }
        
        # Send progress update
        if file_id in active_connections:
            progress_percentage = (page_index / total_pages) * 100
            await active_connections[file_id].send_json({
                "status": "translating",
                "message": f"Translating page {page['page_number']} of {total_pages}",
                "progress": progress_percentage,
                "page": page["page_number"],
                "total_pages": total_pages
            })
        
        # Use OpenAI to translate the text
        logger.info(f"Translating page {page['page_number']} to {target_language}")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a translator. Translate the following text to {target_language}. Preserve formatting as much as possible."},
                {"role": "user", "content": page["content"]}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        # Extract translated text
        if hasattr(response.choices[0].message, "content"):
            translated_text = response.choices[0].message.content
        else:
            translated_text = response.choices[0].message["content"]
        
        # Send completion update
        if file_id in active_connections:
            progress_percentage = ((page_index + 1) / total_pages) * 100
            await active_connections[file_id].send_json({
                "status": "page_completed",
                "message": f"Completed page {page['page_number']} of {total_pages}",
                "progress": progress_percentage,
                "page": page["page_number"],
                "total_pages": total_pages
            })
        
        return {
            "page_number": page["page_number"],
            "content": translated_text
        }
    except Exception as e:
        logger.error(f"Error translating page {page['page_number']}: {str(e)}")
        logger.error(traceback.format_exc())
        # Send error update
        if file_id in active_connections:
            await active_connections[file_id].send_json({
                "status": "error",
                "page": page["page_number"],
                "message": f"Error translating page {page['page_number']}: {str(e)}"
            })
        raise e

@router.post("/translate")
async def translate_document(file_id: str = Form(...), target_language: str = Form(...)):
    """Translate a PDF document to the target language"""
    try:
        # Check if the file exists
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Start translation process
        result = await translate_pdf(file_id, target_language)
        
        # Return the translation result
        return result
    except Exception as e:
        logger.error(f"Error translating document: {str(e)}")
        error_detail = str(e)
        if "openai" in error_detail.lower():
            error_detail += " - This may be due to an invalid API key or API rate limits."
        raise HTTPException(status_code=500, detail=error_detail)

@router.get("/translate")
async def get_translation(file_id: str, target_language: str):
    """Get translation data for a specific file and language"""
    try:
        # Check if the translation exists in the cache
        if file_id in translations_cache and target_language in translations_cache[file_id]["translations"]:
            # Return cached translation
            return {
                "file_id": file_id,
                "target_language": target_language,
                "pages": translations_cache[file_id]["translations"][target_language],
                "export_url": f"/api/download/{file_id}?format=md&target_language={target_language.lower()}"
            }
        
        # Check if the markdown file exists
        md_filename = f"{file_id}_{target_language.lower()}.md"
        md_path = os.path.join("exports", md_filename)
        
        if os.path.exists(md_path):
            # Read the markdown file to get the translation
            with open(md_path, "r", encoding="utf-8") as md_file:
                content = md_file.read()
            
            # Parse the content to extract page translations
            pages = []
            current_page = None
            current_content = []
            
            for line in content.split('\n'):
                if line.startswith('## Page '):
                    # Save previous page if exists
                    if current_page is not None:
                        pages.append({
                            "page_number": current_page,
                            "content": '\n'.join(current_content)
                        })
                    
                    # Start new page
                    try:
                        current_page = int(line.replace('## Page ', ''))
                        current_content = []
                    except ValueError:
                        current_page = None
                elif current_page is not None:
                    current_content.append(line)
            
            # Add the last page
            if current_page is not None:
                pages.append({
                    "page_number": current_page,
                    "content": '\n'.join(current_content)
                })
            
            # Cache the translation
            if file_id not in translations_cache:
                translations_cache[file_id] = {"translations": {}}
            
            translations_cache[file_id]["translations"][target_language] = pages
            
            return {
                "file_id": file_id,
                "target_language": target_language,
                "pages": pages,
                "export_url": f"/api/download/{file_id}?format=md&target_language={target_language.lower()}"
            }
        
        raise HTTPException(status_code=404, detail="Translation not found")
    except Exception as e:
        logger.error(f"Error getting translation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving translation: {str(e)}")

def extract_text_from_pdf(file_path):
    """Extract text from a PDF file page by page."""
    try:
        pages_content = []
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                pages_content.append({
                    "page_number": page_num + 1,
                    "content": text
                })
        return pages_content
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting text from PDF: {str(e)}")

def translate_text(text, target_language):
    """Translate text to the target language using OpenAI API."""
    try:
        # Check if the text is empty
        if not text or text.strip() == "":
            return "No content to translate."
        
        # Use OpenAI API to translate the text (using the new client)
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate the following text to {target_language}. Preserve the formatting and structure as much as possible."},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        # Extract the translated text from the response
        translated_text = response.choices[0].message.content
        return translated_text
    except Exception as e:
        logger.error(f"Error translating text: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error translating text: {str(e)}")

async def translate_pdf(file_id: str, target_language: str):
    """Translate PDF content to the target language."""
    try:
        # Get the file path
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Extract text from PDF
        pdf_text = extract_text_from_pdf(file_path)
        
        # Check if API key is set
        api_key = os.getenv("OPENAI_API_KEY")
        logger.info(f"API Key status: {'Set' if api_key else 'Not set'}")
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key is not set")
        
        # Log first few characters of API key for debugging (safely)
        if api_key:
            masked_key = api_key[:5] + "..." if len(api_key) > 5 else "invalid_key"
            logger.info(f"API key starts with: {masked_key}")
        
        # Translate each page
        translated_pages = []
        total_pages = len(pdf_text)
        logger.info(f"Found {total_pages} pages to translate")
        
        # Create a markdown export file
        export_filename = f"{file_id}_{target_language.lower()}.md"
        export_path = os.path.join("exports", export_filename)
        
        with open(export_path, "w", encoding="utf-8") as export_file:
            export_file.write(f"# Translated Document\n\n")
            export_file.write(f"*Original language: Auto-detected*\n")
            export_file.write(f"*Target language: {target_language}*\n\n")
            
            for i, page in enumerate(pdf_text):
                page_number = i + 1
                logger.info(f"Translating page {page_number} to {target_language}")
                
                # Send progress update via WebSocket
                if file_id in active_connections:
                    progress_percentage = (i / total_pages) * 100
                    await active_connections[file_id].send_json({
                        "status": "translating",
                        "message": f"Translating page {page_number} of {total_pages}",
                        "progress": progress_percentage,
                        "page": page_number,
                        "total_pages": total_pages
                    })
                
                # Translate the page content
                translated_content = translate_text(page["content"], target_language)
                
                # Add to translated pages
                translated_pages.append({
                    "page_number": page_number,
                    "content": translated_content
                })
                
                # Write to markdown file
                export_file.write(f"## Page {page_number}\n\n")
                export_file.write(f"{translated_content}\n\n")
                
                # Send page completion update via WebSocket
                if file_id in active_connections:
                    progress_percentage = ((i + 1) / total_pages) * 100
                    await active_connections[file_id].send_json({
                        "status": "page_completed",
                        "message": f"Completed page {page_number} of {total_pages}",
                        "progress": progress_percentage,
                        "page": page_number,
                        "total_pages": total_pages
                    })
        
        # Generate PDF from markdown - we'll skip this step and let the download endpoint handle it
        # This way we avoid potential Unicode issues during translation
        
        # Send completion update via WebSocket
        export_url = f"/api/download/{file_id}?format=md&target_language={target_language.lower()}"
        if file_id in active_connections:
            await active_connections[file_id].send_json({
                "status": "completed",
                "message": "Translation completed",
                "progress": 100,
                "export_url": export_url
            })
        
        return {
            "file_id": file_id,
            "target_language": target_language,
            "pages": translated_pages,
            "export_url": export_url
        }
    except Exception as e:
        logger.error(f"Error translating PDF: {str(e)}")
        
        # Send error update via WebSocket
        if file_id in active_connections:
            await active_connections[file_id].send_json({
                "status": "error",
                "message": f"Translation error: {str(e)}",
            })
        
        raise HTTPException(status_code=500, detail=f"Translation error: {str(e)}")

@router.get("/download/{file_id}")
async def download_translated_file(file_id: str, format: str = Query("pdf", enum=["md", "pdf"]), target_language: str = None):
    """Download the translated file in markdown or PDF format."""
    try:
        # Check if target language is provided
        if not target_language:
            # Try to find the file by listing the exports directory
            files = os.listdir("exports")
            matching_files = [f for f in files if f.startswith(f"{file_id}_")]
            
            if not matching_files:
                raise HTTPException(status_code=404, detail="Translated file not found")
            
            # Use the first matching file
            md_filename = matching_files[0]
        else:
            # Use the provided target language
            md_filename = f"{file_id}_{target_language.lower()}.md"
        
        md_path = os.path.join("exports", md_filename)
        
        if not os.path.exists(md_path):
            raise HTTPException(status_code=404, detail=f"Translated file not found: {md_path}")
        
        # If markdown format is requested, return the markdown file
        if format == "md":
            return FileResponse(
                path=md_path,
                filename=md_filename,
                media_type="text/markdown"
            )
        
        # If PDF format is requested, convert markdown to PDF
        pdf_filename = md_filename.replace(".md", ".pdf")
        pdf_path = os.path.join("exports", pdf_filename)
        
        # Convert markdown to PDF if it doesn't exist yet
        if not os.path.exists(pdf_path):
            # Read markdown content
            with open(md_path, "r", encoding="utf-8") as md_file:
                md_content = md_file.read()
            
            try:
                # Create a PDF document
                doc = SimpleDocTemplate(
                    pdf_path,
                    pagesize=letter,
                    rightMargin=72,
                    leftMargin=72,
                    topMargin=72,
                    bottomMargin=72
                )
                
                # Create styles
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle(
                    'Title',
                    parent=styles['Heading1'],
                    alignment=TA_CENTER,
                    fontSize=18
                )
                heading1_style = ParagraphStyle(
                    'Heading1',
                    parent=styles['Heading1'],
                    fontSize=16
                )
                heading2_style = ParagraphStyle(
                    'Heading2',
                    parent=styles['Heading2'],
                    fontSize=14
                )
                normal_style = styles['Normal']
                
                # Create the document content
                content = []
                
                # Parse the markdown content
                lines = md_content.split('\n')
                
                for i, line in enumerate(lines):
                    # Skip empty lines
                    if not line.strip():
                        content.append(Spacer(1, 6))
                        continue
                    
                    # Handle headings
                    if line.startswith('# '):
                        content.append(Paragraph(line[2:], title_style))
                        content.append(Spacer(1, 12))
                    elif line.startswith('## '):
                        content.append(Paragraph(line[3:], heading1_style))
                        content.append(Spacer(1, 10))
                    elif line.startswith('### '):
                        content.append(Paragraph(line[4:], heading2_style))
                        content.append(Spacer(1, 8))
                    # Handle emphasis (italic)
                    elif line.startswith('*') and line.endswith('*') and len(line) > 2:
                        content.append(Paragraph(f"<i>{line[1:-1]}</i>", normal_style))
                    # Regular text
                    else:
                        content.append(Paragraph(line, normal_style))
                
                # Build the PDF
                doc.build(content)
                
            except Exception as e:
                logger.error(f"Error generating PDF: {str(e)}")
                # If PDF generation fails, return the markdown file instead
                return FileResponse(
                    path=md_path,
                    filename=md_filename.replace(".md", ".txt"),
                    media_type="text/plain"
                )
        
        # Return the PDF file
        return FileResponse(
            path=pdf_path,
            filename=pdf_filename,
            media_type="application/pdf"
        )
    except Exception as e:
        logger.error(f"Error downloading translated file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

@router.get("/languages")
async def get_supported_languages():
    """Get a list of languages supported by OpenAI for translation"""
    # This is a comprehensive list of languages that OpenAI models can handle
    languages = [
        "Afrikaans", "Albanian", "Amharic", "Arabic", "Armenian", "Azerbaijani",
        "Basque", "Belarusian", "Bengali", "Bosnian", "Bulgarian", "Catalan",
        "Cebuano", "Chichewa", "Chinese (Simplified)", "Chinese (Traditional)",
        "Corsican", "Croatian", "Czech", "Danish", "Dutch", "English",
        "Esperanto", "Estonian", "Filipino", "Finnish", "French", "Frisian",
        "Galician", "Georgian", "German", "Greek", "Gujarati", "Haitian Creole",
        "Hausa", "Hawaiian", "Hebrew", "Hindi", "Hmong", "Hungarian",
        "Icelandic", "Igbo", "Indonesian", "Irish", "Italian", "Japanese",
        "Javanese", "Kannada", "Kazakh", "Khmer", "Korean", "Kurdish (Kurmanji)",
        "Kyrgyz", "Lao", "Latin", "Latvian", "Lithuanian", "Luxembourgish",
        "Macedonian", "Malagasy", "Malay", "Malayalam", "Maltese", "Maori",
        "Marathi", "Mongolian", "Myanmar (Burmese)", "Nepali", "Norwegian",
        "Odia (Oriya)", "Pashto", "Persian", "Polish", "Portuguese", "Punjabi",
        "Romanian", "Russian", "Samoan", "Scots Gaelic", "Serbian", "Sesotho",
        "Shona", "Sindhi", "Sinhala", "Slovak", "Slovenian", "Somali",
        "Spanish", "Sundanese", "Swahili", "Swedish", "Tajik", "Tamil",
        "Telugu", "Thai", "Turkish", "Ukrainian", "Urdu", "Uzbek",
        "Vietnamese", "Welsh", "Xhosa", "Yiddish", "Yoruba", "Zulu"
    ]
    
    return {"languages": languages}
