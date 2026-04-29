# courses.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from fastapi import HTTPException, status, Depends, APIRouter
from pydantic import BaseModel, Field
from src.utils import execute_sql_statement
from src.login import check_user_authenticated_dependency, User
from logging import debug
from datetime import datetime
from re import match, IGNORECASE
from uuid import UUID
from typing import List, Dict
from json import dumps, loads


class getCourseInformationModel(BaseModel):
    # create a model that checks that getting course information in a POST request is correct by comparing the request has the following: 
    courseID: UUID


class courseModuleModel(BaseModel): 
    # create a model that checks that creating a course module in a POST request is correct by comparing the request has the following: 
    module_title: str
    # each lesson is {"title": str, "content": str}
    lessons: List[Dict[str, str]]


class createCourseModel(BaseModel):
     # create a model that checks that creating a course module in a POST request is correct by comparing the request has the following: 
    title: str
    description: str
    content: List[courseModuleModel]
    # a transparent image link as default image
    image_link: str = "https://thumbs.dreamstime.com/b/transparent-background-blank-isolated-object-jpeg-illustration-188734727.jpg" 
    # image link is optional, the image link above is random image I got off Google
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class runCodeModel(BaseModel):
    code: str

class Course:
    def __init__(self) -> None:
        """
        This is the constructor for the course_class.
        It initializes the course with a course ID.
        This is part of the Course.
        """
        self.courseID = ""  # the course ID of the course
        self.title = ""  # the title of the course
        self.description = ""  # the description of the course
        self.content = ""  # the content of the course
        # the time stamp (in string format) which the course is created at
        self.created_at = ""
        self.image_link = ""  # the image of the course
        self.completion_percentage = 0  # the completion percentage of the course

    async def get_course_information(self, courseID: UUID, user_id: UUID) -> dict:
        """
        This function retrieves the course information from the database based on the course ID.
        This is part of the Course.
        It returns a dictionary with course title, description, image, and course content (in JSON format), and completion percentage.
        This is used in the course page to display the course information in user UI friendly way.
        """
        self.courseID = courseID

        course = await execute_sql_statement(
            """
            SELECT c.title, c.description, c.content, c.created_at, c.image_link, uc.completion_percentage
            FROM courses c
            JOIN user_courses uc ON c.course_id = uc.course_id
            WHERE c.course_id = %s AND uc.user_id = %s;
            """,
            (self.courseID, user_id),
            fetch="all"
        )
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course with ID {self.courseID} does not exist or has not been started by the user."
            )
        self.title = course[0][0]  # title
        self.description = course[0][1]  # description
        self.content = loads(course[0][2])  # content JSON string
        self.created_at = course[0][3]  # datetime
        self.image_link = course[0][4]  # image URL
        self.completion_percentage = course[0][5]  # completion

        return {
            "title": self.title,
            "description": self.description,
            "image_link": self.image_link,
            "content": self.content,
            "created_at": self.created_at,
            "completion_percentage": self.completion_percentage
        }

    async def create_course(self, title: str, description: str, content: str, image_link: str, created_at: str | None = None) -> str:
        """
        This function creates a new course based on the information to it, these information include:
            * title of course
            * description of course
            * content of course in JSON format
            * created at time stamp of course (or if left blank, is current time)
            * the image that the course shows for previewing

        It then adds this new course to the database, so we can fetch it using self.get_course_information later.

        This is part of the Course.
        """

        if not title or not title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Course title cannot be empty."
            )
        if len(title) > 150:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Course title must be 150 characters or fewer."
            )
        if not description or not description.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Course description cannot be empty."
            )
        if len(description) > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Course description must be 500 characters or fewer."
            )
        if not content or not content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Course content cannot be empty."
            )
        if not image_link or not image_link.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image link cannot be empty."
            )
        image_regex = r"(https?:\/\/[^\s]+?\.(?:png|jpg|jpeg|gif|bmp|webp|svg|tiff|tif|ico|avif|apng))"

        # regex source: https://stackoverflow.com/questions/4098415/use-regex-to-get-image-url-in-html-js
        if not match(image_regex, image_link.strip(), IGNORECASE):
            # the regex has been modified by me to fit in my project by rewriting the SQL statement into Python SQL statement format from JavaScript
            # then, I added more image formats so the user can add any user format as required.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image link must be a valid URL to an image."
            )

        if created_at:
            try:
                datetime.fromisoformat(created_at)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid created_at timestamp. Must be ISO format."
                )

        else:
            created_at = datetime.now().isoformat()

        """
        Everything above this piece of code is input validation, checking if the inputs are correct. 
        This ensures that data integrity is kept. 
        """
        try:
            content_str = dumps(content)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid content structure for course module content."
            )

        """
        Currently, course content is stored as a JSON string in the database.
        We convert the content (which is a list of courseModuleModel) to a JSON string using json.dumps() before storing it in the database.
        This allows us to easily retrieve and parse the content back into its original structure when needed.
        Each courseModuleModel contains a module title and a list of lessons, where each lesson has a title and content.
        This means that the content structure would be like this:

        [
            {
                "module_title": "Module 1",
                "lessons": [
                    {
                        "title": "Lesson 1",
                        "type": "text",
                        "content": "Some explanation here."
                    },
                    {
                        "title": "Lesson 2",
                        "type": "code",
                        "language": "JavaScript",
                        "content": "const btn = document.createElement('button'); ..."
                    },
                    {
                        "title": "Lesson 3",
                        "type": "quiz",
                        "question": "Example question?",
                        "options": ["A", "B", "C"],
                        "answer": "A"
                    }
                ]
            },
            {
                "module_title": "Module 2",
                "lessons": [
                    {
                        "title": "Lesson 1",
                        "type": "image",
                        "content": "https://example.com/image.png"
                    },
                    {
                        "title": "Lesson 2",
                        "type": "video",
                        "content": "https://www.youtube.com/embed/example"
                    }
                ]
            }
        ]

        Each module can have multiple lessons, and each lesson has its own title and content, with videos, code exercises, quizzes, etc.
        Each code exercise contains the programming language (under key value of language in the JSON of the )
        This is not a very efficient way to store course content, but it works for the purpose of this NEA project, as it is abstracted a lot as we cannot create courses content.  
        

        Currently, course content is made manually, and dropped into the content already packaged in JSON format here - maybe in a future prototype, we can change this so it automatically creates course content in a JSON administrator UI friendly way. 
        But this is not an essential feature, as the course website is designed for users, not administrators, and will not be added in this project.


        DECLARATION: I used artificial intelligence (Gemini 3 and ChatGPT-5) exclusively to generate course content in the required structure and to pro-duce this declaration. 
        DECLARATION: AI was not used for any other aspect of this NEA. 
        DECLARATION: Its use was limited to these areas because the focus of the project is the implementation of course parsing and the course website, not the creation of course material.
        DECLARATION: My chat history is the following: https://gemini.google.com/share/4efb50e7b65a and https://chatgpt.com/share/69275611-5480-800b-b66e-84f0642925a5 


        """
        self.title = title
        self.description = description
        self.content = content_str
        self.image_link = image_link

        try:
            courseID = await execute_sql_statement("""INSERT INTO courses (title, description, content, image_link, created_at) VALUES (%s, %s, %s, %s, %s) 
                                        RETURNING course_id;""",
                                                   (self.title, self.description, self.content, self.image_link, created_at), fetch='one')
            if not courseID:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail="Course could not be added to the database.")
            # return the course ID of the newly created course
            return str(courseID[0])
        except Exception as exception:
            debug("Error caught at creating course:", str(exception))

            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to create new course")


course_router = APIRouter(prefix="/courses", tags=["Course page"])


@course_router.post("/get_course_info")
async def get_course_information_wrapper(data: getCourseInformationModel,
                                         user: User = Depends(check_user_authenticated_dependency)):
    """
    This function is a wrapper for retrieving course information via the backend API so that the frontend can access it.
    It checks if the user is authenticated and retrieves course information based on the course ID.
    The API route will be hosted at `host.com/course/<courseID>`.
    """
    user_id = await user.get_user_id()
    courseID = data.courseID
    course = Course()
    course_information = await course.get_course_information(courseID=courseID, user_id=user_id)
    course_information['success'] = True
    return course_information


@course_router.post("/create_new_course")
async def create_new_course_wrapper(data: createCourseModel,
                                    user: User = Depends(check_user_authenticated_dependency)):
    title = data.title
    description = data.description
    content = data.content
    image_link = data.image_link
    created_at = data.created_at
    course = Course()
    courseID = await course.create_course(title=title, description=description, content=content, image_link=image_link, created_at=created_at)
    return {"success": True, "course_id": str(courseID), "message": "Successfully created new course!"}
