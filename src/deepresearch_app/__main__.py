import uvicorn

if __name__ == "__main__":
    uvicorn.run("deepresearch_app.api:default_app", factory=True, host="127.0.0.1", port=8765, workers=1)
