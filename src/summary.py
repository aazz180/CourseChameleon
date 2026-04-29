# summary.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from fastapi import APIRouter, Depends, HTTPException, status
from src.login import check_user_authenticated_dependency, User
from src.utils import execute_sql_statement
from pydantic import BaseModel
from uuid import UUID
"""
All the code above is for importing libraries and other components of the back-end API that this file will use.

"""


class getUserSummaryForACourseModel(BaseModel):
    # we create a pydantic base model in this piece of code
    # we verify using the base model and that the courseID is of a UUID format.
    # if we do not have valid request format, then, this program automatically throws an exception and shows an error
    # this ensures data integrity is kept

    courseID: UUID  # we make the courseID a UUID and verify that the request input is a UUID as required


# this creates an API router that connects to api.py which gets all the API routes of this file
summary_router: APIRouter = APIRouter(prefix="/summary", tags=["Summary page"])
# then it appends said routes to all known routes of the backend API.
# the routes in this file will have an prefix (or start with) "/summary" to be accessed by the frontend


# we create an API route that only allow POST requests to "/getSummary"
@summary_router.post("/getUserSummaryForACourse")
async def getSummaryAPI(data: getUserSummaryForACourseModel,
                        user: User = Depends(check_user_authenticated_dependency)):
    # we verify the data input from the POST request and then we verify that the user is indeed authenticated (via the check_user_authenticated_dependency).
    # we get the user_id from the check_user_authenticated_dependency and store in the user_id variable
    user_id: UUID = await user.get_user_id()
    # we get the courseID from the verified data input and store it
    courseID: UUID = data.courseID

    user_results: tuple[list] = await execute_sql_statement("""
        SELECT completion_percentage, questions_correct, questions_wrong
        FROM user_courses
        WHERE course_id = %s AND user_id = %s;
        """, (courseID, user_id,), fetch="all")

    # we get all the completion_percentage, questions done that the user has done correctly, questions that the user has done incorrectly
    # we store all this information in a tuple format

    # we check if the user_results is empty (does not exist therefore is a None)
    if not user_results:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="No summary data found for user in this course.")
    completion_percentage: str = user_results[0][0]
    questions_correct: str = user_results[0][1]
    questions_wrong: str = user_results[0][2]
    if questions_wrong == None:
        questions_wrong = str(0)
    if questions_correct == None:
        questions_correct = str(0)
    return {"success": True, 
            "completion_percentage": str(completion_percentage),
            "questions_correct": str(questions_correct),
            "questions_wrong": str(questions_wrong)}
    # we send this information to the summary page in the frontend
    # this is done to tell users about how many questions they have done right or wrong.