# api.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from src.login import login_router
from src.courses import course_router
from src.summary import summary_router
from src.telemetry import telemetry_router
from src.search import search_router
from src.user_profile import profile_router
from src.home import home_router
from os import environ
import logging
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from uvicorn import run
from fastapi.middleware.cors import CORSMiddleware
from src.startup import init_pool, get_pool, check_databases_exist

"""
The code above is importing libraries, required in this file. 
This file is just the file that is run and executed and contains all the basic startup code for the backend API.
"""


load_dotenv()  # this loads all the settings from .env into the environment so that the environ.get() can use them later
debug: bool
# ensures that the error information and debug information is only shown in debug mode
if environ.get("DEBUG") == "true":
    print("[!] Debug mode detected!")
    debug = True
    # sets the logging style to debug in the logging library to have more information in logging
    logging.basicConfig(level=logging.DEBUG,
                        format="[-] %(asctime)s %(levelname)s %(message)s")
else:
    debug = False
    # sets logging style to info (only important information is given, unlike debug)
    logging.basicConfig(level=logging.INFO,
                        format="[-] %(asctime)s %(levelname)s %(message)s")


# this pieces of code fetches the DB_USER from the .env for later use in the PostgreSQL database url.
db_user: str = environ.get("DB_USER", "")
db_password: str = environ.get("DB_PASSWORD", "")
db_ip: str = environ.get("DB_IP", "")
db_port: str = environ.get("DB_PORT", "")
db_name: str = environ.get("DB_NAME", "")


"""
The code above fetches the environmental information form .env file, and stores it so later, we can make the PostgreSQL database url. 
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This function is the first thing that starts when the FastAPI app begins.

    This function is a piece of code that is used in the FastAPI app, so that connections from back-end databases have a connection pool.
    This connection pool ensures that if multiple SQL requests are done at any given time, the database is not overwhelmed, by the vast number of requests.
    If this function is not kept, then the data integrity of the database fails. 

    This function is part of the startup process of the API.
    """
    await init_pool(database_url)  # initialize the shared connection pool
    await check_databases_exist()  # use the connection pool to check the database

    # the actual code of the API runs here

    yield  # the API ends here, after we close it
    await get_pool().close()  # we close the pool after the API stops running


# the url required to connect to the database
database_url: str = f"postgresql://{db_user}:{db_password}@{db_ip}:{db_port}/{db_name}"
# create an FastAPI instance that we can call upon as needed
app: FastAPI = FastAPI(lifespan=lifespan)


@app.get("/")
async def main_page():
    """
    Users shouldn't be able to access this API, so we redirect the user to a rick roll.
    This is because, it should be only accessed via CORS in the front-end.
    """
    return


@app.exception_handler(StarletteHTTPException)
async def error_page(request: Request, exception: StarletteHTTPException):
    """
    This function is displayed to the user in the front-end every time, we have an error.
    This can be for example, the user going to an unknown API route and getting a 404 error.
    """
    logging.debug(
        # log the error for debugging purposes
        f"Error {exception.status_code} {exception.detail} has been detected.")
    logging.debug(f"Redirecting user to error page.")
    return JSONResponse(
        status_code=exception.status_code,
        content={"success": False, "message": f"{exception.detail}"}
    )  # if not 404 error, we return JSON response so that the front-end can handle it properly

app.include_router(login_router)
app.include_router(course_router)
app.include_router(summary_router)
app.include_router(telemetry_router)
app.include_router(search_router)
app.include_router(profile_router)
app.include_router(home_router)
"""
The code above is used for importing all of the API routes through the back-end via APIRouter so that API routes in multiple classes can be used in this file.
This is done to have a modular code-base here, so that we do not have all the API routes in one big file, and instead they are in multiple files for ease of development and more.
"""
if debug:  # if in debug mode, we allow more origins for CORS coming from Live Server in VSCode
    origins = [
        "http://127.0.0.1:5500",  # if using Live Server in VSCode
        "http://localhost:5500",
    ]
else:
    origins = [
        "https://coursechameleon.netlify.app/"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

"""
The code above is used to set up CORS (Cross-Origin Resource Sharing) so that only the front-end can access the back-end API.
This is important as without this, the front-end will not be able to access the back-end API and otherwise, anyone can access the back-end API.
This would be a security risk, as anyone can access the back-end API and potentially cause harm to the course website.
"""


if __name__ == "__main__":
    run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=debug,
        log_level="debug" if debug else "info"
    )  # starts and runs the backend API
