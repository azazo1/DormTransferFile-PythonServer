import select
import socket

from src import msg


class ConnectingServer:
    SERVER_PORT = 8088

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("0.0.0.0", self.SERVER_PORT))
        self.socket.listen(10)
        self.clients: dict[socket.socket, tuple[str, int]] = {}  # 套接字 : (IP地址, 端口)
        self.senders: dict[socket.socket, tuple[int, int, str]] = {}  # 套接字 : (连接号码, 文件传输服务器端口, 文件名)
        self.connCodeCursor = 1000

    def getNextConnCode(self) -> int:
        rst = self.connCodeCursor
        self.connCodeCursor += 1
        if self.connCodeCursor > 9999:
            self.connCodeCursor = 1000
        return rst

    def close(self):
        for client in self.clients:
            client.close()
        self.socket.close()

    def handleInput(self):
        sockets = [self.socket] + list(self.clients.keys())
        r, w, e = select.select(sockets, [], sockets)  # type: list[socket.socket]
        for soc in e:
            if soc == self.socket:
                print("服务器关闭")
                self.close()
            else:
                soc.close()
                print(self.clients.get(soc), "断开连接")
                self.removeClient(soc)
        for soc in r:
            if soc == self.socket:
                client = self.addClient(self.socket.accept())
                print(self.clients.get(client), "新客户端连接")
            else:
                try:
                    self.handleMsg(soc)
                except Exception as e:
                    print(type(e), self.clients.get(soc), "断开连接")
                    self.removeClient(soc)

    def handleMsg(self, soc: socket.socket):
        msgSeq = int(soc.recv(5))
        msgTypeCode = int(soc.recv(2))
        soc.sendall(f"{msgSeq:05d}".encode("utf-8"))
        soc.sendall(f"{msgTypeCode:02d}".encode("utf-8"))
        if msgTypeCode == msg.MSG_CODE_FETCH_AVAILABLE_SENDERS:
            print("接收到查询全部文件发送者消息")
            soc.sendall(f"{len(self.senders):02d}".encode("utf-8"))
            for soc1 in self.senders.keys():
                connCode, port, filename = self.senders.get(soc1)
                filenameData = f"{filename}".encode("utf-8")
                filenameDataLength = len(filenameData)
                connCodeData = f"{connCode:04d}".encode("utf-8")
                soc.sendall(connCodeData + f"{filenameDataLength:03d}".encode("utf-8") + filenameData)
        elif msgTypeCode == msg.MSG_REGISTER_SENDER:
            print("接收到注册文件发送者消息")
            filenameDataLength = int(soc.recv(3))
            filename = soc.recv(filenameDataLength).decode('utf-8')
            port = int(soc.recv(5))
            connCode = self.addSender(port, filename, soc)
            soc.sendall(f"{connCode:04d}".encode("utf-8"))
        elif msgTypeCode == msg.MSG_QUERY_SENDER_SERVER_ADDRESS:
            print("接收到查询文件发送者地址消息")
            targetConnCode = int(soc.recv(4))
            find = False
            for sock, (connCode, port, filename) in zip(self.senders.keys(), self.senders.values()):
                if targetConnCode == connCode:
                    ip, _ = self.clients.get(sock)
                    ipData = ip.encode("utf-8")
                    ipDataLength = len(ipData)
                    soc.sendall(f"{ipDataLength:02d}".encode("utf-8") + ipData + f"{port:05d}".encode("utf-8"))
                    find = True
                    break
            if not find:
                soc.sendall(b'00')

    def addSender(self, port: int, filename: str, soc: socket.socket) -> int:
        connCode = self.getNextConnCode()
        self.senders[soc] = (connCode, port, filename)
        return connCode

    def addClient(self, arg: tuple[socket.socket, tuple[str, int]]):
        self.clients[arg[0]] = arg[1]
        return arg[0]

    def removeClient(self, soc: socket.socket):
        # 同时还要移除已经创建的sender
        self.clients.pop(soc)
        try:
            self.senders.pop(soc)
        except KeyError:
            pass  # 没注册为文件发送者


if __name__ == '__main__':
    server = ConnectingServer()
    while True:
        server.handleInput()
