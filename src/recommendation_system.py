# recommendation_system.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from pydantic import BaseModel
from src.login import check_user_authenticated_dependency, User
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from src.utils import execute_sql_statement, insertion_sort_reverse
from fastapi import HTTPException, Depends, status
from logging import debug


class RecommendationSystem:

    def __init__(self, user_id) -> None: # constructor method that is created and ran at first to create
        self.user_id: UUID = user_id # private attributes that can be only accessed in this current initialisation of the class
        self.user_courses: list = [] # this assures that other classes cannot access this values when not needed
        self.total_courses: list = []
        self.user_profile: dict = {}

    async def init_courses(self, generate: bool = False, amount: int = 10) -> None:
        """
        This function is a mixed getter method for both self.get_total_user_courses() and self.create_total_courses_list().
        It requires the parameters: 
        * generate (a boolean value that if True -> that the user has not done any courses before -> false, we assume that the user has done courses before).
        * amount -> the amount of courses to be recommended / generated -> depending on generate boolean
        
        It also checks if the return values of the self.get_total_user_courses() is of a type list or bool.
        If it is of list data type and generate is True, then we can assume that the user has not done any courses before, and then, this subroutine then generates some courses randomly for the user to do.
        If it is not of a list type, this subroutine is then does not return anything but only runs self.create_total_courses_list().
        Self.create_total_courses_list() then initialises and creates the total list of courses in the database. 
        This is done so that later the user can fetch their recommended courses via the ranking of the Jaccard similarity algorithm (explained later). 

        TODO: Edit this subroutine so that it does not call self.create_total_courses_list() each time, the user sends a request for their recommended courses.
        TODO: This is not efficient, as the backend must send a request to the backend database to refresh all the total courses in the database, each time that the user sends a request for recommendation. 
        TODO: This can be more optimised in a future prototype, if the backend fetches all the total courses of the backend at startup, instead as currently.
        TODO: This would completely decrease the runtime and pauses between recommendation for the user, and decrease the space complexity for this function. 

        This function should be re-written in future prototypes if given time and it currently works, but is not code modular.
        It is in yellow section, as to indicate possible re-write in a future prototype, as this approach is not modular enough for this project's codebase.
        This function is public and can be accessed from outside the RecommendationSystem class.
        """
        total_user_courses = await self.get_total_user_courses(generate=generate, amount=amount) # create the user_courses list
        if type(total_user_courses) is list and generate is True: # if the return of the total_users_courses is of a list type
            self.user_courses = total_user_courses # then we know that the user has not done any courses before so we recommend them some
            return total_user_courses
        await self.create_total_courses_list()

    async def get_total_user_courses(self, generate: bool = False, amount: int = 10) -> bool | int:
        """
        This function retrieves all courses that the user has completed from the database and creates the self.user_courses list, given that generate boolean value parameter is False.
        If the parameter value of the generate boolean is True, that this function serves an alternative purpose.
        This is due to that the user has not done any courses, therefore, the self.user_courses list would be empty. If the courses done by user list is empty, no course can be generated - this causes an error.
        This error is fixed by the inclusion of adding a feature of generating a list of *amount* length of random courses for the user to do.

        However, due to this nature, this function should be re-written in future prototypes if given time and it currently works, but is not code modular.
        It is in yellow, as to indicate possible re-write in the future. 
        It is a private function and can only be accessed within the RecommendationSystem class.
        """
        courses = await execute_sql_statement(
            """
            SELECT c.course_id AS id, c.title AS name
            FROM courses c
            JOIN user_courses uc ON c.course_id = uc.course_id
            WHERE uc.user_id = %s;
            """,
            (self.user_id,),
            fetch="all"
        ) # run a SQL query to get all the courses that the user has done 

        self.user_courses = [{"id": row[0], "name": row[1]} for row in courses]
        # changes the format of the self.user_courses to be like
        """
        [
            {"id": 1, "name": "Introduction to Python"},
            {"id": 2, "name": "Advanced SQL"}
        ]
        """ # this is a dictionary format

        for course in self.user_courses: # iterate through course in the user's done courses
            course_tags = await execute_sql_statement(
                """
                SELECT t.tag_name, ct.weight
                FROM course_tags ct
                JOIN tags t ON ct.tag_id = t.tag_id
                WHERE ct.course_id = %s;
                """,
                (course["id"],),
                fetch="all"
            ) # run SQL statement to get the tags and weights of each course
            course["tags"] = {row[0]: row[1]
                              for row in course_tags if len(row) == 2}

            # this then adds a "tags" key to each course dictionary in self.user_courses
            # the value of the "tags" key is a dictionary of tags and their weights
            # for example, after this loop, self.user_courses might look like:
            """
            [
                {"id": 1, "name": "Introduction to Python", "tags": {"python": 5, "programming": 3}},
                {"id": 2, "name": "Advanced SQL", "tags": {"sql": 4, "database": 2}}
            ]
            """
        if generate and len(self.user_courses) == 0: # check if the generate value is True and the user has no done courses
            # if yes, then we generate some random courses from the course database for the user to do
            query = """
                SELECT course_id, title
                FROM courses
                ORDER BY RANDOM()
                LIMIT %s;
            """ # create a SQL statement that we execute to generate amount random of courses to give to the user in the frontend 
            results: list = await execute_sql_statement(query, (amount,), fetch="all")  # execute the SQL command
            # however, this returns a list of course ids and their titles, and for this to mean anything to the frontend
            # it must contain also the tags and their weight -> for processing
            recommendations = [] # thus, we create a list for these recommendations 
            for row in results: # we iterate through course
                course_id = row[0] # get the course id so we can use it as a foreign key to get the course tag names and their weights
                title = row[1] # get the course title

                # fetch tags for this course using the course id as the foreign key to join these databases together
                tag_rows = await execute_sql_statement(
                    """
                    SELECT t.tag_name, ct.weight
                    FROM course_tags ct
                    JOIN tags t ON ct.tag_id = t.tag_id
                    WHERE ct.course_id = %s;
                    """,
                    (course_id,),
                    fetch="all"
                ) 
                # this ends up generating a list of tags for each course
                # and these tags might be duplicated
                # for the recommendation system to process this data, we must find the highest weight of each tag and put it as the highest tag
                # the code below does this for each tag in the course tags
                tags = {tag_name: weight for tag_name,
                        weight in tag_rows if len(tag_name) > 0}

                recommendations.append({ # we append this new data to our recommendation list, so that the frontend can handle it appropriately for all needed tags
                    "id": course_id,
                    "name": title,
                    "tags": tags
                })

            return recommendations # return these recommendations so that the frontend can tell the user which course they start with
            # this return is a list and tells the self.init_courses() that the user has no courses to be done, and to just recommend these courses produced
            
            # TODO: refractor this entire code block to more modular
        if len(self.user_courses) == 0: # this shouldn't happen but this is validation just in case self.user_courses is empty for some reason
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="No user courses found. Please complete some courses first.")
        return True # return a boolean value

    async def create_total_courses_list(self) -> None:
        """
        This function retrieves all courses from the database and tags them.
        It populates the self.total_courses list with the courses and their tags in a dictionary format.
        The purpose of populating these courses is that, later in the process of recommendation engine, this list will be used in course comparison using Jaccard similarity for the most likely course for users to do.
        This function is private and can only be accessed within the RecommendationSystem class.
        """
        course_info = await execute_sql_statement(
            """
            SELECT c.course_id, c.title, t.tag_name, ct.weight
            FROM courses c
            LEFT JOIN course_tags ct ON c.course_id = ct.course_id
            LEFT JOIN tags t ON ct.tag_id = t.tag_id;
            """,
            (),
            fetch="all"
        ) # fetch every course information so that we compile a list of them

        courses = {} # create a dictionary for these courses - when designing the algorithm of the backend in the pseudocode section of my project
        # I used a dictionary instead of multiple 3D arrays, so to go with my pseudocode, I will be also using a dictionary as well here

        for course_id, title, tag_name, weight in course_info: # we iterate through each course and
            # insert the data from the course_info to courses so we can use it later
            if course_id not in courses:
                courses[course_id] = {"id": course_id, "name": title, "tags": {}}
            if tag_name:  # in case a course has no tags
                courses[course_id]["tags"][tag_name.lower()] = weight
        # at the end of the for loop, courses looks like this:
        """
        {
        1: {"id": 1, "name": "Intro to Python", "tags": {"beginner": 0.8, "logic": 0.5}},
        2: {"id": 2, "name": "AI Ethics", "tags": {"ethics": 1.0, "ai": 0.9}}
        }
        """
        self.total_courses = list(courses.values()) # get all the values of courses and put it into self.total_courses as a list
        # so self.total_courses looks like this at the end:
        """
        [
        {"id": 1, "name": "Intro to Python", "tags": {"beginner": 0.8, "logic": 0.5}},
        {"id": 2, "name": "AI Ethics", "tags": {"ethics": 1.0, "ai": 0.9}}
        ]
        """
        # TODO: optimise this if possible -> it works but it feels very not optimised
        # TODO: technically, the time complexity of this subroutine is O(n), but it feels very sketchy

        if not self.total_courses: # validation 
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="No courses found in the database.")

    async def create_user_profile(self) -> None:
        """
        This function creates and populates self.user_profile (a dictionary) with the user's done courses and the weighted tags of each course done.
        This subroutine is needed as later, we need to use self.user_profile in self.calculate_weighted_jaccard_similarity().
        This is done so that we can get all the course tags of the user for the Jaccard similarity recommendation to work.

        This function is a private function and can only be accessed within the RecommendationSystem class.
        """
        for course in self.user_courses: # we iterate through each course that the user has done
            for tag, weight in course["tags"].items(): # fetch the weight and tags of each course
                if tag not in self.user_profile: # check if the tag is not already in the self.user_profile
                    self.user_profile[tag] = weight # if it is not, then, we add the tag weight to the self.user_profile
                else: # if it is not in the self.user_profile
                    self.user_profile[tag] += weight # then we add the weight of the tag to the weight in the user_profile
                    # we add the weight of previous weight to the new weight, as in general, based on the Jaccard similarity, if the user sees more of courses
                    # with a tag, they have a higher interest in courses with this tag (e.g. they are doing a course and this will increase the weight of courses that are similar to it)

        
        if len(self.user_profile) == 0: # validation 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="No user profile found. Please complete some courses first.")

    async def calculate_weighted_jaccard_similarity(self, course_tags: dict) -> float:
        """
        This function computes the weighted Jaccard similarity between the user profile (current user) and the current course's tags.
        It returns a similarity score between 0 and 1, where 0 means no similarity and 1 means perfect similarity.
        It is used to find the similarity between the user's profile and the courses' tags.
        The function uses the formula:
        similarity = (sum of minimum weights for each tag) / (sum of maximum weights for each tag)
        where the minimum and maximum weights are taken from the user profile and the total courses' tags.

        The function iterates through all tags in the user profile and total courses, calculating the numerator and denominator for the similarity score.
        The function returns the similarity score as a float.
        This similarity score is used to rank the courses based on their relevance to the user's profile (with the highest score being the most relevant).
        The most relevant courses are then recommended to the user.
        This function is private and can only be accessed within the RecommendationSystem class.
        """

        numerator: float = 0.0 # this is the float and the numerator of the Jaccard similarity equation ((sum of minimum weights for each tag) )) -> its a float because this is the numerator is of a real number
        denominator: float = 0.0 # likewise as the numerator, but this is is denominator instead ((sum of maximum weights for each tag))
        # numerator is / by denominator to find the Jaccard similarity score of a course. 

        all_tags = set(self.user_profile.keys()) | set(course_tags.keys()) # get every tag in the both course tags and the tags of the user profile that exists in either of them - and we de duplicate them
        # we do this to get all possible tags in the database so we can iterate through each of them

        for tag in all_tags: # we iterate through each tag in all_tags (all tags in user_profile and the course_tags of the course)
            user_tag_weight = self.user_profile.get(tag, 0) # get the weight of the tag from the user's side (the weight of the tag for the user)
            course_tag_weight = course_tags.get(tag, 0) # get the weight of tag from the database

            numerator += min(user_tag_weight, course_tag_weight) # add the smaller of the weights of the user and the course 
            denominator += max(user_tag_weight, course_tag_weight) # # add the largest of the weights of the user and the course 
        # at the end of this piece of code, currently the numerator variable is sum of minimum weights for each tag
        # and the denominator variable is the sum of maximum weights for each tag in the course
        # we can divide these to find the jaccard similarity score

        if denominator == 0: # in case, both course weights and user tag weights are 0 -> meaning that both have no weights for the course tag
            # if we divide the numerator, then it would give an MATH error because we cannot divide a value by 0
            # as the denominator would be 0 then, if both user and course weights are 0 (as the denominator is the maximum value of both of them)
            return 0.0

        return numerator / denominator # return the jaccard similarity value by diving the numerator and the denominator, as a float (real)

    async def recommend_next_course_from_json(self, amount: int) -> list:
        """
        This function recommends the next course by doing a reverse insertion sort keyed to the Jaccard similarity of each course (not done by the user) against an array of courses that the user has done.
        This ends up finding the most optimal courses that the user should do and this subroutine then returns it to be recommended to the user.
        These optimal courses end up fulfilling the following requirements: 
        * the user has not done these courses before
        * they have the highest possible Jaccard similarity
        This function is private and can only be accessed within the RecommendationSystem class.
        """
        if not self.user_courses or not self.total_courses or amount <= 0: # validation just in case both self.user_courses and self.total_courses are empty
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="User courses or total courses are empty or amount is less than or equal to 0.")
        await self.create_user_profile() # we create the user profile (dictionary) so that we can do the jaccard similarity later
        user_completed_ids = [] # an array of the all the courses ids for all the courses that the user has done 
        for course in self.user_courses: # add these courses ids to the array by iterating through the dictionary and getting all the ids of every course and adding it to the array 
            user_completed_ids.append(course["id"]) 
        # so at the end of this piece of code, user_completed_ids looks like 
        # [id of course 1 completed by user, id of course 2 completed by user,..., id of last course completed by the user]
        # we use this array later to ensure that the courses that being recommended to the user has not been done by them before.
        # as we do not want the user to keep doing the same courses infinitely, as if the user has done a course before, the jaccard score between these courses would be the highest
        # and the user would be kept recommended the same course forever -> they would not continue their learning journey, 

        scored_courses = [] # an 2D array of all the courses in the database and the similarity scores of each course compared to the user's previously done courses
        for course in self.total_courses: # iterate through each of the courses in the backend database
            if course["id"] not in user_completed_ids: # check to ensure that the user has not done any of the courses to be recommended before
                # as if done before, the done courses would have the highest similarity score -> forcing the user to redo the same courses indefinitely
                course_tags = course["tags"] # get all the tags of the current coursed being checked
                course_similarity = await self.calculate_weighted_jaccard_similarity(course_tags) # do the jaccard similarity on the course and it's tags with the user's tags -> to get a jaccard similarity score
                scored_courses.append(
                    {"course": course, "similarity": course_similarity}) 
                    # append it the course and the similarity score so we can do an inverse insertion sort later to get recommendations

        # at the end of this loop ,scored_courses looks like:
        # [
        #   {
        #     "course": {
        #        "id": 2,
        #        "name": "AI Ethics",
        #        "tags": {
        #           "ethics": 1.0,
        #           "ai": 0.9
        #        }
        #     },
        #     "similarity": 0.64 # similarity score
        #   },
        #   ...
        # ]

        scored_courses = insertion_sort_reverse(scored_courses, "similarity") # now we do an reverse insertion sort on these courses
        # so now the courses are sorted based on their similarity score in an inverse fashion
        # we do this because insertion sort is the most optimal in both space complexity and time complexity for my solution
        # and also because if we use a ascending insertion sort and not an insertion sort version, we wouldn't get the most optimal courses
        # for example:
        # similarity scores unsorted: [0.7, 0.1, 0.5]
        # similarity scores sorted in the ascending order: [0.1, 0.5, 0.7] 
        # similarity scores sorted in descending order: [0.7, 0.5, 0.1]
        # thus, to find the most optimal recommendations, we must sort in a descending insertion sort in such a manner that similarity scores with the highest value is the highest
    
        recommendations = [] # create an array for the course recommendations to be recommended back to the user and returned
        for k in range(0, min(amount, len(scored_courses))):  # we iterate through the recommended courses and collate *amount* number into an array
            # to be passed to the user
            if k >= len(scored_courses):
                break
            recommendations.append(scored_courses[k]["course"])

        # TODO: there must a more efficient way to create a *amount* of recommendations -> will try to improve in a future prototype if given enough time
        # TODO: maybe using slicing is more optimised -> will have to look into this more in future prototypes if given enough time.
        # TODO: this code does work however, so this is in yellow, and is of time complexity O(min(m,n))
        if len(recommendations) == 0: # validation 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="No course recommendations found. Please complete more courses to get better recommendations.")
        return recommendations # we return the array to the frontend for recommendations 

    async def get_course_recommendations(self, amount):
        """
        This function fetches and returns an array of course recommendations for the frontend home page - it is a getter method for recommend_next_course_from_json().
        This function is a public subroutine and can only be accessed within the RecommendationSystem class.
        This method does not need to be changed in future prototypes, and thus, is in green.
        """
        if amount <= 0: # validation
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Amount must be greater than 0.")

        recommendations = await self.recommend_next_course_from_json(amount) # get next recommended courses as a getter method.
        return recommendations 
    async def get_search_courses(self, tag_list: list, amount: int) -> list:
        """
        This function is a wrapper function for the substring and tagged based searching functionally of the backend as to return courses that alike to the search query.
        """
        if not tag_list or amount <= 0: # validation check
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Tags cannot be empty and amount must be greater than 0.") 
        if not self.total_courses or len(self.total_courses) == 0: # check if the total courses collected in the backend database is empty
            await self.create_total_courses_list() # if it is empty, then we collate and collect the courses from the backend database, so we can search using tags later for courses

            if not self.total_courses: # validation check
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="No courses found in the database.")
            
        recommendations = [] # we create an array for all course recommendations so that we can add all the courses
        # that are associated with the user's search query.
        substring_recommendations = await self.search_courses_by_substring(tag_list=tag_list, amount=amount) 
        # fetch all the courses that have strings that substring of the search query inside the tags in them
        tag_recommendations = await self.search_courses_by_tags(tag_list=tag_list, amount=amount)
        # fetch all the courses that have tags with the exact values as the ones in the user's search query.
        seen_ids = set() # we create a set of seen_ids so that we can not have duplicates seen course ids
        # where we add a new course id if we have not seen it before
        for course in substring_recommendations + tag_recommendations: # iterate through both substring and tag recommendations
            # and add courses with unique course ids to the our seen_ids so that later duplicates courses are skipped
            if course["id"] not in seen_ids:
                seen_ids.add(course["id"])
                recommendations.append(course) # add it to our recommendations array for the user
            if len(recommendations) == amount: # if the number of recommendations recommended to the user is above the set amount set by the subroutine, then we stop
                # extending more recommendations to the user
                break
        if len(recommendations) == 0: # validity check
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="No courses found matching the tags provided.")
        return recommendations
        

    async def search_courses_by_substring(self, tag_list: list, amount: int) -> list:
        """
        This function searches for courses based on substring matching the user's provided tag list is checked.
        If it appears anywhere inside another tag, and returns a list of the courses that matches these tags.
        This function currently uses substring matching to do this.
        """
        search_course_results = [] # create an array for the unsorted courses that were queried due to the search query 
        for course in self.total_courses: # we iterate through all the courses in the backend
            score = 0 # and we give each course a score of 0, which increments per each instance of substring of queries is inside the tags of the course
            # this is done to allow a reverse insertion sort of course recommendations based on the number of score
            for queries in tag_list:
                lower_query = queries.lower()
                for tag in course["tags"]:
                    if lower_query in (tag.lower()):
                        score += 1
            if score > 0: # if there is a substring match in the tags of the course, then we add it to the list of recommendations
                search_course_results.append({"course": course, "score": score})

        search_course_results = insertion_sort_reverse(search_course_results, "score") # does an reverse insertion sort and sorts them to find the most highest ranked recommendations, which would be the most optimal courses for the search query
        results = [] # creates an array for the top *amount* of courses to be returned to the user for their search query
        for i in range(min(amount, len(search_course_results))): # iterates through all the search query's sorted courses and finds the top *amount* of courses
            if i >= len(search_course_results):
                break
            results.append(search_course_results[i]["course"])
        return results # return these top *amount* of sorted courses back to the subroutine to be added with the tag recommendations 
                

    async def search_courses_by_tags(self, tag_list: list, amount: int) -> list:
        """
        This function searches for courses based on the provided tags (which is the search query split into tags via spaces) and returns a list of courses that match the tags.
        This function currently uses tag-based searching.
        It is used to find courses that match the user's interests based on the tags they have completed, or when they input a search query into the search engine.
        """

        search_course_results = [] # create an array for the unsorted courses that were queried due to the search query 
        for course in self.total_courses: # iterate through each course in the total courses
            score = 0 # sets a similarity score of 0 that we can edit later to check if the course is alike in tags to the tags in search query
            for tag in tag_list: # iterate through each tag in the tag list of the user's search query
                # and check if the tag is inside the tags of the user's search query
                if tag in course["tags"]:
                    # if the tag is inside the user's search query, then we add the tag's weight to the similarity score
                    score += course["tags"][tag]
            if score > 0: # once we are done iterating through the tag list of the course, then we add the course information and the similarity score
                # for sorting for recommendation later.
                search_course_results.append({"course": course, "score": score})

        search_course_results = insertion_sort_reverse(search_course_results, "score") # does an reverse insertion sort and sorts them to find the most highest ranked recommendations, which would be the most optimal courses for the search query

        results = [] # creates an array for the top *amount* of courses to be returned to the user for their search query
        for i in range(min(amount, len(search_course_results))): # iterates through all the search query's sorted courses and finds the top *amount* of courses
            if i >= len(search_course_results):
                break
            results.append(search_course_results[i]["course"])
        return results # return these top *amount* of sorted courses to the frontend


    async def get_all_tags(self) -> list:
        """
        This function retrieves all tags from the database.
        It returns a list of all tags that can be used by the user.
        This function is public and can be accessed from outside the RecommendationSystem class.
        """
        return set(self.user_profile.keys())

