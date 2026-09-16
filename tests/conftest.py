"""No internet in tests; loopback is opt-in for local daemon integration only."""
import socket
import ipaddress
import pytest

@pytest.fixture(autouse=True)
def no_network_or_ambient_credentials(monkeypatch,request):
    for key in ("PRISM2API_HOME","PRISM2API_KEY"):
        monkeypatch.delenv(key,raising=False)
    connect,connect_ex,getaddrinfo=socket.socket.connect,socket.socket.connect_ex,socket.getaddrinfo
    loopback = request.node.get_closest_marker("loopback") is not None
    def allowed(address):
        host=address[0]
        if host=='localhost':
            return loopback
        try:
            return loopback and ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False
    def guarded(self,address):
        if self.family in (socket.AF_INET,socket.AF_INET6) and not allowed(address):
            raise RuntimeError("AUDIT_NETWORK_DISABLED")
        return connect(self,address)
    def guarded_ex(self,address):
        if self.family in (socket.AF_INET,socket.AF_INET6) and not allowed(address):
            raise RuntimeError("AUDIT_NETWORK_DISABLED")
        return connect_ex(self,address)
    def guarded_dns(host,port,*args,**kwargs):
        if not allowed((host,port)):
            raise RuntimeError("AUDIT_NETWORK_DISABLED")
        return getaddrinfo(host,port,*args,**kwargs)
    monkeypatch.setattr(socket.socket,"connect",guarded)
    monkeypatch.setattr(socket.socket,"connect_ex",guarded_ex)
    monkeypatch.setattr(socket,"getaddrinfo",guarded_dns)
