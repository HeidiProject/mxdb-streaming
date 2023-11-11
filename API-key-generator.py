import secrets
import string

def generate_api_key(length=32):
    # Define the characters to be used in the API key
    characters = string.ascii_letters + string.digits

    # Generate a secure random API key
    api_key = ''.join(secrets.choice(characters) for _ in range(length))

    return api_key

# Generate a 32-character API key
api_key = generate_api_key()
print(api_key)
