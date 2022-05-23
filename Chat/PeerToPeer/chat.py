#!/usr/bin/python3

import logging
import sys
from collections import namedtuple
from client import Client
from gateway import Gateway


Address = namedtuple("address", ["host", "port"])


def main():
    FORMAT = (
        "%(levelname)s - [%(filename)s:%(lineno)s - %(funcName)s()] - %(asctime)s - %(message)s"
    )
    # Habilita mensagens de debug
    logging.basicConfig(level=logging.DEBUG, format=FORMAT)

    username = input("Nome de usuário: ")
    is_gateway = input("Host de entrada? (s/N): ").lower()
    is_gateway = is_gateway in ("s", "sim")

    try:
        (host, port) = input("Endereço desse cliente: ").split(":")
        client_address = Address(host, int(port))

        if not is_gateway:
            (host, port) = input("Porta do gateway: ").split(":")
            gateway_address = Address(host, int(port))
    except ValueError:
        print("ERRO: O endereço deve seguir o formato $host:$porta", file=sys.stderr)
        sys.exit(1)

    node = None
    if is_gateway:
        node = Gateway(client_address, username)
    else:
        node = Client(client_address, username, gateway_address)
    node.run()


if __name__ == "__main__":
    main()
