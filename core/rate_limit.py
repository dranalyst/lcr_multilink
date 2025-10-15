# project_root/core/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

# initialize a global limiter
limiter = Limiter(key_func=get_remote_address)