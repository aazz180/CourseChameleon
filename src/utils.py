# utils.py
# Zhi Zeng
# Candidate Number: 6888
# Prototype 2

from src.startup import get_pool
"""
The code above is importing libraries, required in this file. 
"""


async def execute_sql_statement(sql_statement: str, params: tuple, fetch: str = None) -> str | list | None:
    """
    This function executes a SQL statement using a connection pool, and returns the result of the SQL statement.
    It does this safely and closes the connection to the connection pool afterwards.
    This function is really here to assume modular design, as I do not need to have duplicate pieces of code to do SQL statements.

    This is a utility function and used in other sections of the back-end.
    """

    async with get_pool().connection() as conn:  # create a new pool connection for communication with backend
        async with conn.cursor() as cur:  # create a database cursor
            # execute the SQL statement
            await cur.execute(sql_statement, params)
            if fetch == "one":  # if the fetch query is one, we can assume that we only want one output for the SQL statement
                result = await cur.fetchone()  # fetches one output
                if isinstance(result, tuple):  # checks if tuple
                    # fetches the first element of the output from SQL statement
                    result = result[0]
                return result  # returns it back to the statement
            elif fetch == "all":  # if fetch query is "all", we assume that the program wants to have all outputs of the SQL statement
                # TODO: make this piece of code work so that we can just call it and it fetches the row
                # as currently to get more than one response per row in the output query, we have to do result[0][number]
                # it does work, but is suboptimal code
                return await cur.fetchall()  # return an array of the information
            return None  # if we get for fetch, we return no response as the user is not expecting a response from their SQL statement


def insertion_sort_reverse(array: list, key: str) -> list:
    """
    This function sorts a list of dictionaries in descending order based on a specified key using an insertion sort.
    This function requires:
        * the unsorted array
        * the key to sort by
    It is used to sort the courses by their completion percentage in descending order in the recommendation system.
    """

    for i in range(1, len(array)):
        current_value = array[i]
        j = i - 1
        while j >= 0 and current_value[key] > array[j][key]:
            array[j + 1] = array[j]
            j -= 1
        array[j + 1] = current_value
    return array
