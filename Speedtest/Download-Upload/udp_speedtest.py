import logging
from datetime import datetime, timedelta
from socket import timeout

from tqdm import tqdm

from generic_speedtest import Results, SpeedTest, Roles, SocketType


class UDPSpeedTest(SpeedTest):
    """
    Classe responsável por transmitir dados utilizando sockets UDP e calcular as velocidades de
    download e upload entre dois computadores.
    """

    # Pacote utilizado para confirmar que o outro usuário recebeu um pacote.
    CONFIRMATION_PACKET = b"\x01"

    def __init__(
        self,
        listen_address: str,
        connect_address: str,
        port: int,
        starting_role: Roles,
    ):
        super().__init__(
            listen_address,
            connect_address,
            port,
            starting_role,
            SocketType.UDP,
        )

    def receive_data(self) -> Results:
        """
        Recebe dados enviados por outro usuário, armazenando o número de bytes recebidos, ao final
        da transmissão envia o total recebido para o outro usuário.
        """
        self.connection.settimeout(1)

        waiting_message_presented = False
        pbar = None
        received_bytes = 0

        next_tick = datetime.now() + timedelta(seconds=1)
        while True:
            try:
                packet = self.recvall(self.connection, self.PACKET_SIZE)
                # Um pacote vazio indica o fim da transmissão de dados.
                if packet == self.EMPTY_PACKET:
                    break

                if received_bytes == 0:
                    print("Testando velocidade de download...")
                    pbar = tqdm(total=self.RUN_DURATION, bar_format=self.TQDM_FORMAT)

                logging.debug(
                    "%d bytes recebidos, tamanho atual: %d",
                    len(packet),
                    received_bytes,
                )

                received_bytes += len(packet)

                current_time = datetime.now()
                # Atualiza a barra de progresso.
                if current_time >= next_tick:
                    pbar.update(1)
                    pbar.refresh()
                    next_tick = current_time + timedelta(seconds=1)
            except timeout:
                # Indica que está pronto para receber dados.
                self.connection.send(self.EMPTY_PACKET)
            except ConnectionRefusedError:
                # Outro usuário ainda não se conectou.
                if not waiting_message_presented:
                    print("Esperando o outro usuário estabelecer uma conexão...")
                    waiting_message_presented = True
        logging.debug("Fim do recebimento de dados")

        # Garante que o tempo de execução da barra de progresso esteja correto ao fim da
        # execução.
        pbar.n = self.RUN_DURATION
        pbar.refresh()
        pbar.close()

        # Envia o total salvo para o outro usuário.
        while True:
            try:
                stats_packet = self.encode_stats_packet(received_bytes)
                self.connection.send(stats_packet)

                transmitted_bytes = self.connection.recv(self.INT_BYTE_SIZE)
                transmitted_bytes = self.decode_stats_packet(transmitted_bytes)

                status = self.connection.recv(self.PACKET_SIZE)
                if status == self.CONFIRMATION_PACKET:
                    break
            except timeout:
                pass
            except ConnectionRefusedError:
                break

        return Results(transmitted_bytes, received_bytes)

    def send_data(self) -> Results:
        """
        Envia dados para outro usuário, ao final da transmissão recebe o total de bytes recebidos
        pelo o outro usuário.
        """
        # Uma mensagem vazia indica que o outro usuário está pronto para receber os dados.
        print("Esperando o outro usuário estabelecer uma conexão...")
        _, address = self.connection.recvfrom(self.PACKET_SIZE)
        print("Testando velocidade de upload...")

        end_time = datetime.now() + timedelta(seconds=self.RUN_DURATION)
        next_tick = datetime.now() + timedelta(seconds=1)
        transmitted_bytes = 0

        logging.debug("Iniciando envio de dados")
        with tqdm(total=self.RUN_DURATION, bar_format=self.TQDM_FORMAT) as pbar:
            while (current_time := datetime.now()) < end_time:
                packet = self.encode_data_packet()
                self.connection.sendto(packet, address)
                transmitted_bytes += len(packet)
                # Atualiza a barra de progresso.
                if current_time >= next_tick:
                    next_tick = current_time + timedelta(seconds=1)
                    pbar.update(1)
                    pbar.refresh()

            # Garante que o tempo de execução da barra de progresso esteja correto ao fim da
            # execução.
            pbar.n = self.RUN_DURATION
            pbar.refresh()
        logging.debug("Fim do envio de dados")

        self.connection.settimeout(1)
        received_bytes = 0
        # Recebe o total de bytes recebidos pelo o outro usuário.
        while received_bytes == 0:
            try:
                self.connection.sendto(self.EMPTY_PACKET, address)

                received_packet = self.connection.recv(self.INT_BYTE_SIZE)
                received_bytes = self.decode_stats_packet(received_packet)

                stats_packet = self.encode_stats_packet(transmitted_bytes)
                self.connection.sendto(stats_packet, address)

                self.connection.sendto(self.CONFIRMATION_PACKET, address)
            except timeout:
                pass
        self.connection.settimeout(0)
        logging.debug("%d bytes foram recebidos pelo o outro usuário", received_bytes)

        return Results(transmitted_bytes, received_bytes)
