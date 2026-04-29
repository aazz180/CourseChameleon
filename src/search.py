# search.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from fastapi import APIRouter, Depends, HTTPException, status
from src.login import check_user_authenticated_dependency, User
from src.recommendation_system import RecommendationSystem
from pydantic import BaseModel
from uuid import UUID
from logging import debug
"""
All the code above is for importing libraries and other components of the back-end API that this file will use.

"""


class getSearchQueryModel(BaseModel):
    # we create a pydantic base model in this piece of code
    # we verify using the base model and that the search query is of a string format.
    # if we do not have valid request format, then, this program automatically throws an exception and shows an error
    # this ensures data integrity is kept
    search_query: str
    amount: int = 10  # default amount of search results to return is 10


search_router: APIRouter = APIRouter(prefix="/search", tags=["Search page"])

@search_router.post(path="/getSearchQuery")
async def getSearchQueryAPI(data: getSearchQueryModel,
                            user: User = Depends(check_user_authenticated_dependency)):
    user_id: UUID = await user.get_user_id()
    search_query = data.search_query
    amount = data.amount
    if search_query is None or search_query.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty."
        )
    tag_list = search_query.strip().split()
    debug(f"Search query array: {tag_list}")
    recommender = RecommendationSystem(user_id=user_id)
    courses = await recommender.get_search_courses(tag_list=tag_list, amount=amount)
    if not courses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No courses found matching the search query."
        )
    return {"success": True, "courses": courses}
