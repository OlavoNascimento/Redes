import logging
from datetime import datetime, timedelta

from tqdm import tqdm

from generic_speedtest import Results, SpeedTest, Roles, SocketType


class TCPSpeedTest(SpeedTest):
    """
    Classe responsável por transmitir dados utilizando sockets TCP e calcular as velocidades de
    download e upload entre dois computadores.
    """

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
            SocketType.TCP,
        )

    def receive_data(self) -> Results:
        """
        Recebe dados enviados por outro usuário, armazenando o número de bytes recebidos, ao final
        da transmissão envia o total recebido para o outro usuário.
        """

        pbar = None
        received_bytes = 0
        packet = b""

        next_tick = datetime.now() + timedelta(seconds=1)
        while True:
            packet = self.recvall(self.connection, self.PACKET_SIZE)
            if packet == self.EMPTY_PACKET:
                break

            logging.debug(
                "%d bytes recebidos, tamanho atual: %d",
                len(packet),
                received_bytes,
            )

            if received_bytes == 0:
                print("Testando velocidade de download...")
                pbar = tqdm(total=self.RUN_DURATION, bar_format=self.TQDM_FORMAT)
            received_bytes += len(packet)

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
        stats_packet = self.encode_stats_packet(received_bytes)
        self.connection.sendall(stats_packet)
        logging.debug("Receive enviou o número de bytes recebidos")

        transmitted_bytes = self.recvall(self.connection, self.INT_BYTE_SIZE)
        transmitted_bytes = self.decode_stats_packet(transmitted_bytes)
        logging.debug("Receive acabou")

        return Results(transmitted_bytes, received_bytes)

    def send_data(self) -> Results:
        """
        Envia dados para outro usuário, ao final da transmissão recebe o total de bytes recebidos
        pelo o outro usuário.
        """
        # Uma mensagem vazia indica que o outro usuário está pronto para receber os dados.
        print("Esperando o outro usuário estabelecer uma conexão...")
        self.connection.listen()
        client, _ = self.connection.accept()
        print("Testando velocidade de upload...")

        end_time = datetime.now() + timedelta(seconds=self.RUN_DURATION)
        next_tick = datetime.now() + timedelta(seconds=1)
        transmitted_bytes = 0

        logging.debug("Iniciando envio de dados")
        with tqdm(total=self.RUN_DURATION, bar_format=self.TQDM_FORMAT) as pbar:
            while (current_time := datetime.now()) < end_time:
                client.sendall(self.data)
                transmitted_bytes += len(self.data)
                # Atualiza a barra de progresso.
                if current_time >= next_tick:
                    next_tick = current_time + timedelta(seconds=1)
                    pbar.update(1)
                    pbar.refresh()

            # Garante que o tempo de execução da barra de progresso esteja correto ao fim da
            # execução.
            pbar.n = self.RUN_DURATION
            pbar.refresh()
        client.sendall(self.EMPTY_PACKET)
        logging.debug("Fim do envio de dados")

        # Recebe o total de bytes recebidos pelo o outro usuário.
        received_bytes = self.recvall(client, self.INT_BYTE_SIZE)
        received_bytes = self.decode_stats_packet(received_bytes)
        logging.debug("Sender recebeu o número de bytes recebidos")

        stats_packet = self.encode_stats_packet(transmitted_bytes)
        client.sendall(stats_packet)
        logging.debug("Sender acabou")

        logging.debug("%d bytes foram recebidos pelo o outro usuário", received_bytes)
        return Results(transmitted_bytes, received_bytes)
