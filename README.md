git clone 

uv installation - https://docs.astral.sh/uv/getting-started/installation/#installation-methods

uv sync

create .env in text_to_sql folder

add below lines 
GROQ_API_KEY="API KEy"

# Model — llama-3.3-70b-versatile is the best for
# Text-to-SQL accuracy on Groq's free tier
SLM_MODEL=llama-3.3-70b-versatile

add all the three yaml files outside text_to_sql folder 

python main.py
