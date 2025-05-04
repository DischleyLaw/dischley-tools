import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Test the chat model
response = client.chat.completions.create(
    model="gpt-4",  # change this line
    messages=[
        {"role": "user", "content": "Say hello to the Dischley Law team!"}
    ]
)

print(response.choices[0].message.content)