import os
from dotenv import load_dotenv
import anthropic
from time import sleep
from typing import List, Dict
import requests
import yaml
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, Response, stream_with_context

load_dotenv()

BRAVE_API_KEY = os.environ.get('BRAVE_API_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)
    ANSWER_PROMPT = config['ANSWER_PROMPT']

app = Flask(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

@app.route("/")
def index():
    # Home page
    return render_template("index.html")

def stream_response(query: str):
    unique_urls = set()
    full_results = []

    yield (f"Searching for {query}...\n")
    yield ("\n")

    search_results = get_search_results(query)
    for search_result in search_results:
        if search_result["url"] not in unique_urls:
            yield (f"Reading {search_result['title']}\n")
            unique_urls.add(search_result["url"])
            search_result["content"] = get_url_content(search_result["url"])
            search_result["id"] = len(full_results) + 1
            full_results.append(search_result)

    yield from generate_response(query, full_results)

@app.route("/ask", methods=["POST"])
def ask():
    # Ask page (takes a query and returns a response)
    query = request.json["query"]
    unique_urls = set()
    full_results = []

    search_results = get_search_results(query)
    for search_result in search_results:
        if search_result["url"] not in unique_urls:
            print(f"Reading {search_result['title']}")
            unique_urls.add(search_result["url"])
            search_result["content"] = get_url_content(search_result["url"])
            search_result["id"] = len(full_results) + 1
            full_results.append(search_result)

    return Response(
        stream_with_context(stream_response(query)), content_type="text/plain"
    )

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

# def get_url_content(url: str) -> str:
#     # Extract content from a URL using newspaper
#     article = newspaper.Article(url)
#     try:
#         article.download()
#         article.parse()
#     except newspaper.article.ArticleException:
#         return ""
#     return article.text or ""

def get_url_content(url: str) -> str:
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract text from the parsed HTML
        # This will get all text from the page, you might want to refine this based on your needs
        text = soup.get_text(separator=' ', strip=True)

        return text
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching URL content: {e}")
        return ""


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
            yield (text)

    yield ("\n")
    yield ("Sources:\n")
    for result in results:
        yield (f"{result['id']}. {result['title']} ({result['url']})\n")