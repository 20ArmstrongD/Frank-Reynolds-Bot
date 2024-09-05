import sqlite3
from datetime import datetime

# Function to format messages for readability
def format_message(message, line_length=50):
    """Format the message by adding new lines at a specified character count."""
    words = message.split()
    formatted_message = ""
    current_line_length = 0

    for word in words:
        if current_line_length + len(word) + 1 > line_length:
            formatted_message += "\n"  # Start a new line
            current_line_length = 0

        if current_line_length > 0:
            formatted_message += " "  # Add a space before the word

        formatted_message += word
        current_line_length += len(word) + 1  # Update the current line length

    return formatted_message

# Connect to the database and create tables if they don't exist
def connect_db(database_name='mantis_data.db'):
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            message_content TEXT NOT NULL,
            response_content TEXT NOT NULL,
            server_location TEXT NOT NULL,
            channel_location TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    return conn, cursor

# Log a message and response into the database
def log_message(user_id, message_content, response_content, server_location, channel_location, database_name='mantis_data.db'):
    conn, cursor = connect_db(database_name)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Format the messages for better readability
    formatted_user_message = format_message(message_content)
    formatted_bot_response = format_message(response_content)

    cursor.execute('''
        INSERT INTO messages (user_name, message_content, response_content, server_location, channel_location, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)''', 
        (user_id, formatted_user_message, formatted_bot_response, server_location, channel_location, timestamp))
    
    conn.commit()
    conn.close()
