import datetime

from client import Client


class Receiver(Client):
    """
    Classe responsável por receber um arquivo enviado por outro usuário através de um socket.
    """

    def handle_connection(self):
        """
        Recebe um arquivo enviado por outro usuário.
        Retorna verdadeiro caso a conexão deva ser finalizada
        """
        start_time = datetime.datetime.now()

        try:
            size = self.connection.recv(8)
            # Se a mensagem possui zero bytes o servidor fechou a conexão.
            # Veja: https://docs.python.org/3/howto/sockets.html#using-a-socket
            if size == b"":
                return True
            # Socket foi aberto, ainda não foi iniciado a transmissão do arquivo.
            if size == b"\x00\x00\x00\x00":
                return False

            size = int.from_bytes(size, "big")
            file_name = self.connection.recv(1024).decode("utf-8")

            print(f"Recebendo arquivo: {file_name} ({self.format_bytes(size)})")

            buffer = b""
            # Porcentagem já enviada.
            progress = 0
            while len(buffer) < size:
                data = self.connection.recv(size - len(buffer))
                if not data:
                    print("Arquivo incompleto recebido!")
                    break
                progress = self.print_already_sent_message(len(buffer), size, progress, "Recebido")
                buffer += data

            with open(file_name, "wb") as output:
                output.write(buffer)

            end_time = datetime.datetime.now()
            print("Arquivo recebido")
            self.report(size, start_time, end_time)
        except InterruptedError:
            print("Erro! Fechando a conexão...")
            return False
        return True
