from total_llm.app import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("total_llm.app:app", host="0.0.0.0", port=9002, reload=False)
