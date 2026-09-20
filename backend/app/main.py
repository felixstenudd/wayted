from fastapi import FastAPI

app = FastAPI(title="wayted")


@app.get("/")
def root():
    return {"message": "API is running"}
