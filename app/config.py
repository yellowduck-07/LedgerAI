import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_OCR_MODEL = os.getenv("GEMINI_OCR_MODEL", GEMINI_MODEL)
DEFAULT_BUSINESS_STATE = os.getenv("BUSINESS_STATE", "Maharashtra")
