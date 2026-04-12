"""FreeRouter entry point. Run with: python -m freerouter"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("freerouter.server:app", host="0.0.0.0", port=4000, reload=False)
