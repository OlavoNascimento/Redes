import logging
from datetime import datetime, timedelta
from operator import truediv
from time import sleep

from tqdm import tqdm

from client import Client, Roles, SocketType


class TCPTester(Client):
    """
    Classe responsável por transmitir dados utilizando sockets TCOP e calcular as velocidades de
    download e upload entre dois computadores.
    """

    # Pacote utilizado para confirmar que o outro usuário recebeu um pacote.
    CONFIRMATION_PACKET = b"\x01"

    def __init__(
        self,
        connect_address: str,
        port: int,
        starting_role: Roles,
    ):
        super().__init__(
            connect_address,
            port,
            starting_role,
            SocketType.TCP,
        )

    def receive_data(self) -> int:
        """
        Recebe dados enviados por outro usuário, armazenando o número de bytes recebidos, ao final
        da transmissão envia o total recebido para o outro usuário.
        """

        pbar = None
        received_data_size = 0

        next_tick = datetime.now() + timedelta(seconds=1)
        while True:
            data = self.connection.recv(self.PACKET_SIZE)
            if data == self.EMPTY_PACKET:
                break
            logging.debug(
                "%d bytes recebidos, tamanho atual: %d", len(data), received_data_size
            )
            if received_data_size == 0:
                print("Testando velocidade de download...")
                pbar = tqdm(total=self.RUN_DURATION, bar_format=self.TQDM_FORMAT)
            received_data_size += len(data)

            current_time = datetime.now()
            # Atualiza a barra de progresso.
            if current_time >= next_tick:
                pbar.update(1)
                pbar.refresh()
                next_tick = current_time + timedelta(seconds=1)
            
        logging.debug("Fim do recebimento de dados")

        # Garante que o tempo de execução da barra de progresso esteja correto ao fim da
        # execução.
        pbar.n = self.RUN_DURATION
        pbar.refresh()
        pbar.close()

        # Envia o total salvo para o outro usuário.
        self.connection.send(int.to_bytes(received_data_size, 8, "big", signed=False))


        return received_data_size

    def send_data(self):
        """
        Envia dados para outro usuário, ao final da transmissão recebe o total de bytes recebidos
        pelo o outro usuário.
        """
        # Uma mensagem vazia indica que o outro usuário está pronto para receber os dados.
        print("Esperando o outro usuário estabelecer uma conexão...")
        self.connection.listen()
        client, address = self.connection.accept()
        self.connection = client
        print("Testando velocidade de upload...")

        end_time = datetime.now() + timedelta(seconds=self.RUN_DURATION)
        next_tick = datetime.now() + timedelta(seconds=1)

        logging.debug("Iniciando envio de dados")
        with tqdm(total=self.RUN_DURATION, bar_format=self.TQDM_FORMAT) as pbar:
            while (current_time := datetime.now()) < end_time:
                self.connection.sendto(self.data, address)
                # Atualiza a barra de progresso.
                if current_time >= next_tick:
                    next_tick = current_time + timedelta(seconds=1)
                    pbar.update(1)
                    pbar.refresh()

            # Garante que o tempo de execução da barra de progresso esteja correto ao fim da
            # execução.
            pbar.n = self.RUN_DURATION
            pbar.refresh()
        self.connection.sendto(self.EMPTY_PACKET, address)
        logging.debug("Fim do envio de dados")

        # Recebe o total de bytes recebidos pelo o outro usuário.
        message_end = self.connection.recv(self.PACKET_SIZE)
        bytes_transmitted = int.from_bytes(message_end, "big", signed=False)

        logging.debug("%d bytes foram recebidos pelo o outro usuário", bytes_transmitted)
        return bytes_transmitted
