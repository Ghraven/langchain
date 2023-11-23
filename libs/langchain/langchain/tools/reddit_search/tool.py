
"""Tool for the Reddit search API."""

from typing import Optional, Type

from langchain.callbacks.manager import CallbackManagerForToolRun
from langchain.tools.base import BaseTool
from langchain.pydantic_v1 import Field, BaseModel
from langchain.utilities.reddit_search import RedditSearchAPIWrapper

class RedditSearchSchema(BaseModel):
    query: str = Field(description="should be query string that post title should contain, or '*' if anything is allowed.")
    sort: str = Field(description='should be sort method, which is one of: "relevance", "hot", "top", "new", or "comments".')
    time_filter: str = Field(description='should be time period to filter by, which is one of "all", "day", "hour", "month", "week", or "year"')
    subreddit: str = Field(description='should be name of subreddit, like "all" for r/all')
    limit: str = Field(description='a positive integer indicating the maximum number of results to return')
    
class RedditSearchRun(BaseTool):
    """Tool that queries for posts on a subreddit."""

    name: str = "reddit_search"
    description: str = (
        "A tool that searches for posts on Reddit.",
        "Useful when you need to know post information on a subreddit, like post titles, text, score, and authors.",
    )
    api_wrapper: RedditSearchAPIWrapper = Field(default_factory=RedditSearchAPIWrapper)
    args_schema: Type[BaseModel] = RedditSearchSchema

    def _run(self,
        query: str,
        sort: str, 
        time_filter: str,
        subreddit: str,
        limit: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        return self.api_wrapper.run(
            query=query,
            sort=sort,
            time_filter=time_filter,
            subreddit=subreddit,
            limit=int(limit)
        )

