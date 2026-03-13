from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Iran OSINT backend is running"}