"""Keyword retrieval over the synthetic knowledge-base articles.

Each article is a plain Markdown file in docs/kb/. Retrieval scores an
article by how many of the question's words appear in it, and returns
the top matches with their titles. No external search library is used.
"""
import os
import re

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "i", "my", "me", "the", "a", "an", "and", "or", "to", "for", "of", "in",
    "on", "is", "it", "please", "hello", "thank", "you", "can", "would",
    "how", "do", "what", "when", "will", "my", "am", "are",
}


def _stem(token):
    # Light stemming so word forms match: returned -> return,
    # cracked -> crack, charges -> charge, deliveries -> delivery.
    if len(token) > 4 and token.endswith("ing"):
        token = token[:-3]
    elif len(token) > 3 and token.endswith("ed"):
        token = token[:-2]
    elif len(token) > 3 and token.endswith("ies"):
        token = token[:-3] + "y"
    elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    return token


def tokens(text):
    return [_stem(t) for t in TOKEN_RE.findall(text.lower())
            if t not in STOPWORDS]


def load_kb(kb_dir):
    articles = []
    for name in sorted(os.listdir(kb_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(kb_dir, name)) as f:
            body = f.read()
        title = body.splitlines()[0].lstrip("# ").strip() if body else name
        articles.append({"file": name, "title": title, "body": body})
    return articles


def retrieve(query, articles, top_k=2):
    query_tokens = set(tokens(query))
    scored = []
    for article in articles:
        article_tokens = set(tokens(article["body"]))
        overlap = query_tokens & article_tokens
        if overlap:
            scored.append((len(overlap), article))
    scored.sort(key=lambda item: -item[0])
    results = []
    for score, article in scored[:top_k]:
        text = " ".join(article["body"].splitlines()[1:]).strip()
        snippet = text[:180]
        if len(text) > 180:
            snippet = snippet.rsplit(" ", 1)[0] + "..."
        results.append({"file": article["file"], "title": article["title"],
                        "score": score, "snippet": snippet})
    return results
