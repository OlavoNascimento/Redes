# Chat Peer to Peer

- Envia mensagens entre vários usuários utilizando uma rede P2P.

# Exemplo de execução
1. **S**ervidor: Criado
2. **C**liente**1**: Conecta
3. S: Adiciona o endereço do usuário 1 a lista.
4. S: Retorna o endereço dos outros usuários.
5. **C**liente**2**: Conecta
6. S: Adiciona o endereço do usuário 2 a lista.
7. S: Retorna o endereço dos outros usuários.
8. C2: Testa o ping com todos os usuários
9. C2: Escolhe o melhor caminho e abandona os outros.

# Observações
1. Servidor:
    - É a **única** porta de entrada na rede.

# TODO
1. Implementar servidor.
2. Conectar com outros usuários do servidor.
    - Escolher o usuário com menor ping entre os endereços retornados pelo servidor.
    - Conectar a esse usuário.
    - Obs.:
        - Armazenar o usuário que o nó atual depende.
        - Armazenar os usuários que dependem do nó atual.
    - Enviar um sinal aos usuários dependentes ao sair.
3. Calcular nova rota caso um usuário saia.
    - Ao receber um sinal de saída do nó que depende:
        1. Pede ao servidor os endereços dos usuários conectados.
        2. Calcula a opção com menor latência.
        3. Conecta ao outro usuário.
