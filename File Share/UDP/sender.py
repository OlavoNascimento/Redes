import datetime
import logging
import os
from collections import deque
from dataclasses import dataclass
from socket import timeout
from typing import Deque

from client import Client


@dataclass
class Packet:
    """
    Pacote contido em uma janela.
    Contem o pacote que deve ser enviado e informações adicionais sobre o estado do pacote.
    """

    # Pacote correspondente a esse objeto.
    content: bytes
    # Indica se o pacote está esperando a confirmação do outro usuário.
    is_awaiting_ack: bool = False


class Sender(Client):
    """
    Classe responsável por enviar um arquivo para outro usuário através de um socket.
    """

    def __init__(self, file_path: str, packet_size: int, window_size: int):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo {file_path} não existe!")
        super().__init__(packet_size)
        # Pacote atual enviado ao outro usuário e esperando ser confirmado.
        self.current_package = 0
        # Caminho do arquivo a ser enviado.
        self.file_path = file_path
        # Dados do arquivo lido.
        self.file_data: list["Packet"] = []
        # Pacotes que serão enviados ao outro usuário.
        self.window: Deque["Packet"] = deque()
        # Número máximo de pacotes a serem enviados ao mesmo tempo.
        self.window_size = window_size

    def create_packet(self, packet_index: int, data: bytes):
        """
        Utiliza um conjunto de bytes para gerar um pacote. O qual além dos dados também contém
        index, tamanho e checksum dos dados enviados.
        """
        size = len(data)
        checksum = self.checksum(data)
        packet_content = (
            packet_index.to_bytes(8, "big")
            + size.to_bytes(8, "big")
            + checksum.encode("ascii")[0:32]
            + data
        )
        return Packet(packet_content)

    def can_add_to_window(self):
        """
        Verifica se é possível adicionar um novo pacote na janela.
        """
        return len(self.window) < self.window_size

    def read_file(self):
        """
        Preenche a janela com pacotes.
        """
        with open(self.file_path, "rb") as file:
            packet_index = 0
            data_chunk = file.read(self.packet_size)
            while data_chunk:
                packet = self.create_packet(packet_index, data_chunk)
                self.file_data.append(packet)
                if self.can_add_to_window():
                    self.window.append(packet)
                data_chunk = file.read(self.packet_size)
                packet_index += 1

    def send_packet(self, packet: Packet, address):
        """
        Envia um pacote e marca que ele precisa receber uma confirmação ao ser recebido pelo outro
        usuário.
        """
        logging.debug(
            "Enviando pacote %s de tamanho %s",
            int.from_bytes(packet.content[0:8], "big"),
            len(packet.content),
        )
        try:
            self.connection.sendto(packet.content, address)
            packet.is_awaiting_ack = True
            return True
        except timeout:
            logging.debug("Socket recebeu timeout ao enviar pacote!")
            return False

    def resend(self, resend_index: int):
        """
        Limpa a janela e insere todos os pacotes que devem ser reenviados a partir de um índice.
        """
        logging.debug("Reenviando pacotes")
        for packet in self.file_data[resend_index : resend_index + self.window_size]:
            logging.debug(
                "Adicionando pacote %s a janela", int.from_bytes(packet.content[0:8], "big")
            )
            old_packet = self.window.popleft()
            old_packet.is_awaiting_ack = False
            self.window.append(packet)

    def check_current_package_status(self):
        """
        Verifica se o pacote atual foi recebido pelo outro usuário e se a janela atual deve ser
        reenviada.
        """
        try:
            message, _ = self.connection.recvfrom(1024)
        except timeout:
            logging.debug("Socket recebeu timeout!")
            self.resend(self.current_package)
            return True
        if message == b"":
            return False

        ack_packet_index = int.from_bytes(message[0:8], "big")
        status = message[8:].decode("ascii")
        logging.debug(
            "Resposta recebida, esperado: %s, encontrado: %s, status: %s",
            self.current_package,
            ack_packet_index,
            status,
        )

        if ack_packet_index > self.current_package:
            logging.debug(
                "Pacote %s falhou, reenviando os pacotes de %s até %s",
                ack_packet_index,
                ack_packet_index,
                ack_packet_index + self.window_size - 1,
            )
            self.resend(ack_packet_index)
            return False

        if ack_packet_index < self.current_package or status == "NACK":
            return False

        next_packet_index = self.current_package + self.window_size
        if next_packet_index < len(self.file_data):
            logging.debug(
                "Pacote %s confirmado, adicionando pacote %s a janela",
                ack_packet_index,
                next_packet_index,
            )
            self.window.append(self.file_data[next_packet_index])
        self.window.popleft()
        self.current_package += 1
        return True

    def handle_connection(self):
        """
        Envia um arquivo para outro usuário.
        Retorna verdadeiro caso a conexão deva ser finalizada
        """
        # Uma mensagem vazia indica que o outro usuário está pronto para receber o arquivo.
        message_start, address = self.connection.recvfrom(1024)
        if message_start != b"":
            return False
        logging.debug("Mensagem inicial recebida")

        file_size = os.path.getsize(self.file_path)
        start_time = datetime.datetime.now()

        # Envia o nome e tamanho do arquivo.
        file_name = os.path.basename(self.file_path)
        packet = file_size.to_bytes(8, "big") + file_name.encode("utf-8")
        self.connection.sendto(packet, address)
        print(f"Enviando arquivo: {self.file_path} ({self.format_bytes(file_size)})")

        progress = 0
        # Pacotes que tiveram que ser reenviados.
        failed_packages = 0
        self.read_file()

        while len(self.window) > 0:
            # Caso ainda algum pacote da janela não tenha sido enviado, tenta envia-lo.
            for element in self.window:
                if not element.is_awaiting_ack:
                    packet_status = self.send_packet(element, address)
                    # Pacote falhou ao ser enviado, pacotes subsequentes não devem ser enviados, já
                    # que a ordem da janela deve ser mantida.
                    if not packet_status:
                        break

            progress = self.print_progress_message(
                self.packet_size * self.current_package, file_size, progress, "Enviado"
            )

            if not self.check_current_package_status():
                failed_packages += 1

        end_time = datetime.datetime.now()
        print("Arquivo enviado")
        self.report(file_size, failed_packages, start_time, end_time)
        return True

    def prepare_socket(self, address: str, port: int):
        """
        Inicia o servidor no endereço e porta especificados.
        """
        print("Esperando um cliente se conectar...")
        self.connection.bind((address, port))
