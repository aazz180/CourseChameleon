# login.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from uuid import UUID
from pydantic import BaseModel, constr
from src.utils import execute_sql_statement
from fastapi import APIRouter, HTTPException, status, Depends
import logging
from jwt import encode, decode, ExpiredSignatureError, InvalidSignatureError
from datetime import datetime, timedelta
from os import environ
from bcrypt import checkpw, hashpw, gensalt
from re import match
from fastapi.security import OAuth2PasswordRequestForm
from src.startup import oauth2_scheme
from fastapi import APIRouter
import aiohttp
from secrets import token_hex 
from base64 import b64encode
import json

class UserRegistrationModel(BaseModel):
    # create a model that checks that the user registration is correct by comparing the request has the following: 
    email: str
    password: str
    name: str


class UserLoginModelEmail(BaseModel):
    # create a model that checks that the user login is correct by comparing the request has the following: 
    email: str
    password: str


class UserUpdateUserInformationModel(BaseModel):
    # create a model that checks that the user update information is correct by comparing the request has the following: 
    name: str = ""
    new_email: str = ""
    password: str = ""

class CreatePasswordResetLinkModel(BaseModel):
    # create a model that checks that the create password request is correct by comparing the request has the following: 
    email: str

class CheckPasswordResetLinkModel(BaseModel):
    # create a model that checks that the create password request is correct by comparing the request has the following: 
    token: constr(min_length=32, max_length=32) # ensures that the length of the token must be exactly 32 characters (as else, something is wrong with the token, and we do not need to waste processing power on it)
    password: str
    
class User():
    def __init__(self) -> None:
        """
        This is the constructor for the User().
        It initializes the user with an email and password.
        It also checks if the user table exists, and if not, it generates the user table.
        This is part of the User().
        """
        self.user_id: UUID = ""  # initializes the user_id so that we can use it later
        self.jwt_token: str = ""  # initializes the jwt_token so that we can use it later
        self.name: str = ""  # initializes the name so that we can use it later
        self.email: str = ""  # initializes the email so that we can use it later
        # initializes the password_hash so that we can use it later
        self.password_hash: str = ""
        # initializes the created_at so that we can use it later
        self.created_at: str = (datetime.now()).isoformat()
        self.conn = None  # initializes the connection to the database so that we can use it later
        self.cur = None  # initializes the cursor to the database so that we can use it later
        self.jwt_secret_key = environ.get("JWT_SECRET_KEY", "")

    async def get_user_id(self) -> UUID:
        """
        This function retrieves the default user ID from the database based on the email.
        This is part of the user_class.
        It returns the user ID if found, otherwise it returns null.

        Raises:
            HTTPException: Invalid user id is supplied.

        Returns:
            str: user_id
        """
        self.user_id: UUID = await execute_sql_statement("SELECT user_id FROM users WHERE email = %s;", (self.email,), fetch='one')
        logging.debug(f"User ID retrieved: {self.user_id}")
        if not self.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email entered.")
        logging.debug(f"User ID extracted: {self.user_id}")
        return self.user_id

    async def get_jwt_token(self) -> str:
        """This function retrieves the JWT token for a particular user id, and then returns the JWT token.
        This is used in authentication of a user, and the JWT token is stored in the user's session.

        Raises:
            HTTPException: Invalid user id is supplied.

        Returns:
            str: the user's JWT token
        """
        if not self.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user_id entered.")
        self.jwt_token = await execute_sql_statement("SELECT jwt_token FROM users WHERE user_id = %s;", (self.user_id,), fetch='one')
        if not self.jwt_token:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="JWT token was not found for this user.")
        logging.debug(f"JWT token retrieved: {self.jwt_token}")
        return self.jwt_token

    async def set_jwt_token(self, user_id: str) -> str:
        """This function creates a JWT token for a particular user id, and then returns the JWT token.
        This is used in authentication of a user, and the JWT token is stored in the user's session.

        Args:
            user_id (str): the user id of the user

        Raises:
            HTTPException: Invalid user id
            HTTPException: Internal server error where the server cannot create a JWT token for some reason.

        Returns:
            str: the JWT token
        """
        if not self.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user_id entered.")
        token_expiry_time = timedelta(days=1)
        # the expiry time is set to 1 day from now
        expiry_time = token_expiry_time + datetime.now()
        self.jwt_token = encode({"user_id": str(
            user_id), "expiry": expiry_time.isoformat()}, self.jwt_secret_key)
        if not self.jwt_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create JWT token.")
        await execute_sql_statement(
            "UPDATE users SET jwt_token = %s WHERE user_id = %s;",
            (self.jwt_token, user_id)
        )
        logging.debug(f"JWT token created: {self.jwt_token}")
        if not self.jwt_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create JWT token.")
        return self.jwt_token

    async def verify_password(self, password: str) -> bool:
        """
        This function checks the the password supplied is valid and returns a boolean to indicate if the password is valid or  hashing it with bcrypt, it checks it 

        Args:
            password (str): password supplied which is the password that has been supplied by the user

        Raises:
            HTTPException: throws an error to the user, if the User is not found in the database

        Returns:
            bool: true -> password is correct, false -> password is incorrect
        """
        self.password_hash = await execute_sql_statement("SELECT password_hash FROM users WHERE user_id = %s;", (self.user_id,), fetch='one')
        if not self.password_hash:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    async def register_user(self, email: str, password: str, name: str) -> None:
        """
        This function registers a new user in the database.
        It takes the email, password and name of the user as input and creates a new user record.
        It returns a JSON response indicating the success or failure of the operation.
        This is part of the user_class.

        Args:
            email (str): user's email for registration
            password (str): user's password for registration
            name (str): user's name for registration

        Raises:
            HTTPException: throws an error, if the user information provided for registration is invalid in detail.
        """
        if email == "" or password == "" or name == "":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Email, password and name cannot be empty.")
        if len(email) < 5 or len(email) > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Email must be between 5 and 100 characters.")
        if len(password) < 8 or len(password) > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Password must be between 8 and 100 characters.")
        does_user_exist = await execute_sql_statement("SELECT user_id FROM users WHERE email = %s;", (email,), fetch='one')
        if does_user_exist:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="A user already exists with this email.")
        if len(name) <= 2 or len(name) >= 50:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Name must be between 2 and 50 characters.")
        if name == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Name cannot be empty.")

        email_regex = "(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|\"(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21\\x23-\\x5b\\x5d-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])*\")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21-\\x5a\\x53-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])+)\\])"
        # source of email regex statement is from https://uibakery.io/regex-library/email-regex-python

        if email and (not match(email_regex, email)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email is not valid.")

        password_regex = "^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).{8,}$"
        if password and (not match(password_regex, password)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Password does not contain at least 8 characters, 1 uppercase letter, 1 lowercase letter, 1 digit and a special case character.")
        # source of password regex is from https://uibakery.io/regex-library/password-regex-python
        """
        All the code above which is in this function is data validation code that keeps the data integrity of the database in check.
        This is because the code above ensures that invalid inputs via SQL statements are given as SQL statements.
        """

        hashed_password = hashpw(password.encode(
            'utf-8'), gensalt(14)).decode('utf-8')
        current_time = (datetime.now()).isoformat()
        await execute_sql_statement(
            "INSERT INTO users (email, password_hash, name, created_at) VALUES (%s, %s, %s, %s);",
            (email, hashed_password, name, current_time)
        )
        logging.debug(f"User registered with email: {email}")

    async def check_user_authenticated(self, email: str, password: str) -> str:
        """
        This function checks if the user is authenticated via email and password.
        It returns the user's JWT token if True, otherwise, returns "Invalid email or password." if False.
        """
        user_info = await execute_sql_statement("SELECT * FROM users WHERE email = %s;", (email,), fetch='all')

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
        self.email = user_info[0][1]
        self.password_hash = user_info[0][2]
        self.user_id = str(user_info[0][0])
        is_valid = await self.verify_password(password=password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
        self.created_at = user_info[0][3]
        self.jwt_token = await self.set_jwt_token(user_id=self.user_id)
        self.name = user_info[0][5]
        return self.jwt_token

    async def check_user_authenticated_jwt(self, jwt_token: str) -> bool:
        """
        This function checks if the user is authenticated by checking the JWT token.
        It returns True if the user is authenticated, otherwise it returns False.
        We use this function to check if the user is authenticated via JWT token at the start of each API route.
        It decodes the JWT token and retrieves the user_id from it.
        """
        try:
            decoded_token = decode(
                jwt_token, self.jwt_secret_key, algorithms=["HS256"])
            self.user_id = decoded_token["user_id"]
            if not self.user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token.")
            expiry = decoded_token.get("expiry")
            if expiry and datetime.fromisoformat(expiry) < datetime.now():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT token has expired.")
            doesJWTtTokenExistInDatabase = await execute_sql_statement("SELECT jwt_token FROM users WHERE user_id = %s;", (self.user_id,), fetch='one')
            if not doesJWTtTokenExistInDatabase or doesJWTtTokenExistInDatabase != jwt_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT token is invalid.")
            logging.debug(
                f"JWT token decoded successfully for user_id: {self.user_id}")
            self.jwt_token = jwt_token
            user_info = await execute_sql_statement("SELECT * FROM users WHERE user_id = %s;", (self.user_id,), fetch='all')
            if not user_info:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User not found in the database.")
            self.email = user_info[0][1]
            self.password_hash = user_info[0][2]
            self.name = user_info[0][5]
            self.created_at = user_info[0][3]
            return True
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token")
        except InvalidSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token")
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token")
        except Exception as e:
            logging.debug("JWT token:", str(jwt_token))
            logging.error(f"Error decoding JWT token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error decoding JWT token.")

    async def remove_jwt_token(self) -> None:
        """
        This function removes the JWT token from the database for a particular user id.
        It is used to log out the user and remove the JWT token from the database.
        """
        if not self.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user_id.")
        await execute_sql_statement("UPDATE users SET jwt_token = NULL WHERE user_id = %s;", (self.user_id,))
        logging.debug(f"JWT token removed for user_id: {self.user_id}")
        self.jwt_token = ""

    async def get_user_information(self) -> dict:
        """
        This function retrieves the user information from the database for a particular user id.
        It returns a dictionary with the user information.
        """
        if not self.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user_id.")
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "created_at": str(self.created_at)
        }

    async def update_user_information(self, name: str | None = None, new_email: str | None = None, password: str | None = None) -> None:
        """
        This function updates the user information in the database based on the user ID.
        It can update the name, email, and password of the user (leave empty to not update).
        """
        if not self.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user_id.")
        if name == "" or new_email == "" or password == "":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Name, email and password cannot be empty.")
        if new_email and (len(new_email) < 5 or len(new_email) > 100):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Email must be between 5 and 100 characters.")
        if password and (len(password) < 8 or len(password) > 100):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Password must be between 8 and 100 characters.")
        if name and (len(name) <= 2 or len(name) >= 50 or not " " in name):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Name must be between 2 and 50 characters and must contain at least one space.")
        if password and (await self.verify_password(password) is True):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="New password cannot be the same as the old password.")

        email_regex = "(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|\"(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21\\x23-\\x5b\\x5d-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])*\")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21-\\x5a\\x53-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])+)\\])"
        # source of email regex statement is from https://uibakery.io/regex-library/email-regex-python

        if new_email and (not match(email_regex, new_email)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email is not valid.")
        if password is not None:
            hashed_password = hashpw(password.encode(
                'utf-8'), gensalt(14)).decode('utf-8')

        password_regex = "^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).{8,}$"
        if password and (not match(password_regex, password)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Password does not contain at least 8 characters, 1 uppercase letter, 1 lowercase letter, 1 digit and a special case character.")
        # source of password regex is from https://uibakery.io/regex-library/password-regex-python

        """
        Above are just validation checks to ensure that the user information is valid before updating it.
        We check if the user_id is valid, if the old password is correct, if the name, email and password are not empty,
        if the new email is between 5 and 100 characters, if the new password is between 8 and 100 characters,
        if the name is between 2 and 50 characters and contains at least one space,
        and if the new password is not the same as the old password.
        If any of these checks fail, we raise an HTTPException with a 400 status code and a relevant error message.
        We also check if the new email is valid using a regex pattern.
        If the new email is not valid, we raise an HTTPException with a 400 status code and a relevant error message.
        If all checks pass, we update the user information in the database.
        We use the execute_sql_statement function to execute the SQL statements to update the user information.
        We also hash the new password using bcrypt before updating it in the database.
        """

        if name is not None:
            await execute_sql_statement("UPDATE users SET name = %s WHERE user_id = %s;", (name, self.user_id))
            self.name = name
        if new_email is not None:
            await execute_sql_statement("UPDATE users SET email = %s WHERE user_id = %s;", (new_email, self.user_id))
            self.email = new_email
        if password is not None:
            await execute_sql_statement("UPDATE users SET password_hash = %s WHERE user_id = %s;", (hashed_password, self.user_id))
            self.password_hash = hashed_password
        logging.debug(
            f"User information updated for user_id: {self.user_id}, name: {self.name}, email: {self.email}")
    async def send_password_reset_email(self, reset_url_token: str) -> bool:
        """
        This procedure sends an email to the user's email with a password reset link using MailJet.
        I used MailJet as it was the first free email sender with an REST API, as writing an SMTP server is way too complicated for this project
        and emails sent by the SMTP server would be put into the spam filter of the user, as GMAIL and Outlook would assume the email as spam.
        MailJet bypasses all of this, and is also free. 
        The email created by this subroutine contains the following: 
        * the password reset link 
        """
        email_api_key = environ.get("EMAIL_API_KEY", "")
        email_sender_key = environ.get("EMAIL_SECRET_KEY", "")
        email_sender_address = environ.get("EMAIL_SENDER_ADDRESS", "") # we parse the email sender information from the .env file
        reset_link = "http://127.0.0.1:5500/forgot_password.html?reset_token=" + reset_url_token

        send_payload = {
            "Messages": [
                {
                    "From": {
                        "Email": email_sender_address,
                        "Name": "A Level NEA Course Project"
                    },
                    "To": [
                        {"Email": self.email}
                    ],
                    "Subject": "Password Reset Request - A Level NEA Project",
                    "TextPart": (
                        "Someone has requested a password reset for your account.\n\n"
                        f"Click this link to reset your password: {reset_link}\n\n"
                        "This password reset link expires in 10 minutes."
                        "If you did not request a password reset, you can safely ignore this email."
                    ),
                    "HTMLPart": (
                        "<p>Someone has requested a password reset for your account.</p>"
                        f"<p>Click <a href='{reset_link}'>here</a> to reset your password.</p>"
                        "<p>This email expires in 10 minutes.</p>"
                        "<p>If you did not request a password reset, you can safely ignore this email.</p>"
                    )
                }
            ]
        } # this dictionary is payload that send to the MailJet API and contains the email we are going to send to the person who requested to reset their password 

        auth = b64encode(f"{email_api_key}:{email_sender_key}".encode()).decode() # create an authentication key to allow MailJet API to know who we are

        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.mailjet.com/v3.1/send", headers ={"Content-Type": "application/json","Authorization": f"Basic {auth}"}, data=json.dumps(send_payload)) as resp: 
                # we then send the POST request containing our email to MailJet
                try: # and then try to serialize it in JSON format (if it is not in JSON format, we know something is wrong and throw an error)
                    response = await resp.json()
                    smtp_status = response["Messages"][0]["Status"]
                except aiohttp.ContentTypeError: # if JSON cannot be parsed -> error
                    raise HTTPException(status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Response from SMTP server is invalid.")
                if smtp_status != "success": # we check if the password send email was successful, if not, then we throw an error to the user
                    raise HTTPException(status=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Password reset email could not sent to the requested email.")
                return True # return true stating that we have expected that we sent the password reset email to the user without troubles. 

    async def create_password_reset_link(self, email: str) -> None:
        """
        This subroutine creates a password reset link for a given email address and is called by send_password_reset_email, in use when the user requests for a password reset.
        It does the following:
        * checks if an user with the email exists, if it does not, then the subroutine returns without a value (see in the comments for a better explanation).
        * if the user with an email exists, then it creates a reset token with an expiry time of 10 minutes (to ensure that if the user's email has been comprised,
        that previous expiry reset tokens do not work)
        * and we insert this new token into the reset_password table to ensure that if the user has an token, we can ensure that is correct in check_password_reset_link later.
        """
        self.email: str = email # we parse the user's email
        self.user_id: UUID = await execute_sql_statement("SELECT user_id FROM users WHERE email = %s;", (self.email,), fetch='one')
        if not self.user_id:
            return # we return here instead of throwing an error as if we throw an error, an hacker can tell that instantly
            # there is no email connected to the account and this will be suspectable to a bruteforce attack
            # so we tell the frontend that if there is an account attached to the email, then an email has been sent to them
        token_expiry_time: timedelta = timedelta(minutes=10) 
        expiry_time: timedelta = token_expiry_time + datetime.now() # we set the expiry time of the password reset link to be 10 minutes from now
        # this is to ensure that if an hacker gains accesses to our user's email after 10 minutes, they are unable to reset the password of the user's account, as it would have expired
        # also it ensures that hackers cannot bruteforce a password reset link as time taken to bruteforce a key of 32 bit string is > 10 minutes. 
        reset_url_token: token_hex = token_hex(16) # we generate a random URL-safe 128 bit string that as the reset url token -> it is in hex format therefore, it will be in 32 characters
        await execute_sql_statement(
            "INSERT INTO reset_password (user_id, reset_token, expires_at) VALUES (%s, %s, %s);",
            (self.user_id, reset_url_token, expiry_time)) # we store the password reset information to the database so we can parse and check the password reset link later works
        # -> ensures that even if the server goes down
            # all password reset links still function
        await self.send_password_reset_email(reset_url_token=reset_url_token) # we send the password reset email 
    
    async def check_password_reset_link(self, reset_url_token: str, password: str) -> None:
        """
        This subroutine is a subroutine that checks if the user's password reset token is correct, and if it is correct, then it resets the user's password accordingly to their password input."""
        user_info = await execute_sql_statement("SELECT * FROM reset_password WHERE reset_token = %s;", (reset_url_token,), fetch='all')
        self.user_id = str(user_info[0][0]) # we get the user id of the person asking for a restart
        if not self.user_id: # check if the user id of the reset URL token is valid, if it is not, then we can assume that the reset URL token is invalid
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid reset URL token as it does not have an user id.")
        await execute_sql_statement("DELETE FROM reset_password WHERE user_id = %s;", (self.user_id,)) # we delete this password reset token, once we know it is correct, so that
        # be used again to reset the user's password
        expiry = user_info[0][2] # we check if the user's token has expired 
        if expiry and expiry < datetime.now(): # if it has expired, then we raise an error and tell the user that their token has expired
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Reset URL token has expired.")
        await self.update_user_information(password=password) # if all is correct, then we change the user's password



login_router = APIRouter(prefix="/login", tags=["Login page"])


async def check_user_authenticated_dependency(token: str = Depends(oauth2_scheme)) -> User:
    user = User()
    logging.debug(f"Checking user authentication with token: {token}")
    is_user_authenticated = await user.check_user_authenticated_jwt(jwt_token=token)
    if not is_user_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not authenticated."
        )
    return user


@login_router.post("/register")
async def register_user_wrapper(data: UserRegistrationModel):
    """
    This function is a backend API route that registers a new user, and validates the input data (email, password, name).
    It checks if the email is already registered, and if not, it creates a new user in the database.
    It returns a JSON response indicating the success or failure of the operation.
    """
    user = User()
    await user.register_user(email=data.email, password=data.password, name=data.name)
    return {"success": True, "message": "User registered successfully."}


@login_router.post("/check_user_authenticated")
# standard way for jwt token authentication in FastAPI
async def check_user_authenticated_jwt_wrapper(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    This function checks if the user is authenticated by checking the email and password.
    It returns a JSON response with the account's JWT token if the user is authenticated successfully.
    If the user is not authenticated, it raises an HTTPException with a 401 status code
    """
    email = form_data.username  # we have to do this as the FastAPI expects an username and not an email
    password = form_data.password
    data = UserLoginModelEmail(email=email, password=password)
    user = User()
    jwt_token = await user.check_user_authenticated(email=data.email, password=data.password)
    logging.debug(f"User authenticated successfully with email: {email}")
    logging.debug(f"JWT token created: {jwt_token}")

    return {"success": True, "access_token": jwt_token, "token_type": "bearer"}


@login_router.post("/update_user_information")
async def update_user_information(data: UserUpdateUserInformationModel,
                                  user: User = Depends(check_user_authenticated_dependency)):
    """
    This function updates the user's information in the database.
    It can update the name, email, and password of the user (leave empty to not update).
    """

    name = data.name
    new_email = data.new_email
    password = data.password
    if not (name or new_email or password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="At least one field must be provided to update.")

    await user.update_user_information(name=name,
                                       new_email=new_email,
                                       password=password)
    logging.debug(f"User information updated for user_id: {user.user_id}")
    return {"success": True, "message": "User information updated successfully."}


@login_router.get("/logout")
async def logout_user(user: User = Depends(check_user_authenticated_dependency)):
    """
    This function logs out the user by removing the JWT token from the database.
    It returns a JSON response indicating the success or failure of the operation.
    """
    await user.remove_jwt_token()
    logging.debug(f"User logged out successfully for user_id: {user.user_id}")
    return {"success": True, "message": "User logged out successfully."}

@login_router.post("/create_password_link")
async def create_password_link_wrapper(data: CreatePasswordResetLinkModel):
    """
    This function is a wrapper for creating a password reset link that is sent to the user via email.
    It returns a JSON response indicating the success or failure of the operation.
    """
    email = data.email
    user = User()
    await user.create_password_reset_link(email=email)
    return {"success": True, "message": "If user exists, password reset link has been sent to them."}

@login_router.post("/check_password_reset_link")
async def check_password_reset_link_wrapper(data: CheckPasswordResetLinkModel):
    """
    This function is a wrapper for creating a password reset link that is sent to the user via email.
    It returns a JSON response indicating the success or failure of the operation.
    """
    reset_url_token = data.token
    password = data.password
    user = User()
    await user.check_password_reset_link(reset_url_token=reset_url_token, password=password)
    return {"success": True, "message": "User's password has successfully been reset."}