# startup.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from psycopg_pool import AsyncConnectionPool
import logging
from fastapi.security import OAuth2PasswordBearer


pool: AsyncConnectionPool = AsyncConnectionPool  # declare a connection pool
oauth2_scheme: OAuth2PasswordBearer = OAuth2PasswordBearer(
    tokenUrl="login/check_user_authenticated")


async def init_pool(database_url: str):
    """
    This function creates a connection pool and is only here because otherwise, if this function is not here, there will be a circular error whilst importing both api.py and login.py
    This ensures a shared connection pool is used.

    Args:
        database_url (str): _description_
    """
    global pool  # allow pool to be a global variable so we can change the global variable's data
    # create connection pool
    pool = AsyncConnectionPool(database_url, min_size=1)
    await pool.open()  # wait for connections to database in connection pool and run them


def get_pool():
    logging.debug("The connection pool was connected.")
    if pool is None:
        raise RuntimeError("Database pool has not been initialized.")
    return pool


table_definitions: dict = {  # a dictionary containing all the tables in the API and the SQL to make them.
    "users": (
        "CREATE TABLE users ("
        "user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),"
        "email VARCHAR UNIQUE,"
        "password_hash TEXT,"
        "created_at TIMESTAMP,"
        "jwt_token TEXT UNIQUE,"
        "name TEXT"
        ");"
    ),
    "courses": (
        "CREATE TABLE courses ("
        "course_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),"
        "title VARCHAR,"
        "description TEXT,"
        "content TEXT,"
        "created_at TIMESTAMP,"
        "image_link TEXT"
        ");"
    ),
    "tags": (
        "CREATE TABLE tags ("
        "tag_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),"
        "tag_name VARCHAR NOT NULL"
        ");"
    ),
    "course_tags": (
        "CREATE TABLE course_tags ("
        "course_id UUID NOT NULL,"
        "tag_id UUID NOT NULL,"
        "weight INTEGER NOT NULL,"
        "PRIMARY KEY (course_id, tag_id)"
        ");"
    ),
    "user_courses": (
        "CREATE TABLE user_courses ("
        "user_id UUID NOT NULL,"
        "course_id UUID NOT NULL,"
        "completion_percentage FLOAT,"
        "last_updated TIMESTAMP,"
        "questions_correct INTEGER,"
        "questions_wrong INTEGER,"
        "PRIMARY KEY (user_id, course_id)"
        ");"
    ),
    "reset_password": (
        "CREATE TABLE reset_password ("
        "user_id UUID NOT NULL,"
        "reset_token TEXT NOT NULL,"
        "expires_at TIMESTAMP NOT NULL,"
        "PRIMARY KEY (user_id, reset_token)"
        ");"
    ),
}

relationship_keys: list = [  # an array that stores the all SQL required to create relationships between databases.
    "ALTER TABLE course_tags ADD CONSTRAINT fk_ct_course FOREIGN KEY (course_id) REFERENCES courses(course_id);",
    "ALTER TABLE course_tags ADD CONSTRAINT fk_ct_tag FOREIGN KEY (tag_id) REFERENCES tags(tag_id);",
    "ALTER TABLE user_courses ADD CONSTRAINT fk_uc_user FOREIGN KEY (user_id) REFERENCES users(user_id);",
    "ALTER TABLE user_courses ADD CONSTRAINT fk_uc_course FOREIGN KEY (course_id) REFERENCES courses(course_id);",
    "ALTER TABLE reset_password ADD CONSTRAINT fk_rp_user FOREIGN KEY (user_id) REFERENCES users(user_id);",
]


async def check_databases_exist() -> None:
    """
    This function is an asynchronous function, that (at startup of the back-end API) checks that all the tables in the back-end databases are there.
    If yes, the program does nothing, and we continue with startup.
    If no, the program creates these tables (from table_definitions) and links them using the SQL commands in relationship_keys.

    This function is part of the startup process of the API.
    """
    global pool
    async with pool.connection() as conn:  # we create a connection to the back-end database
        async with conn.cursor() as cur:  # we then create a cursor (control structure that allows transversal over the records in the database)
            # we use the uuid-ossp extension if it does not exist, so that we can use custom private keys in the database
            await cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            await conn.commit() # we save immediately current state of database 
            # we iterate through table in table_definitions dict
            for table_name, creation_sql in table_definitions.items():
                await cur.execute(
                    "SELECT EXISTS ("
                    "SELECT FROM information_schema.tables WHERE table_name = %s"
                    ");", (table_name,)
                )  # check if table exists via SQL statement
                # if exists, we get a response. if it doesn't exist we get null in response
                doesTableExist = (await cur.fetchone())[0]

                if not doesTableExist:  # checking if the table exists
                    # if it doesn't, we log it
                    logging.info("Creating table '%s'...", table_name)
                    # then we create a new table
                    await cur.execute(creation_sql)
                    await conn.commit()
                else:
                    logging.debug(
                        "Table '%s' exists: %s - skipping creating this table", table_name, doesTableExist)
                    # if it doesn't exist, we just log it as well for logging purposes
                    
            for key in relationship_keys:  # we iterate through all relationships between databases
                try:
                    # we log that we applying them
                    logging.info(
                        "Applying relationship between databases: %s", key)
                    # we then execute the SQL statement to apply this relationship
                    await cur.execute(key)
                    await conn.commit()
                except Exception as e:  # this is a catch statement incase something goes wrong
                    # we log it for debug purposes
                    await conn.rollback() # rollback any damage to the database
                    logging.debug(
                        "Relationship between databases already exists or failed: %s", e)
"""'
The code above is for checking that the tables in the back-end database has been successfully created, if they already exist, we ignore them.
If not, then, the table is created and the relationship relating to each table are assigned after every table is created.
"""
