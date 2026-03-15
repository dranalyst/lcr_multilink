# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client
from config import settings
import time
from fastapi import FastAPI, Request
import asyncio, os


# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = settings.TWILIO_ACCOUNT_SID
auth_token = settings.TWILIO_AUTH_TOKEN
client = Client(account_sid, auth_token)

call = client.calls.create(
    url="http://demo.twilio.com/docs/voice.xml",
    to="+256769675440",
    from_="+34632041356",
)

time.sleep(5)

call2= client.calls(call.sid).fetch()

print(call2.sid)
print(call2._from)
print(call2.to)
print(call2.phone_number_sid)
print(call2.start_time)
print(call2.status)
print(call2.duration)
print(call2.trunk_sid)
print(call2.uri)
print(call2._context)
print(call2.price)
print(call2.price_unit)
print(call2.direction)
print(call2.answered_by)
print(call2.api_version)