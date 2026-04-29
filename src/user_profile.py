
# profile.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from fastapi import APIRouter, Depends, HTTPException
from src.login import check_user_authenticated_dependency, User
from src.recommendation_system import RecommendationSystem
from uuid import UUID


profile_router = APIRouter(prefix="/profile", tags=["Profile page"])


@profile_router.get("/get_user_information")
async def get_user_information(user: User = Depends(check_user_authenticated_dependency)):
    """
    This function retrieves the user's information by checking the JWT token.
    It returns a JSON response with the user's information if the token is valid.
    """

    user_info = await user.get_user_information() 
    # this is done to fetch the user information for display in the front-end profile page
    # and is used to fetch the following information from the user
    # {
    #         "user_id": user's user_id
    #         "email": self.email,
    #         "name": self.name,
    #         "created_at": str(self.created_at)
    # }
    # and shows it to the user in the profile page  
    return {"success": True, "user_info": user_info}


@profile_router.get("/get_all_tags")
async def get_all_tags(user: User = Depends(check_user_authenticated_dependency)):
    """
    This function retrieves all unique tags from the courses in the database.
    This API route can be called in the future prototype as to allow users to change their tags as required.
    It returns a JSON response with a list of unique tags.
    """
    user_id: UUID = await user.get_user_id()
    recommender = RecommendationSystem(user_id=user_id)
    await recommender.init_courses()
    tags = await recommender.get_all_tags()
    return {"success": True, "tags": tags}

@profile_router.post("/update_user_tags")
async def update_user_tags(user: User = Depends(check_user_authenticated_dependency)):
    user_id: UUID = await user.get_user_id()
    recommender = RecommendationSystem(user_id=user_id)
    await recommender.init_courses()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This API route has not been implemented!"
    )