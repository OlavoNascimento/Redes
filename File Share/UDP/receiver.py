from collections import deque
import datetime
import logging
from socket import timeout
from typing import Deque

from client import Client


class Receiver(Client):
    """
    Classe responsável por receber um arquivo enviado por outro usuário através de um socket.
    """

    def __init__(self, packet_size: int):
        super().__init__(packet_size)
        # Endereço do outro usuário.
        self.address = None
        # Dados recebidos do arquivo.
        self.buffer: Deque["bytes"] = deque()
        # Tamanho do buffer
        self.buffer_size = 0
        # Índice do pacote a ser recebido.
        self.current_package = 0

    def send_packet(self, message: str):
        """
        Envia uma mensagem para o outro usuário.
        """
        logging.debug(
            "Enviando mensagem de status %s para o pacote %s", message, self.current_package
        )
        packet = self.current_package.to_bytes(8, "big") + message.encode("ascii")
        self.connection.sendto(packet, self.address)

    def send_ack(self):
        """
        Envia uma mensagem confirmando que o pacote de índice current_package foi recebido com
        sucesso.
        """
        self.send_packet("ACK")

    def send_nack(self):
        """
        Envia uma mensagem avisando que houve falha ao receber o pacote de índice current_package.
        """
        self.send_packet("NACK")

    def receive_packet(self):
        """
        Recebe um pacote, decodifica suas informações e separa seus dados.
        """
        # Tamanho do pacote a ser recebido.
        try:
            data, _ = self.connection.recvfrom(8 + 8 + 32 + self.packet_size)
        except timeout:
            logging.debug("Socket recebeu timeout!")
            return None, None, None, None

        # Se a mensagem está vazia o outro usuário fechou a conexão.
        if data == b"":
            logging.debug("Pacote vazio!")
            return None, None, None, None

        packet_index = int.from_bytes(data[0:8], "big")
        packet_data_size = int.from_bytes(data[8:16], "big")
        packet_checksum = data[16:48].decode("ascii")
        packet_data = data[48:]

        logging.debug(
            "Pacote recebido, index: %s, size: %s, checksum: %s",
            packet_index,
            packet_data_size,
            packet_checksum,
        )

        return packet_index, packet_data_size, packet_checksum, packet_data

    def check_package(self, packet: bytes):
        """
        Verifica se não houve erro na transmissão do pacote.
        """
        packet_index, packet_size, packet_checksum, packet_data = packet
        if packet_data is None:
            self.send_nack()
            return False

        # O pacote recebido esteja abaixo do pacote esperado, isso significa que as mensagens de
        # ACK enviadas não foram recebidas pelo outro programa, portanto é necessário envia-las
        # novamente.
        if packet_index < self.current_package:
            diff = self.current_package - packet_index
            logging.debug(
                "Recebido pacote menor que o esperado: esperado %s, encontrado: %s, reenviando %s ACKs",
                self.current_package,
                packet_index,
                diff,
            )
            self.current_package = packet_index
            for _ in range(diff):
                self.send_ack()
                self.current_package += 1
            return False

        # O pacote recebido esteja acima do pacote esperado, isso significa que o pacote esperado
        # falhou e portanto deve ser reenviado.
        if packet_index > self.current_package:
            logging.debug(
                "Recebido pacote maior do que o esperado: esperado %s, encontrado: %s",
                self.current_package,
                packet_index,
            )
            self.send_nack()
            return False

        if len(packet_data) != packet_size or self.checksum(packet_data) != packet_checksum:
            logging.debug("Erro ao receber o pacote %s!", packet_index)
            logging.debug(
                "Valores encontrados: index: %s, size: %s, checksum: %s",
                self.current_package,
                len(packet_data),
                self.checksum(packet_data),
            )
            logging.debug(
                "Valores esperados: index: %s, size: %s, checksum: %s",
                packet_index,
                packet_size,
                packet_checksum,
            )
            self.send_nack()
            return False
        return True

    def handle_connection(self):
        """
        Recebe um arquivo enviado por outro usuário.
        Retorna verdadeiro caso a conexão deva ser finalizada
        """
        start_time = datetime.datetime.now()

        packet, address = self.connection.recvfrom(1032)
        if packet == b"":
            print("Erro ao receber o nome e tamanho do arquivo!")
            return True
        file_size = int.from_bytes(packet[0:8], "big")
        file_name = packet[8:].decode("utf-8")

        print(f"Recebendo arquivo: {file_name} ({self.format_bytes(file_size)})")
        self.address = address
        # Porcentagem já enviada.
        progress = 0
        # Pacotes que tiveram que ser reenviados.
        failed_packages = 0

        while self.buffer_size < file_size:
            packet = self.receive_packet()
            # Verifica se houve erro na transmissão do pacote.
            if not self.check_package(packet):
                failed_packages += 1
                continue

            self.send_ack()
            progress = self.print_progress_message(
                self.buffer_size, file_size, progress, "Recebido"
            )
            self.buffer.append(packet[3])
            self.buffer_size += packet[1]
            self.current_package += 1

        with open(file_name, "wb") as output:
            output.write(b"".join(self.buffer))

        end_time = datetime.datetime.now()
        print("Arquivo recebido")
        self.report(file_size, failed_packages, start_time, end_time)
        return True

    def prepare_socket(self, address: str, port: int):
        """
        Conecta-se ao servidor no endereço e porta especificados.
        """
        self.connection.connect((address, port))
        # Avisa o outro usuário que o cliente está pronto para receber o arquivo.
        self.connection.sendto(b"", (address, port))
