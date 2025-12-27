import os

from dotenv import load_dotenv

load_dotenv()

discogs_user_token = os.getenv('DISCOGS_USER_TOKEN')
