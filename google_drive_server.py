from fastapi import FastAPI, HTTPException
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import logging
import io
from docx import Document
import PyPDF2
from googleapiclient.http import MediaIoBaseDownload

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Google Drive MCP
class GoogleMCP:
    def __init__(self):
        creds = None
        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        try:
            if os.path.exists("token.json"):
                creds = Credentials.from_authorized_user_file("token.json", scopes)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired token")
                    creds.refresh(Request())
                else:
                    logger.info("Initiating new OAuth flow")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        "credentials.json", scopes
                    )
                    creds = flow.run_local_server(port=0)
                    with open("token.json", "w") as token:
                        token.write(creds.to_json())
            self.drive_service = build("drive", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Failed to initialize Google API: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Google API initialization failed: {str(e)}")

    def query_drive(self, query):
        logger.info(f"Searching Google Drive for: {query}")
        try:
            results = self.drive_service.files().list(
                q=f"name contains '{query}'",
                fields="files(id, name, mimeType)",
                pageSize=5
            ).execute()
            files = results.get("files", [])[:5]
            logger.info(f"Found {len(files)} files in Google Drive")
            return [{"name": file["name"], "location": f"Google Drive (file ID: {file['id']})", "mimeType": file["mimeType"]} for file in files]
        except HttpError as e:
            logger.error(f"Google Drive API error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Google Drive API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected Google Drive error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Unexpected Google Drive error: {str(e)}")

    def get_file_content(self, file_id):
        logger.info(f"Fetching content for file ID: {file_id}")
        try:
            # Get file metadata
            logger.info(f"Calling files().get for file ID: {file_id}")
            file_metadata = self.drive_service.files().get(fileId=file_id, fields="name, mimeType").execute()
            mime_type = file_metadata.get("mimeType", "")
            file_name = file_metadata.get("name", "Unknown")
            logger.info(f"File: {file_name}, MIME type: {mime_type}")

            # Download file content
            logger.info(f"Downloading content for {file_name}")
            request = self.drive_service.files().get_media(fileId=file_id)
            file_stream = io.BytesIO()
            downloader = MediaIoBaseDownload(file_stream, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            logger.info(f"Downloaded {file_name}")

            file_stream.seek(0)
            content = ""

            # Extract text based on file type
            if mime_type == "text/plain":
                content = file_stream.read().decode("utf-8", errors="ignore")
                logger.info(f"Extracted text/plain content: {len(content)} characters")
            elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                try:
                    doc = Document(file_stream)
                    content = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                    logger.info(f"Extracted docx content: {len(content)} characters")
                except Exception as e:
                    logger.error(f"Failed to extract docx content for {file_name}: {str(e)}")
                    return {"content": "", "error": f"Cannot extract .docx content: {str(e)}"}
            elif mime_type == "application/pdf":
                try:
                    pdf_reader = PyPDF2.PdfReader(file_stream)
                    content = "\n".join([page.extract_text() or "" for page in pdf_reader.pages])
                    logger.info(f"Extracted pdf content: {len(content)} characters")
                except Exception as e:
                    logger.error(f"Failed to extract pdf content for {file_name}: {str(e)}")
                    return {"content": "", "error": f"Cannot extract PDF content: {str(e)}"}
            else:
                logger.warning(f"Unsupported file type: {mime_type} for {file_name}")
                return {"content": "", "error": f"Unsupported file type: {mime_type}"}

            return {"content": content[:10000], "error": None}  # Limit to 10k chars
        except HttpError as e:
            logger.error(f"Google Drive API error for file {file_id}: {str(e)}")
            if e.resp.status == 404:
                return {"content": "", "error": "File not found or inaccessible"}
            elif e.resp.status == 403:
                return {"content": "", "error": "Insufficient permissions to access file"}
            raise HTTPException(status_code=500, detail=f"Google Drive API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error fetching file {file_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Cannot extract content: {str(e)}")

# Placeholder for Outlook MCP (commented out)
"""
class OutlookMCP:
    def __init__(self):
        # Requires msal and microsoft_credentials.json
        pass
    def query_outlook(self, query):
        # Placeholder for Microsoft Graph API
        return []
"""

# Instantiate MCP
try:
    google_mcp = GoogleMCP()
except Exception as e:
    logger.error(f"Failed to instantiate GoogleMCP: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Failed to instantiate GoogleMCP: {str(e)}")

@app.get("/google_drive")
async def query_google_drive(query: str):
    return google_mcp.query_drive(query)

@app.get("/google_drive/content/{file_id}")
async def get_file_content(file_id: str):
    return google_mcp.get_file_content(file_id)

# Placeholder for Outlook endpoint (commented out)
"""
@app.get("/outlook")
async def query_outlook(query: str):
    return outlook_mcp.query_outlook(query)
"""
