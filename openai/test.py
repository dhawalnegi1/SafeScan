import requests

url = "https://api.perplexity.ai/chat/completions"

payload = {
    "model": "llama-3.1-sonar-small-128k-online",
    "messages": [
        {
            "role": "system",
            "content": "Be precise and concise."
        },
        {
            "role": "user",
            "content": "What are the ingredients or components of the product 'Nail Tek Mosturizing Strengthener 4' which is from brand 'NAIL TEK'?"
        }
    ],
    "max_tokens": 1000,
    "temperature": 0.2,
    "top_p": 0.9,
    "return_citations": True,
    "search_domain_filter": ["perplexity.ai"],
    "return_images": False,
    "return_related_questions": False,
    "search_recency_filter": "month",
    "top_k": 0,
    "stream": False,
    "presence_penalty": 0,
    "frequency_penalty": 1
}
headers = {
    "Authorization": "Bearer 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",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)

print(response.text)