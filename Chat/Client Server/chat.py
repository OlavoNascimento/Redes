#!/usr/bin/python3

import socket
import datetime
import select
import sys


class Server:
    """
    Classe que cria um socket que pode ser utilizado para conectar usuários, se a conexão for bem
    sucedida um socket é criado para o usuário e gerenciado pelo servidor.
    """

    def __init__(self, address, port):
        # Endereço onde o servidor deve esperar por conexões.
        self.address = address
        # Porta onde o servidor deve esperar por conexões.
        self.port = port
        # Socket que gerencia a conexão.
        self.connection = None
        # Usuários conectados atualmente. Dicionário que relaciona o socket ao nick do usuário.
        self.users = {}

    def addUser(self):
        """
        Adiciona um usuário e avisa os outros usuários.
        """
        client, address = self.connection.accept()
        # Pergunta o nick do usuário.
        client.send("NICK".encode("utf-8"))
        nick = client.recv(1024).decode("utf-8")
        self.users[client] = nick

        print(f"{str(address)} se conectou com nick {nick}")
        self.broadcast(f"{nick} entrou!\n")
        return client

    def broadcast(self, message, socket=None):
        """
        Envia uma mensagem a todos os usuários conectados.
        """
        now = datetime.datetime.now()
        username = ""
        if socket is not None:
            username = f"{self.users[socket]}: "
        for client in self.users.keys():
            client.send(f"[{now.hour}:{now.minute}] {username}{message}".encode("utf-8"))

    def removeUser(self, client):
        """
        Remove um usuário e avisa os outros usuários.
        """
        client.close()
        nick = self.users.pop(client)
        print(f"{nick} se desconectou")
        self.broadcast(f"{nick} saiu!\n")

    def receive(self):
        """
        Recebe a conexão de um usuário e cria um socket.
        """
        sockets_to_watch = [self.connection]
        while True:
            # Espera por eventos nos sockets especificados.
            read_sockets, _, exception_sockets = select.select(
                sockets_to_watch,
                [],
                [],
            )
            for sock in read_sockets:
                if sock == self.connection:
                    # Se o socket do servidor recebeu um evento um usuário está se conectando.
                    client = self.addUser()
                    sockets_to_watch.append(client)
                else:
                    # Caso contrário um usuário existente está enviando uma mensagem
                    message = sock.recv(1024)
                    if message == b"":
                        # Se a mensagem possui zero bytes o cliente fechou a conexão.
                        # Veja: https://docs.python.org/3/howto/sockets.html#using-a-socket
                        self.removeUser(sock)
                        sockets_to_watch.remove(sock)
                    else:
                        self.broadcast(message.decode("utf-8"), sock)

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                self.removeUser(notified_socket)
                sockets_to_watch.remove(notified_socket)

    def run(self):
        """
        Executa o servidor e fecha todas as conexões ao pressionar ctrl+c.
        """
        try:
            self.start()
            self.receive()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def start(self):
        """
        Inicia o servidor, conectando-se ao endereço e porta específicadas e espera por conexões.
        """
        print(f"Servidor aberto no ip: {self.address}:{self.port}")
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.bind((self.address, self.port))
        self.connection.listen()

    def stop(self):
        """
        Desconecta todos os usuários e fecha o socket do servidor.
        """
        print("Parando servidor")
        self.broadcast("Servidor foi fechado!\n")
        for user in list(self.users.keys()):
            self.removeUser(user)
        self.connection.close()
        self.connection = None


class Client:
    """
    Classe que lida com a conexão com um servidor e gerencia o envio e recebimento de mensagens.
    """

    def __init__(self, nickname):
        self.nick = nickname
        self.connection = None

    def handleConnection(self):
        """
        Gerencia o envio de mensagens do usuário ao servidor e o recebimento de mensagens do
        servidor.
        """
        sockets_to_watch = [sys.stdin, self.connection]
        while self.connection is not None:
            # Verifica se o stdin ou o servidor tem algum dado a ser lido.
            read_sockets, _, _ = select.select(
                sockets_to_watch,
                [],
                [],
            )
            for socks in read_sockets:
                if socks == self.connection:
                    self.receive()
                else:
                    self.write()

    def receive(self):
        """
        Recebe uma mensagem do servidor.
        Caso o servidor feche a conexão ou um erro aconteça o cliente é finalizado corretamente.
        """
        try:
            message = self.connection.recv(1024)
            # Se a mensagem possui zero bytes o servidor fechou a conexão.
            # Veja: https://docs.python.org/3/howto/sockets.html#using-a-socket
            if message == b"":
                self.stop()
                return
            decoded_message = message.decode("utf-8")

            if decoded_message == "NICK":
                # Envia o nick do usuário ao servidor.
                self.connection.send(self.nick.encode("utf-8"))
            else:
                print(decoded_message, end="")
        except:
            print("Erro! Fechando a conexão...")
            self.stop()

    def run(self, address, port):
        """
        Executa o cliente até ctrl+c ser pressionado.
        """
        try:
            self.start(address, port)
            self.handleConnection()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def start(self, address, port):
        """
        Conecta-se ao servidor no endereço e porta especificados.
        """
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect((address, port))

    def stop(self):
        """
        Finaliza a conexão com o servidor.
        """
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def write(self):
        """
        Lê uma mensagem do stdin e envia para o servidor.
        """
        message = sys.stdin.readline()
        if len(message) > 0:
            self.connection.send(message.encode("utf-8"))


address = input("Endereço do servidor: ")
port = int(input("Porta do servidor: "))
type = input("Iniciar servidor(S) ou cliente(C)?: ")

if port < 1000 or port > 65535:
    print("Porta deve estar entre 1000 e 65535 (inclusivo)")
    sys.exit(1)

if type.lower() == "s" or type.lower() == "servidor":
    server = Server(address, port)
    server.run()
elif type.lower() == "c" or type.lower() == "cliente":
    nick = input("Nome de usuário: ")
    client = Client(nick)
    client.run(address, port)
