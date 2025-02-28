import requests
from time import sleep
from typing import List, Dict
import newspaper3k  # alternative to beautifulsoup
import anthropic
import os

BRAVE_API_KEY = ''
ANSWER_PROMPT = ''

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def ask(query: str):
    # Given a user query, fetch search results and create a response
    pass

def get_search_results(search_query: str, limit: int = 3):
    # Search using Brave Search API
    headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY}
    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": search_query, "count": limit},
        headers=headers,
        timeout=60,
    )
    if not response.ok:
        raise Exception(f"HTTP error {response.status_code}")
    sleep(1)  # avoid Brave rate limit
    return response.json().get("web", {}).get("results")

def get_url_content(url: str) -> str:
    # Extract content from a URL using newspaper3k
    article = newspaper.Article(url)
    try:
        article.download()
        article.parse()
    except newspaper.article.ArticleException:
        return ""
    return article.text or ""

def generate_response(query: str, results: List[Dict]) -> str:
    # Format the search results
    formatted_results = "\n\n".join(
        [
            f"{result['id']}. {result['title']}\n{result['url']}\n{result['content']}"
            for result in results
        ]
    )

    # Generate a response using LLM (Anthropic) with citations
    prompt = ANSWER_PROMPT.format(QUESTION=query, SEARCH_RESULTS=formatted_results)

    # Make an API call to Anthropic (using Claude 3.5 Sonnet)
    with client.messages.stream(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1000,
        temperature=0.5,
        messages=[
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "Here is the answer: <answer>"},
        ],
        stop_sequences=["</answer>"],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print("\n\n")
    print("Sources:")
    for result in results:
        print(f"{result['id']}. {result['title']} ({result['url']})")