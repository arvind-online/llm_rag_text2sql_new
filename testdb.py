import socket
from sqlalchemy import create_engine

# Force IPv4 resolution
old_getaddrinfo = socket.getaddrinfo

def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = ipv4_only_getaddrinfo

# Now create engine normally
DATABASE_URL = "postgresql://user:123445@db.symkcqsvcrtgqmqcsfuq.supabase.co:5432/dbname"
engine = create_engine(DATABASE_URL)
