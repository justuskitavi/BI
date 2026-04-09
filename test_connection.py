import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DB_URL")

if not db_url:
    print("DB_URL not found in environment variables.")
    exit(1)

try: 
    con = psycopg2.connect(db_url)
    cursor = con.cursor()
    print("Successfully established a connection with Neon!")

    schemas = ["star", "snowflake", "galaxy"]
    for schema in schemas: 
        cursor.execute("select schema_name from information_schema.schemata where schema_name = %s", (schema,))
        exists = cursor.fetchone()
        if exists:
            print(f"Schema '{schema}' exists.")
        else: 
            print(f"Schema '{schema}' does not exist yet.")

    cursor.close()
    con.close()
    print("fire up the ETL scripts.")

except Exception as e:
    print(f"An error occurred: {e}")