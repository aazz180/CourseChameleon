# telemetry.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from fastapi import HTTPException, status, Depends, APIRouter
from pydantic import BaseModel
from src.utils import execute_sql_statement
from src.login import check_user_authenticated_dependency, User
from uuid import UUID


class postTelemetryAPIModel(BaseModel):
    courseID: UUID
    event: str
    progress: int = 0
    questions_correct: int = 0
    questions_incorrect: int = 0


telemetry_router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@telemetry_router.post("/postTelemetryAPI")
async def postTelemetryAPI(data: postTelemetryAPIModel,
                           user: User = Depends(check_user_authenticated_dependency)):
    """
    This function is backend code that serves as a wrapper for sending telemetry data to the backend.
    It is designed to be used in a context where telemetry data needs to be sent from the frontend to the backend via an API.
    This API route will be hosted for example in `host.com/telemetry`.
    Then depending on the event of the telemetry data, we add custom weights to the tags of the course.
    This function hooks into the selected user interactions:
    ·	Course viewed -> +1 weight
    ·	If the course has been started -> +2 weight
    ·	The progress of the course -> this is calculated by (progress done/100) * 4 weight
    ·	If the course is completed -> if course is completed , then 4 weight, else 0.
    ·	Questions answered correctly -> this is used to show the summary of the course
    ·	Questions answered incorrectly -> this is used to show the summary of the course

    """
    course_id = data.courseID
    event = data.event
    user_id = user.user_id
    if event not in ["course_viewed", "course_completed", "course_started", "course_progress_updated", "course_questions_correct", "course_questions_incorrect"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid telemetry event data type"
        )

    """
    ·	Course viewed -> +1 weight
    ·	If the course has been started -> +2 weight
    ·	The progress of the course -> this is calculated by (progress done/100) * 4 weight
    ·	If the course is completed -> if course is completed , then 4 weight, else 0.
    """
    weight = 0
    if event == "course_viewed":
        weight = 1
    elif event == "course_started":
        weight = 2
        await execute_sql_statement(
            """
            INSERT INTO user_courses (user_id, course_id, completion_percentage, last_updated)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id, course_id)
            DO UPDATE SET 
                completion_percentage = CASE 
                    WHEN user_courses.completion_percentage IS NULL THEN EXCLUDED.completion_percentage
                    ELSE user_courses.completion_percentage
                END,
                last_updated = NOW();
            """,
            (user_id, course_id, data.progress)
        )
    # check if the telemetry request content is about progress course updating
    elif event == "course_progress_updated":
        if data.progress is not None:
            weight = (data.progress / 100) * 4

        await execute_sql_statement(
            """
            INSERT INTO user_courses (user_id, course_id, completion_percentage, last_updated)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id, course_id)
            DO UPDATE SET completion_percentage = EXCLUDED.completion_percentage,
                          last_updated = NOW();
            """,
            (user_id, course_id, data.progress, )
        )
    elif event == "course_questions_correct":
        await execute_sql_statement(
            """
            INSERT INTO user_courses (user_id, course_id, questions_correct, last_updated)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id, course_id)
            DO UPDATE SET 
                questions_correct = COALESCE(user_courses.questions_correct, 0) + 1,
                last_updated = NOW();
            """,
            (user_id, course_id, data.questions_correct, )
        )
    elif event == "course_questions_incorrect":
        await execute_sql_statement(
            """
            INSERT INTO user_courses (user_id, course_id, questions_wrong, last_updated)
            VALUES (%s, %s, 1, NOW())
            ON CONFLICT (user_id, course_id)
            DO UPDATE SET 
                questions_wrong = COALESCE(user_courses.questions_wrong, 0) + 1,
                last_updated = NOW();
            """,
            (user_id, course_id)
        )

    elif event == "course_completed":
        weight = 4.0
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect telemetry event - this should not happen."
        )

    tags = await execute_sql_statement(
        "SELECT tag_id, weight FROM course_tags WHERE course_id = %s",
        (course_id,),
        fetch="all"
    )

    if not tags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid course ID or no tags associated with this course."
        )

    for tag_id, tag_weight in tags:
        new_weight = tag_weight + weight
        await execute_sql_statement(
            """
            UPDATE course_tags
            SET weight = %s
            WHERE course_id = %s AND tag_id = %s
            """,
            (new_weight, course_id, tag_id)
        )

    return {"status": "success", "message": "Telemetry recorded and weights updated."}
