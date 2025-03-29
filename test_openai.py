import os
import openai
from dotenv import load_dotenv, find_dotenv
import sys

# Set up basic logging
print("Starting OpenAI API test...")

# Find and load .env file
dotenv_path = find_dotenv()
if dotenv_path:
    print(f"Found .env file at: {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    print("No .env file found. Will try to use environment variables.")
    load_dotenv()  # Try default loading anyway

# Get API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("ERROR: OpenAI API key is not set in environment variables.")
    sys.exit(1)

print(f"API key found (starts with {api_key[:5]}...)")

# Set API key for OpenAI
openai.api_key = api_key

# Test API connection
try:
    print("Testing OpenAI API connection...")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello world!"}
        ],
        max_tokens=10
    )
    
    print("API connection successful!")
    print(f"Response type: {type(response)}")
    
    if hasattr(response.choices[0].message, "content"):
        content = response.choices[0].message.content
        print(f"Response content (attribute access): {content}")
    else:
        content = response.choices[0].message["content"]
        print(f"Response content (dictionary access): {content}")
        
    print("Test completed successfully!")
    
except Exception as e:
    print(f"ERROR: Failed to connect to OpenAI API: {str(e)}")
    import traceback
    print(traceback.format_exc())
    sys.exit(1)
