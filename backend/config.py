"""Configuration for the LLM Council."""

import os

from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    # Google
    "google/gemini-3.1-pro-preview",
    "google/gemini-3-pro-preview",
    "google/gemini-3.8-flash",
    # Anthropic
    #"anthropic/claude-fable-5.1", # $$$
    #"anthropic/claude-opus-5", # $$$
    "anthropic/claude-opus-4.8",
    "anthropic/claude-sonnet-5",
    # Grok
    "x-ai/grok-4.6",
    # OpenAI
    "openai/gpt-6-astra",
    "openai/gpt-5.6-sol",
    "openai/gpt-5.6-luna",
    "openai/gpt-5.6-terra",
    # Meta
    "meta/muse-spark-1.3",
    # Kimi
    "moonshotai/kimi-k3", # $$
    # Free
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "z-ai/glm-5.2:free",
    "minimax/minimax-m3:free",
    "thinkingmachines/inkling:free",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3.1-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
