import os
from generate_process import text_to_audio, create_reel   # reuse your existing functions

def generate_reel_job(folder_id: str):
    # folder_id is your uuid folder in user_uploads
    text_to_audio(folder_id)
    create_reel(folder_id)
    return True