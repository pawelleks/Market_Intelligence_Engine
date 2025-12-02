import uvicorn
import os

os.environ['PYTHONUNBUFFERED'] = '1'

# Set the current directory as the app directory explicitly
os.environ['UVICORN_APP_DIR'] = os.path.dirname(__file__)

if __name__ == "__main__":
    # Note: the app path is now just 'api_server:app' because Uvicorn is run via Python -m
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
