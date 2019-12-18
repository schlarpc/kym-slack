import functools
import json
import gzip
import sys
import base64
import urllib.request
import urllib.parse
import html.parser


class KYMParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self._next_img_is_result = False
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        element_class = attrs_dict.get("class")
        if self._next_img_is_result and tag == "img":
            image_url = attrs_dict["data-src"].replace("/masonry/", "/original/")
            self.images.append(image_url)
        self._next_img_is_result = element_class == "photo"


@functools.lru_cache(maxsize=1)
def get_current_user_agent():
    user_agents_url = (
        "https://github.com/intoli/user-agents/raw/master/src/user-agents.json.gz"
    )
    with urllib.request.urlopen(user_agents_url) as response:
        user_agents = json.load(gzip.open(response, mode="rt", encoding="utf-8"))
    user_agent = sorted(user_agents, key=lambda x: x["weight"])[-1]["userAgent"]
    return user_agent


def search_image(query):
    search_request = urllib.request.Request(
        url=urllib.parse.urljoin(
            "https://knowyourmeme.com/search",
            "?"
            + urllib.parse.urlencode(
                {"context": "images", "sort": "relevance", "q": query}
            ),
        ),
        headers={"User-Agent": get_current_user_agent()},
    )
    parser = KYMParser()
    with urllib.request.urlopen(search_request) as response:
        parser.feed(response.read().decode("utf-8"))
    if not parser.images:
        return None
    return parser.images[0]


def get_query(event):
    query = None
    try:
        if event["httpMethod"] == "GET":
            query = event["multiValueQueryStringParameters"]["text"][-1]
        elif event["httpMethod"] == "POST":
            if event["isBase64Encoded"]:
                query_string = base64.b64decode(event["body"]).decode("utf-8")
            else:
                query_string = event["body"]
            query = urllib.parse.parse_qs(query_string)["text"][-1]
    finally:
        return query


def handler(event, _context=None):
    query = get_query(event)
    if query:
        image_url = search_image(query)
        if image_url:
            block = {
                "type": "image",
                "image_url": image_url,
                "alt_text": query,
            }
        else:
            block = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "No images found :("},
            }
    else:
        block = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "No query provided :("},
        }

    return {
        "statusCode": "200",
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"response_type": "in_channel", "blocks": [block]}),
    }


if __name__ == "__main__":
    print(search_image(sys.argv[1]))
