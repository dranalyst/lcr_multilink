# from fastapi import APIRouter
# from pydantic import BaseModel
# from datetime import datetime
# import psycopg2
#
# router = APIRouter()
#
# class PhoneUser(BaseModel):
#     phoneNumber: str
#     #createdOn: datetime
#
# # Update these DB settings to match your environment
# DB_PARAMS = {
#     "host": "localhost",
#     "port": 5432,
#     "dbname": "postgres",
#     "user": "postgres",
#     "password": "c6emcpostgres"
# }
#
# @router.post("/phoneuser")
# def insert_phoneuser(user: PhoneUser):
#     try:
#         conn = psycopg2.connect(**DB_PARAMS)
#         cur = conn.cursor()
#         cur.execute(
#             'INSERT INTO "testCall"."phoneusers" (phoneNumber) VALUES (%s)',
#             (user.phoneNumber)
#         )
#         conn.commit()
#         cur.close()
#         conn.close()
#         return {"status": "success"}
#     except Exception as e:
#         return {"status": "error", "detail": str(e)}