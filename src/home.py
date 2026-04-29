
# home.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from fastapi import APIRouter, Depends
from src.login import check_user_authenticated_dependency, User
from src.recommendation_system import RecommendationSystem
from src.utils import execute_sql_statement
from pydantic import BaseModel
from uuid import UUID
from logging import debug


class getHomePageRecommendationsModel(BaseModel):
    # create a model that checks that get recommendations for home is correct by comparing the request has the following: 
    amount: int = 10


home_router = APIRouter(prefix="/home", tags=["Home page"])


@home_router.post("/getCourseRecommendations")
async def getCourseRecommendations(data: getHomePageRecommendationsModel,
                                   user: User = Depends(check_user_authenticated_dependency)):
    """
    This function retrieves course recommendations for the home page based on the user's preferences and history.
    If the user is new (without previous courses done), this function also generates some random courses for the user.
    It returns a JSON response with a list of recommended courses.
    """
    user_id: UUID = await user.get_user_id()
    amount = data.amount
    recommender = RecommendationSystem(user_id)
    # generate=True to ensure user courses are fetched
    recommendations = await recommender.init_courses(generate=True)
    # i rewrote this function to ensure that if the user has no courses, it generates some recommendations anyway
    debug(recommendations)
    # this is really inefficient code but it works for now 
    if type(recommendations) is list and len(recommendations) > 0: # if the result of the recommendations is a list
        # then we can be sure that the generate value is true (from init_courses) and that there was 0 recommendations because
        # the user's account has not done any courses
        # therefore, we just generate some random courses for them
        # so they can start up courses and start courses for course recommendation 

        return {"success": True, "recommendations": recommendations}

    recommendations = await recommender.get_course_recommendations(amount)

    return {"success": True, "recommendations": recommendations}


@home_router.get("/previouslyStartedCourses")
async def previouslyStartedCourses(user: User = Depends(check_user_authenticated_dependency)):
    """
    This function retrieves courses that the user has previously started but not completed.
    This is used for the home page's previously started section, and is an API wrapper.
    It returns a JSON response with a list of these courses.
    """
    user_id: UUID = await user.get_user_id()
    query = """
        SELECT c.course_id, c.title, c.description, c.content, c.created_at, c.image_link, uc.completion_percentage
        FROM courses c
        JOIN user_courses uc ON c.course_id = uc.course_id
        WHERE uc.user_id = %s AND uc.completion_percentage < 100
        ORDER BY uc.completion_percentage ASC
        LIMIT 4;
    """ # a SQL statement that fetches the completion percentage of every course started by the user
    # fetches course id, title, description, content, created at, course image link of the course
    # it joins the user_courses and courses tables together using a relationship with the foreign key
    # being course_id and user_id
    # we limit the amount of courses done to 4 as the user may have started a lot of courses
    # and  we do not wish to overwhelm the frontend UI with tens and tens of courses
    # as this would be not user friendly to navigate
    # we also order the courses by ascending on the completion_percentage as the higher the completion_percentage
    # the more likely the user is completing the course currently
    # so we present it to them to complete

    results: list = await execute_sql_statement(query, (user_id,), fetch="all")
    courses = []
    for row in results:
        course = {
            "course_id": row[0],
            "title": row[1],
            "description": row[2],
            "content": row[3],
            "created_at": row[4],
            "image_link": row[5],
            "completion_percentage": row[6],
        }
        courses.append(course)
    return {"success": True, "courses": courses}
